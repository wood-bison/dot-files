# Theme sources

**Fluent Glass** is the active desktop family. Its stable source is
[themes/fluent-glass/tokens.json](themes/fluent-glass/tokens.json).
Existing web token names and portable CSS remain compatible with consuming products.

```sh
python3 design-system/themes/fluent-glass/build.py
```

This validates both palettes and generates CSS, Zed themes, Ghostty themes and
a local Fluent icon extension. Installation is separate: `bash install.sh`.

Cameo remains an optional Zed theme. Sources: `tokens/cameo-*.toml` and
`tokens/zed-map.toml`; output: `targets/zed/cameo.json`.
The licensed glyph library `targets/zed-icons` is also an input to Fluent's
icon adapter. Keep its upstream license notices.

```sh
python3 design-system/build.py --zed
python3 design-system/build.py --web
```

The Cameo builder no longer emits shell, Ghostty, Git, Yazi or lazygit files.
`--web` retains the Cameo CSS/JSON compatibility exports.
`build_zed_icons.py` maintains the source glyph library if its mapping changes.

Previous desktop experiments and screenshots are available in Git history.
Current installation instructions live only in the root README.
