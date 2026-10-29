import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from scripts import make_dist

ROOT = Path(__file__).resolve().parents[1]


class DistributionTests(unittest.TestCase):
    def test_launchers_select_utf8_before_chinese_and_use_crlf_without_bom(self):
        for name in ("run.bat", "setup.bat"):
            raw = (ROOT / name).read_bytes()
            self.assertFalse(raw.startswith(b"\xef\xbb\xbf"), name)
            self.assertNotIn(b"\n", raw.replace(b"\r\n", b""), name)
            text = raw.decode("utf-8")
            first_non_ascii = next(i for i, char in enumerate(text) if ord(char) > 127)
            self.assertIn("chcp 65001 >nul", text[:first_non_ascii])
            self.assertIn('set "PYTHONUTF8=1"', text)
            self.assertIn('set "PYTHONIOENCODING=utf-8"', text)

    def test_package_normalizes_launchers_and_excludes_private_and_generated_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "source"
            root.mkdir()
            for name in ("run.bat", "setup.bat", "config_template.py"):
                # Simulate a Git checkout that normalized launchers to LF.
                (root / name).write_text((ROOT / name).read_text(encoding="utf-8"), encoding="utf-8")
            marker = "private-credential-for-packaging-test"
            (root / "config.py").write_text(f'LLM_API_KEY = "{marker}"', encoding="utf-8")
            (root / ".env").write_text(marker, encoding="utf-8")
            (root / "customer.xlsx").write_bytes(b"customer-data")
            for name in ("data", "output", "outputs", ".playwright-cli"):
                (root / name).mkdir()
                (root / name / "private.txt").write_text(marker, encoding="utf-8")
            destination = Path(directory) / "package.zip"
            with patch.object(make_dist, "PROJ", root):
                make_dist.build(destination)
            with zipfile.ZipFile(destination) as archive:
                self.assertIsNone(archive.testzip())
                self.assertEqual(set(archive.namelist()), {
                    f"xbench-fp-filter/{name}" for name in
                    ("run.bat", "setup.bat", "config_template.py", "config.py")
                })
                for name in ("run.bat", "setup.bat"):
                    raw = archive.read(f"xbench-fp-filter/{name}")
                    self.assertFalse(raw.startswith(b"\xef\xbb\xbf"))
                    self.assertNotIn(b"\n", raw.replace(b"\r\n", b""))
                self.assertNotIn(marker.encode(), archive.read("xbench-fp-filter/config.py"))

    def test_package_rejects_credential_accidentally_copied_into_another_file(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            marker = "private-credential-for-packaging-test"
            (root / "config.py").write_text(f'LLM_API_KEY = "{marker}"', encoding="utf-8")
            stage = root / "staged-package"
            stage.mkdir()
            (stage / "config.py").write_text('LLM_API_KEY = "your-api-key-here"', encoding="utf-8")
            (stage / "notes.txt").write_text(marker, encoding="utf-8")
            with patch.object(make_dist, "PROJ", root):
                with self.assertRaisesRegex(ValueError, "Credential found.*notes.txt"):
                    make_dist._assert_no_credentials(stage)
