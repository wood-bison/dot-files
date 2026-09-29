# Zed setup

The root [README](../../README.md) owns the installation instructions.
`zed/settings.json` and `zed/keymap.json` are portable defaults installed as copies.
`~/.config/zed/settings.json` is the active machine file, not a repository symlink.

Default: Fluent Glass Light/Dark and Fluent Glass Light/Dark Icons in system mode.
Cameo Light/Dark remain in the theme selector (Zed → Settings → Select Theme).
The Fluent icon extension is generated from licensed source glyphs.

User edits survive repeated installs. `~/.config/dotfiles/zed.local.json` holds
overrides reapplied when replacing configs. SDKMAN Java paths are detected locally.

See [the family README](../themes/fluent-glass/README.md) for outputs and visual
verification boundaries.
