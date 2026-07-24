"""Legacy hotkey scripts are thin wrappers over relay-bar --action."""
import importlib.util
import os
import unittest
from importlib.machinery import SourceFileLoader
from pathlib import Path
from unittest import mock

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"


def _load(name):
    path = SCRIPTS / name
    loader = SourceFileLoader(name.replace("-", "_"), str(path))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


rephrase = _load("voxtype-rephrase")
summarize = _load("voxtype-summarize")


class LegacyWrapperTests(unittest.TestCase):
    def test_rephrase_execs_relay_bar_rewrite(self):
        bar = str(SCRIPTS / "relay-bar")
        with mock.patch.object(rephrase, "_relay_bar", return_value=bar), \
             mock.patch.object(rephrase.os, "execv") as execv:
            rephrase.main()
        execv.assert_called_once_with(bar, [bar, "--action", "rewrite"])

    def test_summarize_execs_relay_bar_summarize(self):
        bar = str(SCRIPTS / "relay-bar")
        with mock.patch.object(summarize, "_relay_bar", return_value=bar), \
             mock.patch.object(summarize.os, "execv") as execv:
            summarize.main()
        execv.assert_called_once_with(bar, [bar, "--action", "summarize"])

    def test_missing_bar_returns_127(self):
        with mock.patch.object(rephrase, "_relay_bar", return_value=None):
            self.assertEqual(rephrase.main(), 127)

    def test_relay_bar_prefers_sidecar(self):
        path = rephrase._relay_bar()
        self.assertEqual(path, str(SCRIPTS / "relay-bar"))
        self.assertTrue(os.path.isfile(path))


if __name__ == "__main__":
    unittest.main()
