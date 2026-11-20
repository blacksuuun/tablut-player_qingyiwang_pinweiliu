"""
Iterative-deepening negamax with alpha-beta pruning and a hard time limit.
The best move of the last completed depth is always kept, so the player can
answer in time whatever happens.

Enhancements (each can be switched off for experiments):
  * transposition table (always on)
  * move ordering: TT move, captures / king escapes, killer moves, history
  * PVS  (principal variation search): after the first move, the others are
         searched with a null window and re-searched only if they look better
  * LMR  (late move reductions): late, quiet moves are first searched with a
         reduced depth; if they turn out good they are re-searched normally
"""
import time

from rules import (WHITE_TURN, BLACK_TURN, WHITE_WIN, BLACK_WIN, EMPTY, WHITE,
                   BLACK, KING, THRONE, IS_CAMP, IS_EDGE, NEIGH2,
                   gen_moves, apply_move, position_key)
from evaluation import evaluate

WIN_SCORE = 1000000
INF = 10 ** 9
EXACT, LOWER, UPPER = 0, 1, 2
TT_MAX_SIZE = 1500000
MAX_PLY = 128

# ordering bonuses
TT_BONUS = 100000000
ESCAPE_BONUS = 10000000
CAPTURE_BONUS = 1000000
KILLER1_BONUS = 900000
KILLER2_BONUS = 800000
KING_MOVE_BONUS = 5000
KING_ATTACK_BONUS = 3000

# LMR parameters
LMR_MIN_DEPTH = 3     # only reduce when remaining depth >= this
LMR_FULL_MOVES = 4    # the first N moves are always searched at full depth


class TimeUp(Exception):
    pass


