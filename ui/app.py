"""Langlobal Xbench false-positive review workspace. Run: streamlit run ui/app.py"""

import sys
from html import escape
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import streamlit as st

from ui.backend import (
    RunConfig, default_config_from_module, get_all_models, add_custom_model,
    remove_model, start_processing_task, test_api_connection,
)
from ui.presentation import (
    LOGO, configuration_errors, duplicate_filenames, load_theme, page_header, workflow,
)
from ui.results import render_results

st.set_page_config(
    page_title="Xbench 误报筛查 · Langlobal", page_icon=LOGO,
    layout="wide", initial_sidebar_state="expanded",
)
st.logo(LOGO, size="large", icon_image=LOGO)
load_theme()

if "cfg" not in st.session_state:
    st.session_state.cfg = default_config_from_module()
    if st.session_state.cfg.model not in get_all_models():
        add_custom_model(st.session_state.cfg.model)
for key, value in {
    "page": "filter", "results": [], "file_bytes_map": {}, "api_status": None,
    "task": None, "zip_cache": None, "upload_generation": 0,
}.items():
    if key not in st.session_state:
        st.session_state[key] = value
if "_pending_model" in st.session_state:
    st.session_state.settings_model = st.session_state.pop("_pending_model")

# Settle completed tasks before rendering controls, including after page navigation.
if st.session_state.task is not None and st.session_state.task.done:
    st.session_state.results = st.session_state.task.results
    st.session_state.task = None
    st.session_state.zip_cache = None


def navigate(page: str) -> None:
    st.session_state.page = page


def clear_workspace() -> None:
    st.session_state.results = []
    st.session_state.file_bytes_map = {}
    st.session_state.zip_cache = None
    st.session_state.upload_generation += 1
    for key in ("report-selection", "verdict-filter", "result-search"):
        st.session_state.pop(key, None)


with st.sidebar:
    st.markdown(
        '<div class="sidebar-brand"><strong>Xbench QA</strong>'
        '<span>误报筛查工具</span></div>'
        '<div class="sidebar-label">工作区</div>', unsafe_allow_html=True,
    )
    with st.container(key="navigation"):
        for page, label, icon in [
            ("filter", "误报筛查", ":material/fact_check:"),
            ("settings", "参数设置", ":material/tune:"),
            ("about", "使用说明", ":material/help_outline:"),
        ]:
            st.button(
                label, key=f"nav_{page}", icon=icon, width="stretch",
                type="primary" if st.session_state.page == page else "secondary",
                on_click=navigate, args=(page,),
            )
    sidebar_note = st.container(key="sidebar-note")


@st.fragment(run_every=0.5)
def task_progress() -> None:
    task = st.session_state.task
    if task is None:
        return
    if task.done:
        st.rerun()
    with st.container(border=True):
        st.markdown("**正在筛查，请保留当前页面**")
        st.progress(
            min(task.current / max(task.total, 1), 1.0),
            text=f"处理第 {min(task.current + 1, task.total)} / {task.total} 份报告",
        )
        st.text(task.current_name)
        if task.stage_total:
            label = {"parse": "解析报告", "llm": "模型复核"}.get(task.stage, "准备中")
            st.progress(
                min(task.stage_done / task.stage_total, 1.0),
                text=f"{label} · {task.stage_done} / {task.stage_total} 条",
            )


def render_run_settings() -> None:
    cfg = st.session_state.cfg
    ready = not configuration_errors(cfg)
    status = st.session_state.api_status
    state = "连接已验证" if status and status[0] else "连接失败" if status else "连接未测试"
    state_class = "error" if status and not status[0] else "ready" if ready else ""
    with st.container(border=True, key="run-settings"):
        st.subheader("本次筛查设置")
        st.markdown(
            '<div class="run-fact"><small>复核模型</small>'
            f'<strong>{escape(cfg.model)}</strong></div>'
            '<div class="run-fact"><small>并发条目</small>'
            f'<strong>{cfg.max_workers} 条</strong></div>'
            f'<span class="config-state {state_class}">'
            f'{"API 已配置" if ready else "API 待配置"} · {state}</span>',
            unsafe_allow_html=True,
        )
        st.button(
            "调整参数", icon=":material/arrow_forward:", width="stretch",
            on_click=navigate, args=("settings",),
        )
        st.caption("按当前模型逐条复核；调用失败的条目会保留在报告中。")


