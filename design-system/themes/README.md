# Theme families

- **Fluent Glass** is the default desktop family: [sources and outputs](fluent-glass/README.md).
- **Cameo** is an optional Zed theme, built from `../tokens/cameo-*.toml`.
  Its licensed SVG glyph library is also an input to Fluent's icon adapter.

Each family owns its token source. Building generates assets; the root installer
connects them to applications. Fluent's web tokens keep their existing paths/names.
