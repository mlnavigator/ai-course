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
