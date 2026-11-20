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

## Tuning log (evaluation weights)

Method: `tests/match.py` plays the current code against a frozen baseline,
40 games per test (20 openings x both colours), fixed depth 3 (reproducible);
promising settings are re-checked on 40 openings and with a time budget.
Reference when both sides are equal: 20/40 (white 8/20, black 12/20 - Ashton
rules favour Black).

| Change vs v2 | Score /40 |
|---|---|
| king_attacker 40 / 120 | 15.5 / 21.0 |
| black_blocker 15 / 60 | 21.0 / 18.0 |
| two_step_escape 20 / 80 | 23.5 / 13.5 |
| white_piece 70 / 120 | 15.5 / 21.5 |
| two_step_escape 10 / 30 | 24.0 / 21.0 |
| king_attacker 160 | 21.5 |
| white_piece 150 | 23.0 |
| tse 20 + white_piece 120 | 25.0 |
| **tse 20 + white_piece 120 + king_attacker 120 (= v3)** | **26.0** |
| v3 + black_blocker 15 | 24.5 |
| tse 10 + wp 120 + ka 120 | 20.5 |
| tse 15 + wp 150 + ka 120 | 19.5 |

v3 validation: 51/80 on 40 openings (depth 3), 14/24 with 0.3 s per move.

## Search enhancements (v4)

v4 = v3 + killer moves + PVS (principal variation search) + LMR (late move
reductions). In 3 s, LMR reaches one ply deeper in most test positions.
Search changes must be tested with a time budget (fixed-depth tests cannot
show that the same time now buys a deeper search).

| 0.5 s per move, 40 games vs baseline v3 | Score /40 | as White /20 | as Black /20 |
|---|---|---|---|
| reference (enhancements off = v3 vs v3) | 17.0 | 1.0 | 16.0 |
| **v4 (killers + PVS + LMR)** | **24.5** | **8.0** | 16.5 |

With a deeper search Black dominates (Ashton rules favour Black); the extra
ply mostly helps White, which needs longer combinations (e.g. preparing a
square with two free lines) to escape.