class Searcher:
    def __init__(self, max_depth=64, verbose=False, eval_fn=None,
                 killers=True, pvs=True, lmr=True):
        self.evaluate = eval_fn or evaluate
        self.max_depth = max_depth
        self.verbose = verbose
        self.use_killers = killers
        self.use_pvs = pvs
        self.use_lmr = lmr
        self.tt = {}
        self.history = {}
        self.killers = [[None, None] for _ in range(MAX_PLY)]
        self.nodes = 0
        self.deadline = 0.0
        self.last_depth = 0
        self.last_nodes = 0

    # ------------------------------------------------------------------
    def choose_move(self, board, turn, time_budget, game_history=()):
        """
        board: bytearray, turn: WHITE_TURN/BLACK_TURN,
        time_budget: seconds we may spend,
        game_history: set of position keys already seen in the game
        (used to detect draws by repetition).
        """
        start = time.time()
        self.deadline = start + max(0.05, time_budget)
        self.nodes = 0
        self.seen = set(game_history)
        if len(self.tt) > TT_MAX_SIZE:
            self.tt.clear()
        # age the history heuristic, reset killers
        for m in list(self.history):
            self.history[m] //= 4
        self.killers = [[None, None] for _ in range(MAX_PLY)]

        moves = gen_moves(board, turn)
        if not moves:
            return None
        best_move = moves[0]
        self.last_depth = 0
        if len(moves) == 1:
            return best_move

        # immediate win?
        for m in moves:
            _, res = apply_move(board, m, turn)
            if res is not None:
                return m

        root_moves, _ = self._order(board, turn, moves, None, 0)
        completed_depth = 0
        try:
            for depth in range(1, self.max_depth + 1):
                alpha, beta = -INF, INF
                best_this_iter = None
                best_score = -INF
                scores = {}
                for i, m in enumerate(root_moves):
                    child, res = apply_move(board, m, turn)
                    if i == 0 or not self.use_pvs:
                        score = self._child_score(child, res, turn, depth, -beta, -alpha, 1)
                    else:
                        score = self._child_score(child, res, turn, depth, -alpha - 1, -alpha, 1)
                        if alpha < score < beta:
                            score = self._child_score(child, res, turn, depth, -beta, -alpha, 1)
                    scores[m] = score
                    if score > best_score:
                        best_score = score
                        best_this_iter = m
                        # a fully searched move that beats the previous best
                        # of this iteration is trustworthy even if we stop now
                        best_move = m
                    if score > alpha:
                        alpha = score
                completed_depth = depth
                best_move = best_this_iter
                # best move first, the others by score
                root_moves = sorted(root_moves, key=lambda mv: (mv != best_move, -scores[mv]))
                if self.verbose:
                    print("depth %d best %s score %d nodes %d time %.2f" % (
                        depth, best_move, best_score, self.nodes, time.time() - start))
                if best_score >= WIN_SCORE - 100 or best_score <= -WIN_SCORE + 100:
                    break  # forced result found
        except TimeUp:
            pass
        self.last_depth = completed_depth
        self.last_nodes = self.nodes
        return best_move

    # ------------------------------------------------------------------
    def _child_score(self, child, res, turn, depth, alpha, beta, ply):
        """Score of a child position from the point of view of the side that moved."""
        if res is not None:
            # the mover just won
            return WIN_SCORE - ply
        opp = BLACK_TURN if turn == WHITE_TURN else WHITE_TURN
        return -self._negamax(child, opp, depth - 1, alpha, beta, ply)

    def _negamax(self, board, turn, depth, alpha, beta, ply):
        self.nodes += 1
        if (self.nodes & 1023) == 0 and time.time() > self.deadline:
            raise TimeUp()

        if depth <= 0:
            v = self.evaluate(board, turn)
            return v if turn == WHITE_TURN else -v

        key = position_key(board, turn)
        if key in self.seen:
            return 0  # repetition = draw

        alpha_orig = alpha
        tt_move = None
        entry = self.tt.get(key)
        if entry is not None:
            e_depth, e_val, e_flag, e_move = entry
            tt_move = e_move
            if e_depth >= depth:
                if e_flag == EXACT:
                    return e_val
                if e_flag == LOWER and e_val > alpha:
                    alpha = e_val
                elif e_flag == UPPER and e_val < beta:
                    beta = e_val
                if alpha >= beta:
                    return e_val

        moves = gen_moves(board, turn)
        if not moves:
            return -WIN_SCORE + ply  # cannot move: lose

        moves, tactical = self._order(board, turn, moves, tt_move, ply)
        opp = BLACK_TURN if turn == WHITE_TURN else WHITE_TURN
        best = -INF
        best_m = moves[0]
        use_pvs = self.use_pvs
        use_lmr = self.use_lmr and depth >= LMR_MIN_DEPTH
        self.seen.add(key)
        try:
            for i, m in enumerate(moves):
                child, res = apply_move(board, m, turn)
                if res is not None:
                    score = WIN_SCORE - ply - 1
                elif i == 0 or not use_pvs:
                    score = -self._negamax(child, opp, depth - 1, -beta, -alpha, ply + 1)
                else:
                    # LMR: late quiet moves get a reduced-depth null-window search first
                    reduction = 0
                    if use_lmr and i >= LMR_FULL_MOVES and m not in tactical:
                        reduction = 1 if i < 12 else 2
                    if reduction:
                        score = -self._negamax(child, opp, depth - 1 - reduction,
                                               -alpha - 1, -alpha, ply + 1)
                    else:
                        score = alpha + 1  # force the normal null-window search
                    if score > alpha:
                        score = -self._negamax(child, opp, depth - 1, -alpha - 1, -alpha, ply + 1)
                        if alpha < score < beta:
                            score = -self._negamax(child, opp, depth - 1, -beta, -alpha, ply + 1)
                if score > best:
                    best = score
                    best_m = m
                if score > alpha:
                    alpha = score
                if alpha >= beta:
                    self.history[m] = self.history.get(m, 0) + depth * depth
                    if self.use_killers and m not in tactical and ply < MAX_PLY:
                        k = self.killers[ply]
                        if k[0] != m:
                            k[1] = k[0]
                            k[0] = m
                    break
        finally:
            self.seen.discard(key)

        if best <= alpha_orig:
            flag = UPPER
        elif best >= beta:
            flag = LOWER
        else:
            flag = EXACT
        self.tt[key] = (depth, best, flag, best_m)
        return best

    # ------------------------------------------------------------------
    def _order(self, board, turn, moves, tt_move, ply):
        """Return (ordered moves, set of tactical moves)."""
        hist_get = self.history.get
        white = turn == WHITE_TURN
        is_camp = IS_CAMP
        is_edge = IS_EDGE
        neigh2 = NEIGH2
        if self.use_killers and ply < MAX_PLY:
            k1, k2 = self.killers[ply]
        else:
            k1 = k2 = None
        scored = []
        append = scored.append
        tactical = set()
        for m in moves:
            s, t = m
            sc = hist_get(m, 0)
            tac = False
            if m == tt_move:
                sc += TT_BONUS
            if white:
                if board[s] == KING:
                    sc += KING_MOVE_BONUS
                    tac = True  # king moves are never reduced
                    if is_edge[t]:
                        sc += ESCAPE_BONUS
                for n, beyond in neigh2[t]:
                    if board[n] == BLACK and beyond >= 0 and beyond != s:
                        bv = board[beyond]
                        if bv == WHITE or bv == KING or beyond == THRONE or is_camp[beyond]:
                            sc += CAPTURE_BONUS
                            tac = True
            else:
                for n, beyond in neigh2[t]:
                    v = board[n]
                    if v == WHITE:
                        if beyond >= 0 and beyond != s and (board[beyond] == BLACK or beyond == THRONE or is_camp[beyond]):
                            sc += CAPTURE_BONUS
                            tac = True
                    elif v == KING:
                        sc += KING_ATTACK_BONUS
                        tac = True
            if not tac:
                if m == k1:
                    sc += KILLER1_BONUS
                elif m == k2:
                    sc += KILLER2_BONUS
            if tac:
                tactical.add(m)
            append((sc, m))
        scored.sort(reverse=True)
        return [m for _, m in scored], tactical
