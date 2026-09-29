# Copy selected lines to ~/.zshrc.local. This file is never installed or sourced.
# Use $HOME; keep project launchers and local AI tools out of shared startup.
#
# [[ -d "$HOME/.bun/bin" ]] && path=("$HOME/.bun/bin" $path)
# [[ -s "$HOME/.bun/_bun" ]] && source "$HOME/.bun/_bun"
# [[ -x "$HOME/developer/my-app/run.sh" ]] && alias my-app="$HOME/developer/my-app/run.sh"
#
# ~/.zprofile.local is also supported for login-only setup.
