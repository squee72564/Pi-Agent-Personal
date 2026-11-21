"""Offline tests; no Tavily requests or credential access."""
import argparse
import contextlib
import importlib.util
import io
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("tavily_web", Path(__file__).with_name("web.py"))
web = importlib.util.module_from_spec(spec)
spec.loader.exec_module(web)


class WebTests(unittest.TestCase):
    def capture_search(self, results, limit=450, count=3):
        output = io.StringIO()
        args = argparse.Namespace(query="weather test", max_results=count, snippet_chars=limit)
        with patch.object(web, "invoke", return_value={"results": results}), contextlib.redirect_stdout(output):
            web.search(args)
        return output.getvalue()

    def test_compact_preserves_words_and_values(self):
        self.assertEqual(web.compact('  Temp:\n61°F\tUpdated: 2026-11-19 16:15  '),
                         'Temp: 61°F Updated: 2026-11-19 16:15')

    def test_noisy_results_are_bounded_and_source_metadata_survives(self):
        item = {"title": "Weather\nforecast", "url": "https://example.com/weather",
                "published_date": "2026-11-19", "content": ("Forecast\n\n\n" * 1000)}
        text = self.capture_search([item] * 3)
        self.assertEqual(text.count("[truncated]"), 3)
        self.assertEqual(text.count("https://example.com/weather"), 3)
        self.assertIn("Published: 2026-11-19", text)
        self.assertIn("Source dates may differ", text)
        self.assertLess(len(text), 2100)
        self.assertLessEqual(len(text.splitlines()), 18)

    def test_snippet_can_expand_or_be_omitted(self):
        item = {"title": "Title", "url": "https://example.com", "content": "x" * 2000}
        self.assertIn("x" * 1500 + " [truncated]", self.capture_search([item], limit=1500))
        text = self.capture_search([item], limit=0)
        self.assertIn("https://example.com", text)
        self.assertNotIn("xxx", text)

    def test_search_defaults(self):
        with patch.object(sys, "argv", ["web.py", "search", "test"]), patch.object(web, "search") as call:
            web.main()
        args = call.call_args.args[0]
        self.assertEqual((args.max_results, args.snippet_chars), (3, 450))

    def test_limits(self):
        for limit in [0, 450, 4000]:
            with patch.object(sys, "argv", ["web.py", "search", "test", "--snippet-chars", str(limit)]), patch.object(web, "search"):
                web.main()
        for command in [["search", "test", "--snippet-chars", "4001"],
                        ["search", "test", "--snippet-chars", "-1"],
                        ["extract", "https://example.com", "--max-chars", "25001"]]:
            with patch.object(sys, "argv", ["web.py"] + command), contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as error:
                    web.main()
                self.assertEqual(error.exception.code, 2)
        with patch.object(sys, "argv", ["web.py", "extract", "https://example.com", "--max-chars", "25000", "--start", "50000"]), patch.object(web, "extract") as call:
            web.main()
        self.assertEqual(call.call_args.args[0].max_chars, 25000)
        self.assertEqual(call.call_args.args[0].start, 50000)

    def test_extract_layout_and_cache_continuation_unchanged(self):
        content = "# Heading\n\n| Key | Value |\n| --- | --- |\n| a | 42 |\n" * 10
        response = {"results": [{"url": "https://example.com", "title": "Doc", "raw_content": content}]}
        with tempfile.TemporaryDirectory() as directory, patch.object(web, "CACHE", Path(directory)), patch.object(web, "invoke", return_value=response) as call:
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                web.extract(argparse.Namespace(url="https://example.com", start=0, max_chars=100, refresh=False))
            self.assertIn(content[:100], output.getvalue())
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                web.extract(argparse.Namespace(url="https://example.com", start=100, max_chars=100, refresh=False))
            self.assertIn(content[100:200], output.getvalue())
            self.assertIn("Cache: hit", output.getvalue())
            self.assertEqual(call.call_count, 1)

    def test_auth_hides_credentials_and_stops_when_missing(self):
        for success in [True, False]:
            status = argparse.Namespace(returncode=0 if success else 1,
                                        stdout="Authenticated via OAuth SECRET" if success else "Not authenticated SECRET",
                                        stderr="")
            output = io.StringIO()
            with patch.object(web, "invoke", return_value=status), contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
                if success:
                    web.authenticate()
                else:
                    with self.assertRaises(SystemExit):
                        web.authenticate()
            self.assertNotIn("SECRET", output.getvalue())


if __name__ == "__main__":
    unittest.main()
