# Xbench FP Filter

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.x-blue.svg)](https://www.python.org/)
[![Xbench](https://img.shields.io/badge/Xbench-QA%20workflow-blueviolet.svg)](https://www.xbench.net/)

English | [中文](README_ZH.md)

## Overview

 Game-localization QA false-positive filter that reads Xbench Excel reports and uses an LLM to classify false positives.

## Key Capabilities

- Evaluates Xbench QA entries one by one.
- Outputs filtered reports and analysis workbooks.
- Targets game-localization QA review workflows.

## Usage

 Prepare the Xbench Excel report, API configuration, and output directory as described below.

 Setup, operation, and recovery: [Usage notes (Chinese)](使用说明.txt) or the in-app usage guide.

### 2026-10-21 update

- Detects the outer OLE workbook before testing for ZIP content. This prevents XLS files containing embedded theme ZIPs from being misidentified as XLSX and failing with `File contains no valid workbook part`.
- Supports Excel 97–2003 `.xls` and `.xlsx` Xbench reports. Legacy workbooks are converted before review; exports use `.xlsx`, retaining report text, rich-text highlights, and common cell formatting.
- Detects mixed-format filenames that would collide on export, and checks for the legacy Excel reader during Windows startup.
- Windows launchers now select UTF-8 before Chinese output, set Python UTF-8 output, and retain BOM-free UTF-8 with CRLF in distribution packages.
- The UI follows the Langlobal workspace palette, system fonts, and logo treatment, with result filters, search, and individual report downloads.
- Running tasks lock upload/restart/reset actions. File failures are reported independently and do not block later files.
- Settings require an explicit Apply action and last for the current session. Connection checks have a 15-second timeout with no automatic retries.

## Notes

 LLM classifications should be spot-checked by QA/localization staff.

## Command and Configuration Reference

The following code blocks keep commands, paths, filenames, and configuration keys literal; explanatory comments are translated for the English README.

```
run.bat
```

```
streamlit run ui/app.py
```

```
fp-filter/
├── ui/                  frontend modules
│   ├── app.py           Streamlit page routing, component rendering, progress polling
│   └── backend.py       UI/backend adapter: RunConfig, ProcessingTask, export functions, model management
├── run.bat / setup.bat  one-click Windows launcher / environment initialization (downloads embedded Python)
├── config.py / config_template.py  runtime config and sanitized template
├── requirements.txt     Python dependencies
│
├── core/                core LLM modules
│   ├── xbench.py        Xbench Excel parsing + row filtering
│   └── llm_review.py    LLM review: prompts, async calls, retries, result parsing
│
├── rag/                 vector retrieval layer (experimental; incomplete)
│   ├── store.py         case library (SQLite + FAISS + bge-m3 embedding)
│   ├── search.py        vector search + decision routing
│   └── engine.py        RAGEngine: unified entry point for the full RAG pipeline
│
├── scripts/             batch testing and evaluation
│   ├── run_test.py      RAG batch test entry point
│   └── data_calculator.py  metric calculation (precision, recall, F1, F2)
│
└── data/
    ├── database/        SQLite case library + FAISS index
    ├── raw_data/        parsed JSON cache
    ├── custom_models.json   user custom model list (written by UI)
    ├── report/          historical test reports
    └── 已导入/           case data waiting to be imported
```

```python
from rag.engine import RAGEngine

engine = RAGEngine(
    db_path="data/database/cases.db",
    faiss_path="data/database/cases.faiss",
    llm_api_key="sk-xxx",
    llm_api_base="https://api.xxx/v1",
    llm_model="gemini-3.1-flash-lite",
)

result = engine.judge(
    error_type="术语违规",
    error_description="开封府 | Kaifeng Prefecture | Kaifeng",
    source_text="来人，把此人押回开封府。",
    target_text="Guards, haul him off to Kaifeng.",
)
```
