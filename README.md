# Fluent dotfiles для macOS

Zed + Ghostty + zsh. Fluent Glass Light/Dark следуют оформлению macOS.
Cameo Light/Dark остаются дополнительными темами Zed.
Цвета Zed, Ghostty и Fluent-иконок собираются из
[одного источника](design-system/themes/fluent-glass/tokens.json).

Пересмотрено **29 сентября 2026** для macOS 27 Golden Gate / Apple Silicon.
Локальные проверки выполнены на macOS 26.7. Чистая установка на Golden Gate
в этой среде не проверялась. [Источники и решения](docs/migration.md).

## Установка

Репозиторий: **https://github.com/wood-bison/dot-files**

Если Git ещё недоступен: `xcode-select --install`, затем заверши установку Apple.
Клонирование публичного репозитория:

```sh
git clone https://github.com/wood-bison/dot-files.git ~/dotfiles
cd ~/dotfiles
bash install.sh
```

Можно также скачать ZIP, распаковать в постоянную папку и запустить
там `bash install.sh`. Пробелы в пути допустимы. Авторизация GitHub для скачивания не нужна.

Скрипт установит Homebrew, если его нет, затем зависимости из [Brewfile](Brewfile):
Ghostty, Zed, Maple Mono NF, delta, Python, eza, bat, fd, ripgrep, fzf/fzf-tab,
zoxide и два плагина zsh. Официальный установщик Homebrew может запросить пароль
администратора и установку Command Line Tools.

Затем он соберёт темы/иконки, установит конфиги, подключит настройки Git и уберёт
старый сервис theme-auto, если тот принадлежит этому checkout.
После установки открой новый терминал. В Ghostty — **Cmd+Shift+,**.
Для обнаружения иконок Zed может потребоваться обычное закрытие/открытие приложения.
Языковые расширения Zed установятся при запуске. JDK/.NET/Node и зависимости
конкретных проектов устанавливаются отдельно.

```sh
bash install.sh --dry-run          # только план, без изменений
bash install.sh --config-only      # зависимости уже установлены
bash install.sh --upgrade          # обновить пакеты Brewfile и необходимые зависимости
```

Обычный запуск использует `brew bundle install --no-upgrade`: добавляет недостающее.
Глобального `brew upgrade`, удаления пакетов и очистки других приложений нет.
Точные версии пакетов не зафиксированы.

## Настройки и повторная установка

При первой установке заменяемые файлы сохраняются в
`~/.local/state/dotfiles/backups/<запуск>/`.
Конфиги приложений и shell устанавливаются обычными копиями. Темы связаны
симлинками с checkout — **оставь папку репозитория на месте**.

Повторная установка обновляет только файлы, не изменённые после установки.
Твои правки сохраняются; скрипт перечисляет такие файлы. Для явного возврата
к настройкам репозитория с новым бэкапом:

```sh
bash install.sh --config-only --replace-configs
```

После обновления репозитория запускай установщик ещё раз.
Чтобы вернуть отдельный файл, скопируй его из бэкапа поверх установленного.
Бэкап файлов-симлинков содержит сами данные, поэтому переживает изменения checkout.

| Что | Где |
| --- | --- |
| Настройки и клавиши Zed | `zed/settings.json`, `zed/keymap.json` → `~/.config/zed/` |
| Терминал | `ghostty/config` → `~/.config/ghostty/config` |
| Shell | `zsh/` → `~/.zshrc`, `~/.zprofile`, `~/.zshenv` |
| Цвета | `design-system/themes/fluent-glass/tokens.json` |
| Личные команды и секреты | `~/.zshrc.local`, `~/.zprofile.local` |
| Локальные настройки Ghostty | `~/.config/ghostty/local.conf` |
| Дополнения к шаблону Zed | `~/.config/dotfiles/zed.local.json` — обычный JSON, рекурсивное объединение |

Личные файлы установщик не перезаписывает. Имя, почта, credential helpers
остаются в `~/.gitconfig`; подключается только общий include.
Если SDKMAN уже содержит JDK, путь для Zed определяется на этой машине.

## Каждый день

- `ll`, `lt` — список/дерево eza. Стандартные `ls`, `cat` и `cd` сохраняют своё поведение.
- **Ctrl+R** — история fzf; **Ctrl+T** — поиск файлов; **Option+C** — папки.
- `z <имя>` — переход zoxide. `rgg` и `todos` — помощники ripgrep.
- `gs`, `gd`, `gc`, `gp`, `gpl`, `gb`, `gco`, `gl` — короткие команды Git.
- `dps`, `dpsa` — таблица контейнеров, если Docker уже установлен.
- Zed: **Cmd+B** — панель, **Cmd+P** — файлы, **F12** — определение.
- Ghostty: **Option+Shift+H/J/K/L** — сплиты; **Option+H/J/K/L** — переход;
  **Ctrl+Shift+H/J/K/L** — размер; **Option+Z** — увеличение сплита.
- Выпадающий терминал: **Cmd+Shift+обратная кавычка**. Для глобальной клавиши
  macOS может запросить разрешение Accessibility; оно выдаётся в System Settings.

Cameo в Zed выбирается через **Zed → Settings → Select Theme**. Для автоматической пары задай
`theme.light = "Cameo Light"`, `theme.dark = "Cameo Dark"` и `theme.mode = "system"`.
Оформление иконок следует системе независимо.

Atuin, lazygit, Yazi, локальные LLM, замена иконок приложений и экспериментальные
шейдеры в новый набор не входят. Существующие данные этих приложений не удаляются.
Сервис theme-auto и gtheme больше не нужны: Zed и Ghostty следят за оформлением
сами, а shell использует ANSI-цвета терминала.

## Изменение темы

```sh
python3 design-system/themes/fluent-glass/build.py
python3 -m unittest discover -s tests -v
```

Правь токены/адаптеры, затем собирай. Сгенерированные файлы не редактируются вручную.
Библиотека SVG Cameo сохранена как лицензированный источник Fluent-иконок.
[Устройство design-system](design-system/README.md).
