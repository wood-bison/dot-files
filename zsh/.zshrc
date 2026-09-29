# install.sh prepends DOTFILES_ROOT with this checkout's actual location.
typeset -U path PATH
: "${DOTFILES_ROOT:=$HOME/dotfiles}"
_brew="${HOMEBREW_PREFIX:-}"
if [[ -z "$_brew" ]]; then
  [[ -x /opt/homebrew/bin/brew ]] && _brew=/opt/homebrew
  [[ -z "$_brew" && -x /usr/local/bin/brew ]] && _brew=/usr/local
fi
# Fill missing Homebrew paths without outranking SDKMAN or personal tools.
if [[ -n "$_brew" ]]; then
  for _dir in "$_brew/bin" "$_brew/sbin"; do
    (( ${path[(Ie)$_dir]} )) || path+=("$_dir")
  done
  unset _dir
fi
source "$DOTFILES_ROOT/shell/ui.zsh"

# Complete once per day; do not overwrite another plugin's precmd hook.
autoload -Uz compinit
_dotfiles_cache="${XDG_CACHE_HOME:-$HOME/.cache}/zsh"
mkdir -p "$_dotfiles_cache"
if [[ -n "$_dotfiles_cache/zcompdump"(#qN.mh+24) || ! -f "$_dotfiles_cache/zcompdump" ]]; then
  compinit -d "$_dotfiles_cache/zcompdump"
else
  compinit -C -d "$_dotfiles_cache/zcompdump"
fi
unset _dotfiles_cache
zstyle ':completion:*' menu select
zstyle ':completion:*' matcher-list 'm:{a-zA-Z}={A-Za-z}'

HISTSIZE=20000
SAVEHIST=20000
HISTFILE="$HOME/.zsh_history"
setopt appendhistory sharehistory hist_ignore_all_dups hist_ignore_space

# Standard ls, cat and cd keep their usual behavior.
if (( $+commands[eza] )); then
  alias ll='eza -la --icons --group-directories-first --git --time-style=long-iso'
  alias lt='eza --tree --icons --level=3 --group-directories-first'
fi
alias ..='cd ..'
alias ...='cd ../..'
alias cls='clear'
alias g='git'
alias gs='git status'
alias gd='git diff'
alias gc='git commit'
alias gp='git push'
alias gpl='git pull'
alias gb='git branch'
alias gco='git checkout'
alias gl='git log -20 --oneline --graph --decorate'

if (( $+commands[fzf] )); then
  source <(fzf --zsh)
  if (( $+commands[fd] )); then
    export FZF_DEFAULT_COMMAND='fd --type f --strip-cwd-prefix --hidden --exclude .git'
    export FZF_CTRL_T_COMMAND="$FZF_DEFAULT_COMMAND"
    export FZF_ALT_C_COMMAND='fd --type d --strip-cwd-prefix --hidden --exclude .git'
  fi
fi
# fzf-tab must load after compinit and fzf's widgets.
if [[ -f "$_brew/opt/fzf-tab/share/fzf-tab/fzf-tab.zsh" ]]; then
  source "$_brew/opt/fzf-tab/share/fzf-tab/fzf-tab.zsh"
  zstyle ':fzf-tab:complete:cd:*' fzf-preview 'eza --icons --color=always -1 -- "$realpath"'
  zstyle ':fzf-tab:complete:*:*' fzf-preview 'bat --color=always --line-range :40 -- "$realpath" 2>/dev/null || eza --icons --color=always -1 -- "$realpath"'
  zstyle ':fzf-tab:*' switch-group '<' '>'
fi
export RIPGREP_CONFIG_PATH="$DOTFILES_ROOT/shell/ripgreprc"
alias rgg='rg -n --heading'
alias todos='rg -n --heading -C1 "TODO|FIXME|HACK|XXX"'
(( $+commands[zoxide] )) && eval "$(zoxide init zsh)"

bindkey '^[[1;3D' backward-word
bindkey '^[[1;3C' forward-word
[[ -f "$_brew/share/zsh-autosuggestions/zsh-autosuggestions.zsh" ]] && \
  source "$_brew/share/zsh-autosuggestions/zsh-autosuggestions.zsh"
[[ -f "$_brew/opt/zsh-fast-syntax-highlighting/share/zsh-fast-syntax-highlighting/fast-syntax-highlighting.plugin.zsh" ]] && \
  source "$_brew/opt/zsh-fast-syntax-highlighting/share/zsh-fast-syntax-highlighting/fast-syntax-highlighting.plugin.zsh"
unset _brew

if (( $+commands[docker] )); then
  dps() { docker ps --format 'table {{.ID}}\t{{.Image}}\t{{.Names}}\t{{.Status}}\t{{.Ports}}' "$@" }
  alias dpsa='dps -a'
fi
# Personal tools and secrets belong here; the installer never overwrites it.
[[ -f "${ZDOTDIR:-$HOME}/.zshrc.local" ]] && source "${ZDOTDIR:-$HOME}/.zshrc.local"
true
