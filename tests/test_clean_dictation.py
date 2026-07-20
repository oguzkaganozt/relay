"""Unit tests for voxtype-clean-dictation pure logic.

Stdlib only (unittest) to match the no-dependencies constraint. The script
has no .py extension and runs as an executable, so we load it by path.
Importing it only reads config/env at module level (no network, no exit),
which is safe under test.

Run: python3 -m unittest discover -s tests
"""
import importlib.util
import io
import json
import sys
import unittest
import urllib.error
from importlib.machinery import SourceFileLoader
from pathlib import Path
from unittest import mock

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "voxtype-clean-dictation"


def _load():
    # The script has no .py suffix, so spec_from_file_location can't infer a
    # loader. Use SourceFileLoader explicitly to load it as a Python module.
    loader = SourceFileLoader("voxtype_clean_dictation", str(SCRIPT))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


cd = _load()

# Long enough to pass should_skip (>=90 chars, >=14 words, no code markers).
_LONG = " ".join(["word"] * 40)
_UNSET = object()


class ShouldSkipTests(unittest.TestCase):
    def test_empty_and_short_pass_through(self):
        self.assertTrue(cd.should_skip(""))
        self.assertTrue(cd.should_skip("merhaba"))
        self.assertTrue(cd.should_skip("hello there friend"))

    def test_long_sentence_is_cleaned(self):
        # >=90 chars AND >=14 words, no code markers -> not skipped.
        text = " ".join(["word"] * 20)  # 20 words, 99 chars
        self.assertGreaterEqual(len(text), 90)
        self.assertFalse(cd.should_skip(text))

    def test_char_boundary(self):
        # 89-char single token: len < 90 and 1 word < 14 -> skip.
        self.assertTrue(cd.should_skip("a" * 89))
        # 90-char single token: len not < 90, no marker -> not skipped.
        self.assertFalse(cd.should_skip("a" * 90))

    def test_word_boundary(self):
        # 13 short words: both conditions true -> skip.
        self.assertTrue(cd.should_skip(" ".join(["a"] * 13)))
        # 14 short words (< 90 chars but words not < 14), no marker -> not skip.
        self.assertFalse(cd.should_skip(" ".join(["a"] * 14)))

    def test_code_markers_force_skip(self):
        for marker in ["&&", "||", "sudo ", "git ", "docker ", "systemctl ",
                       "journalctl ", "~/", "./", "--"]:
            # Long, many-worded text that would otherwise be cleaned.
            text = " ".join(["word"] * 30) + " " + marker + "thing"
            self.assertFalse(cd.should_skip(" ".join(["word"] * 30)),
                             "control: marker-free long text is cleaned")
            self.assertTrue(cd.should_skip(text), f"marker {marker!r} should skip")


class OutputTooLongTests(unittest.TestCase):
    def test_similar_length_ok(self):
        self.assertFalse(cd.output_too_long("a" * 100, "b" * 100))

    def test_short_input_uses_additive_floor(self):
        # max(7.5, 125) = 125; 200 > 125 -> too long.
        self.assertTrue(cd.output_too_long("hello", "x" * 200))
        self.assertFalse(cd.output_too_long("hello", "x" * 120))

    def test_long_input_uses_multiplier(self):
        # max(1500, 1120) = 1500.
        self.assertFalse(cd.output_too_long("a" * 1000, "b" * 1400))
        self.assertTrue(cd.output_too_long("a" * 1000, "b" * 1600))


class MainFailOpenTests(unittest.TestCase):
    """main() must never crash or lose the transcription on any failure.

    The fail-open contract is the core safety property of the VoxType
    post-processor: on network error, missing auth, parse error, empty
    response, or oversized output, the original text is emitted unchanged so
    the daemon never blocks. These tests lock that contract end-to-end.
    """

    def _run(self, stdin_text=_LONG, *, side_effect=_UNSET, return_value=_UNSET):
        kwargs = {}
        if side_effect is not _UNSET:
            kwargs["side_effect"] = side_effect
        elif return_value is not _UNSET:
            kwargs["return_value"] = return_value
        with mock.patch.object(cd, "clean", **kwargs) as clean_mock, \
             mock.patch.object(cd, "_notify") as notify_mock:
            old_in, old_out = sys.stdin, sys.stdout
            sys.stdin = io.StringIO(stdin_text)
            out = io.StringIO()
            sys.stdout = out
            try:
                rc = cd.main()
            finally:
                sys.stdin, sys.stdout = old_in, old_out
        return rc, out.getvalue(), clean_mock, notify_mock

    def test_network_error_emits_original(self):
        rc, out, clean, _ = self._run(side_effect=urllib.error.URLError("boom"))
        self.assertEqual(rc, 0)
        self.assertEqual(out, _LONG)
        self.assertTrue(clean.called)

    def test_timeout_emits_original(self):
        rc, out, _, _ = self._run(side_effect=TimeoutError())
        self.assertEqual(rc, 0)
        self.assertEqual(out, _LONG)

    def test_missing_auth_emits_original(self):
        rc, out, _, _ = self._run(side_effect=RuntimeError("no api key"))
        self.assertEqual(rc, 0)
        self.assertEqual(out, _LONG)

    def test_parse_error_emits_original(self):
        rc, out, _, _ = self._run(
            side_effect=json.JSONDecodeError("no json", "{", 0))
        self.assertEqual(rc, 0)
        self.assertEqual(out, _LONG)

    def test_oserror_emits_original(self):
        rc, out, _, _ = self._run(side_effect=OSError("boom"))
        self.assertEqual(rc, 0)
        self.assertEqual(out, _LONG)

    def test_empty_response_emits_original(self):
        rc, out, _, _ = self._run(return_value="")
        self.assertEqual(rc, 0)
        self.assertEqual(out, _LONG)

    def test_oversized_output_emits_original(self):
        rc, out, _, _ = self._run(return_value="x" * 400)
        self.assertEqual(rc, 0)
        self.assertEqual(out, _LONG)

    def test_success_emits_cleaned(self):
        rc, out, _, notify = self._run(return_value="cleaned text")
        self.assertEqual(rc, 0)
        self.assertEqual(out, "cleaned text")
        self.assertTrue(notify.called)

    def test_short_text_passes_through_without_clean(self):
        rc, out, clean, _ = self._run("merhaba")
        self.assertEqual(rc, 0)
        self.assertEqual(out, "merhaba")
        self.assertFalse(clean.called)

    def test_empty_input_writes_nothing(self):
        rc, out, clean, _ = self._run("")
        self.assertEqual(rc, 0)
        self.assertEqual(out, "")
        self.assertFalse(clean.called)


if __name__ == "__main__":
    unittest.main()
