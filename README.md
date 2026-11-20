# aBC4 – Tablut Challenge 2026/27 player

Python 3 agent for the UniBo *Fundamentals of AI and Knowledge Representation*
Tablut Challenge (Ashton rules). Pure standard library, no dependencies.

## Run

```bash
/home/tablut/tablut/runmyplayer.sh <WHITE|BLACK> <timeout_seconds> <server_ip>
# e.g.
/home/tablut/tablut/runmyplayer.sh WHITE 60 192.168.20.101
```

* The role is case-insensitive (`white`, `wHitE`, `WHITE` all work).
* The timeout and the server IP are always taken from the arguments.

Optional parameters (appended after the three mandatory ones; defaults are
used in the competition):

| Option | Default | Meaning |
|---|---|---|
| `--name NAME` | `aBC4` | name sent to the server |
| `--margin SEC` | `0.12*timeout + 1.5` | safety margin subtracted from the timeout |
| `--verbose` | off | print search info to stderr (off by default: no disk usage) |

## Design

| File | Role |
|---|---|
| `rules.py` | board (81-cell `bytearray`), Ashton move generation, captures (throne/camps special cases), win detection, JSON conversion. All game rules live here, so a variant (Brandubh, classic Tablut) only needs changes in this module. |
| `evaluation.py` | side-to-move-aware heuristic: immediate threats (king escape next move, king capture next move, 2+ free lines = unstoppable), material, "two-step" escape squares, king mobility, attackers around the king, distance from the throne, black pawns on key blocking squares. |
| `search.py` | iterative-deepening negamax alpha-beta with transposition table, move ordering (TT move, captures, king escapes, history heuristic), repetition = draw, hard time limit (best move of the last finished depth is always available). |
| `player.py` | TCP client (4-byte big-endian length + UTF-8 JSON, ports 5800/5801), game loop. |
| `tests/` | offline tests: `selfplay.py` (vs random / self-play), `match.py` (new vs old evaluation, both colours, used to validate every change), `fake_server.py` (protocol test). |

## Test locally with the official server

One command (starts the server, our player and the official random player
in the right order; white always connects first):

```bash
tests/local_game.sh white 10    # we play WHITE, 10 s per move
tests/local_game.sh black 10    # we play BLACK
```

Or manually, in three terminals (start order: server, WHITE, BLACK):

```bash
java -jar ~/TablutCompetition/Tablut/Executables/Server.jar
./runmyplayer.sh white 10 127.0.0.1 --verbose
java -jar ~/TablutCompetition/Tablut/Executables/RandomPlayer.jar black 10 127.0.0.1
```
