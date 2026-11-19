"""
Tablut rules engine (Ashton rules), written to mirror the official
GameAshtonTablut.java behaviour of the University of Bologna competition.

Board representation
--------------------
The board is a ``bytearray`` of 81 cells, index = row * 9 + col.
Row 0 is the top row (server "1"), col 0 is column "a".
Cell values: EMPTY, WHITE (soldier), BLACK (soldier), KING.
The throne (castle) is the fixed cell THRONE = 40 (e5); when the king is
not on it the cell holds EMPTY, but nobody can enter or cross it.

Keeping all rules in this file makes it easy to adapt the player to other
Tafl variants (Brandubh, classic Tablut...): only this module would change.
"""

EMPTY, WHITE, BLACK, KING = 0, 1, 2, 3

# Turn / result codes
WHITE_TURN, BLACK_TURN = 0, 1
WHITE_WIN, BLACK_WIN, DRAW = 2, 3, 4

SIZE = 9
N_CELLS = SIZE * SIZE
THRONE = 4 * SIZE + 4  # e5


def idx(r, c):
    return r * SIZE + c


def cell_name(i):
    """Index -> server coordinate, e.g. 0 -> 'a1', 40 -> 'e5'."""
    r, c = divmod(i, SIZE)
    return chr(ord('a') + c) + str(r + 1)


def parse_cell(name):
    c = ord(name[0].lower()) - ord('a')
    r = int(name[1:]) - 1
    return idx(r, c)


# Camps (citadels): the 16 black starting cells
CAMPS = frozenset(parse_cell(n) for n in (
    "a4", "a5", "a6", "b5",
    "d1", "e1", "f1", "e2",
    "i4", "i5", "i6", "h5",
    "d9", "e9", "f9", "e8",
))
IS_CAMP = bytearray(1 if i in CAMPS else 0 for i in range(N_CELLS))

# Central outer camp cells: in the official engine they do NOT act as a
# capture "barrier" when White captures a black pawn.
CAMP_NO_BARRIER_FOR_WHITE = frozenset(parse_cell(n) for n in ("e1", "e9", "a5", "i5"))

# Cells orthogonally adjacent to the throne
NEAR_THRONE = frozenset((THRONE - SIZE, THRONE + SIZE, THRONE - 1, THRONE + 1))

DIRS = ((-1, 0), (1, 0), (0, -1), (0, 1))

# Precomputed rays: RAYS[i] = list of 4 tuples of indices going outward
RAYS = []
for _i in range(N_CELLS):
    _r, _c = divmod(_i, SIZE)
    _rays = []
    for dr, dc in DIRS:
        ray = []
        rr, cc = _r + dr, _c + dc
        while 0 <= rr < SIZE and 0 <= cc < SIZE:
            ray.append(idx(rr, cc))
            rr += dr
            cc += dc
        _rays.append(tuple(ray))
    RAYS.append(tuple(_rays))
RAYS = tuple(RAYS)

# NEIGH2[i] = list of (neighbor, beyond) pairs (beyond may be -1 if off-board)
NEIGH2 = []
for _i in range(N_CELLS):
    lst = []
    for ray in RAYS[_i]:
        if len(ray) >= 1:
            lst.append((ray[0], ray[1] if len(ray) >= 2 else -1))
    NEIGH2.append(tuple(lst))
NEIGH2 = tuple(NEIGH2)

NEIGH = tuple(tuple(n for n, _ in NEIGH2[i]) for i in range(N_CELLS))

