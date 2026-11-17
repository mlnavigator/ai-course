"""Общий код для ноутбуков 02+ (всё это подробно разобрано в 01_fulltext_search).

- загрузка корпуса RuBQ 2.0;
- анализатор: токены >= 3 символов, грубый стемминг (первые 4 символа), биграммы стем;
- матрица счётчиков, TF-IDF, BM25;
- метрики Hit@k и MRR.
"""

import re
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import CountVectorizer

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "rubq"
BASE_URL = "https://huggingface.co/datasets/d0rj/RuBQ_2.0/resolve/main/data/"
FILES = {
    "paragraphs.parquet": "paragraphs-00000-of-00001-d1f2ba7d11822891.parquet",
    "dev.parquet": "dev-00000-of-00001-d7e3040a344e1e68.parquet",
    "test.parquet": "test-00000-of-00001-d519841742f463e6.parquet",
}


# ---------------------------------------------------------------- данные
def download_rubq(data_dir=DATA_DIR):
    data_dir.mkdir(parents=True, exist_ok=True)
    for local_name, remote_name in FILES.items():
        path = data_dir / local_name
        if not path.exists():
            print(f"скачиваю {remote_name} ...")
            urllib.request.urlretrieve(BASE_URL + remote_name, path)


def load_paragraphs(data_dir=DATA_DIR):
    """Список текстов: texts[uid] — абзац с этим uid."""
    download_rubq(data_dir)
    paragraphs = pd.read_parquet(data_dir / "paragraphs.parquet").sort_values("uid")
    assert (paragraphs["uid"].to_numpy() == np.arange(len(paragraphs))).all()
    return paragraphs["text"].tolist()


def load_questions(split="dev", data_dir=DATA_DIR):
    """Вопросы с непустым множеством relevant (uid абзацев с ответом)."""
    download_rubq(data_dir)
    df = pd.read_parquet(data_dir / f"{split}.parquet")
    df["relevant"] = df["paragraphs_uids"].map(lambda p: {int(x) for x in p["with_answer"]})
    df["related"] = df["paragraphs_uids"].map(lambda p: [int(x) for x in p["all_related"]])
    return df[df["relevant"].map(len) > 0].reset_index(drop=True)


# ---------------------------------------------------------------- анализатор
TOKEN_RE = re.compile(r"\w+")
MIN_TOKEN_LEN = 3
STEM_LEN = 4


def tokenize(text):
    tokens = TOKEN_RE.findall(text.lower().replace("ё", "е"))
    return [t for t in tokens if len(t) >= MIN_TOKEN_LEN]


def analyze(text, stem_len=STEM_LEN, ngrams="uni"):
    stems = [t if stem_len is None else t[:stem_len] for t in tokenize(text)]
    terms = []
    if "uni" in ngrams:
        terms += stems
    if "bi" in ngrams:
        terms += [f"{a}_{b}" for a, b in zip(stems, stems[1:])]
    return terms


def build_counts(texts, stem_len=STEM_LEN, ngrams="uni"):
    vectorizer = CountVectorizer(analyzer=lambda text: analyze(text, stem_len, ngrams))
    counts = vectorizer.fit_transform(texts).tocsr().astype(np.float64)
    return vectorizer, counts


# ---------------------------------------------------------------- веса
def tfidf_from_counts(counts):
    n_docs = counts.shape[0]
    df = np.bincount(counts.indices, minlength=counts.shape[1])
    idf = np.log((n_docs + 1) / (df + 1)) + 1
    weights = counts.copy()
    weights.data = (1 + np.log(weights.data)) * idf[weights.indices]
    norms = np.sqrt(np.asarray(weights.multiply(weights).sum(axis=1)).ravel())
    weights = weights.multiply(1 / np.maximum(norms, 1e-12)[:, None]).tocsr()
    return weights, idf


def bm25_from_counts(counts, k1=1.5, b=0.75):
    n_docs = counts.shape[0]
    df = np.bincount(counts.indices, minlength=counts.shape[1])
    idf = np.log(1 + (n_docs - df + 0.5) / (df + 0.5))
    doc_len = np.asarray(counts.sum(axis=1)).ravel()
    row_len = np.repeat(doc_len, np.diff(counts.indptr))
    weights = counts.copy()
    tf = weights.data
    weights.data = idf[weights.indices] * tf * (k1 + 1) / (tf + k1 * (1 - b + b * row_len / doc_len.mean()))
    return weights


def binary_query(query_counts):
    q = query_counts.copy().tocsr()
    q.data[:] = 1.0
    return q


class BM25Index:
    """BM25 на стемах-4 — лучший вариант из ноутбука 01."""

    def __init__(self, texts, stem_len=STEM_LEN, ngrams="uni", k1=1.5, b=0.75):
        self.vectorizer, self.counts = build_counts(texts, stem_len, ngrams)
        self.weights = bm25_from_counts(self.counts, k1, b)
        self.weights_t = self.weights.T.tocsr()

    def scores(self, queries):
        """Матрица скоров (число запросов × число документов), dense."""
        q = binary_query(self.vectorizer.transform(list(queries)))
        return (q @ self.weights_t).toarray()

    def search(self, query, k=5):
        s = self.scores([query])[0]
        top = np.argsort(-s)[:k]
        return [(int(i), float(s[i])) for i in top if s[i] > 0]


# ---------------------------------------------------------------- метрики
def top_k_from_scores(scores, k=20):
    """scores: dense (запросы × документы). Возвращает top-k индексов документов по строкам."""
    top = np.argpartition(-scores, kth=min(k, scores.shape[1] - 1), axis=1)[:, :k]
    order = np.take_along_axis(scores, top, axis=1).argsort(axis=1)[:, ::-1]
    return np.take_along_axis(top, order, axis=1)


def rankings_in_batches(score_fn, queries, k=20, batch_size=64):
    """score_fn(список запросов) -> dense скоры; считаем батчами, чтобы не держать всю матрицу."""
    rankings = []
    for start in range(0, len(queries), batch_size):
        rankings.extend(top_k_from_scores(score_fn(queries[start:start + batch_size]), k))
    return rankings


def ranks_of_first_relevant(rankings, relevant_sets):
    ranks = []
    for ranking, relevant in zip(rankings, relevant_sets):
        hits = [pos for pos, uid in enumerate(ranking, start=1) if uid in relevant]
        ranks.append(hits[0] if hits else np.inf)
    return np.array(ranks, dtype=float)


def metrics_from_ranks(ranks):
    return {
        "Hit@1": np.mean(ranks <= 1),
        "Hit@5": np.mean(ranks <= 5),
        "Hit@10": np.mean(ranks <= 10),
        "Hit@20": np.mean(ranks <= 20),
        "MRR@10": np.mean(np.where(ranks <= 10, 1 / ranks, 0.0)),
    }