def page_filter() -> None:
    page_header("误报筛查", "上传 Xbench 报告，复核误报，保留需要继续处理的条目。")
    busy = st.session_state.task is not None
    workflow(1 if busy else 2 if st.session_state.results else 0)
    main, aside = st.columns([2.5, 1], gap="medium")
    with main:
        with st.container(border=True, key="import-panel"):
            st.subheader("导入报告")
            st.caption("支持 .xls 和 .xlsx，可同时上传多份报告；旧版 .xls 的处理结果统一导出为 .xlsx。")
            uploaded = st.file_uploader(
                "Xbench 报告", type=["xlsx", "xls"], accept_multiple_files=True,
                label_visibility="collapsed", disabled=busy,
                key=f"reports-{st.session_state.upload_generation}",
            )
            duplicates = duplicate_filenames(uploaded)
            if duplicates:
                st.error("这些报告导出后会重名，请修改文件名后重新上传：" + "、".join(duplicates))
            ready = not configuration_errors(st.session_state.cfg)
            if not ready:
                st.info("先在「参数设置」中填写 API Key 和接口地址，再开始筛查。", icon=":material/key:")
            if uploaded:
                size_mb = sum(f.size for f in uploaded) / 1024 / 1024
                st.caption(f"已选择 {len(uploaded)} 份报告 · {size_mb:.2f} MB")
            run_col, clear_col = st.columns([1.2, 1])
            with run_col:
                run = st.button(
                    "正在筛查…" if busy else "开始筛查", icon=":material/play_arrow:",
                    type="primary", width="stretch",
                    disabled=busy or not uploaded or not ready or bool(duplicates),
                )
            with clear_col:
                st.button(
                    "清空文件与结果", icon=":material/restart_alt:", width="stretch",
                    disabled=busy or not (uploaded or st.session_state.results),
                    on_click=clear_workspace,
                )
    with aside:
        render_run_settings()

    if run:
        files = [(file.name, file.getvalue()) for file in uploaded]
        st.session_state.file_bytes_map = dict(files)
        st.session_state.results = []
        st.session_state.zip_cache = None
        cfg = RunConfig.from_dict(st.session_state.cfg.to_dict())
        st.session_state.task = start_processing_task(files, cfg)
        st.rerun()
    if busy:
        task_progress()
    elif st.session_state.results:
        render_results()
    else:
        st.markdown(
            '<div class="deliverables">'
            '<div><strong>过滤后报告</strong><p>删除判为误报的条目，保留原报告的红字高亮与格式，供后续修正。</p></div>'
            '<div><strong>分析总表</strong><p>保留全部条目、模型判定及复核依据，方便抽查与回溯。</p></div>'
            '</div>', unsafe_allow_html=True,
        )


