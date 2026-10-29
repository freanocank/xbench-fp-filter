"""Result summaries, searchable row review and downloads."""

import os

import streamlit as st

from ui.backend import build_analysis_xlsx, build_filtered_xlsx, build_zip_bytes

XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def render_results() -> None:
    results = st.session_state.results
    valid = [r for r in results if r.get("rows") and not r.get("error")]
    failures = [r for r in results if r.get("error")]
    st.markdown(
        '<div class="section-heading"><h2>筛查结果</h2>'
        f'<span>{len(valid)} 份完成 · {len(failures)} 份失败</span></div>',
        unsafe_allow_html=True,
    )
    for result in failures:
        st.error(f"{result['filename']}：{result['error']}", icon=":material/error:")
    if not valid:
        if failures and all(str(r.get("error", "")).startswith("解析失败：") for r in failures):
            st.info("请检查报告文件后重新上传，解析成功后才会开始模型筛查。")
        else:
            st.info("请根据上方失败原因检查报告或 API 设置后重新筛查。")
        return

    total = sum(r.get("stats", {}).get("total", 0) for r in valid)
    suppressed = sum(r.get("stats", {}).get("suppressed", 0) for r in valid)
    with st.container(key="results-metrics"):
        columns = st.columns(4)
        for col, (label, value) in zip(columns, [
            ("报告条目", f"{total:,}"),
            ("判为误报", f"{suppressed:,}"),
            ("保留复核", f"{total - suppressed:,}"),
            ("误报占比", f"{suppressed / total:.1%}" if total else "—"),
        ]):
            col.metric(label, value)

    st.caption("模型判定供复核参考。过滤后报告保留待处理条目；原有红字高亮与行格式随报告保留。")
    st.dataframe(
        [{
            "文件名": r["filename"],
            "报告条目": r.get("stats", {}).get("total", 0),
            "判为误报": r.get("stats", {}).get("suppressed", 0),
            "保留复核": r.get("stats", {}).get("kept", 0),
        } for r in valid],
        width="stretch", hide_index=True,
        column_config={"文件名": st.column_config.TextColumn(width="large")},
    )

    if st.session_state.zip_cache is None:
        st.session_state.zip_cache = build_zip_bytes(results, st.session_state.file_bytes_map)
    st.download_button(
        "打包下载全部结果", st.session_state.zip_cache,
        file_name="Xbench_Filtered_Results.zip", mime="application/zip",
        icon=":material/folder_zip:", type="primary", on_click="ignore",
        help="每份报告各包含一份过滤后报告和一份分析总表。",
    )

    with st.container(border=True, key="report-panel"):
        st.subheader("报告与明细")
        selected = st.selectbox("选择报告", [r["filename"] for r in valid], key="report-selection")
        result = next(r for r in valid if r["filename"] == selected)
        original = st.session_state.file_bytes_map.get(selected)
        stem = os.path.splitext(selected)[0]
        left, right = st.columns(2)
        with left:
            if original:
                st.download_button(
                    "下载过滤后报告", build_filtered_xlsx(original, result["rows"]),
                    file_name=f"{stem}_filtered.xlsx", mime=XLSX_MIME,
                    icon=":material/download:", width="stretch", on_click="ignore",
                    help="删除判为误报的条目，保留原报告格式。",
                )
        with right:
            st.download_button(
                "下载分析总表", build_analysis_xlsx(result["rows"]),
                file_name=f"{stem}_analysis.xlsx", mime=XLSX_MIME,
                icon=":material/table_view:", width="stretch", on_click="ignore",
                help="包含所有条目的原文、译文、判定及复核依据。",
            )

        st.divider()
        filter_col, search_col = st.columns([1.2, 1.8])
        with filter_col:
            verdict = st.segmented_control(
                "按判定查看", ["全部", "误报", "保留复核"], default="全部",
                selection_mode="single", required=True, key="verdict-filter",
            )
        with search_col:
            query = st.text_input(
                "搜索条目", placeholder="原文、译文、报错类型或复核依据",
                key="result-search",
            ).strip().casefold()

        rows = []
        for row in result["rows"]:
            is_suppressed = row.verdict == "误报"
            if verdict == "误报" and not is_suppressed:
                continue
            if verdict == "保留复核" and is_suppressed:
                continue
            display = {
                "原行号": row.row_num,
                "判定": "误报" if is_suppressed else "保留复核",
                "原文": str(row.source_text or ""),
                "译文": str(row.target_text or ""),
                "报错类型": str(row.error_type or ""),
                "报错描述": str(row.error_description or ""),
                "复核依据": str(row.llm_analysis or ""),
            }
            if not query or any(query in str(v).casefold() for v in display.values()):
                rows.append(display)
        st.caption(f"显示 {len(rows):,} / {len(result['rows']):,} 条")
        if rows:
            st.dataframe(
                rows, width="stretch", hide_index=True, height=380,
                column_config={
                    "原行号": st.column_config.NumberColumn(width="small"),
                    "判定": st.column_config.TextColumn(width="small"),
                    "原文": st.column_config.TextColumn(width="medium"),
                    "译文": st.column_config.TextColumn(width="medium"),
                    "复核依据": st.column_config.TextColumn(width="large"),
                },
            )
        else:
            st.info("没有匹配的条目，可更换判定筛选或清空搜索词。")
