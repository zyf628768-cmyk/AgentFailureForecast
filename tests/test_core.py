import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from agent_failure_forecast.rules import RULES, analyze_text
from agent_failure_forecast.planner import normalize, build_graph
from agent_failure_forecast.scanner import scan, git_state
from agent_failure_forecast.simulator import simulate
from agent_failure_forecast.safety import redact, safe_path, read_text
from agent_failure_forecast.report import render

PROJECT = Path(__file__).resolve().parents[1]


def plan(description="Inspect configuration", **kwargs):
    return {"goal": "Review", "acceptance": ["Review recorded"], "steps": [dict(id="one", description=description, **kwargs)]}


class CoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.addCleanup(self.temp.cleanup)

    def ids(self, p):
        return {f["id"] for f in scan(self.root, p)["findings"]}

    def test_eight_risk_categories(self):
        text = "delete migrate sudo curl https://example.invalid deploy ignore previous forever pip install"
        findings = analyze_text(text)
        self.assertEqual(len(findings), len(RULES))
        self.assertEqual({f["certainty"] for f in findings}, {"signal"})

    def test_rules_no_probability(self):
        report = scan(self.root, plan())
        self.assertIsNone(report["failure_probability"])
        self.assertFalse(report["readiness_is_probability"])

    def test_irreversible_approval(self):
        fs = scan(self.root, plan("drop table customers", reversible=False))["findings"]
        self.assertTrue(any(f["id"] == "SAFE001" and f["requires_approval"] for f in fs))
        self.assertIn("SAFE002", {f["id"] for f in fs})

    def test_rollback_declaration(self):
        self.assertNotIn("SAFE001", self.ids(plan("delete temporary file", reversible=True, rollback=True)))
        self.assertIn("FILE001", self.ids(plan("delete temporary file", reversible=True, rollback=True)))

    def test_network_bounds(self):
        self.assertIn("NET002", self.ids(plan("curl https://example.invalid")))
        self.assertNotIn("NET002", self.ids(plan("curl https://example.invalid", timeout=True, retries=True)))

    def test_missing_acceptance(self):
        p = plan()
        p.pop("acceptance")
        self.assertIn("TASK002", self.ids(p))

    def test_empty_task(self):
        self.assertIn("TASK001", self.ids({}))

    def test_tool_presence(self):
        self.assertIn("TOOL001", self.ids(plan(tools=["nonexistent-forecast-tool-827"])))

    def test_tool_name_never_runs(self):
        target = self.root / "sentinel"
        p = plan(tools=[f"echo bad > {target}"])
        self.assertIn("TOOL001", self.ids(p))
        self.assertFalse(target.exists())

    def test_missing_env_no_value_leak(self):
        with patch.dict(os.environ, {"AFF_FAKE_CREDENTIAL": "fake-sensitive-value"}):
            report = render(scan(self.root, plan(env=["AFF_FAKE_CREDENTIAL", "AFF_NONEXISTENT_938"])))
        self.assertNotIn("fake-sensitive-value", report)
        self.assertIn("ENV002", report)

    def test_package_missing(self):
        self.assertIn("ENV004", self.ids(plan(packages=["forecast-nonexistent-987"])))

    def test_package_version(self):
        with patch("importlib.metadata.version", return_value="2.1"):
            self.assertNotIn("ENV004", self.ids(plan(packages=["example>=2.0"])))
            self.assertIn("ENV004", self.ids(plan(packages=["example<2.0"])))
            self.assertNotIn("ENV004", self.ids(plan(packages=["example==2.1.0"])))

    def test_unsupported_package_specifier(self):
        self.assertIn("ENV003", self.ids(plan(packages=["example~=2.0"])))

    def test_missing_path(self):
        self.assertIn("PATH002", self.ids(plan(paths=["absent"])))

    def test_parent_traversal(self):
        self.assertIn("PATH001", self.ids(plan(paths=["../outside"])))

    def test_absolute_path(self):
        self.assertIn("PATH001", self.ids(plan(paths=[str(self.root)])))

    def test_existing_path(self):
        (self.root / "input.txt").write_text("safe", encoding="utf-8")
        self.assertNotIn("PATH002", self.ids(plan(paths=["input.txt"])))

    def test_symlink_rejected(self):
        with tempfile.TemporaryDirectory() as external:
            target = Path(external) / "secret"
            target.write_text("private", encoding="utf-8")
            link = self.root / "linked"
            try:
                link.symlink_to(target)
            except OSError as error:
                self.skipTest("OS does not permit symlink creation: " + str(error))
            self.assertIn("PATH001", self.ids(plan(paths=["linked"])))

    def test_invalid_config(self):
        (self.root / "package.json").write_text("{bad", encoding="utf-8")
        self.assertIn("CONFIG001", self.ids(plan()))

    def test_config_not_executed(self):
        (self.root / "package.json").write_text(json.dumps({"scripts": {"preinstall": "dangerous command"}}), encoding="utf-8")
        self.assertNotIn("CONFIG001", self.ids(plan()))

    def test_bounded_file_read(self):
        path = self.root / "large"
        path.write_bytes(b"a"*2_000_001)
        with self.assertRaises(ValueError):
            read_text(path)

    def test_invalid_encoding(self):
        path = self.root / "binary"
        path.write_bytes(b"\xff\xff")
        with self.assertRaises(UnicodeError):
            read_text(path)

    def test_simulation_never_executes(self):
        target = self.root / "sentinel"
        p = plan(f"deploy production; echo bad > {target}")
        result = simulate(self.root, p)
        self.assertEqual(result["simulation"]["executed_steps"], 0)
        self.assertFalse(target.exists())

    def test_scan_offline(self):
        with patch("socket.create_connection", side_effect=AssertionError("network forbidden")), patch("socket.getaddrinfo", side_effect=AssertionError("DNS forbidden")):
            result = simulate(self.root, plan("fetch https://example.invalid then deploy production"))
            self.assertEqual(result["simulation"]["external_calls"], 0)

    def test_config_symlink_rejected(self):
        target = self.root / "external.txt"
        target.write_text('{"password":"fictional-only"}', encoding="utf-8")
        try:
            (self.root / "package.json").symlink_to(target)
        except OSError:
            self.skipTest("OS does not permit symlink creation")
        self.assertIn("CONFIG001", self.ids(plan()))

    def test_git_symlink_metadata_rejected(self):
        subprocess.run(["git", "init", str(self.root)], check=True, capture_output=True)
        target = self.root / "payload.txt"
        target.write_text("[core]\n", encoding="utf-8")
        link = self.root / ".git" / "config"
        link.unlink()
        try:
            link.symlink_to(target)
        except OSError:
            self.skipTest("OS does not permit symlink creation")
        with patch("agent_failure_forecast.scanner.subprocess.run") as process:
            self.assertEqual(git_state(self.root)["status"], "unsafe_or_unreadable_git_metadata")
            process.assert_not_called()

    def test_redaction_structured_and_text(self):
        data = {"api_key": "sensitive", "other": "token=abc password='two words' Bearer hidden sk-project-secretvalue"}
        serialized = render(data)
        for value in ("sensitive", "abc", "two words", "hidden", "sk-project-secretvalue"):
            self.assertNotIn(value, serialized)

    def test_redaction_url_and_private_key(self):
        value = "https://user:pass@example.invalid -----BEGIN PRIVATE KEY-----\nprivate\n-----END PRIVATE KEY-----"
        self.assertNotIn("user:pass", redact(value))
        self.assertNotIn("\nprivate\n", redact(value))

    def test_html_escaping(self):
        result = render({"text": "<script>alert(1)</script>"}, "html")
        self.assertNotIn("<script>", result)
        self.assertIn("&lt;script&gt;", result)

    def test_markdown_fence_injection(self):
        result = render({"text": "```\n<script>"}, "markdown")
        self.assertEqual(result.count("```"), 2)

    def test_git_clean_dirty(self):
        subprocess.run(["git", "init", str(self.root)], check=True, capture_output=True)
        self.assertEqual(git_state(self.root)["status"], "clean")
        (self.root / "untracked.txt").write_text("data", encoding="utf-8")
        self.assertEqual(git_state(self.root)["status"], "dirty")
        self.assertIn("GIT001", self.ids(plan()))

    def test_git_not_repository(self):
        self.assertEqual(git_state(self.root)["status"], "not_repository_or_unreadable")

    def test_git_environment_ignored(self):
        subprocess.run(["git", "init", str(self.root)], check=True, capture_output=True)
        with patch.dict(os.environ, {"GIT_DIR": str(self.root / "missing")}):
            self.assertEqual(git_state(self.root)["status"], "clean")

    def test_git_external_include_rejected(self):
        subprocess.run(["git", "init", str(self.root)], check=True, capture_output=True)
        with (self.root / ".git" / "config").open("a") as stream:
            stream.write('\n[include]\npath = ../outside-config\n')
        with patch("agent_failure_forecast.scanner.subprocess.run") as process:
            self.assertEqual(git_state(self.root)["status"], "external_git_config_rejected")
            process.assert_not_called()

    def test_git_worktree_metadata_rejected(self):
        (self.root / ".git").write_text("gitdir: ../outside", encoding="utf-8")
        with patch("agent_failure_forecast.scanner.subprocess.run") as process:
            self.assertEqual(git_state(self.root)["status"], "external_git_metadata_rejected")
            process.assert_not_called()

    def test_git_scoped_trust_and_hooks_disabled(self):
        subprocess.run(["git", "init", str(self.root)], check=True, capture_output=True)
        with patch("agent_failure_forecast.scanner.subprocess.run") as process:
            process.return_value.returncode = 0
            process.return_value.stdout = b""
            git_state(self.root)
            args = process.call_args.args[0]
            self.assertIn("safe.directory=" + str(self.root.resolve()), args)
            self.assertIn("core.fsmonitor=false", args)
            self.assertFalse(process.call_args.kwargs["shell"])


