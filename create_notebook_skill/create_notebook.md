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
