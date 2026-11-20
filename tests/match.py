"""
Engine-vs-engine match to measure whether a change is an improvement.

  python3 tests/match.py [n_openings] [budget_seconds] [workers] [--set key=value ...] [--depth D]

  --set     override evaluation weights of the NEW player for this match only,
            e.g.  --set king_attacker=100 black_blocker=50
            (names: see DEFAULT_WEIGHTS in evaluation.py)
  --depth   fixed search depth instead of a time budget (reproducible results)
  --opts    switch search enhancements of the NEW player, e.g. --opts lmr=0

Plays NEW (the current code in the repository root: search.py +
evaluation.py) against OLD, a frozen copy of a previous version stored in
baselines/<name>/ (default: baselines/v4). Choose another baseline with
the environment variable OLD, e.g.  OLD=v2 python3 tests/match.py 8 0.3
To freeze a new baseline, copy rules.py, evaluation.py and search.py into
baselines/<name>/ and make their imports relative (from .rules import ...).

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

import importlib
import rules as R
from search import Searcher as NewSearcher
from evaluation import DEFAULT_WEIGHTS, make_evaluate

OLD_NAME = os.environ.get('OLD', 'v4')
OldSearcher = importlib.import_module('baselines.%s.search' % OLD_NAME).Searcher

MAX_PLIES = 160


def make_opening(seed, plies=2):
    rng = random.Random(seed)
    board, turn = R.initial_board(), R.WHITE_TURN
    for _ in range(plies):
        board, _ = R.apply_move(board, rng.choice(R.gen_moves(board, turn)), turn)
        turn = 1 - turn
    return board, turn


def play(args):
    seed, new_is_white, budget, overrides, depth, opts = args
    board, turn = make_opening(seed)
    max_depth = depth if depth else 64
    if depth:
        budget = 10 ** 6  # depth limit, not time, stops the search
    new = NewSearcher(max_depth=max_depth, eval_fn=make_evaluate(overrides), **opts)
    old = OldSearcher(max_depth=max_depth)
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


def parse_cli(argv):
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument('n', nargs='?', type=int, default=8)
    p.add_argument('budget', nargs='?', type=float, default=0.3)
    p.add_argument('workers', nargs='?', type=int, default=2)
    p.add_argument('--set', nargs='*', default=[], metavar='KEY=VALUE')
    p.add_argument('--depth', type=int, default=0)
    p.add_argument('--opts', nargs='*', default=[], metavar='FLAG=0/1',
                   help="search switches of the NEW player, e.g. --opts lmr=0 pvs=1 killers=1")
    a = p.parse_args(argv)
    a.opts = {k: bool(int(v)) for k, v in (x.split('=') for x in a.opts)}
    overrides = {}
    for item in a.set:
        k, v = item.split('=')
        if k not in DEFAULT_WEIGHTS:
            p.error("unknown weight %r; valid: %s" % (k, ', '.join(sorted(DEFAULT_WEIGHTS))))
        overrides[k] = float(v)
    return a, overrides


if __name__ == '__main__':
    a, overrides = parse_cli(sys.argv[1:])
    n, budget, workers = a.n, a.budget, a.workers
    jobs = [(s, w, budget, overrides, a.depth, a.opts) for s in range(n) for w in (True, False)]
    total = 0.0
    as_white = as_black = 0.0
    print("NEW weights changed:", overrides or "none", "| search opts:", a.opts or "default",
          "| search:", ("depth %d" % a.depth) if a.depth else ("%.2fs per move" % budget), flush=True)
    with Pool(workers) as pool:
        for seed, nw, result, plies, sc in pool.imap_unordered(play, jobs):
            total += sc
            if nw:
                as_white += sc
            else:
                as_black += sc
            print("opening %2d NEW as %s: %-8s in %3d plies -> %.1f" % (
                seed, 'WHITE' if nw else 'BLACK', result, plies, sc), flush=True)
    print("NEW vs baseline %s" % OLD_NAME)
    print("NEW score: %.1f / %d  (as white %.1f/%d, as black %.1f/%d)" % (
        total, len(jobs), as_white, n, as_black, n))
