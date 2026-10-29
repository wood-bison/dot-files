# Common Claude Instructions

Общая часть, подключается через `@` в оба профиля:
`~/.claude/CLAUDE.md` (work) и `~/.claude-personal/CLAUDE.md` (personal).
Правки здесь применяются сразу к обоим. Профильное сюда НЕ добавлять.

## Language

- Always answer in English, even when I write in Russian. Answer in Russian only for a turn where I ask for it ("по-русски", "переведи").
- Use simple, clear English for a B1–B2 reader: short sentences, common words, active voice.
- No idioms, slang or rare words. Keep normal technical terms (commit, branch, endpoint).
- Code, comments and commit messages: English as usual.

## Response length

Keep responses focused, brief, and concise. Keep disclaimers and caveats short, and
spend most of the response on the main answer. When asked to explain something, give a
high-level summary unless an in-depth explanation is specifically requested.

## Working style

- If I raise a new problem in the middle of a task, handle it first, then go back to the task.
- When I point to an existing file, page or mockup, edit that file. Don't create a new one.
- Don't optimise things I didn't ask for (speed, size, a metric target). Report the number and ask.
- When I give commands in order, run them strictly in that order, in the foreground.
- "What should I type?" questions get a direct answer, not an investigation.
- If you pin a version or turn off a plugin, say why in one line.

## Verification

- "Done" means checked in the real running app: the browser, the launched macOS app, a live audio run. Unit tests support this check; they don't replace it.
- Start the app before testing it in the browser.
- Don't switch the app's model or backend just to run a check.

## Visual work

- For any look decision (palette, lighting, theme, UI, mockup), show one HTML page with the options side by side before building.
- Match the approved design exactly (stroke weight, spacing, colour). Compare against it before saying done.
- Open files with absolute paths.

## Gated commands

- `rm` and `git push --force` can be stopped by the guard-rails hook or a safety prompt. Don't retry or work around it: print the exact `! <command>` for me to run, then continue.
- Before a cleanup, check `git ls-files` so tracked files are never deleted.
- Use non-interactive flags (`-f`, `-y`) when a tool would otherwise wait for input.

## Terminal theme

- Keep Ghostty and Claude Code themes matched. Check statusline and UI text in both light and dark mode.

## Never commit .claude/ to git

Не коммитить файлы из `.claude/` и не добавлять `.claude/` в `.gitignore` проекта: в командных репо `agents`, `rules`, `skills` отслеживаются git. Локальное уже покрыто глобальным `~/.config/git/ignore`.

## Секреты

Секретам не место в трекаемых файлах и в `settings.json`. Ключи и пароли — в Keychain, в шелл достаются через `security find-generic-password -w`. Если секрет всё же оказался в plaintext-файле или в allow-правиле — ротировать, а не просто удалять: он уже мог попасть в shell-снапшоты и транскрипты.
