"""Home — visual mirror of shopbuddy-discovery (React) index page."""

from __future__ import annotations

import json

import streamlit as st

from shopping_agent.explain import (
    DEFAULT_OLLAMA_HOST,
    DEFAULT_OLLAMA_MODEL,
    explain_report,
    model_choices,
)
from ui.helpers import (
    LIMIT_CHOICES,
    OUTPUT_PATH,
    format_pipeline_error,
    init_state,
    parse_budget,
    run_pipeline,
)
from ui.landing import (
    EXAMPLE_CHIPS,
    inject_landing_styles,
    render_brand_footer,
    render_header,
    render_hero_title,
    render_search_progress,
)

init_state()

options, ollama_up = model_choices(
    host=DEFAULT_OLLAMA_HOST,
    preferred=st.session_state.selected_model or DEFAULT_OLLAMA_MODEL,
)
if st.session_state.selected_model in options:
    default_index = options.index(st.session_state.selected_model)
else:
    default_index = 0

default_top = str(st.session_state.top_n if st.session_state.top_n in LIMIT_CHOICES else 5)

inject_landing_styles(busy=False)

# Do not emit empty <div class="sb-page"> / <div class="sb-main"> wrappers.
# Streamlit cannot nest later widgets inside those tags, so a lone 100vh
# .sb-page div pushes the real UI below the fold (page "flashes then vanishes").
render_header(ollama_up=ollama_up)
render_hero_title()

with st.form("research_form", clear_on_submit=False):
    search_col, submit_col = st.columns([4.5, 1.4], vertical_alignment="center")
    with search_col:
        if "home_query" not in st.session_state:
            st.session_state.home_query = st.session_state.query_text
        query = st.text_input(
            "Shopping request",
            placeholder="What are you looking for?",
            label_visibility="collapsed",
            key="home_query",
        )
    with submit_col:
        submitted = st.form_submit_button(
            "Search",
            type="primary",
            width="stretch",
            icon=":material/arrow_forward:",
        )

    with st.expander("Advanced preferences", expanded=False):
        model_col, budget_col, top_col = st.columns(
            [2, 1, 1], vertical_alignment="bottom"
        )
        with model_col:
            selected_model = st.selectbox(
                "Local model",
                options=options,
                index=default_index,
                help="Required for AI pick explanations. Does not reweight scores.",
            )
        with budget_col:
            budget_text = st.text_input(
                "Budget USD",
                value="",
                placeholder="100",
                help="Blank uses the request budget or category default.",
            )
        with top_col:
            top_n_label = st.selectbox(
                "Show top",
                options=[str(n) for n in LIMIT_CHOICES],
                index=[str(n) for n in LIMIT_CHOICES].index(default_top),
            )
        mode = st.segmented_control(
            "Mode",
            options=["Live", "Fixtures"],
            default="Live",
            help="Live uses eBay (+ optional SerpApi). Fixtures is offline rehearsal.",
        )
        include_serpapi = st.checkbox(
            "Include SerpApi",
            value=False,
            help="Uses monthly credits. Leave off for eBay-only demos.",
        )

progress_box = st.container()


def _use_example(value: str) -> None:
    st.session_state.home_query = value
    st.session_state.query_text = value


running = False
if submitted:
    cleaned = (query or "").strip()
    top_n = int(top_n_label or "5")
    st.session_state.query_text = cleaned or st.session_state.query_text
    st.session_state.selected_model = selected_model
    st.session_state.top_n = top_n
    if not cleaned:
        st.session_state.last_error = "Enter a shopping request first."
        st.session_state.ran = False
    else:
        live = (mode or "Live") == "Live"
        budget = None
        budget_error: str | None = None
        try:
            budget = parse_budget(budget_text)
        except ValueError as exc:
            budget_error = str(exc)

        if budget_error is not None:
            st.session_state.report = None
            st.session_state.explanation = None
            st.session_state.last_error = budget_error
            st.session_state.ran = False
        elif not ollama_up:
            st.session_state.report = None
            st.session_state.explanation = None
            st.session_state.last_error = (
                "Ollama is required for ShopBuddy explanations. "
                "Start Ollama locally (http://127.0.0.1:11434), pull your model, "
                "then search again."
            )
            st.session_state.ran = False
        else:
            running = True
            inject_landing_styles(busy=True)
            with progress_box:
                render_search_progress(
                    "Live discovery can take a few minutes…"
                    if live
                    else "Running fixtures research…"
                )
                status_line = st.empty()

                def on_progress(message: str) -> None:
                    status_line.caption(message)

                try:
                    report = run_pipeline(
                        cleaned,
                        budget=budget,
                        live=live,
                        include_serpapi=include_serpapi,
                        limit=top_n,
                        on_progress=on_progress,
                    )
                    on_progress(
                        f"Writing point-wise explanations with {selected_model}…"
                    )
                    explained = explain_report(
                        report,
                        model=selected_model,
                        host=DEFAULT_OLLAMA_HOST,
                        timeout=120.0,
                        use_llm=True,
                    )
                    explanation_payload = explained.to_dict()
                    report["explanation"] = explanation_payload
                    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
                    OUTPUT_PATH.write_text(
                        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8",
                    )
                    st.session_state.report = report
                    st.session_state.explanation = explanation_payload
                    st.session_state.last_error = None
                    st.session_state.ran = True
                    on_progress("Opening picks…")
                    st.switch_page("app_pages/picks.py")
                except Exception as exc:  # noqa: BLE001
                    st.session_state.report = None
                    st.session_state.explanation = None
                    st.session_state.last_error = format_pipeline_error(exc, live=live)
                    st.session_state.ran = False
                    running = False

if not running:
    with st.container(
        horizontal=True,
        horizontal_alignment="center",
        gap="small",
        key="example_chips_row",
    ):
        for label, value in EXAMPLE_CHIPS:
            st.button(
                label,
                key=f"example_{value}",
                width="content",
                on_click=_use_example,
                args=(value,),
            )
    # If a prior run finished on disk but session never navigated (e.g. Ollama hang),
    # offer one-click recovery to Picks.
    if st.session_state.report is None and OUTPUT_PATH.exists():
        if st.button(
            "Open last shortlist",
            icon=":material/grid_view:",
            help="Load the most recent saved report and go to Picks.",
        ):
            try:
                saved = json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))
                st.session_state.report = saved
                st.session_state.explanation = saved.get("explanation")
                st.session_state.last_error = None
                st.session_state.ran = True
                st.switch_page("app_pages/picks.py")
            except (OSError, json.JSONDecodeError) as exc:
                st.session_state.last_error = f"Could not load saved report: {exc}"
    render_brand_footer()

if st.session_state.last_error and not running:
    st.error(
        st.session_state.last_error,
        title="Could not run research",
        icon=":material/error:",
    )
