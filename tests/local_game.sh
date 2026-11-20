#!/bin/bash
# One-command local test game: official server + our player + official random player.
#
# Usage:  tests/local_game.sh <white|black> [timeout_seconds]
#   e.g.  tests/local_game.sh white 10
#
# Our player's output is shown on screen; server and random player logs go to
# /tmp/tablut_server.log and /tmp/tablut_random.log.
# Set EXE_DIR if the official Executables folder is somewhere else.

EXE_DIR="${EXE_DIR:-$HOME/TablutCompetition/Tablut/Executables}"
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUR_ROLE="$(echo "${1:-white}" | tr '[:upper:]' '[:lower:]')"
TIMEOUT="${2:-10}"

if [[ "$OUR_ROLE" != "white" && "$OUR_ROLE" != "black" ]]; then
    echo "Usage: $0 <white|black> [timeout_seconds]"
    exit 1
fi
if [[ ! -f "$EXE_DIR/Server.jar" ]]; then
    echo "Server.jar not found in $EXE_DIR (set EXE_DIR=...)"
    exit 1
fi

cleanup() {
    kill "$SERVER_PID" "$RANDOM_PID" "$OUR_PID" 2>/dev/null
}
trap cleanup EXIT INT TERM

echo "Starting server..."
java -jar "$EXE_DIR/Server.jar" > /tmp/tablut_server.log 2>&1 &
SERVER_PID=$!
sleep 2

# White must connect first
if [[ "$OUR_ROLE" == "white" ]]; then
    "$DIR/runmyplayer.sh" white "$TIMEOUT" 127.0.0.1 --verbose &
    OUR_PID=$!
    sleep 1
    java -jar "$EXE_DIR/RandomPlayer.jar" black "$TIMEOUT" 127.0.0.1 > /tmp/tablut_random.log 2>&1 &
    RANDOM_PID=$!
else
    java -jar "$EXE_DIR/RandomPlayer.jar" white "$TIMEOUT" 127.0.0.1 > /tmp/tablut_random.log 2>&1 &
    RANDOM_PID=$!
    sleep 1
    "$DIR/runmyplayer.sh" black "$TIMEOUT" 127.0.0.1 --verbose &
    OUR_PID=$!
fi

wait "$OUR_PID"
echo "Game finished (we played $OUR_ROLE). Server log: /tmp/tablut_server.log"