IS_EDGE = bytearray(
    1 if (i // SIZE in (0, SIZE - 1) or i % SIZE in (0, SIZE - 1)) else 0
    for i in range(N_CELLS))


def initial_board():
    b = bytearray(N_CELLS)
    for i in CAMPS:
        b[i] = BLACK
    for n in ("e3", "e4", "e6", "e7", "c5", "d5", "f5", "g5"):
        b[parse_cell(n)] = WHITE
    b[THRONE] = KING
    return b


def _dist(a, b):
    ra, ca = divmod(a, SIZE)
    rb, cb = divmod(b, SIZE)
    return abs(ra - rb) + abs(ca - cb)


def gen_moves(board, turn):
    """Return the list of legal moves (from, to) for the side to move."""
    moves = []
    append = moves.append
    if turn == WHITE_TURN:
        mine = (WHITE, KING)
    else:
        mine = (BLACK,)
    is_camp = IS_CAMP
    for s in range(N_CELLS):
        p = board[s]
        if p == EMPTY or p not in mine:
            continue
        src_camp = is_camp[s]
        for ray in RAYS[s]:
            for t in ray:
                if t == THRONE or board[t] != EMPTY:
                    break
                if is_camp[t]:
                    if not src_camp:
                        break  # cannot enter / cross a camp from outside
                    # camp -> camp: landing allowed only within distance 5
                    if _dist(s, t) > 5:
                        continue
                append((s, t))
    return moves


def is_legal(board, turn, move):
    return move in gen_moves(board, turn)


def apply_move(board, move, turn):
    """
    Return (new_board, result) where result is None (game goes on),
    WHITE_WIN or BLACK_WIN. Does not modify ``board``.
    """
    s, t = move
    b = bytearray(board)
    piece = b[s]
    b[s] = EMPTY
    b[t] = piece
    result = None
    if turn == WHITE_TURN:
        # White captures black pawns
        for n, beyond in NEIGH2[t]:
            if b[n] == BLACK and beyond >= 0:
                bv = b[beyond]
                if (bv == WHITE or bv == KING or beyond == THRONE or
                        (IS_CAMP[beyond] and beyond not in CAMP_NO_BARRIER_FOR_WHITE)):
                    b[n] = EMPTY
        if piece == KING and IS_EDGE[t]:
            result = WHITE_WIN
    else:
        for n, beyond in NEIGH2[t]:
            v = b[n]
            if v == WHITE:
                if beyond >= 0 and (b[beyond] == BLACK or beyond == THRONE or IS_CAMP[beyond]):
                    b[n] = EMPTY
            elif v == KING:
                if king_captured(b, n, beyond):
                    result = BLACK_WIN
    return b, result


def king_captured(b, k, beyond):
    """King at k, just attacked by a black pawn; beyond = cell on the far side."""
    if k == THRONE:
        for n in NEIGH[k]:
            if b[n] != BLACK:
                return False
        return True
    if k in NEAR_THRONE:
        for n in NEIGH[k]:
            if n != THRONE and b[n] != BLACK:
                return False
        return True
    if beyond < 0:
        return False
    return b[beyond] == BLACK or IS_CAMP[beyond] == 1


def position_key(board, turn):
    return bytes(board) + bytes((turn,))


def board_to_str(board):
    sym = {EMPTY: '.', WHITE: 'W', BLACK: 'B', KING: 'K'}
    lines = []
    for r in range(SIZE):
        row = []
        for c in range(SIZE):
            i = idx(r, c)
            ch = sym[board[i]]
            if ch == '.' and i == THRONE:
                ch = 'T'
            elif ch == '.' and IS_CAMP[i]:
                ch = '*'
            row.append(ch)
        lines.append(str(r + 1) + ' ' + ' '.join(row))
    lines.append('  ' + ' '.join('abcdefghi'))
    return '\n'.join(lines)


# ---------- conversion from / to server JSON ----------

_PAWN_MAP = {
    'EMPTY': EMPTY, 'O': EMPTY, 'THRONE': EMPTY, 'T': EMPTY,
    'WHITE': WHITE, 'W': WHITE,
    'BLACK': BLACK, 'B': BLACK,
    'KING': KING, 'K': KING,
}

_TURN_MAP = {
    'WHITE': WHITE_TURN, 'W': WHITE_TURN,
    'BLACK': BLACK_TURN, 'B': BLACK_TURN,
    'WHITEWIN': WHITE_WIN, 'WW': WHITE_WIN,
    'BLACKWIN': BLACK_WIN, 'BW': BLACK_WIN,
    'DRAW': DRAW, 'D': DRAW,
}


def board_from_json(state):
    rows = state['board']
    b = bytearray(N_CELLS)
    for r in range(SIZE):
        for c in range(SIZE):
            b[idx(r, c)] = _PAWN_MAP[str(rows[r][c]).upper()]
    return b


def turn_from_json(state):
    return _TURN_MAP[str(state['turn']).upper()]


def move_to_json(move, turn):
    s, t = move
    return {
        'from': cell_name(s),
        'to': cell_name(t),
        'turn': 'WHITE' if turn == WHITE_TURN else 'BLACK',
    }
