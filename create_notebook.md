# Lecture notebooks

All machine-learning lectures must be created using
Jupytext `py:percent` format.

For every lecture:

1. Create `lectures/<name>.py`.
2. Alternate Markdown and code cells.
3. Use small executable examples.
4. Never depend on variables defined many cells earlier
   unless pedagogically necessary.
5. Use deterministic random seeds.
6. All plots must have title and axis labels.
7. Notebook must run from top to bottom.
8. Convert the source to `.ipynb` using Jupytext.
9. Execute the resulting notebook.
10. Fix all execution errors before finishing.

The `.py` file is the canonical source.
The `.ipynb` file is the lecture artifact.

To create ipynb notebook call in bash `python3 -m  jupytext --to notebook <path_to_target_py_file>`

Reference example for py file to convert:

```python

# %% [markdown]
# # Линейная регрессия
#
# В этой лекции:
# - создадим искусственные данные;
# - обучим LinearRegression;
# - посмотрим коэффициенты;
# - визуализируем результат.

# %%
import numpy as np
import matplotlib.pyplot as plt

from sklearn.linear_model import LinearRegression

# %% [markdown]
# ## Генерируем данные

# %%
rng = np.random.default_rng(42)

X = rng.uniform(0, 10, size=(100, 1))
y = 3 * X[:, 0] + 5 + rng.normal(0, 3, size=100)

# %%
plt.scatter(X[:, 0], y)
plt.xlabel("X")
plt.ylabel("y")
plt.show()

# %% [markdown]
# ## Обучаем модель

# %%
model = LinearRegression()
model.fit(X, y)

print("coef =", model.coef_)
print("intercept =", model.intercept_)

# %% [markdown]
# ## Визуализируем предсказание

# %%
x_grid = np.linspace(0, 10, 100).reshape(-1, 1)
y_pred = model.predict(x_grid)

plt.scatter(X[:, 0], y)
plt.plot(x_grid[:, 0], y_pred)
plt.show()
```

