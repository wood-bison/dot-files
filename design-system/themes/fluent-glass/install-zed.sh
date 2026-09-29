#!/bin/sh
# Install the generated theme only; never select it or overwrite another file.
set -eu
theme_root=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
theme_source="$theme_root/generated/fluent-glass.json"
theme_target="$HOME/.config/zed/themes/fluent-glass.json"
if [ ! -f "$theme_source" ]; then
  printf '%s\n' 'Build first: python3 design-system/themes/fluent-glass/build.py' >&2
  exit 1
fi
if [ -L "$theme_target" ] && [ "$(readlink "$theme_target")" = "$theme_source" ]; then
  printf '%s\n' 'Fluent Glass is already linked to this repository.'
elif [ -e "$theme_target" ] || [ -L "$theme_target" ]; then
  printf '%s\n' "Existing file preserved: $theme_target" >&2
  printf '%s\n' 'Compare or back it up before replacing it manually.' >&2
  exit 1
else
  mkdir -p "$(dirname -- "$theme_target")"
  ln -s "$theme_source" "$theme_target"
  printf '%s\n' "Linked: $theme_target"
fi
printf '%s\n' 'In Zed: Cmd+K, Cmd+T; choose Fluent Glass Light or Fluent Glass Dark.'
printf '%s\n' 'Active settings and Cameo were not changed.'
