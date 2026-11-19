"""
Heuristic evaluation. Scores are always from WHITE's point of view
(positive = good for White); the search flips the sign for Black.
"""
from rules import (EMPTY, WHITE, BLACK, KING, SIZE, THRONE, IS_CAMP, RAYS,
                   NEIGH, idx)

# ---- weights (tunable) ----
W_WHITE_PIECE = 90      # value of each white soldier
W_BLACK_PIECE = 50      # value of each black soldier
W_ONE_ROUTE = 350       # king has one free line to the border
W_TWO_ROUTES = 2000     # king has 2+ free lines: black can block only one
W_KING_ATTACKER = 70    # each black pawn / camp next to the king
W_KING_MOBILITY = 4     # each square the king can reach
W_KING_FROM_CENTER = 10  # per step of king distance from the throne
W_BLACK_BLOCKER = 30    # black pawn on a key blocking square

# Squares diagonal to the corners' approach: black pawns here seal escapes
BLOCKERS = tuple(idx(r, c) for r, c in (
    (1, 2), (2, 1), (1, 6), (2, 7), (6, 1), (7, 2), (6, 7), (7, 6)))


def evaluate(board):
    n_white = board.count(WHITE)
    n_black = board.count(BLACK)
    score = W_WHITE_PIECE * n_white - W_BLACK_PIECE * n_black

    k = board.find(KING)
    if k < 0:
        return -100000  # should not happen (king captured is terminal)

    # free lines to the border + mobility
    routes = 0
    mobility = 0
    for ray in RAYS[k]:
        free = True
        for t in ray:
            if t == THRONE or board[t] != EMPTY or IS_CAMP[t]:
                free = False
                break
            mobility += 1
        if free and ray:
            routes += 1
    if routes >= 2:
        score += W_TWO_ROUTES
    elif routes == 1:
        score += W_ONE_ROUTE
    score += W_KING_MOBILITY * mobility

    # attackers around the king
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
