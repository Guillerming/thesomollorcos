#!/bin/zsh
# Gestiona el bot como LaunchAgent: arranca al iniciar sesión y se reinicia si se cae.
# Uso: scripts/service.sh install | uninstall | restart | status | logs
set -euo pipefail

LABEL="com.thesomollorcos.bot"
ROOT="${0:A:h:h}"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
PYTHON="$(command -v python3)"
SERVICE_PATH="/opt/homebrew/bin:/usr/local/bin:$HOME/.local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
DOMAIN="gui/$(id -u)"

write_plist() {
  mkdir -p "$ROOT/state" "${PLIST:h}"
  cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key>
  <array><string>$PYTHON</string><string>-u</string><string>-m</string><string>bot</string></array>
  <key>WorkingDirectory</key><string>$ROOT</string>
  <key>EnvironmentVariables</key>
  <dict><key>PATH</key><string>$SERVICE_PATH</string></dict>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>ThrottleInterval</key><integer>30</integer>
  <key>StandardOutPath</key><string>$ROOT/state/bot.log</string>
  <key>StandardErrorPath</key><string>$ROOT/state/bot.err.log</string>
</dict>
</plist>
EOF
}

case "${1:-status}" in
  install)
    write_plist
    launchctl bootout "$DOMAIN/$LABEL" 2>/dev/null || true
    launchctl bootstrap "$DOMAIN" "$PLIST"
    echo "Instalado y arrancado: $LABEL"
    ;;
  uninstall)
    launchctl bootout "$DOMAIN/$LABEL" 2>/dev/null || true
    rm -f "$PLIST"
    echo "Desinstalado: $LABEL"
    ;;
  restart)
    launchctl kickstart -k "$DOMAIN/$LABEL"
    echo "Reiniciado: $LABEL"
    ;;
  status)
    launchctl print "$DOMAIN/$LABEL" 2>/dev/null | grep -E "state =|pid =|last exit" || echo "No instalado"
    ;;
  logs)
    tail -n 40 -f "$ROOT/state/bot.err.log"
    ;;
  *)
    echo "Uso: $0 install | uninstall | restart | status | logs" >&2
    exit 1
    ;;
esac
