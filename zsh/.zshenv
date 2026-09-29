# Keep this file tiny. Do not store tokens here.
# guard: без него удаление/переустановка rustup ломает КАЖДЫЙ zsh,
# включая неинтерактивные — .zshenv читается всегда и первым.
[ -f "$HOME/.cargo/env" ] && . "$HOME/.cargo/env"
true
