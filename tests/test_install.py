"""Regression tests for the configurable, non-activating dotfiles installer."""
import importlib.util
import json
from pathlib import Path
import shlex
import tempfile
import unittest


REPO = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "dotfiles_install", REPO / "scripts" / "install.py"
)
install_module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(install_module)
Installer = install_module.Installer


class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="dotfiles installer ")
        self.addCleanup(self.temp.cleanup)
        base = Path(self.temp.name)
        self.root = base / "checkout with spaces"
        self.home = base / "home for another person"
        self.home.mkdir()
        self._make_checkout()

    def source(self, relative, content="source\n"):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        return path

    def _make_checkout(self):
        self.root.mkdir()
        sources = {
            "zsh/.zshrc": "# managed zshrc\n",
            "zsh/.zprofile": "# managed zprofile\n",
            "zsh/.zshenv": "# managed zshenv\n",
            "ghostty/config": "font-size = 14\n",
            "zed/settings.json": json.dumps({"theme": {"mode": "light"}, "ui_font_size": 18}),
            "zed/keymap.json": "[]\n",
            "git/config": "[init]\n  defaultBranch = main\n",
            "git/ignore": "*.swp\n",
            "ghostty/themes/fluent-glass-light": "light theme\n",
            "ghostty/themes/fluent-glass-dark": "dark theme\n",
            "design-system/targets/zed/cameo.json": '{"name":"Cameo"}\n',
            "design-system/themes/fluent-glass/generated/fluent-glass.json": '{"name":"Fluent Glass"}\n',
            "design-system/themes/fluent-glass/generated/fluent-glass-icons/extension.toml":
                'id = "fluent-glass-icons"\n',
        }
        for relative, content in sources.items():
            self.source(relative, content)

    def install(self, replace=False):
        Installer(self.root, self.home, replace=replace).install(activate=False)

    def backup_files(self, relative):
        backup_root = self.home / ".local/state/dotfiles/backups"
        return list(backup_root.glob(f"*/{relative}")) if backup_root.exists() else []

    def test_fresh_install_preserves_git_identity_credentials_and_other_includes(self):
        original = (
            '[user]\n name = Existing User\n email = user@example.test\n'
            '[credential "https://example.test"]\n helper = manager\n'
            '[include]\n path = /some/other/config\n'
        )
        (self.home / ".gitconfig").write_text(original)

        self.install()

        config = self.home / ".gitconfig"
        self.assertFalse(config.is_symlink())
        self.assertEqual(
            "Existing User",
            install_module.subprocess.run(
                ["git", "config", "--file", str(config), "--get", "user.name"],
                text=True, capture_output=True, check=True,
            ).stdout.strip(),
        )
        self.assertEqual(
            "user@example.test",
            install_module.subprocess.run(
                ["git", "config", "--file", str(config), "--get", "user.email"],
                text=True, capture_output=True, check=True,
            ).stdout.strip(),
        )
        self.assertEqual(
            ["manager"],
            install_module.subprocess.run(
                ["git", "config", "--file", str(config), "--get-all",
                 'credential.https://example.test.helper'],
                text=True, capture_output=True, check=True,
            ).stdout.splitlines(),
        )
        includes = install_module.subprocess.run(
            ["git", "config", "--file", str(config), "--get-all", "include.path"],
            text=True, capture_output=True, check=True,
        ).stdout.splitlines()
        self.assertIn("/some/other/config", includes)
        self.assertEqual(1, includes.count(str(self.root.resolve() / "git/config")))
        self.assertNotIn("Sergey Zhechko", config.read_text())
        self.assertNotIn("nexxen.com", config.read_text())

    def test_repeated_install_is_idempotent_without_new_backups(self):
        self.install()
        config_before = (self.home / ".gitconfig").read_bytes()
        settings_before = (self.home / ".config/zed/settings.json").read_bytes()
        manifest_before = (self.home / ".local/state/dotfiles/installed.json").read_bytes()
        backups_before = sorted(
            path.relative_to(self.home / ".local/state/dotfiles/backups")
            for path in (self.home / ".local/state/dotfiles/backups").rglob("*")
        )

        self.install()

        self.assertEqual(config_before, (self.home / ".gitconfig").read_bytes())
        self.assertEqual(settings_before, (self.home / ".config/zed/settings.json").read_bytes())
        self.assertEqual(manifest_before, (self.home / ".local/state/dotfiles/installed.json").read_bytes())
        backups_after = sorted(
            path.relative_to(self.home / ".local/state/dotfiles/backups")
            for path in (self.home / ".local/state/dotfiles/backups").rglob("*")
        )
        self.assertEqual(backups_before, backups_after)
        config = install_module.subprocess.run(
            ["git", "config", "--file", str(self.home / ".gitconfig"), "--get-all", "include.path"],
            text=True, capture_output=True, check=True,
        ).stdout.splitlines()
        self.assertEqual(1, config.count(str(self.root.resolve() / "git/config")))

    def test_user_zed_settings_are_preserved_unless_replace_is_requested(self):
        self.install()
        settings_path = self.home / ".config/zed/settings.json"
        customized = json.loads(settings_path.read_text())
        customized["ui_font_size"] = 23
        customized["user_setting"] = "keep me"
        customized_bytes = (json.dumps(customized, indent=2) + "\n").encode()
        settings_path.write_bytes(customized_bytes)

        self.install()

        self.assertEqual(customized_bytes, settings_path.read_bytes())
        self.assertEqual([], self.backup_files(".config/zed/settings.json"))

        self.install(replace=True)

        self.assertEqual(18, json.loads(settings_path.read_text())["ui_font_size"])
        backups = self.backup_files(".config/zed/settings.json")
        self.assertTrue(backups)
        self.assertEqual(customized_bytes, backups[-1].read_bytes())

    def test_preexisting_destination_symlink_is_backed_up_by_content(self):
        external = self.home.parent / "external-theme-source"
        external.write_text("keep this target untouched\n")
        destination = self.home / ".config/ghostty/themes/fluent-glass-light"
        destination.parent.mkdir(parents=True)
        destination.symlink_to(external)

        self.install()

        self.assertEqual("keep this target untouched\n", external.read_text())
        self.assertTrue(destination.is_symlink())
        backups = self.backup_files(".config/ghostty/themes/fluent-glass-light")
        self.assertTrue(backups)
        self.assertTrue(all(not path.is_symlink() for path in backups))
        self.assertEqual("keep this target untouched\n", backups[-1].read_text())

    def test_paths_with_spaces_and_nonstandard_home_name(self):
        self.install()

        zshrc = (self.home / ".zshrc").read_text()
        self.assertIn(f"export DOTFILES_ROOT={shlex.quote(str(self.root.resolve()))}", zshrc)
        self.assertTrue((self.home / ".config/ghostty/themes/fluent-glass-light").is_symlink())
        self.assertEqual(
            str(self.root.resolve() / "git/config"),
            install_module.subprocess.run(
                ["git", "config", "--file", str(self.home / ".gitconfig"),
                 "--get", "include.path"],
                text=True, capture_output=True, check=True,
            ).stdout.strip(),
        )
        self.assertNotIn("/Users/sergeyzhechko", (self.home / ".gitconfig").read_text())

    def test_missing_required_source_fails_before_home_changes(self):
        (self.root / "zsh/.zshrc").unlink()
        before = sorted(
            (str(path.relative_to(self.home)), path.read_bytes() if path.is_file() else None)
            for path in self.home.rglob("*")
        )

        with self.assertRaisesRegex(RuntimeError, "Missing source:.*zsh/.zshrc"):
            self.install()

        after = sorted(
            (str(path.relative_to(self.home)), path.read_bytes() if path.is_file() else None)
            for path in self.home.rglob("*")
        )
        self.assertEqual(before, after)

    def test_dangling_gitconfig_fails_before_changes(self):
        target = self.home / ".gitconfig"
        target.symlink_to(self.root / "git/deleted-root")
        with self.assertRaisesRegex(RuntimeError, "Dangling"):
            self.install()
        self.assertTrue(target.is_symlink())
        self.assertFalse((self.home / ".config").exists())

    def test_invalid_local_settings_fail_before_changes(self):
        target = self.home / ".config/dotfiles/zed.local.json"
        target.parent.mkdir(parents=True)
        target.write_text("{broken")
        with self.assertRaises(json.JSONDecodeError):
            self.install()
        self.assertFalse((self.home / ".config/ghostty").exists())
        self.assertFalse((self.home / ".zshrc").exists())

    def test_missing_legacy_git_include_fails_before_changes(self):
        (self.home / ".gitconfig").write_text(
            '[include]\n path = "' + str(self.root / 'git/.gitconfig') + '"\n')
        with self.assertRaisesRegex(RuntimeError, "Legacy Git include is missing"):
            self.install()
        self.assertFalse((self.home / ".config").exists())

    def test_retire_only_owned_legacy_special_links(self):
        themes = self.home / ".config/ghostty/themes"
        themes.mkdir(parents=True)
        owned = themes / "fluent-glass-special-light"
        owned.symlink_to(self.root / "design-system/themes/fluent-glass-special/generated/terminals/fluent-glass-special-light")
        custom = themes / "fluent-glass-special-dark"
        custom.symlink_to(self.home / "personal-missing-theme")
        self.install()
        self.assertFalse(owned.is_symlink())
        self.assertTrue(custom.is_symlink())
        self.assertTrue(self.backup_files(".config/ghostty/themes/fluent-glass-special-light"))

    def test_local_zed_override_merges_and_sdkman_java_is_detected(self):
        java_home = self.home / ".sdkman/candidates/java/current"
        (java_home / "bin").mkdir(parents=True)
        (java_home / "bin/java").write_text("fake java executable\n")
        override_path = self.home / ".config/dotfiles/zed.local.json"
        override_path.parent.mkdir(parents=True)
        override_path.write_text(json.dumps({
            "ui_font_size": 21,
            "theme": {"mode": "dark"},
            "private_setting": True,
        }))

        self.install()

        settings = json.loads((self.home / ".config/zed/settings.json").read_text())
        self.assertEqual(21, settings["ui_font_size"])
        self.assertEqual({"mode": "dark"}, settings["theme"])
        self.assertTrue(settings["private_setting"])
        self.assertEqual(
            str(java_home.resolve()), settings["lsp"]["jdtls"]["settings"]["java_home"]
        )


if __name__ == "__main__":
    unittest.main()
