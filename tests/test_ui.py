import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from ui.backend import ProcessingTask, RunConfig
from ui.presentation import configuration_errors, duplicate_filenames

APP = Path(__file__).resolve().parents[1] / "ui" / "app.py"


class WorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.config = patch("ui.backend.default_config_from_module", return_value=RunConfig(api_key="", model="test-model"))
        self.models = patch("ui.backend.get_all_models", return_value=["test-model"])
        self.config.start()
        self.models.start()
        self.addCleanup(self.config.stop)
        self.addCleanup(self.models.stop)

    def app(self):
        app = AppTest.from_file(str(APP)).run()
        self.assertEqual(len(app.exception), 0)
        return app

    def test_unconfigured_workspace_has_disabled_start_and_working_navigation(self):
        app = self.app()
        self.assertTrue(next(b for b in app.button if b.label == "开始筛查").disabled)
        app.button(key="nav_settings").click().run()
        self.assertEqual(len(app.exception), 0)
        app.button(key="nav_about").click().run()
        self.assertEqual(len(app.exception), 0)

    def test_uploader_accepts_both_legacy_and_modern_excel(self):
        app = self.app()
        allowed = app.get("file_uploader")[0].proto.type
        self.assertEqual(set(allowed), {".xls", ".xlsx"})

    def test_settings_require_apply_and_invalidate_old_connection_status(self):
        app = self.app()
        app.button(key="nav_settings").click().run()
        app.text_input(key="settings_key").set_value("local-test-key").run()
        app.text_input(key="settings_base").set_value("http://127.0.0.1:9999/v1").run()
        self.assertEqual(app.session_state.cfg.api_key, "")
        app.session_state.api_status = (True, "previous endpoint")
        next(b for b in app.button if b.label == "应用设置").click().run()
        self.assertEqual(app.session_state.cfg.api_key, "local-test-key")
        self.assertIsNone(app.session_state.api_status)
        with patch("ui.backend.test_api_connection", return_value=(True, "mock connection")) as test_api:
            next(b for b in app.button if b.label == "应用并测试连接").click().run()
        test_api.assert_called_once()
        self.assertEqual(app.session_state.api_status, (True, "mock connection"))
        self.assertEqual(len(app.exception), 0)

    def test_active_task_locks_restart_clear_and_settings(self):
        app = self.app()
        task = ProcessingTask(["report.xlsx"])
        app.session_state.task = task
        app.run()
        for label in ("正在筛查…", "清空文件与结果"):
            self.assertTrue(next(b for b in app.button if b.label == label).disabled)
        app.button(key="nav_settings").click().run()
        self.assertTrue(app.text_input(key="settings_key").disabled)
        self.assertTrue(next(b for b in app.button if b.label == "应用设置").disabled)
        task._done_event.set()
        app.run()
        self.assertIsNone(app.session_state.task)
        self.assertFalse(next(b for b in app.button if b.label == "应用设置").disabled)
        self.assertEqual(len(app.exception), 0)

    def test_duplicate_names_are_rejected_case_insensitively(self):
        files = [SimpleNamespace(name=name) for name in ("报告.xlsx", "report.xlsx", "REPORT.xlsx")]
        self.assertEqual(duplicate_filenames(files), ["REPORT.xlsx"])

    def test_mixed_excel_extensions_cannot_collide_in_export_names(self):
        files = [SimpleNamespace(name=name) for name in ("报告.xls", "报告.xlsx")]
        self.assertEqual(duplicate_filenames(files), ["报告.xlsx"])

    def test_placeholder_key_and_invalid_endpoint_are_not_ready(self):
        cfg = RunConfig(api_key="your-api-key-here", api_base="api.example.com")
        self.assertEqual(len(configuration_errors(cfg)), 2)
        cfg.api_key = "local-test-key"
        cfg.api_base = "http://127.0.0.1:9999/v1"
        self.assertEqual(configuration_errors(cfg), [])
