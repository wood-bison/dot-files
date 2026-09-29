#!/usr/bin/env python3
"""Install files with backups and preserve post-install user edits. No package installs."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile
from datetime import datetime
import uuid

ROOT = Path(__file__).resolve().parent.parent


def digest(data):
    return hashlib.sha256(data).hexdigest()


def merge(base, override):
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            merge(base[key], value)
        else:
            base[key] = value
    return base


class Installer:
    def __init__(self, root, home, replace=False):
        self.root, self.home, self.replace = root.resolve(), home.resolve(), replace
        self.state_dir = self.home / ".local/state/dotfiles"
        self.manifest = self.state_dir / "installed.json"
        self.entries = json.loads(self.manifest.read_text()) if self.manifest.exists() else {}
        run = datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:6]
        self.backup_dir = self.state_dir / "backups" / run
        self.preserved = []

    def backup(self, target):
        if not target.exists() and not target.is_symlink():
            return
        dest = self.backup_dir / target.relative_to(self.home)
        dest.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        if target.is_dir():
            shutil.copytree(target, dest, symlinks=True)
        elif target.exists():
            # Materialize links: backup stays useful after a checkout changes.
            shutil.copy2(target, dest)
            dest.chmod(0o600)
        else:
            dest.symlink_to(os.readlink(target))

    def atomic_write(self, target, data):
        if isinstance(data, str):
            data = data.encode()
        target.parent.mkdir(parents=True, exist_ok=True)
        fd, name = tempfile.mkstemp(prefix=".dotfiles-", dir=target.parent)
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(data)
            os.replace(name, target)
        finally:
            if os.path.lexists(name):
                os.unlink(name)

    def write(self, relative, data):
        if isinstance(data, str):
            data = data.encode()
        target = self.home / relative
        previous = self.entries.get(relative)
        if target.exists() and target.is_file() and not target.is_symlink():
            current = target.read_bytes()
            if current == data:
                self.entries[relative] = {"sha256": digest(data)}
                return
            if previous and previous.get("sha256") != digest(current) and not self.replace:
                self.preserved.append(relative)
                print("Preserved user edits:", relative)
                return
        elif previous and target.is_symlink() and not self.replace:
            self.preserved.append(relative)
            print("Preserved user symlink:", relative)
            return
        if target.is_dir():
            raise RuntimeError(f"Expected a file, found directory: {target}")
        self.backup(target)
        self.atomic_write(target, data)
        self.entries[relative] = {"sha256": digest(data)}
        print("Installed:", relative)

    def link(self, relative, source):
        if not source.exists():
            raise RuntimeError(f"Missing generated asset: {source}")
        target = self.home / relative
        if target.is_symlink() and target.resolve() == source.resolve():
            self.entries[relative] = {"link": str(source)}
            return
        previous = self.entries.get(relative)
        if previous and (target.exists() or target.is_symlink()) and not self.replace:
            if not target.is_symlink() or os.readlink(target) != previous.get("link"):
                self.preserved.append(relative)
                print("Preserved user asset:", relative)
                return
        self.backup(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.is_dir() and not target.is_symlink():
            shutil.rmtree(target)  # A complete copy was saved above.
        elif target.exists() or target.is_symlink():
            target.unlink()
        target.symlink_to(source)
        self.entries[relative] = {"link": str(source)}
        print("Linked:", relative)

    def git(self):
        target = self.home / ".gitconfig"
        before = target.read_bytes() if target.exists() else b""
        # Work on a temporary copy so git never edits a repository via a symlink.
        self.state_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        fd, name = tempfile.mkstemp(dir=self.state_dir)
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(before)
            def config(*args, check=True):
                return subprocess.run(["git", "config", "--file", name, *args],
                                      text=True, capture_output=True, check=check)
            config("--list")
            values = config("--get-all", "include.path", check=False).stdout.splitlines()
            # Remove this installer's former include only, not unrelated includes.
            for value in values:
                expanded = value.replace("~/", str(self.home) + "/", 1) if value.startswith("~/") else value
                if Path(expanded).resolve() == (self.root / "git/.gitconfig").resolve():
                    # Preserve the old install's behavioral choices on this Mac only.
                    if Path(expanded).exists():
                        for key in ("pull.rebase", "push.autoSetupRemote", "alias.undo"):
                            if config("--get", key, check=False).returncode != 0:
                                old = subprocess.run(["git", "config", "--file", expanded, "--get", key],
                                                     text=True, capture_output=True)
                                if old.returncode == 0:
                                    config(key, old.stdout.strip())
                    config("--fixed-value", "--unset-all", "include.path", value)
            include = str(self.root / "git/config")
            values = config("--get-all", "include.path", check=False).stdout.splitlines()
            if include not in values:
                config("--add", "include.path", include)
            if config("--get", "core.excludesFile", check=False).returncode != 0:
                config("core.excludesFile", str(self.home / ".config/git/ignore"))
            after = Path(name).read_bytes()
            if after != before or target.is_symlink():
                self.backup(target)
                self.atomic_write(target, after)
                print("Included Git settings; existing identity and credentials preserved.")
        finally:
            Path(name).unlink(missing_ok=True)

    def retire(self, activate):
        # Retire only paths owned by this checkout. User app data is untouched.
        retired = {
            ".config/ghostty/profiles": "ghostty/profiles",
            ".config/ghostty/shaders/cameo": "ghostty/shaders/cameo",
            ".config/ghostty/themes/cameo-light": "ghostty/themes/cameo-light",
            ".config/ghostty/themes/cameo-dark": "ghostty/themes/cameo-dark",
            ".config/ghostty/themes/fluent-glass-special-light":
                "design-system/themes/fluent-glass-special/generated/terminals/fluent-glass-special-light",
            ".config/ghostty/themes/fluent-glass-special-dark":
                "design-system/themes/fluent-glass-special/generated/terminals/fluent-glass-special-dark",
            ".config/zed/themes/fluent-glass-special.json":
                "design-system/themes/fluent-glass-special/generated/fluent-glass-special.json",
            "Library/Application Support/Zed/extensions/installed/cameo-icons":
                "design-system/targets/zed-icons",
            "Library/Application Support/Zed/extensions/installed/fluent-glass-special-icons":
                "design-system/themes/fluent-glass-special/generated/fluent-glass-special-icons",
        }
        for relative, old in retired.items():
            if "ghostty" in relative and any(p in self.preserved for p in (".zshrc", ".config/ghostty/config")):
                continue
            if "zed" in relative.lower() and ".config/zed/settings.json" in self.preserved:
                continue
            target = self.home / relative
            if target.is_symlink() and target.resolve() == (self.root / old).resolve():
                self.backup(target)
                target.unlink()
                print("Retired old managed link:", relative)
        # Optional apps keep ordinary config files instead of dangling links.
        for relative in (".config/atuin/config.toml", ".config/lazygit/config.yml",
                         ".config/yazi/theme.toml"):
            target = self.home / relative
            if target.is_symlink() and target.exists() and target.resolve().is_relative_to(self.root):
                data = target.read_bytes()
                self.backup(target)
                self.atomic_write(target, data)
        for name in ("cameo.yazi", "cameo-light.yazi"):
            target = self.home / ".config/yazi/flavors" / name
            if target.is_symlink() and target.exists() and target.resolve().is_relative_to(self.root):
                self.backup(target)
                source = target.resolve()
                target.unlink()
                shutil.copytree(source, target)
        plist = self.home / "Library/LaunchAgents/com.szhechko.theme-auto.plist"
        if (not any(p in self.preserved for p in (".zshrc", ".config/ghostty/config"))
                and plist.exists() and str(self.root / "scripts/theme-auto.sh") in plist.read_text()):
            if activate:
                service = f"gui/{os.getuid()}/com.szhechko.theme-auto"
                if subprocess.run(["launchctl", "print", service], capture_output=True).returncode == 0:
                    subprocess.run(["launchctl", "bootout", service], check=True, capture_output=True)
            self.backup(plist)
            plist.unlink()
            print("Retired legacy theme-auto LaunchAgent.")

    def install(self, activate=False):
        fluent = self.root / "design-system/themes/fluent-glass/generated"
        required = [
            "zsh/.zshrc", "zsh/.zprofile", "zsh/.zshenv", "ghostty/config",
            "zed/settings.json", "zed/keymap.json", "git/config", "git/ignore",
            "ghostty/themes/fluent-glass-light", "ghostty/themes/fluent-glass-dark",
            "design-system/targets/zed/cameo.json",
            "design-system/themes/fluent-glass/generated/fluent-glass.json",
            "design-system/themes/fluent-glass/generated/fluent-glass-icons/extension.toml",
        ]
        for source in required:
            if not (self.root / source).is_file():
                raise RuntimeError(f"Missing source: {source}; run the full installer.")
        # Validate local input before replacing any configuration or asset.
        git_config = self.home / ".gitconfig"
        if git_config.is_symlink() and not git_config.exists():
            raise RuntimeError("Dangling ~/.gitconfig symlink: restore its contents from a backup before installing.")
        if git_config.exists():
            subprocess.run(["git", "config", "--file", str(git_config), "--list"],
                           check=True, capture_output=True)
            includes = subprocess.run(
                ["git", "config", "--file", str(git_config), "--get-all", "include.path"],
                text=True, capture_output=True)
            for value in includes.stdout.splitlines():
                expanded = value.replace("~/", str(self.home) + "/", 1) if value.startswith("~/") else value
                if Path(expanded).resolve() == (self.root / "git/.gitconfig").resolve() and not Path(expanded).exists():
                    raise RuntimeError("Legacy Git include is missing: restore git/.gitconfig from a backup before installing.")
        settings = json.loads((self.root / "zed/settings.json").read_text())
        java = self.home / ".sdkman/candidates/java/current"
        if (java / "bin/java").exists():
            settings["lsp"] = {"jdtls": {"settings": {"java_home": str(java)}}}
        overrides = self.home / ".config/dotfiles/zed.local.json"
        if overrides.exists():
            override = json.loads(overrides.read_text())
            if not isinstance(override, dict):
                raise RuntimeError("zed.local.json must be a JSON object.")
            merge(settings, override)
        if not isinstance(settings, dict):
            raise RuntimeError("Zed settings must be a JSON object.")
        for mode in ("light", "dark"):
            self.link(f".config/ghostty/themes/fluent-glass-{mode}",
                      self.root / f"ghostty/themes/fluent-glass-{mode}")
        self.link(".config/zed/themes/fluent-glass.json", fluent / "fluent-glass.json")
        self.link(".config/zed/themes/cameo.json", self.root / "design-system/targets/zed/cameo.json")
        self.link("Library/Application Support/Zed/extensions/installed/fluent-glass-icons",
                  fluent / "fluent-glass-icons")
        for source, target in {
            "zsh/.zprofile": ".zprofile", "zsh/.zshenv": ".zshenv",
            "ghostty/config": ".config/ghostty/config",
            "zed/keymap.json": ".config/zed/keymap.json",
            "git/ignore": ".config/git/ignore",
        }.items():
            self.write(target, (self.root / source).read_bytes())
        shell = "export DOTFILES_ROOT=" + shlex.quote(str(self.root)) + "\n"
        self.write(".zshrc", shell + (self.root / "zsh/.zshrc").read_text())
        self.write(".config/zed/settings.json", json.dumps(settings, indent=2) + "\n")
        self.git()
        self.retire(activate)
        self.atomic_write(self.manifest, json.dumps(self.entries, indent=2) + "\n")
        if self.backup_dir.exists():
            print("Backups:", self.backup_dir)
        if self.preserved:
            print("To deliberately replace preserved files: bash install.sh --config-only --replace-configs")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--replace-configs", action="store_true")
    parser.add_argument("--activate", action="store_true", help="Unload this user's legacy LaunchAgent.")
    args = parser.parse_args()
    Installer(ROOT, Path.home(), args.replace_configs).install(args.activate)
