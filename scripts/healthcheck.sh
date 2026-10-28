#!/bin/sh
# Vigila /health y avisa por Telegram (si TELEGRAM_BOT_TOKEN y TELEGRAM_CHAT_ID estan definidos) al fallar y al recuperarse.
# Pensado para cron cada 5 minutos:  */5 * * * * /opt/radar/scripts/healthcheck.sh
# Considera fallo: sin respuesta, status distinto de "ok", o ingesta parada (>180 s sin ciclo con alguien mirando).
URL="${RADAR_URL:-http://127.0.0.1:8000}/health"
STATE="${RADAR_STATE:-/tmp/radar-health.state}"

body=$(curl -fsS -m 10 "$URL" 2>/dev/null)
problem=""
if [ -z "$body" ]; then
    problem="sin respuesta de $URL"
else
    echo "$body" | grep -q '"status":"ok"' || problem="fuentes de datos degradadas"
    age=$(echo "$body" | sed -n 's/.*"last_cycle_age_s":\([0-9.]*\).*/\1/p')
    [ -n "$age" ] && [ "${age%.*}" -gt 180 ] && problem="ingesta parada hace ${age}s"
fi

notify() {
    echo "$1"
    [ -n "$TELEGRAM_BOT_TOKEN" ] && [ -n "$TELEGRAM_CHAT_ID" ] &&
        curl -fsS -m 10 "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/sendMessage" \
            --data-urlencode "chat_id=$TELEGRAM_CHAT_ID" --data-urlencode "text=$1" >/dev/null
}

previous=$(cat "$STATE" 2>/dev/null)
if [ -n "$problem" ]; then
    [ "$previous" != "down" ] && notify "SkyMonitor: $problem"
    echo down >"$STATE"
    exit 1
fi
[ "$previous" = "down" ] && notify "SkyMonitor: recuperado"
echo up >"$STATE"
