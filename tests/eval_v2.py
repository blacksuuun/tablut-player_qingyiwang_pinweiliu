"""
Heuristic evaluation. Scores are always from WHITE's point of view
(positive = good for White); the search flips the sign for Black.

The evaluation is aware of the side to move, so that immediate threats
seen at the leaves of the search are scored correctly:
  * White to move and the king has a free line to the border -> White wins.
  * Black to move and Black can capture the king -> Black wins.
  * Black to move and the king has 2+ free lines -> Black cannot block both.
This works as a cheap "quiescence" check against the horizon effect.
"""
from rules import (EMPTY, WHITE, BLACK, KING, SIZE, THRONE, IS_CAMP, RAYS,
                   NEIGH, NEAR_THRONE, WHITE_TURN, idx)

# ---- weights (tunable) ----
W_WHITE_PIECE = 90       # value of each white soldier
W_BLACK_PIECE = 50       # value of each black soldier
W_ONE_ROUTE_BLACK_TO_MOVE = 300   # black is forced to block
W_TWO_STEP_ESCAPE = 40   # each square from where the king could escape next
W_FORK_SQUARE = 3000     # king can reach a square with 2+ free lines
W_CAPTURE_THREAT = 250   # black threatens to capture the king next move
W_KING_ATTACKER = 70     # each black pawn / camp next to the king
W_KING_MOBILITY = 4      # each square the king can reach
W_KING_FROM_CENTER = 10  # per step of king distance from the throne
W_BLACK_BLOCKER = 30     # black pawn on a key blocking square
NEAR_WIN = 90000         # static score for a position that is won next move

# Squares diagonal to the corners' approach: black pawns here seal escapes
BLOCKERS = tuple(idx(r, c) for r, c in (
    (1, 2), (2, 1), (1, 6), (2, 7), (6, 1), (7, 2), (6, 7), (7, 6)))


def _free_routes(board, pos, ignore=-1):
    """Number of free straight lines from pos to the border."""
    n = 0
    for ray in RAYS[pos]:
        if not ray:
            continue
        free = True
        for t in ray:
            if t == THRONE or IS_CAMP[t] or (board[t] != EMPTY and t != ignore):
                free = False
                break
        if free:
            n += 1
    return n


def _black_can_reach(board, cell):
    """True if some black pawn can move to the empty cell in one move."""
    dest_camp = IS_CAMP[cell]
    for ray in RAYS[cell]:
        path_camp = False
        for s in ray:
            v = board[s]
            if s == THRONE:
                break
            if v == EMPTY:
                if IS_CAMP[s]:
                    path_camp = True
                continue
            if v == BLACK:
                if IS_CAMP[s]:
                    if dest_camp:
                        r1, c1 = divmod(s, SIZE)
                        r2, c2 = divmod(cell, SIZE)
                        if abs(r1 - r2) + abs(c1 - c2) > 5:
                            break
                    return True
                if not path_camp and not dest_camp:
                    return True
            break
    return False


def black_capture_threat(board, k):
    """True if Black, to move, can capture the king at k right now."""
    neigh = NEIGH[k]
    if k == THRONE or k in NEAR_THRONE:
        empties = [n for n in neigh if n != THRONE and board[n] != BLACK]
        if len(empties) == 1 and board[empties[0]] == EMPTY:
            return _black_can_reach(board, empties[0])
        return False
    # standard capture on one axis: one side hostile, other side reachable
    kr, kc = divmod(k, SIZE)
    for (dr, dc) in ((1, 0), (0, 1)):
        r1, c1, r2, c2 = kr - dr, kc - dc, kr + dr, kc + dc
        if not (0 <= r1 < SIZE and 0 <= c1 < SIZE and 0 <= r2 < SIZE and 0 <= c2 < SIZE):
            continue
        a, b = r1 * SIZE + c1, r2 * SIZE + c2
        for x, y in ((a, b), (b, a)):
            if (board[x] == BLACK or IS_CAMP[x]) and board[y] == EMPTY and not IS_CAMP[y]:
                if _black_can_reach(board, y):
                    return True
    return False


def evaluate(board, turn=WHITE_TURN):
    k = board.find(KING)
    if k < 0:
        return -NEAR_WIN

    routes = _free_routes(board, k)
    if turn == WHITE_TURN:
        if routes >= 1:
            return NEAR_WIN
    else:
        if black_capture_threat(board, k):
            return -NEAR_WIN
        if routes >= 2:
            return NEAR_WIN - 1000

    n_white = board.count(WHITE)
    n_black = board.count(BLACK)
    score = W_WHITE_PIECE * n_white - W_BLACK_PIECE * n_black

    if turn != WHITE_TURN and routes == 1:
        score += W_ONE_ROUTE_BLACK_TO_MOVE

    # king mobility and "two-step" escape squares
    mobility = 0
    escape_squares = 0
    fork = False
    for ray in RAYS[k]:
        for t in ray:
            if t == THRONE or board[t] != EMPTY or IS_CAMP[t]:
                break
            mobility += 1
            r = _free_routes(board, t, ignore=k)
            if r:
                escape_squares += 1
                if r >= 2:
                    fork = True
    score += W_KING_MOBILITY * mobility + W_TWO_STEP_ESCAPE * escape_squares
    if fork and turn == WHITE_TURN:
        score += W_FORK_SQUARE

    if turn == WHITE_TURN and black_capture_threat(board, k):
        score -= W_CAPTURE_THREAT

    att = 0
    for n in NEIGH[k]:
        if board[n] == BLACK or IS_CAMP[n]:
            att += 1
    score -= W_KING_ATTACKER * att

    kr, kc = divmod(k, SIZE)
    score += W_KING_FROM_CENTER * (abs(kr - 4) + abs(kc - 4))

    blockers = 0
    for b in BLOCKERS:
        if board[b] == BLACK:
            blockers += 1
    score -= W_BLACK_BLOCKER * blockers
    return score
