#!/bin/bash
# Usage: ./runmyplayer.sh <WHITE|BLACK> <timeout_seconds> <server_ip> [optional args]
# Example: /home/tablut/tablut/runmyplayer.sh WHITE 60 192.168.20.101

if [[ $# -lt 3 ]]; then
    echo "Need all arguments"
    echo "white or black as first parameter"
    echo "timeout as second parameter"
    echo "server ip as third parameter"
    echo "Example: $0 white 60 192.168.20.254"
    exit 1
fi

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$DIR/player.py" "$@"
