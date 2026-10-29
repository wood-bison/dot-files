# Claude Code config backup

A copy of the shared Claude Code files. The live copies are in `~/.claude-shared/`.

| File | Live path | Used by |
|---|---|---|
| `CLAUDE-common.md` | `~/.claude-shared/CLAUDE-common.md` | both profiles, through `@` import in their `CLAUDE.md` |
| `output-styles/plain-english.md` | `~/.claude-shared/output-styles/plain-english.md` | both profiles, linked into `output-styles/` and set as `outputStyle` |

`install.sh` does not install these files. Copy them back by hand:

```sh
mkdir -p ~/.claude-shared/output-styles
cp claude/CLAUDE-common.md ~/.claude-shared/
cp claude/output-styles/plain-english.md ~/.claude-shared/output-styles/
```

Profile files (`~/.claude*/CLAUDE.md`, `settings.json`) are not here: they hold personal and work details.
