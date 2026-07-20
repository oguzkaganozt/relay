"""Unit tests for Relay privacy settings (stdlib only)."""
import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest import mock

MODULE = Path(__file__).resolve().parent.parent / "scripts" / "_relay_settings.py"


def _load():
    spec = importlib.util.spec_from_file_location("_relay_settings", MODULE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


settings = _load()


class LoadDefaultsTests(unittest.TestCase):
    def test_missing_file_returns_defaults(self):
        cfg = settings.load(Path("/nonexistent/x.toml"))
        self.assertEqual(cfg, settings.DEFAULTS)

    def test_defaults_cloud_on_context_off_until_consent(self):
        cfg = settings.DEFAULTS
        self.assertTrue(cfg["cloud_processing"])
        self.assertTrue(cfg["context_sharing"])
        self.assertFalse(cfg["context_sharing_consented"])


class LoadFileTests(unittest.TestCase):
    def test_parses_privacy_section(self):
        with tempfile.NamedTemporaryFile("w", suffix=".toml", delete=False) as f:
            f.write("[privacy]\ncloud_processing = false\ncontext_sharing = true\ncontext_sharing_consented = true\n")
            p = Path(f.name)
        try:
            cfg = settings.load(p)
        finally:
            p.unlink()
        self.assertFalse(cfg["cloud_processing"])
        self.assertTrue(cfg["context_sharing"])
        self.assertTrue(cfg["context_sharing_consented"])

    def test_malformed_file_falls_back_to_defaults(self):
        with tempfile.NamedTemporaryFile("w", suffix=".toml", delete=False) as f:
            f.write("not valid toml {{{")
            p = Path(f.name)
        try:
            cfg = settings.load(p)
        finally:
            p.unlink()
        self.assertEqual(cfg, settings.DEFAULTS)

    def test_non_bool_values_ignored(self):
        with tempfile.NamedTemporaryFile("w", suffix=".toml", delete=False) as f:
            f.write('[privacy]\ncloud_processing = "yes"\n')
            p = Path(f.name)
        try:
            cfg = settings.load(p)
        finally:
            p.unlink()
        self.assertTrue(cfg["cloud_processing"])  # default kept


class SaveRoundtripTests(unittest.TestCase):
    def test_save_then_load(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "s.toml"
            settings.save({"cloud_processing": False, "context_sharing": False,
                           "context_sharing_consented": True}, p)
            cfg = settings.load(p)
        self.assertFalse(cfg["cloud_processing"])
        self.assertFalse(cfg["context_sharing"])
        self.assertTrue(cfg["context_sharing_consented"])

    def test_save_drops_unknown_keys(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "s.toml"
            settings.save({"cloud_processing": True, "bogus": "x"}, p)
            text = p.read_text()
        self.assertIn("[privacy]", text)
        self.assertNotIn("bogus", text)


class EnabledTests(unittest.TestCase):
    def test_cloud_enabled_default(self):
        self.assertTrue(settings.cloud_processing_enabled({"cloud_processing": True}))

    def test_cloud_disabled(self):
        self.assertFalse(settings.cloud_processing_enabled({"cloud_processing": False}))

    def test_context_sharing_requires_consent(self):
        # V2: context sharing on ONLY after consent.
        self.assertFalse(settings.context_sharing_enabled(
            {"context_sharing": True, "context_sharing_consented": False}))
        self.assertTrue(settings.context_sharing_enabled(
            {"context_sharing": True, "context_sharing_consented": True}))

    def test_context_sharing_off_even_if_consented(self):
        self.assertFalse(settings.context_sharing_enabled(
            {"context_sharing": False, "context_sharing_consented": True}))


class ConsentTests(unittest.TestCase):
    def test_consent_turns_on_and_persists(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "s.toml"
            cfg = settings.consent_to_context_sharing(p)
            self.assertTrue(cfg["context_sharing"])
            self.assertTrue(cfg["context_sharing_consented"])
            reloaded = settings.load(p)
        self.assertTrue(reloaded["context_sharing_consented"])
        self.assertTrue(settings.context_sharing_enabled(reloaded))


if __name__ == "__main__":
    unittest.main()
