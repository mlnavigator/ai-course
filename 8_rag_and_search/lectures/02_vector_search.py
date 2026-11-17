# ---
# jupyter:
#   jupytext:
#     formats: py:percent,ipynb
#     text_representation:
#       extension: .py
#       format_name: percent
#   kernelspec:
#     display_name: Python 3
#     language: python
#     name: python3
# ---

# %% [markdown]
# # Векторный поиск: эмбеддинги без GPU
#
# В этой лекции:
# - разберёмся, откуда брать векторы текстов, если на машине нет GPU;
# - получим нейросетевые эмбеддинги через API OpenRouter — **только для ~50 текстов**, с кэшем на диске;
# - увидим, где векторный поиск находит то, что пропускает лексический (синонимы, перефразы);
# - сравним с BM25 на «мини-бенчмарке» из размеченных вопросов RuBQ;
# - построим плотные векторы для **всего** корпуса без нейросетей (LSA) и измерим их качество;
# - попробуем приближённый поиск ближайших соседей (ANN) в FAISS.
#
# Код анализатора и BM25 из ноутбука 01 вынесен в модуль `search_common.py`.

# %% [markdown]
# ## 1. Откуда брать векторы без GPU
#
# | Вариант | Качество | Цена / время на 57 тыс. абзацев | Минусы |
# |---|---|---|---|
# | **API эмбеддингов** (OpenRouter, OpenAI, …) | высокое, мультиязычное | центы, минуты | нужен ключ и сеть, тексты уходят провайдеру |
# | **Маленькая локальная модель на CPU** (`rubert-tiny2`, `multilingual-e5-small`) | среднее–хорошее | бесплатно, ~0.5 ч на 8 ядрах (замер: ~37 абзацев/с у `rubert-tiny2`) | долго на большом корпусе, нужно скачать модель |
# | **LSA**: SVD от матрицы TF-IDF | низкое | бесплатно, ~1 мин | это всё ещё «статистика слов», синонимы ловит слабо |
#
# Главное правило: **документы и запросы векторизуются одной и той же моделью**. Векторы разных моделей несравнимы,
# поэтому при смене модели индекс пересчитывается целиком.
#
# В лекции используем API для маленького набора текстов (это стоит доли цента) и LSA — для всего корпуса.

# %%
import hashlib
import json
import os
import time
import urllib.request
from pathlib import Path

import faiss
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from dotenv import load_dotenv
from openai import OpenAI
from sklearn.decomposition import TruncatedSVD
from sklearn.feature_extraction.text import TfidfVectorizer

from search_common import (
    BM25Index,
    analyze,
    build_counts,
    load_paragraphs,
    load_questions,
    metrics_from_ranks,
    rankings_in_batches,
    ranks_of_first_relevant,
    tfidf_from_counts,
)

pd.set_option("display.max_colwidth", 100)
np.random.seed(42)

# %% [markdown]
# ## 2. Клиент эмбеддингов OpenRouter с кэшем
#
# OpenRouter предоставляет OpenAI-совместимый endpoint `/api/v1/embeddings`, поэтому подходит обычный клиент `openai`.
#
# Ключ берётся из переменной окружения `OPENROUTER_API_KEY` или из файла `8_rag_and_search/.env`:
#
# ```
# OPENROUTER_API_KEY=sk-or-...
# OPENROUTER_EMBED_MODEL=openai/text-embedding-3-small   # необязательно
# ```
#
# Чтобы не платить повторно, каждый вектор сохраняется в `8_rag_and_search/embeddings/<модель>.json`
# (ключ — хэш текста). Этот файл лежит в репозитории, поэтому ноутбук работает **и без ключа**,
# пока набор текстов не меняется. Защита от случайных трат: не больше `MAX_NEW_TEXTS` новых текстов за вызов.

# %%
load_dotenv(Path("../.env"))
load_dotenv(Path(".env"))

OPENROUTER_KEY = os.environ.get("OPENROUTER_API_KEY", "").strip()
EMBED_MODEL = os.environ.get("OPENROUTER_EMBED_MODEL", "openai/text-embedding-3-small").strip()
CACHE_DIR = Path("../embeddings")
MAX_NEW_TEXTS = 50

