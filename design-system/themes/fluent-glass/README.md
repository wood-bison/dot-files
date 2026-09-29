# Fluent Glass

The default Light/Dark family for Zed, Ghostty and shell. Both native apps follow
macOS appearance. Portable web tokens remain independent of app configuration.

## Sources and build

- `tokens.json`: palettes, editor roles and portable web tokens.
- `zed.py`: Zed style/syntax mapping and contrast validation.
- `terminal.py`: Ghostty from the validated Zed terminal palette.
- `icons.py`: Fluent colors on the licensed Cameo SVG glyph library.
- `build.py`: validates Light/Dark, then generates all outputs.

```sh
python3 design-system/themes/fluent-glass/build.py
```

Outputs: `generated/fluent-glass.css`, `generated/fluent-glass.json`,
`generated/fluent-glass-icons/`, and `ghostty/themes/fluent-glass-{light,dark}`.
Icons are generated locally and ignored by Git. Python 3.11+ stdlib only.

Install with the root `install.sh`. The narrower `install-zed.sh` links only the
theme JSON without selecting it or replacing another file.

| Appearance | Theme | Icons |
| --- | --- | --- |
| Light | Fluent Glass Light | Fluent Glass Light Icons |
| Dark | Fluent Glass Dark | Fluent Glass Dark Icons |

## Portable web use

Import `generated/fluent-glass.css`. Set `data-design="fluent-glass"` and
`data-theme="light"` or `"dark"`. Observe `prefers-color-scheme` for a System option.
Existing `--fel-*` names, including historical `--fel-cameo*` aliases, stay compatible.

Use system sans-serif and stable opaque reading sheets; keep prose near 68ch.
Blue means actions/concepts, green observations, warm yellow a short insight, red
errors. Meaning must also be clear without color. Glass belongs to navigation
and controls. Honor reduced transparency, increased contrast and reduced motion;
the CSS includes fallbacks. This is our interpretation, not Apple's native API.

Use `<dfn class="concept">` to introduce a term and a short `<mark>` for one causal
insight. Do not highlight every keyword. Components/layout remain product-owned.

## Verification and provenance

The build validates role parity and selected contrast pairs. Editor syntax is
checked on editor, active-line, selection, search and document-highlight surfaces.
It does not certify every composition, third-party capture, display, font or
color-vision condition. Inspect native rendering after visual changes.

Extracted from the approved Fluent Notebooks direction on 2026-09-10, with editor
surface corrections on 2026-09-13. Primary sheets use `plate`; the inset code-block
surface does not become the entire editor. Building never activates a theme.