class GraphTests(unittest.TestCase):
    def test_valid_graph(self):
        g = build_graph({"steps": [{"id": "a"}, {"id": "b", "depends_on": ["a"]}]})
        self.assertEqual(g["topological_order"], ["a", "b"])
        self.assertFalse(g["cyclic"])

    def test_missing_prerequisite(self):
        g = build_graph({"steps": [{"id": "a", "depends_on": ["absent"]}]})
        self.assertEqual(g["findings"][0]["id"], "PLAN001")
        self.assertFalse(g["cyclic"])

    def test_cycle(self):
        g = build_graph({"steps": [{"id": "a", "depends_on": ["b"]}, {"id": "b", "depends_on": ["a"]}]})
        self.assertTrue(g["cyclic"])
        self.assertIn("PLAN003", {f["id"] for f in g["findings"]})

    def test_self_cycle(self):
        self.assertTrue(build_graph({"steps": [{"id": "a", "depends_on": ["a"]}]})["cyclic"])

    def test_order_violation(self):
        g = build_graph({"steps": [{"id": "b", "depends_on": ["a"]}, {"id": "a"}]})
        self.assertIn("PLAN002", {f["id"] for f in g["findings"]})
        self.assertEqual(g["topological_order"], ["a", "b"])

    def test_artifact_needs_ancestor(self):
        g = build_graph({"steps": [{"id": "a", "produces": ["backup"]}, {"id": "b", "requires": ["backup"]}]})
        self.assertIn("PLAN004", {f["id"] for f in g["findings"]})

    def test_transitive_artifact(self):
        g = build_graph({"steps": [{"id": "a", "produces": ["backup"]}, {"id": "b", "depends_on": ["a"]}, {"id": "c", "depends_on": ["b"], "requires": ["backup"]}]})
        self.assertFalse(g["findings"])

    def test_duplicate_ids_rejected(self):
        with self.assertRaises(ValueError):
            normalize({"steps": [{"id": "a"}, {"id": "a"}]})

    def test_malformed_inputs(self):
        for p in ({"steps": "wrong"}, {"inputs": [3]}, {"steps": [{"id": "x", "paths": "bad"}]}, {"steps": [{"id": "x", "rollback": "yes"}]}, {"acceptance": "bad"}, []):
            with self.subTest(p=p), self.assertRaises(ValueError):
                normalize(p)

    def test_text_sequential(self):
        g = build_graph("First step\nSecond step")
        self.assertEqual(g["edges"], [{"from": "1", "to": "2"}])

    def test_maximum_chain_no_recursion_failure(self):
        p = {"steps": [{"id": str(i), "depends_on": [str(i+1)] if i < 499 else []} for i in range(500)]}
        graph = build_graph(p)
        self.assertFalse(graph["cyclic"])
        self.assertEqual(len(graph["topological_order"]), 500)

    def test_step_limit(self):
        with self.assertRaises(ValueError):
            normalize({"steps": [{"id": str(i)} for i in range(501)]})


if __name__ == "__main__":
    unittest.main()