print("ключ OpenRouter задан:", bool(OPENROUTER_KEY))
print("модель эмбеддингов:   ", EMBED_MODEL)


# %%
def text_key(text):
    return hashlib.sha1(text.encode("utf-8")).hexdigest()


class CachedEmbedder:
    def __init__(self, model, cache_dir=CACHE_DIR, api_key=OPENROUTER_KEY):
        self.model = model
        self.path = cache_dir / (model.replace("/", "__") + ".json")
        self.api_key = api_key
        if self.path.exists():
            self.cache = json.loads(self.path.read_text(encoding="utf-8"))
        else:
            self.cache = {"model": model, "usage": {"texts": 0, "tokens": 0}, "items": {}}

    def _save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.cache, ensure_ascii=False, indent=1), encoding="utf-8")

    def _call_api(self, texts):
        if not self.api_key:
            raise RuntimeError(
                f"{len(texts)} текстов нет в кэше {self.path}, а OPENROUTER_API_KEY не задан. "
                "Добавьте ключ в 8_rag_and_search/.env"
            )
        if len(texts) > MAX_NEW_TEXTS:
            raise RuntimeError(f"{len(texts)} новых текстов > MAX_NEW_TEXTS={MAX_NEW_TEXTS}: защита от лишних трат")
        client = OpenAI(api_key=self.api_key, base_url="https://openrouter.ai/api/v1")
        response = client.embeddings.create(model=self.model, input=texts)
        usage = getattr(response, "usage", None)
        tokens = int(getattr(usage, "prompt_tokens", 0) or 0)
        print(f"API: {len(texts)} текстов, {tokens} токенов")
        return [item.embedding for item in sorted(response.data, key=lambda d: d.index)], tokens

    def embed(self, texts):
        """Возвращает L2-нормированные векторы (len(texts) × dim)."""
        items = self.cache["items"]
        missing = list(dict.fromkeys(t for t in texts if text_key(t) not in items))
        if missing:
            vectors, tokens = self._call_api(missing)
            for text, vec in zip(missing, vectors):
                items[text_key(text)] = {"text": text, "vector": [round(x, 6) for x in vec]}
            self.cache["usage"]["texts"] += len(missing)
            self.cache["usage"]["tokens"] += tokens
            self._save()
        matrix = np.array([items[text_key(t)]["vector"] for t in texts], dtype=np.float32)
        return matrix / np.linalg.norm(matrix, axis=1, keepdims=True)


embedder = CachedEmbedder(EMBED_MODEL)
print("в кэше:", len(embedder.cache["items"]), "векторов")

# %% [markdown]
# ## 3. Игрушечный пример: смысл против совпадения слов
#
# Шесть «документов» службы поддержки и два запроса, сформулированных **другими словами**.

# %%
toy_docs = [
    "Чтобы сбросить пароль, нажмите «Забыли пароль» на странице входа.",
    "Возврат денег на банковскую карту занимает до десяти рабочих дней.",
    "Курьер доставляет заказы ежедневно с девяти до двадцати одного часа.",
    "Оплатить покупку можно наличными или картой при получении.",
    "Ошибка E17 означает, что банк отклонил платёж.",
    "Котёнок спит на тёплом подоконнике.",
]
toy_queries = [
    "не могу вспомнить код доступа к учётной записи",
    "когда мне вернут средства за покупку",
]

toy_doc_vecs = embedder.embed(toy_docs)
toy_query_vecs = embedder.embed(toy_queries)
print("размерность эмбеддинга:", toy_doc_vecs.shape[1])

# %% [markdown]
# Для L2-нормированных векторов косинусное сходство — это просто скалярное произведение.
# Сравним с TF-IDF на стемах (лексический поиск из ноутбука 01).

# %%
toy_tfidf = TfidfVectorizer(analyzer=analyze, sublinear_tf=True)
toy_doc_tfidf = toy_tfidf.fit_transform(toy_docs)
toy_query_tfidf = toy_tfidf.transform(toy_queries)

