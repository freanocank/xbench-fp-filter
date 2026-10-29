"""Shared presentation and input checks for the Streamlit workspace."""

from html import escape
from pathlib import Path
from urllib.parse import urlsplit

import streamlit as st

from ui.backend import RunConfig

ROOT = Path(__file__).resolve().parents[1]
LOGO = str(ROOT / "assets" / "logo.jpeg")


def load_theme() -> None:
    css = (ROOT / "ui" / "styles.css").read_text(encoding="utf-8")
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


def page_header(title: str, description: str) -> None:
    st.markdown(
        '<div class="page-heading">'
        '<div class="eyebrow">LANGLOBAL / XBENCH QA</div>'
        f"<h1>{escape(title)}</h1><p>{escape(description)}</p></div>",
        unsafe_allow_html=True,
    )


def workflow(stage: int) -> None:
    steps = [("导入报告", ".xls / .xlsx"), ("模型复核", "逐条判定误报"), ("下载结果", "报告与分析总表")]
    items = []
    for index, (title, detail) in enumerate(steps):
        state = "complete" if index < stage else "active" if index == stage else "waiting"
        items.append(
            f'<div class="workflow-step {state}">'
            f'<span class="step-index">{index + 1:02d}</span>'
            f'<div><strong>{title}</strong><small>{detail}</small></div></div>'
        )
    st.markdown('<div class="workflow">' + "".join(items) + "</div>", unsafe_allow_html=True)


def configuration_errors(cfg: RunConfig) -> list[str]:
    errors = []
    if not cfg.api_key.strip() or cfg.api_key.strip().lower() in {
        "your-api-key-here", "your_api_key", "sk-xxx",
    }:
        errors.append("请填写 API Key。")
    try:
        url = urlsplit(cfg.api_base.strip())
        valid_url = url.scheme in {"http", "https"} and bool(url.hostname)
    except ValueError:
        valid_url = False
    if not valid_url:
        errors.append("Base URL 需为完整的 http:// 或 https:// 地址。")
    if not cfg.model.strip():
        errors.append("请选择或添加一个模型。")
    return errors


def duplicate_filenames(files) -> list[str]:
    seen, duplicates = set(), []
    for file in files:
        # Both input formats export to .xlsx, so equal stems would overwrite.
        normalized = Path(file.name).stem.casefold()
        if normalized in seen:
            duplicates.append(file.name)
        seen.add(normalized)
    return duplicates
