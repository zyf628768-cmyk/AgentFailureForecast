"""Release-facing behavior and bounded-input regressions."""
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import test_cli_schema as cli_tests
from agent_failure_forecast.planner import normalize
from agent_failure_forecast.safety import parse_json, safe_path, write_report


class InputLimitsTests(unittest.TestCase):
    def test_offline_rebuild_rejects_old_backend(self):
        from scripts.verify_distribution import validate_build_backend
        with patch("importlib.metadata.version", return_value="65.5.0"):
            with self.assertRaisesRegex(ValueError, "setuptools>=77"):
                validate_build_backend()

    def test_offline_rebuild_accepts_declared_backend(self):
        from scripts.verify_distribution import validate_build_backend
        with patch("importlib.metadata.version", return_value="77.0.0"):
            validate_build_backend()

    def test_windows_reparse_without_is_junction_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch("agent_failure_forecast.safety.Path.lstat", return_value=SimpleNamespace(st_mode=0o040755, st_file_attributes=0x400)):
                with self.assertRaises(ValueError):
                    safe_path(directory, "junction")
                with self.assertRaises(ValueError):
                    write_report(Path(directory)/"report", "data", force=True)

    def test_overflowing_json_float_rejected(self):
        for text in ('{"value":1e999}', '{"value":-1e999}'):
            with self.subTest(text=text), self.assertRaises(ValueError):
                parse_json(text)

    def test_excessive_dependency_entries_rejected(self):
        with self.assertRaises(ValueError):
            normalize({"steps": [{"id": "one", "depends_on": ["missing"]*10001}]})


class PolicyExitTests(unittest.TestCase):
    setUp = cli_tests.CliTests.setUp
    run_cli = cli_tests.CliTests.run_cli

    def test_fail_on_writes_report_before_exit_three(self):
        output = self.root/"report.json"
        result = self.run_cli("scan", "--plan", self.input, "--root", self.root,
                              "--fail-on", "high", "--output", output)
        self.assertEqual(result.returncode, 3, result.stderr)
        self.assertIn("DEPLOY001", output.read_text())

    def test_default_exit_remains_success_for_risks(self):
        self.assertEqual(self.run_cli("scan", "--plan", self.input, "--root", self.root).returncode, 0)

    def test_lower_severity_does_not_trip_policy(self):
        self.input.write_text(json.dumps({"goal": "inspect", "steps": [{"id": "one"}]}), encoding="utf-8")
        result = self.run_cli("scan", "--plan", self.input, "--root", self.root, "--fail-on", "critical")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_plan_cycle_trips_policy(self):
        self.input.write_text('{"steps":[{"id":"one","depends_on":["one"]}]}', encoding="utf-8")
        result = self.run_cli("plan", "--plan", self.input, "--fail-on", "high")
        self.assertEqual(result.returncode, 3, result.stderr)

    def test_invalid_input_still_exit_two(self):
        self.input.write_text('{"bad":1e999}', encoding="utf-8")
        result = self.run_cli("scan", "--plan", self.input, "--root", self.root, "--fail-on", "critical")
        self.assertEqual(result.returncode, 2)

    def test_unicode_console_report(self):
        self.input.write_text('{"goal":"本地检查","steps":[{"id":"检查"}]}', encoding="utf-8")
        result = self.run_cli("plan", "--plan", self.input)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["nodes"], ["检查"])

    def test_json_stdout_utf8_even_with_ascii_environment(self):
        self.input.write_text('{"goal":"本地检查","steps":[{"id":"检查"}]}', encoding="utf-8")
        with patch.dict("os.environ", {"PYTHONIOENCODING": "ascii"}):
            result = self.run_cli("plan", "--plan", self.input)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["nodes"], ["检查"])