sim_dense = toy_query_vecs @ toy_doc_vecs.T
sim_lexical = (toy_query_tfidf @ toy_doc_tfidf.T).toarray()

fig, axes = plt.subplots(1, 2, figsize=(13, 3.2))
for ax, sim, title in [(axes[0], sim_lexical, "TF-IDF (стемы-4)"), (axes[1], sim_dense, f"Эмбеддинги {EMBED_MODEL}")]:
    im = ax.imshow(sim, cmap="viridis", aspect="auto")
    ax.set_title(f"Косинусное сходство: {title}")
    ax.set_xlabel("Документ")
    ax.set_ylabel("Запрос")
    ax.set_xticks(range(len(toy_docs)))
    ax.set_yticks(range(len(toy_queries)))
    for i in range(sim.shape[0]):
        for j in range(sim.shape[1]):
            ax.text(j, i, f"{sim[i, j]:.2f}", ha="center", va="center", color="white", fontsize=9)
    fig.colorbar(im, ax=ax)
plt.tight_layout()
plt.show()

for i, q in enumerate(toy_queries):
    print(f"\nЗАПРОС: {q}")
    print(f"  TF-IDF   → [{sim_lexical[i].argmax()}] {toy_docs[sim_lexical[i].argmax()]}  (score {sim_lexical[i].max():.2f})")
    print(f"  эмбеддинг→ [{sim_dense[i].argmax()}] {toy_docs[sim_dense[i].argmax()]}  (score {sim_dense[i].max():.2f})")

# %% [markdown]
# Что видно:
# - в первом запросе единственный общий стем — `дост` («**дост**упа» / «**дост**авляет»): ложное совпадение грубого
#   стемминга уводит TF-IDF к курьеру, а эмбеддинг находит сброс пароля;
# - во втором запросе общее слово «покупку» тянет TF-IDF к документу про **оплату**, эмбеддинг выбирает **возврат**;
# - у эмбеддингов сходство никогда не равно нулю: даже «котёнок» получает ненулевой скор.
#   Поэтому порог «нашли / не нашли» для векторного поиска подбирают отдельно, и он зависит от модели.

# %% [markdown]
# ## 4. Мини-бенчмарк на RuBQ
#
# Векторизовать все 57 тыс. абзацев через API мы не будем. Соберём маленький, но **трудный** набор:
# 8 вопросов из dev, для каждого — абзац с ответом и 3 абзаца **из той же статьи** без ответа
# (hard negatives: тема та же, слова похожие). Итого ≤ 32 абзаца + 8 вопросов.

# %%
texts = load_paragraphs()
dev = load_questions("dev")

candidates = dev[dev.apply(lambda r: len(set(r["related"]) - r["relevant"]) >= 3, axis=1)]
picked = candidates.sample(8, random_state=42).reset_index(drop=True)

mini_uids = []
for _, row in picked.iterrows():
    positive = min(row["relevant"])
    negatives = sorted(set(row["related"]) - row["relevant"])[:3]
    for uid in [positive] + negatives:
        if uid not in mini_uids:
            mini_uids.append(uid)

mini_relevant = [row["relevant"] & set(mini_uids) for _, row in picked.iterrows()]
mini_questions = picked["question_text"].tolist()

print("абзацев в мини-корпусе:", len(mini_uids))
picked[["question_text", "answer_text"]]

# %%
mini_doc_vecs = embedder.embed([texts[u] for u in mini_uids])
mini_query_vecs = embedder.embed(mini_questions)
print("в кэше:", len(embedder.cache["items"]), "векторов; потрачено токенов:", embedder.cache["usage"]["tokens"])

# %% [markdown]
# Векторный поиск — это просто сортировка по скалярному произведению. На 32 документах — полный перебор.

# %%
def vector_search(query_vec, doc_vecs, k=3):
    scores = doc_vecs @ query_vec
    top = np.argsort(-scores)[:k]
    return [(int(i), float(scores[i])) for i in top]


