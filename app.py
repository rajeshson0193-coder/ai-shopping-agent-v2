"""ShopBuddy — local shopping research UI.

Run from the project root:
  $env:PYTHONPATH = "src"
  .\\.venv\\Scripts\\streamlit run app.py

For GPU Ollama (before starting the model server):
  .\\scripts\\start_ollama_gpu.ps1
"""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from ui.helpers import APP_NAME, init_state

st.set_page_config(
    page_title=f"{APP_NAME} — Find the right product",
    page_icon=":material/shopping_bag:",
    layout="wide",
    initial_sidebar_state="collapsed",
)
init_state()

pages = [
    st.Page("app_pages/home.py", title="Home", icon=":material/home:", default=True),
    st.Page("app_pages/picks.py", title="Picks", icon=":material/grid_view:"),
]
# Keep multipage routing, but the discovery landing hides Streamlit chrome via CSS
# so the first screen matches shopbuddy-discovery.
page = st.navigation(pages, position="sidebar")
page.run()
