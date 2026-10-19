"""Pre-release regressions: real boundaries rather than implementation snapshots."""
import copy
from datetime import datetime, timedelta
import json
import os
from pathlib import Path
import subprocess
import sys
import io
import tarfile
import tempfile
import unittest
from unittest.mock import patch

from agent_failure_forecast.predictor import evaluate, predict, timestamp
from agent_failure_forecast.scanner import git_state
from agent_failure_forecast.report import render
from agent_failure_forecast.safety import write_report, load_json
import test_cli_schema as cli_tests
from test_history import synthetic_history


def provenance_history():
    rows = synthetic_history()
    for r in rows:
        r["plan_recorded_at"] = r["started_at"]
        r["outcome_recorded_at"] = r["finished_at"]
    return rows


class OutputBoundaryTests(unittest.TestCase):
    setUp = cli_tests.CliTests.setUp
    run_cli = cli_tests.CliTests.run_cli
    def test_force_does_not_modify_hardlink_target(self):
        victim = self.root / "unrelated.txt"
        victim.write_text("preserve", encoding="utf-8")
        destination = self.root / "output.json"
        os.link(victim, destination)
        result = self.run_cli("scan", "--plan", self.input, "--root", self.root, "--output", destination, "--force")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(victim.read_text(), "preserve")
        self.assertIn("findings", json.loads(destination.read_text()))

    def test_failed_replacement_preserves_existing_report(self):
        destination = self.root / "report.json"
        destination.write_text("original", encoding="utf-8")
        with patch("agent_failure_forecast.safety.os.replace", side_effect=PermissionError("fixture")):
            with self.assertRaises(PermissionError):
                write_report(destination, "replacement", force=True)
        self.assertEqual(destination.read_text(), "original")
        self.assertFalse(list(self.root.glob(".forecast-*.tmp")))

    def test_force_symlink_target_preserved(self):
        victim = self.root / "victim"
        victim.write_text("preserve", encoding="utf-8")
        destination = self.root / "linked"
        try:
            destination.symlink_to(victim)
        except OSError:
            self.skipTest("OS cannot create symlinks")
        with self.assertRaises(ValueError):
            write_report(destination, "replacement", force=True)
        self.assertEqual(victim.read_text(), "preserve")

    def test_authorization_header_redacted(self):
        text = render({"text": "Authorization: Bearer fictional-sensitive-value"})
        self.assertNotIn("fictional-sensitive-value", text)

    def test_prefixed_environment_assignment_redacted(self):
        text = render({"text": "AWS_SECRET_ACCESS_KEY=fictional-sensitive-value"})
        self.assertNotIn("fictional-sensitive-value", text)

    def test_duplicate_json_keys_rejected(self):
        self.input.write_text('{"goal":"one","goal":"two"}', encoding="utf-8")
        with self.assertRaises(ValueError):
            load_json(self.input)

    def test_nonfinite_json_rejected(self):
        self.input.write_text('{"value":NaN}', encoding="utf-8")
        with self.assertRaises(ValueError):
            load_json(self.input)

    def test_quoted_json_secret_inside_text_redacted(self):
        text = render({"text": 'embedded {"api_key": "fictional-sensitive-value"}'})
        self.assertNotIn("fictional-sensitive-value", text)


class ModelReviewTests(unittest.TestCase):
    def test_holdout_labels_do_not_select_model(self):
        rows = provenance_history()
        before, weights_before = evaluate(rows)
        changed = copy.deepcopy(rows)
        for r in changed[-36:]:
            r["failed"] = not r["failed"]
        after, weights_after = evaluate(changed)
        self.assertEqual(before["eligible"], after["eligible"])
        self.assertEqual(weights_before, weights_after)
        self.assertEqual(before["model_version"], after["model_version"])

    def test_delayed_outcome_excluded_at_as_of(self):
        rows = provenance_history()
        for r in rows:
            r["outcome_recorded_at"] = "2027-01-01T00:00:00Z"
        result = predict({}, rows, "2026-01-01T00:00:00Z")
        self.assertEqual(result["excluded_future_records"], 240)
        self.assertIsNone(result["failure_probability"])

    def test_post_execution_plan_snapshot_rejected(self):
        rows = provenance_history()
        rows[0]["plan_recorded_at"] = rows[0]["finished_at"]
        with self.assertRaises(ValueError):
            evaluate(rows)

    def test_missing_provenance_withholds_probability(self):
        rows = provenance_history()
        for r in rows:
            r.pop("plan_recorded_at")
        metrics, model = evaluate(rows)
        self.assertFalse(metrics["eligible"])
        self.assertIsNone(model)
        self.assertEqual(metrics["reason"], "unverified_history_provenance")

    def test_known_groups_cannot_span_blocks(self):
        rows = provenance_history()
        for r in rows:
            r["group_id"] = "same-project-incident"
        self.assertEqual(evaluate(rows)[0]["reason"], "group_overlap_between_blocks")

    def test_incomplete_group_ids_withhold_probability(self):
        rows = provenance_history()
        rows[0]["group_id"] = "annotated-only-one-row"
        self.assertEqual(evaluate(rows)[0]["reason"], "incomplete_group_metadata")

    def test_single_class_test_labels_do_not_change_eligibility(self):
        rows = provenance_history()
        before, model_before = evaluate(rows)
        for r in rows[-36:]:
            r["failed"] = False
        after, model_after = evaluate(rows)
        self.assertEqual(before["eligible"], after["eligible"])
        self.assertEqual(model_before, model_after)

    def test_delayed_training_outcome_blocks_fit(self):
        rows = provenance_history()
        rows[0]["outcome_recorded_at"] = rows[170]["started_at"]
        self.assertEqual(evaluate(rows)[0]["reason"], "overlapping_time_blocks")

    def test_outcome_before_completion_rejected(self):
        rows = provenance_history()
        rows[0]["outcome_recorded_at"] = rows[0]["started_at"]
        with self.assertRaises(ValueError):
            evaluate(rows)

    def test_overflow_timestamp_is_validation_error(self):
        with self.assertRaises(ValueError):
            timestamp("9999-12-31T23:59:59-23:00")


class GitReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.addCleanup(self.temp.cleanup)

    def git(self, *args):
        return subprocess.run(["git", "-c", "safe.directory="+str(self.root), "-c", "user.name=Test", "-c", "user.email=test@example.invalid", "-c", "core.hooksPath="+os.devnull, "-C", str(self.root), *args], check=True, capture_output=True)

    def test_git_status_must_not_run_clean_filter(self):
        self.git("init")
        (self.root/".gitattributes").write_text("data.txt filter=probe\n", encoding="utf-8")
        data = self.root/"data.txt"
        data.write_text("alpha\n", encoding="utf-8")
        self.git("add", ".")
        self.git("commit", "-m", "fixture")
        marker = self.root/"filter-executed"
        script = self.root/"filter.py"
        script.write_text("from pathlib import Path\nimport sys\nPath("+repr(str(marker))+").write_text('executed')\nsys.stdout.buffer.write(sys.stdin.buffer.read())\n", encoding="utf-8")
        self.git("config", "filter.probe.clean", '"'+sys.executable.replace("\\", "/")+'" "'+str(script).replace("\\", "/")+'"')
        data.write_text("bravo\n", encoding="utf-8")
        os.utime(data, (data.stat().st_atime, data.stat().st_mtime+10))
        status = git_state(self.root)
        self.assertFalse(marker.exists(), "git status executed the repository's filter")
        self.assertNotEqual(status["status"], "clean")

    def test_cwd_git_binary_not_considered_trusted(self):
        # Search must explicitly avoid PATH's relative/current-directory entries.
        from agent_failure_forecast.scanner import trusted_git
        with patch.dict(os.environ, {"PATH": "."}):
            self.assertIsNone(trusted_git(self.root))

    def test_git_metadata_walk_error_fails_closed(self):
        self.git("init")
        with patch("agent_failure_forecast.scanner.os.walk", side_effect=PermissionError("denied")), patch("agent_failure_forecast.scanner.subprocess.run") as process:
            self.assertEqual(git_state(self.root)["status"], "unsafe_or_unreadable_git_metadata")
            process.assert_not_called()

    def test_git_lookup_ignores_link_cycles(self):
        from agent_failure_forecast.scanner import trusted_git
        one, two = self.root/"one", self.root/"two"
        try:
            one.symlink_to(two, target_is_directory=True)
            two.symlink_to(one, target_is_directory=True)
        except OSError:
            self.skipTest("OS cannot create directory symlinks")
        with patch.dict(os.environ, {"PATH": str(one)}):
            self.assertIsNone(trusted_git(self.root))


class DistributionBoundaryTests(unittest.TestCase):
    def test_source_extractor_rejects_traversal(self):
        from scripts.verify_distribution import extract_source
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = root/"bad.tar.gz"
            with tarfile.open(archive, "w:gz") as stream:
                member = tarfile.TarInfo("../escaped")
                member.size = 1
                stream.addfile(member, io.BytesIO(b"x"))
            with self.assertRaises(ValueError):
                extract_source(archive, root/"extract")
            self.assertFalse((root/"escaped").exists())

    def test_source_extractor_rejects_links(self):
        from scripts.verify_distribution import extract_source
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = root/"bad.tar.gz"
            with tarfile.open(archive, "w:gz") as stream:
                member = tarfile.TarInfo("project/link")
                member.type = tarfile.SYMTYPE
                member.linkname = "../../outside"
                stream.addfile(member)
            with self.assertRaises(ValueError):
                extract_source(archive, root/"extract")
