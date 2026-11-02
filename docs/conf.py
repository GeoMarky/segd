"""Sphinx configuration."""

from __future__ import annotations

import sys
from datetime import UTC
from datetime import datetime
from importlib.metadata import metadata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

meta = metadata("segd")
project = "segd"
author = meta["Author-email"].split("<")[0].strip()
copyright = f"{datetime.now(tz=UTC).year}, {author}"  # noqa: A001
release = meta["Version"]
version = ".".join(release.split(".")[:2])

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx.ext.intersphinx",
    "sphinx.ext.autosummary",
    "sphinx.ext.viewcode",
    "sphinx_copybutton",
    "sphinx_design",
    "myst_nb",
    "autodoc_pydantic",
    "sphinxcontrib.typer",
]

autosummary_generate = True
autodoc_typehints = "description"
nb_execution_mode = "off"
html_theme = "furo"
html_title = "segd"
templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
    "numpy": ("https://numpy.org/doc/stable/", None),
}

myst_enable_extensions = ["colon_fence", "deflist", "linkify"]
