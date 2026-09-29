#!/bin/bash
# macOS bootstrap. Re-running installs missing packages and preserves edited configs.
set -euo pipefail
DOTFILES_ROOT="$(cd "$(dirname "$0")" && pwd)"
config_only=0
upgrade=0
replace=0
dry_run=0
for arg in "$@"; do
  case "$arg" in
    --config-only) config_only=1 ;;
    --upgrade) upgrade=1 ;;
    --replace-configs) replace=1 ;;
    --dry-run) dry_run=1 ;;
    --help|-h)
      cat <<'HELP'
Usage: bash install.sh [--config-only] [--upgrade] [--replace-configs] [--dry-run]
  default            Install missing dependencies; back up initial configs.
  --upgrade          Also upgrade dependencies listed in Brewfile.
  --config-only      Skip Homebrew; generate themes and install configuration.
  --replace-configs  Back up and replace configs edited since the previous install.
  --dry-run          Print the plan; do not download, build or modify anything.
HELP
      exit 0 ;;
    *) printf 'Unknown option: %s\n' "$arg" >&2; exit 2 ;;
  esac
done
if [ "$dry_run" -eq 1 ]; then
  printf 'Checkout: %s\n' "$DOTFILES_ROOT"
  cat "$DOTFILES_ROOT/Brewfile"
  printf '\nPlan: build Fluent themes/icons; install zsh, Ghostty and Zed configs;\n'
  printf 'include Git presentation settings; retire the old theme-auto agent.\n'
  printf 'Copies edited after installation are preserved unless --replace-configs is used.\n'
  printf 'Config only: %s; upgrade listed packages: %s; replace edited configs: %s\n' "$config_only" "$upgrade" "$replace"
  exit 0
fi
if [ "$(uname -s)" != Darwin ]; then
  printf 'This setup targets macOS.\n' >&2
  exit 1
fi
if [ "$config_only" -eq 1 ] && [ "$upgrade" -eq 1 ]; then
  printf '%s\n' '--config-only and --upgrade cannot be combined.' >&2
  exit 2
fi
if ! command -v brew >/dev/null 2>&1; then
  if [ -x /opt/homebrew/bin/brew ]; then
    eval "$(/opt/homebrew/bin/brew shellenv)"
  elif [ -x /usr/local/bin/brew ]; then
    eval "$(/usr/local/bin/brew shellenv)"
  fi
fi
if [ "$config_only" -eq 0 ]; then
  if ! command -v brew >/dev/null 2>&1; then
    brew_installer="$(mktemp -t dotfiles-homebrew)"
    trap 'rm -f "$brew_installer"' EXIT
    curl --fail --show-error --location https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh -o "$brew_installer"
    /bin/bash "$brew_installer"
    if [ -x /opt/homebrew/bin/brew ]; then
      eval "$(/opt/homebrew/bin/brew shellenv)"
    else
      eval "$(/usr/local/bin/brew shellenv)"
    fi
  fi
  brew update
  if [ "$upgrade" -eq 1 ]; then
    brew bundle install --file="$DOTFILES_ROOT/Brewfile"
  else
    brew bundle install --no-upgrade --file="$DOTFILES_ROOT/Brewfile"
  fi
fi
if command -v brew >/dev/null 2>&1; then
  eval "$(brew shellenv)"
fi
python3 -c 'import sys; assert sys.version_info >= (3, 11), "Python 3.11+ required; run the full installer first."'
python3 "$DOTFILES_ROOT/design-system/themes/fluent-glass/build.py"
if [ "$replace" -eq 1 ]; then
  python3 "$DOTFILES_ROOT/scripts/install.py" --activate --replace-configs
else
  python3 "$DOTFILES_ROOT/scripts/install.py" --activate
fi
printf '\nInstalled. Open a new shell; reload Ghostty with Cmd+Shift+,.\n'
printf 'Zed may need a normal quit/reopen to discover the local icon extension.\n'