q_idx = 0
print("ВОПРОС:", mini_questions[q_idx], "| ОТВЕТ:", picked.loc[q_idx, "answer_text"])
for i, score in vector_search(mini_query_vecs[q_idx], mini_doc_vecs):
    uid = mini_uids[i]
    mark = "✔" if uid in mini_relevant[q_idx] else " "
    print(f"{mark} {score:.3f} [{uid}] {texts[uid][:150]}")

# %% [markdown]
# ### Сравнение с BM25 на тех же кандидатах
#
# BM25 строим по **всему** корпусу (чтобы IDF был честным), а ранжируем только абзацы мини-корпуса.
# Так оба метода выбирают из одних и тех же 32 кандидатов.

# %%
bm25 = BM25Index(texts)

mini_scores = {
    "BM25 (стемы-4)": bm25.scores(mini_questions)[:, mini_uids],
    f"Эмбеддинги ({EMBED_MODEL})": mini_query_vecs @ mini_doc_vecs.T,
}


def mini_ranks(scores):
    rankings = [[mini_uids[j] for j in np.argsort(-row)] for row in scores]
    return ranks_of_first_relevant(rankings, mini_relevant)


mini_table = pd.DataFrame({name: mini_ranks(s) for name, s in mini_scores.items()})
mini_table.insert(0, "вопрос", mini_questions)
mini_table

# %%
summary = pd.DataFrame(
    {
        name: {
            "Hit@1": np.mean(r <= 1),
            "Hit@3": np.mean(r <= 3),
            "MRR": np.mean(1 / r),
            "средний ранг": np.mean(r),
        }
        for name, r in ((n, mini_ranks(s)) for n, s in mini_scores.items())
    }
).T
summary.round(3)

# %% [markdown]
# 8 вопросов — это **иллюстрация, а не измерение**: одна ошибка меняет Hit@1 на 12.5 процентных пунктов.
# Для честного вывода нужен большой размеченный набор — а значит, векторизация всего корпуса.
#
# ### Сколько стоило бы векторизовать весь корпус?
#
# Оценим по фактическому расходу токенов (OpenRouter возвращает `usage`) и цене модели из публичного списка.

# %%
def embedding_price_per_token(model):
    try:
        with urllib.request.urlopen("https://openrouter.ai/api/v1/embeddings/models", timeout=15) as r:
            models = json.load(r)["data"]
        return float(next(m["pricing"]["prompt"] for m in models if m["id"] == model))
    except Exception as error:  # нет сети или модели нет в списке
        print("не удалось получить цену:", error)
        return 0.02 / 1e6


usage = embedder.cache["usage"]
price = embedding_price_per_token(EMBED_MODEL)
paragraph_chars = np.mean([len(t) for t in texts])
tokens_per_char = usage["tokens"] / max(sum(len(i["text"]) for i in embedder.cache["items"].values()), 1)

full_tokens = tokens_per_char * paragraph_chars * len(texts)
print(f"цена модели: ${price * 1e6:.3f} за 1M токенов")
print(f"потрачено: {usage['tokens']} токенов на {usage['texts']} текстов = ${usage['tokens'] * price:.5f}")
print(f"токенов на символ (русский текст): {tokens_per_char:.2f}")
print(f"весь корпус: ~{full_tokens / 1e6:.1f}M токенов ≈ ${full_tokens * price:.2f}")

# %% [markdown]
# ## 5. Плотные векторы без нейросети: LSA
#
# **LSA (Latent Semantic Analysis)** — классический способ получить плотные векторы:
# берём разреженную матрицу TF-IDF (документы × ~50 тыс. стем) и сжимаем её усечённым SVD до `d = 256` измерений.
# Стемы, которые часто встречаются в одних и тех же документах, попадают в похожие направления —
# так появляется зачаток «семантики» без обучения нейросети.

# %%
t0 = time.perf_counter()
vectorizer, counts = build_counts(texts)  # стемы-4, униграммы
tfidf_docs, idf = tfidf_from_counts(counts)