def page_settings() -> None:
    page_header("参数设置", "配置复核接口与模型，应用后用于下一次筛查。")
    cfg = st.session_state.cfg
    busy = st.session_state.task is not None
    if busy:
        st.info("报告正在筛查，完成后即可修改参数。")
    for key, value in {
        "settings_key": cfg.api_key, "settings_base": cfg.api_base,
        "settings_model": cfg.model, "settings_temperature": cfg.temperature,
        "settings_workers": cfg.max_workers,
    }.items():
        if key not in st.session_state:
            st.session_state[key] = value
    models = get_all_models()
    if st.session_state.settings_model not in models:
        st.session_state.settings_model = models[0]
    left, right = st.columns([2.2, 1], gap="medium")
    with left:
        with st.container(border=True, key="api-panel"):
            st.subheader("API 接口")
            api_key = st.text_input("API Key", key="settings_key", type="password", disabled=busy)
            api_base = st.text_input(
                "Base URL", key="settings_base", disabled=busy,
                help="填写服务商提供的 OpenAI 兼容接口地址，通常以 /v1 结尾。",
            )
            model = st.selectbox("复核模型", models, key="settings_model", disabled=busy)
            with st.expander("管理模型列表"):
                new_model = st.text_input("模型 ID", placeholder="填写服务商提供的模型 ID", key="new-model", disabled=busy)
                add_col, del_col = st.columns(2)
                add = add_col.button("添加模型", icon=":material/add:", width="stretch", disabled=busy or not new_model.strip())
                delete = del_col.button(
                    "移除当前模型", icon=":material/remove:", width="stretch",
                    disabled=busy or len(models) <= 1,
                    help="从列表中移除选中的模型，可随时重新添加。",
                )
                if add:
                    add_custom_model(new_model.strip())
                    st.session_state._pending_model = new_model.strip()
                    st.rerun()
                if delete:
                    remove_model(model)
                    st.session_state._pending_model = get_all_models()[0]
                    st.rerun()
        with st.container(border=True, key="engine-panel"):
            st.subheader("执行参数")
            temp_col, worker_col = st.columns(2)
            temperature = temp_col.slider(
                "Temperature", 0.0, 1.0, step=0.05, key="settings_temperature", disabled=busy,
                help="控制输出的随机程度，建议先使用 0.3。",
            )
            max_workers = worker_col.number_input(
                "并发条目数", 1, 64, key="settings_workers", disabled=busy,
                help="接口频繁限流时，可降低此数值。",
            )
        draft = RunConfig(
            api_key=api_key.strip(), api_base=api_base.strip(), model=model,
            temperature=temperature, max_tokens=cfg.max_tokens, max_workers=max_workers,
        )
        apply_col, test_col = st.columns(2)
        apply = apply_col.button("应用设置", type="primary", icon=":material/check:", width="stretch", disabled=busy)
        test = test_col.button("应用并测试连接", icon=":material/wifi_tethering:", width="stretch", disabled=busy)
        if apply or test:
            errors = configuration_errors(draft)
            if errors:
                for error in errors:
                    st.error(error)
            else:
                st.session_state.cfg = draft
                st.session_state.api_status = None
                if test:
                    with st.spinner("正在测试连接…"):
                        st.session_state.api_status = test_api_connection(draft)
                else:
                    st.success("设置已应用，下次筛查将使用此配置。")
        status = st.session_state.api_status
        if status and draft == st.session_state.cfg:
            if status[0]:
                st.success(status[1], icon=":material/check_circle:")
            else:
                st.error(status[1], icon=":material/error:")
        elif draft != st.session_state.cfg:
            st.caption("设置有改动，点击「应用设置」后生效。")
        st.caption("设置仅在当前会话有效，重启后恢复默认配置。")
    with right:
        with st.container(border=True, key="settings-help"):
            st.markdown("**配置提示**")
            st.caption("API Key 和 Base URL 需来自同一服务商，模型 ID 需与该接口支持的名称一致。")
            st.divider()
            st.markdown("**遇到限流时**")
            st.caption("先降低并发条目数，再重新筛查。测试连接会发送一条简短请求。")
            st.button("返回误报筛查", icon=":material/arrow_back:", on_click=navigate, args=("filter",), width="stretch")


def page_about() -> None:
    page_header("使用说明", "从 Xbench 报告到可追溯的误报复核结果。")
    with st.container(border=True, key="guide-panel"):
        for number, title, description in [
            ("01", "配置复核接口", "进入「参数设置」，填写 API Key、Base URL 并选择模型。点击「应用并测试连接」确认配置。"),
            ("02", "上传并开始筛查", "上传 Xbench 导出的 .xls 或 .xlsx 报告，支持多份文件。点击「开始筛查」，页面会显示逐文件、逐条目的处理进度。旧版 .xls 会自动转换，结果统一导出为 .xlsx。"),
            ("03", "查看判定与下载", "在结果明细中按误报或保留复核筛选，也可搜索原文、译文及复核依据。抽查后下载过滤后报告和分析总表，或一键打包全部结果。"),
        ]:
            st.markdown(
                f'<div class="guide-step"><span>{number}</span><div><strong>{title}</strong>'
                f'<p>{description}</p></div></div>', unsafe_allow_html=True,
            )
    with st.expander("两种导出文件有什么区别？", expanded=True):
        st.markdown("**过滤后报告**：删除判为误报的条目，保留待处理条目及原有红字、行高等格式。\n\n**分析总表**：包含全部条目、模型判定及判定依据，用于抽查和复盘。")
    with st.expander("调用失败或没有结果时怎么办？"):
        st.markdown("单条模型调用失败时，该条目默认保留，可在分析总表中查看原因。文件解析失败会单独显示，其他文件继续处理。检查报告格式或 API 设置后，重新上传筛查即可。")
    st.button("开始使用", type="primary", icon=":material/arrow_forward:", on_click=navigate, args=("filter",))


{"filter": page_filter, "settings": page_settings, "about": page_about}.get(
    st.session_state.page, page_filter,
)()
with sidebar_note:
    st.caption("正在处理报告" if st.session_state.task is not None else "本地运行 · 当前会话")
    st.caption("Langlobal · Localization tools")
