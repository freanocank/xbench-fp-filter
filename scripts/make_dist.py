"""Build a dated Windows source package, excluding credentials and local data."""

import argparse
import ast
import shutil
import tempfile
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

PROJ = Path(__file__).resolve().parents[1]
NAME = "xbench-fp-filter"
EXCLUDE_DIRS = {
    "__pycache__", ".git", "venv", ".venv", "env", "python", "node_modules",
    "data", "docs", "dailies", "annotation_requirements", ".streamlit_cache",
    ".pytest_cache", ".playwright-cli", ".ruff_cache", "output", "outputs", "dist",
}
EXCLUDE_FILES = {"config.py", ".DS_Store", "secrets.toml", "get_pip.py", "python_embed.zip"}
EXCLUDE_EXT = {".pyc", ".pyo", ".xlsx", ".xls", ".faiss", ".db", ".zip"}


def _ignore(dirpath, names):
    drop = set()
    for name in names:
        path = Path(dirpath) / name
        if path.is_dir():
            if name in EXCLUDE_DIRS:
                drop.add(name)
        elif (name in EXCLUDE_FILES or name.startswith(".env")
              or path.suffix.lower() in EXCLUDE_EXT or ".bak" in name):
            drop.add(name)
    return drop


def _normalize_launchers(stage: Path) -> None:
    for path in stage.rglob("*"):
        if path.suffix.lower() not in {".bat", ".cmd"}:
            continue
        text = path.read_text(encoding="utf-8-sig")
        first_chinese = next((i for i, char in enumerate(text) if ord(char) > 127), len(text))
        if "chcp 65001 >nul" not in text[:first_chinese]:
            raise ValueError(f"UTF-8 console setup missing before non-ASCII text: {path.name}")
        path.write_bytes(text.replace("\r\n", "\n").replace("\n", "\r\n").encode("utf-8"))


def _assert_no_credentials(stage: Path) -> None:
    source_config = PROJ / "config.py"
    if not source_config.exists():
        return
    tree = ast.parse(source_config.read_text(encoding="utf-8-sig"))
    keys = [
        node.value.value.encode("utf-8")
        for node in tree.body
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "LLM_API_KEY" for target in node.targets)
        and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str)
        and len(node.value.value) >= 12 and node.value.value != "your-api-key-here"
    ]
    for path in stage.rglob("*"):
        if path.is_file() and any(key in path.read_bytes() for key in keys):
            raise ValueError(f"Credential found in distribution: {path.relative_to(stage)}")


def build(output: str | Path | None = None) -> Path:
    stamp = datetime.now(timezone(timedelta(hours=8))).strftime("%Y%m%d")
    destination = Path(output) if output else Path.home() / "Desktop" / f"{NAME}_dist_{stamp}.zip"
    destination = destination.expanduser().resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="xbench_dist_") as temp:
        stage = Path(temp) / NAME
        shutil.copytree(PROJ, stage, ignore=_ignore)
        shutil.copyfile(stage / "config_template.py", stage / "config.py")
        _normalize_launchers(stage)
        _assert_no_credentials(stage)
        files = sorted(path for path in stage.rglob("*") if path.is_file())
        with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED) as archive:
            for path in files:
                archive.write(path, (Path(NAME) / path.relative_to(stage)).as_posix())
    print(f"OK  {destination}")
    print(f"    {len(files)} files, {destination.stat().st_size / 1024 / 1024:.2f} MB")
    return destination


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="ZIP destination; defaults to a dated Desktop package")
    build(parser.parse_args().output)
