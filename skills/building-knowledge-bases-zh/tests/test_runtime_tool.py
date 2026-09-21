import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parents[1]
SCRIPT = SKILL_DIR / "scripts" / "runtime_tool.py"


class RuntimeToolTests(unittest.TestCase):
    def run_tool(self, *args: str, expect: int = 0) -> subprocess.CompletedProcess[str]:
        result = subprocess.run(
            [sys.executable, str(SCRIPT), *args],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(
            result.returncode,
            expect,
            msg=f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}",
        )
        return result

    def create_project(self, root: Path) -> Path:
        project = root / "knowledge-system"
        section = project / "evidence"
        section.mkdir(parents=True)
        (project / "AGENTS.md").write_text(
            "# Rules\n\nRead [the root index](index.md).\n", encoding="utf-8"
        )
        (project / "index.md").write_text(
            "# Index\n\n- [Evidence](evidence/index.md)\n", encoding="utf-8"
        )
        (section / "AGENTS.md").write_text(
            "# Evidence rules\n\nMaintain sources and relationships.\n", encoding="utf-8"
        )
        (section / "index.md").write_text("# Evidence\n", encoding="utf-8")
        (section / "source.md").write_text("# Source\n", encoding="utf-8")
        return project

    def write_validation(self, project: Path, *, result: str = "passed") -> Path:
        path = project / "first-validation.json"
        stages = {
            "design_traceability": {
                "result": "passed",
                "summary": "explicit knowledge objects mapped to the design",
                "evidence": ["evidence/source.md"],
                "confirmed_by_user": True,
                "knowledge_objects": [
                    {
                        "name": "source evidence",
                        "source": "representative user task",
                        "management": "section",
                        "target": "evidence",
                    }
                ],
                "confirmed_sections": ["evidence"],
            }
        }
        for name in (
            "retrieval",
            "durable_increment",
            "temporary_input",
            "change_impact",
            "linked_update",
            "consistency",
        ):
            stages[name] = {
                "result": "passed",
                "summary": f"{name} verified",
                "evidence": ["evidence/source.md"],
            }
        path.write_text(
            json.dumps({"result": result, "stages": stages}, ensure_ascii=False),
            encoding="utf-8",
        )
        return path

    def test_inventory_excludes_noise_sensitive_files_and_external_links(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "source"
            source.mkdir()
            (source / "notes.md").write_text("useful", encoding="utf-8")
            (source / ".env").write_text("SECRET=x", encoding="utf-8")
            cache = source / "node_modules"
            cache.mkdir()
            (cache / "package.js").write_text("noise", encoding="utf-8")
            external = root / "outside.md"
            external.write_text("outside", encoding="utf-8")
            (source / "outside-link.md").symlink_to(external)

            result = self.run_tool("inventory", "--source", str(source))
            payload = json.loads(result.stdout)
            entries = {item["path"]: item for item in payload["entries"]}

            self.assertEqual(entries["notes.md"]["classification"], "candidate")
            self.assertEqual(entries[".env"]["classification"], "sensitive")
            self.assertEqual(entries["node_modules"]["classification"], "noise")
            self.assertEqual(entries["outside-link.md"]["classification"], "external-link")

    def test_complete_manifest_requires_all_first_validation_stages(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            project = self.create_project(Path(temp_dir))
            validation = project / "first-validation.json"
            validation.write_text(
                json.dumps(
                    {
                        "result": "passed",
                        "stages": {
                            "retrieval": {
                                "result": "passed",
                                "summary": "retrieval verified",
                                "evidence": ["evidence/source.md"],
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )

            result = self.run_tool(
                "manifest",
                "--project",
                str(project),
                "--section",
                "evidence",
                "--validation-file",
                "first-validation.json",
                "--status",
                "complete",
                expect=2,
            )

            self.assertIn("missing validation stages", result.stderr)
            self.assertFalse((project / ".knowledge-system.json").exists())

    def test_complete_manifest_requires_design_traceability(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            project = self.create_project(Path(temp_dir))
            validation = self.write_validation(project)
            payload = json.loads(validation.read_text(encoding="utf-8"))
            del payload["stages"]["design_traceability"]
            validation.write_text(json.dumps(payload), encoding="utf-8")

            result = self.run_tool(
                "manifest",
                "--project",
                str(project),
                "--section",
                "evidence",
                "--validation-file",
                "first-validation.json",
                "--status",
                "complete",
                expect=2,
            )

            self.assertIn("design_traceability", result.stderr)
            self.assertFalse((project / ".knowledge-system.json").exists())

    def test_complete_manifest_requires_confirmed_sections(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            project = self.create_project(Path(temp_dir))
            validation = self.write_validation(project)
            payload = json.loads(validation.read_text(encoding="utf-8"))
            del payload["stages"]["design_traceability"]["confirmed_sections"]
            validation.write_text(json.dumps(payload), encoding="utf-8")

            result = self.run_tool(
                "manifest",
                "--project",
                str(project),
                "--section",
                "evidence",
                "--validation-file",
                "first-validation.json",
                "--status",
                "complete",
                expect=2,
            )

            self.assertIn("confirmed_sections", result.stderr)
            self.assertFalse((project / ".knowledge-system.json").exists())

    def test_complete_manifest_rejects_actual_root_structure_drift(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            project = self.create_project(Path(temp_dir))
            legacy = project / "legacy"
            legacy.mkdir()
            (legacy / "AGENTS.md").write_text("# Legacy rules\n", encoding="utf-8")
            (legacy / "index.md").write_text("# Legacy\n", encoding="utf-8")
            self.write_validation(project)

            result = self.run_tool(
                "manifest",
                "--project",
                str(project),
                "--section",
                "evidence",
                "--validation-file",
                "first-validation.json",
                "--status",
                "complete",
                expect=2,
            )

            self.assertIn("unexpected root sections", result.stderr)
            self.assertFalse((project / ".knowledge-system.json").exists())

    def test_design_traceability_requires_mapped_knowledge_objects(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            project = self.create_project(Path(temp_dir))
            validation = self.write_validation(project)
            payload = json.loads(validation.read_text(encoding="utf-8"))
            payload["stages"]["design_traceability"] = {
                "result": "passed",
                "summary": "structure reviewed",
                "evidence": ["evidence/source.md"],
                "knowledge_objects": [],
            }
            validation.write_text(json.dumps(payload), encoding="utf-8")

            result = self.run_tool(
                "manifest",
                "--project",
                str(project),
                "--section",
                "evidence",
                "--validation-file",
                "first-validation.json",
                "--status",
                "complete",
                expect=2,
            )

            self.assertIn("knowledge_objects", result.stderr)

    def test_non_section_mapping_requires_rationale(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            project = self.create_project(Path(temp_dir))
            validation = self.write_validation(project)
            payload = json.loads(validation.read_text(encoding="utf-8"))
            mapped = payload["stages"]["design_traceability"]["knowledge_objects"][0]
            mapped["management"] = "index"
            mapped["target"] = "cross-project-index.md"
            validation.write_text(json.dumps(payload), encoding="utf-8")

            result = self.run_tool(
                "manifest",
                "--project",
                str(project),
                "--section",
                "evidence",
                "--validation-file",
                "first-validation.json",
                "--status",
                "complete",
                expect=2,
            )

            self.assertIn("needs rationale", result.stderr)

    def test_manifest_and_diagnose_complete_knowledge_system(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            project = self.create_project(Path(temp_dir))
            self.write_validation(project)

            self.run_tool(
                "manifest",
                "--project",
                str(project),
                "--section",
                "evidence",
                "--generated-file",
                "evidence/source.md",
                "--validation-file",
                "first-validation.json",
                "--status",
                "complete",
            )
            manifest = json.loads((project / ".knowledge-system.json").read_text())

            self.assertEqual(manifest["schema_version"], 2)
            self.assertEqual(manifest["status"], "complete")
            self.assertEqual(manifest["sections"], ["evidence"])
            self.assertIn("AGENTS.md", manifest["rule_fingerprints"])
            self.assertIn("evidence/AGENTS.md", manifest["rule_fingerprints"])

            result = self.run_tool("diagnose", "--project", str(project))
            report = json.loads(result.stdout)
            self.assertEqual(report["errors"], [])
            self.assertEqual(report["status"], "complete")

    def test_diagnose_reports_broken_markdown_link(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            project = self.create_project(Path(temp_dir))
            self.write_validation(project)
            (project / "index.md").write_text(
                "# Index\n\n[Missing](missing.md)\n", encoding="utf-8"
            )
            self.run_tool(
                "manifest",
                "--project",
                str(project),
                "--section",
                "evidence",
                "--validation-file",
                "first-validation.json",
                "--status",
                "complete",
            )

            result = self.run_tool(
                "diagnose", "--project", str(project), expect=1
            )
            report = json.loads(result.stdout)
            self.assertTrue(
                any("broken Markdown link" in error for error in report["errors"])
            )

    def test_diagnose_warns_when_generated_rules_were_edited(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            project = self.create_project(Path(temp_dir))
            self.write_validation(project)
            self.run_tool(
                "manifest",
                "--project",
                str(project),
                "--section",
                "evidence",
                "--validation-file",
                "first-validation.json",
                "--status",
                "complete",
            )
            (project / "AGENTS.md").write_text(
                "# User-maintained rules\n", encoding="utf-8"
            )

            result = self.run_tool("diagnose", "--project", str(project))
            report = json.loads(result.stdout)
            self.assertTrue(
                any("rule file changed" in warning for warning in report["warnings"])
            )


if __name__ == "__main__":
    unittest.main()