svd = TruncatedSVD(n_components=256, random_state=42)
lsa_docs = svd.fit_transform(tfidf_docs).astype(np.float32)
lsa_docs /= np.linalg.norm(lsa_docs, axis=1, keepdims=True) + 1e-12
print(f"LSA: {lsa_docs.shape}, {time.perf_counter() - t0:.0f} с")
print(f"доля объяснённой дисперсии: {svd.explained_variance_ratio_.sum():.1%}")


def lsa_embed_queries(queries):
    q = vectorizer.transform(list(queries))
    q.data = (1 + np.log(q.data)) * idf[q.indices]
    vecs = svd.transform(q).astype(np.float32)
    return vecs / (np.linalg.norm(vecs, axis=1, keepdims=True) + 1e-12)


# %% [markdown]
# Компоненты SVD можно «прочитать»: у каждой есть стемы с наибольшими весами.

# %%
terms = vectorizer.get_feature_names_out()
for c in range(1, 7):
    top_terms = terms[np.argsort(-svd.components_[c])[:10]]
    print(f"компонента {c}: {', '.join(top_terms)}")

# %% [markdown]
# ### Качество LSA на всех 444 вопросах dev
#
# Здесь уже честное сравнение по всему корпусу, как в ноутбуке 01.

# %%
questions = dev["question_text"].tolist()
relevant = dev["relevant"].tolist()

t0 = time.perf_counter()
ranks_bm25 = ranks_of_first_relevant(rankings_in_batches(bm25.scores, questions), relevant)
print(f"BM25: {time.perf_counter() - t0:.1f} с")

t0 = time.perf_counter()
ranks_lsa = ranks_of_first_relevant(
    rankings_in_batches(lambda qs: lsa_embed_queries(qs) @ lsa_docs.T, questions), relevant
)
print(f"LSA:  {time.perf_counter() - t0:.1f} с")

pd.DataFrame({"BM25 (стемы-4)": metrics_from_ranks(ranks_bm25), "LSA-256": metrics_from_ranks(ranks_lsa)}).T.round(3)

# %%
ks = np.arange(1, 21)
plt.figure(figsize=(8, 4))
for name, r in [("BM25 (стемы-4)", ranks_bm25), ("LSA-256", ranks_lsa)]:
    plt.plot(ks, [(r <= k).mean() for k in ks], marker=".", label=name)
plt.title("Hit@k на dev-вопросах RuBQ: лексический поиск против LSA")
plt.xlabel("k — сколько документов берём из выдачи")
plt.ylabel("Hit@k")
plt.ylim(0, 1)
plt.grid(alpha=0.3)
plt.legend()
plt.show()

# %% [markdown]
# LSA заметно хуже BM25: сжатие до 256 измерений «размывает» редкие термы — имена, названия, даты, —
# а именно они решают фактологические вопросы. «Семантика» LSA — это лишь совместная встречаемость слов.
# Нейросетевые эмбеддинги обучены на огромных корпусах и парах «вопрос — ответ», поэтому ведут себя иначе.
#
# Сравним все три подхода на мини-бенчмарке (LSA тоже ранжирует только 32 кандидата).

# %%
mini_scores["LSA-256"] = lsa_embed_queries(mini_questions) @ lsa_docs[mini_uids].T

mini_summary = pd.DataFrame(
    {name: {"Hit@1": np.mean(mini_ranks(s) <= 1), "MRR": np.mean(1 / mini_ranks(s))} for name, s in mini_scores.items()}
).T

ax = mini_summary.plot.bar(figsize=(8, 4), rot=0)
ax.set_title("Мини-бенчмарк: 8 вопросов × 32 абзаца-кандидата")
ax.set_xlabel("Метод")
ax.set_ylabel("Значение метрики")
ax.set_ylim(0, 1.05)
plt.tight_layout()
plt.show()
mini_summary.round(3)

# %% [markdown]
# ## 6. Приближённый поиск ближайших соседей (ANN)
#
# Полный перебор = умножение запроса на матрицу N × d. Для 57 тыс. × 256 это миллисекунды,
# но для 100 млн векторов уже нет. Векторные БД (FAISS, Qdrant, pgvector…) используют **приближённые** индексы.
#
# Самый популярный — **HNSW**: многоуровневый граф «близких соседей», по которому поиск идёт жадно.
# Платим небольшой потерей точности (recall) за большую скорость.
# Сравним в FAISS точный `IndexFlatIP` и `IndexHNSWFlat` на векторах LSA.

