#!/bin/sh
# Prints the time left in this lab session for the tmux status bar and
# window title. LAB_END_TIME (unix seconds) is passed in by lab-shell.sh.
end="${LAB_END_TIME:-}"
case "$end" in ''|*[!0-9]*) exit 0 ;; esac
left=$(( end - $(date +%s) ))
[ "$left" -lt 0 ] && left=0
h=$(( left / 3600 )); m=$(( left % 3600 / 60 )); s=$(( left % 60 ))
if [ "$h" -gt 0 ]; then t=$(printf '%d:%02d:%02d' "$h" "$m" "$s"); else t=$(printf '%02d:%02d' "$m" "$s"); fi
if [ "$1" = "--plain" ]; then
  printf 'TIME LEFT %s' "$t"
elif [ "$left" -le 300 ]; then
  printf '#[bg=red,fg=white,bold] TIME LEFT %s #[default]' "$t"
else
  printf '#[fg=black] TIME LEFT %s #[default]' "$t"
fi
