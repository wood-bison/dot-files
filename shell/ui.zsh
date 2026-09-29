# Indexed ANSI colors follow Ghostty's Fluent light/dark palette immediately.
# No process polls macOS appearance, and no RGB palette is duplicated here.
export BAT_THEME=ansi
export EZA_COLORS='di=34:ln=36:ex=32:or=31:fi=0:da=90:sn=33:sb=90:uu=35:gu=35'
export FZF_DEFAULT_OPTS='--color=fg:-1,bg:-1,hl:4,fg+:4,bg+:-1,hl+:4,info:3,prompt:4,pointer:1,marker:2,spinner:4,header:8,border:8 --border=rounded'
ZSH_AUTOSUGGEST_HIGHLIGHT_STYLE='fg=8'

autoload -Uz vcs_info add-zsh-hook
zstyle ':vcs_info:git:*' check-for-changes false
zstyle ':vcs_info:git:*' formats ' %F{4}%b%f'
zstyle ':vcs_info:git:*' actionformats ' %F{4}%b%f %F{1}(%a)%f'
_dotfiles_vcs() { vcs_info }
add-zsh-hook -d precmd _dotfiles_vcs 2>/dev/null
add-zsh-hook precmd _dotfiles_vcs
setopt prompt_subst
PROMPT=$'\n''%F{8}╭─%f %F{2}%~%f${vcs_info_msg_0_}'$'\n''%F{8}╰─%f%(?..%F{1}✗%f )%F{4}❯%f '
