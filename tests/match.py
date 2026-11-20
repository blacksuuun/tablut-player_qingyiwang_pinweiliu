"""
Engine-vs-engine match to measure whether a change is an improvement.

  python3 tests/match.py [n_openings] [budget_seconds] [workers]

Plays NEW (current evaluation.py) against OLD (tests/eval_v1.py).
Each opening (2 random plies from the start position) is played twice,
swapping colours, so the result is fair. Win = 1, draw = 0.5.
"""
import os
import random
import sys
from multiprocessing import Pool

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..'))
sys.path.insert(0, HERE)

import rules as R
from search import Searcher
import evaluation as eval_new
import importlib
eval_old = importlib.import_module(os.environ.get('OLD', 'eval_v1'))

MAX_PLIES = 160


def make_opening(seed, plies=2):
    rng = random.Random(seed)
    board, turn = R.initial_board(), R.WHITE_TURN
    for _ in range(plies):
        board, _ = R.apply_move(board, rng.choice(R.gen_moves(board, turn)), turn)
        turn = 1 - turn
    return board, turn


def play(args):
    seed, new_is_white, budget = args
    board, turn = make_opening(seed)
    new = Searcher(eval_fn=eval_new.evaluate)
    old = Searcher(eval_fn=eval_old.evaluate)
    players = {R.WHITE_TURN: new if new_is_white else old,
               R.BLACK_TURN: old if new_is_white else new}
    seen = {R.position_key(board, turn)}
    result = 'DRAW'
    for ply in range(MAX_PLIES):
        legal = R.gen_moves(board, turn)
        if not legal:
            result = 'BLACKWIN' if turn == R.WHITE_TURN else 'WHITEWIN'
            break
        move = players[turn].choose_move(board, turn, budget, seen)
        assert move in legal
        board, res = R.apply_move(board, move, turn)
        if res == R.WHITE_WIN:
            result = 'WHITEWIN'; break
        if res == R.BLACK_WIN:
            result = 'BLACKWIN'; break
        turn = 1 - turn
        key = R.position_key(board, turn)
        if key in seen:
            result = 'DRAW'; break
        seen.add(key)
    if result == 'DRAW':
        new_score = 0.5
    else:
        new_won = (result == 'WHITEWIN') == new_is_white
        new_score = 1.0 if new_won else 0.0
    return seed, new_is_white, result, ply + 1, new_score


if __name__ == '__main__':
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 6
    budget = float(sys.argv[2]) if len(sys.argv) > 2 else 0.3
    workers = int(sys.argv[3]) if len(sys.argv) > 3 else 2
    jobs = [(s, w, budget) for s in range(n) for w in (True, False)]
    total = 0.0
    as_white = as_black = 0.0
    with Pool(workers) as pool:
        for seed, nw, result, plies, sc in pool.imap_unordered(play, jobs):
            total += sc
            if nw:
                as_white += sc
            else:
                as_black += sc
            print("opening %2d NEW as %s: %-8s in %3d plies -> %.1f" % (
                seed, 'WHITE' if nw else 'BLACK', result, plies, sc), flush=True)
    print("NEW score: %.1f / %d  (as white %.1f/%d, as black %.1f/%d)" % (
        total, len(jobs), as_white, n, as_black, n))