# %%
faiss.omp_set_num_threads(4)
query_vecs = lsa_embed_queries(questions)
dim = lsa_docs.shape[1]

flat = faiss.IndexFlatIP(dim)  # скалярное произведение = косинус для нормированных векторов
flat.add(lsa_docs)
t0 = time.perf_counter()
_, exact_top = flat.search(query_vecs, 10)
flat_ms = (time.perf_counter() - t0) / len(questions) * 1000

hnsw = faiss.IndexHNSWFlat(dim, 32, faiss.METRIC_INNER_PRODUCT)  # 32 — число связей вершины графа
t0 = time.perf_counter()
hnsw.add(lsa_docs)
build_s = time.perf_counter() - t0

hnsw_rows = []
for ef_search in [8, 16, 32, 64, 128]:
    hnsw.hnsw.efSearch = ef_search
    t0 = time.perf_counter()
    _, approx_top = hnsw.search(query_vecs, 10)
    ms = (time.perf_counter() - t0) / len(questions) * 1000
    recall = np.mean([len(set(a) & set(e)) / 10 for a, e in zip(approx_top, exact_top)])
    hnsw_rows.append({"efSearch": ef_search, "recall@10": recall, "мс на запрос": ms})

print(f"построение HNSW: {build_s:.1f} с; точный поиск: {flat_ms:.3f} мс на запрос")
hnsw_df = pd.DataFrame(hnsw_rows)
hnsw_df.round(3)

# %%
plt.figure(figsize=(7, 4))
plt.plot(hnsw_df["мс на запрос"], hnsw_df["recall@10"], marker="o")
for _, r in hnsw_df.iterrows():
    plt.annotate(f"ef={int(r['efSearch'])}", (r["мс на запрос"], r["recall@10"]), textcoords="offset points", xytext=(5, -10))
plt.axvline(flat_ms, color="gray", ls="--", label="точный поиск (Flat)")
plt.title("HNSW: компромисс скорость / полнота")
plt.xlabel("Время на запрос, мс")
plt.ylabel("Recall@10 относительно точного поиска")
plt.legend()
plt.show()

# %% [markdown]
# `recall@10` здесь — доля **точных** соседей, которые нашёл приближённый индекс (а не качество ответа на вопрос).
# Параметр `efSearch` — ширина поиска в графе: больше → точнее и медленнее.
# На 57 тыс. векторах выигрыш небольшой; на миллионах и выше без ANN не обойтись.

# %% [markdown]
# ## Итоги
#
# - Эмбеддинг — плотный вектор, в котором близкие по смыслу тексты оказываются рядом; поиск — по косинусу.
# - Без GPU реалистичные варианты: API (дёшево, быстро, но данные уходят наружу), маленькая CPU-модель (бесплатно, медленно),
#   LSA (бесплатно и быстро, но слабо).
# - Нейросетевые эмбеддинги ловят синонимы и перефразы, которые лексический поиск пропускает.
# - Лексический поиск сильнее на редких точных термах: имена, коды, даты. LSA эту силу теряет, а семантики не добавляет.
# - Отсюда идея **гибридного поиска**: объединить BM25 и векторы — тема следующего ноутбука.
# - Векторы кэшируйте: модель + текст → вектор. Смена модели = переиндексация всего корпуса.
#
# ## Задания
#
# 1. Придумайте 5 запросов-перефразов к мини-корпусу (без общих слов с абзацем) и сравните BM25 и эмбеддинги.
# 2. Поменяйте `OPENROUTER_EMBED_MODEL` (например, `qwen/qwen3-embedding-4b` или `baai/bge-m3`) и сравните результаты.
#    Не забудьте: векторы разных моделей смешивать нельзя.
# 3. Измените число компонент LSA (64, 128, 512). Как меняются Hit@10 и время?
# 4. Постройте `faiss.IndexIVFFlat` и сравните с HNSW по скорости и recall.
