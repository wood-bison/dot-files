# Login environment. Homebrew may already be on PATH (e.g. nested shells).
typeset -U path PATH
if (( $+commands[brew] )); then
  eval "$(brew shellenv zsh)"
elif [[ -x /opt/homebrew/bin/brew ]]; then
  eval "$(/opt/homebrew/bin/brew shellenv zsh)"
elif [[ -x /usr/local/bin/brew ]]; then
  eval "$(/usr/local/bin/brew shellenv zsh)"
fi
for _dir in "$HOME/bin" "$HOME/.local/bin"; do
  [[ -d "$_dir" ]] && path=("$_dir" $path)
done
for _dir in "$HOME/.docker/bin" \
            "$HOME/Library/Application Support/JetBrains/Toolbox/scripts"; do
  [[ -d "$_dir" ]] && path+=("$_dir")
done
unset _dir
export SDKMAN_DIR="$HOME/.sdkman"
[[ -s "$SDKMAN_DIR/bin/sdkman-init.sh" ]] && source "$SDKMAN_DIR/bin/sdkman-init.sh"
[[ -f "${ZDOTDIR:-$HOME}/.zprofile.local" ]] && source "${ZDOTDIR:-$HOME}/.zprofile.local"
true
