# Overleaf assets

* `main.tex`: standalone preview project (IEEEtran, pdfLaTeX). Upload the ZIP to Overleaf (New Project → Upload Project) and compile; it typesets every figure and table.
* `figures/*.pdf`: vector figures (PNG 300 dpi and SVG versions are in `paper_assets/`).
* `tables/*.tex`: booktabs tables with caption and label; include with `\input{tables/<name>}`.
* `captions_figures.tex`: figure captions as macros (`\Cap...`).
* `latex_inclusion_examples.tex`: copy-paste patterns.
* `references/references.bib`: method references; verify each entry before submission.

Required packages: graphicx, booktabs, amsmath, url, cite (all available on Overleaf).
