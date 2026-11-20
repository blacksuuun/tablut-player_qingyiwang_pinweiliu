"""
Evolutionary tuning of the evaluation weights.

Genome  : the weights of evaluation.DEFAULT_WEIGHTS
Fitness : score (win 1, draw 0.5) of the individual against the frozen
          baseline (baselines/v3 by default, env OLD=...) over several openings, both colours.
          Fixed-depth search is used so that results are reproducible and
          independent of CPU load.
Algorithm: elitist GA - keep the best `elite` individuals, fill the rest of
          the population with uniform crossover of two tournament-selected
          parents + multiplicative Gaussian mutation (w *= exp(sigma * N(0,1))).
          The openings change every generation (less overfitting) but are the
          same for all individuals of a generation (fair comparison).

Run (from the repository root):
  python3 tests/evolve.py --pop 12 --gens 10 --openings 6 --depth 3 --workers 8

Results are written to ea_results/: a log per generation (log.csv) and the
best weights found (best_weights.json).
"""
import argparse
import csv
import json
import math
import os
import random
import sys
import time
from multiprocessing import Pool

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..')
sys.path.insert(0, ROOT)

import rules as R
from evaluation import DEFAULT_WEIGHTS, make_evaluate
from search import Searcher
import importlib
BASELINE = os.environ.get('OLD', 'v3')
BaselineSearcher = importlib.import_module('baselines.%s.search' % BASELINE).Searcher

KEYS = sorted(DEFAULT_WEIGHTS)
MAX_PLIES = 160
BIG_BUDGET = 10 ** 6   # seconds: depth limit, not time, stops the search


def make_opening(seed, plies=2):
    rng = random.Random(seed)
    board, turn = R.initial_board(), R.WHITE_TURN
    for _ in range(plies):
        board, _ = R.apply_move(board, rng.choice(R.gen_moves(board, turn)), turn)
        turn = 1 - turn
    return board, turn


def play_one(job):
    """Play one game: individual (weights) vs baseline. Returns (ind, score)."""
    ind, weights, opening_seed, ind_is_white, depth = job
    board, turn = make_opening(opening_seed)
    me = Searcher(max_depth=depth, eval_fn=make_evaluate(weights))
    base = BaselineSearcher(max_depth=depth)
    players = {R.WHITE_TURN: me if ind_is_white else base,
               R.BLACK_TURN: base if ind_is_white else me}
    seen = {R.position_key(board, turn)}
    winner = None
    for _ in range(MAX_PLIES):
        legal = R.gen_moves(board, turn)
        if not legal:
            winner = 1 - turn
            break
        move = players[turn].choose_move(board, turn, BIG_BUDGET, seen)
        board, res = R.apply_move(board, move, turn)
        if res == R.WHITE_WIN:
            winner = R.WHITE_TURN; break
        if res == R.BLACK_WIN:
            winner = R.BLACK_TURN; break
        turn = 1 - turn
        key = R.position_key(board, turn)
        if key in seen:
            break  # draw by repetition
        seen.add(key)
    if winner is None:
        return ind, 0.5
    my_colour = R.WHITE_TURN if ind_is_white else R.BLACK_TURN
    return ind, 1.0 if winner == my_colour else 0.0


def mutate(w, sigma, rng, rate=0.5):
    child = dict(w)
    for k in KEYS:
        if rng.random() < rate:
            child[k] = max(1, int(round(child[k] * math.exp(sigma * rng.gauss(0, 1)))))
    return child


def crossover(a, b, rng):
    return {k: (a[k] if rng.random() < 0.5 else b[k]) for k in KEYS}


def tournament(pop, fit, rng, k=3):
    best = None
    for i in rng.sample(range(len(pop)), min(k, len(pop))):
        if best is None or fit[i] > fit[best]:
            best = i
    return pop[best]


def evaluate_population(pool, pop, gen, args):
    seeds = [10000 * (gen + 1) + i for i in range(args.openings)]
    jobs = [(i, w, s, white, args.depth)
            for i, w in enumerate(pop) for s in seeds for white in (True, False)]
    scores = [0.0] * len(pop)
    for ind, sc in pool.imap_unordered(play_one, jobs):
        scores[ind] += sc
    n_games = 2 * args.openings
    return [s / n_games for s in scores]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pop', type=int, default=12)
    ap.add_argument('--gens', type=int, default=10)
    ap.add_argument('--elite', type=int, default=3)
    ap.add_argument('--openings', type=int, default=6)
    ap.add_argument('--depth', type=int, default=3)
    ap.add_argument('--sigma', type=float, default=0.3)
    ap.add_argument('--workers', type=int, default=os.cpu_count() or 2)
    ap.add_argument('--seed', type=int, default=42)
    ap.add_argument('--out', default=os.path.join(ROOT, 'ea_results'))
    args = ap.parse_args()

    rng = random.Random(args.seed)
    os.makedirs(args.out, exist_ok=True)
    log_path = os.path.join(args.out, 'log.csv')

    # initial population: the current weights + mutated copies
    pop = [dict(DEFAULT_WEIGHTS)]
    while len(pop) < args.pop:
        pop.append(mutate(DEFAULT_WEIGHTS, args.sigma * 1.5, rng, rate=0.7))

    best_ever, best_ever_fit = dict(DEFAULT_WEIGHTS), -1.0
    with Pool(args.workers) as pool, open(log_path, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['gen', 'best_fit', 'mean_fit', 'default_fit'] + KEYS)
        for gen in range(args.gens):
            t0 = time.time()
            fit = evaluate_population(pool, pop, gen, args)
            order = sorted(range(len(pop)), key=lambda i: -fit[i])
            best = pop[order[0]]
            default_fit = next((fit[i] for i, w in enumerate(pop) if w == DEFAULT_WEIGHTS), float('nan'))
            writer.writerow([gen, '%.3f' % fit[order[0]], '%.3f' % (sum(fit) / len(fit)),
                             '%.3f' % default_fit] + [best[k] for k in KEYS])
            f.flush()
            print("gen %2d  best %.3f  mean %.3f  (%.0fs)  %s" % (
                gen, fit[order[0]], sum(fit) / len(fit), time.time() - t0,
                json.dumps(best, sort_keys=True)), flush=True)
            if fit[order[0]] > best_ever_fit:
                best_ever, best_ever_fit = dict(best), fit[order[0]]
                with open(os.path.join(args.out, 'best_weights.json'), 'w') as bf:
                    json.dump({'fitness_vs_baseline': best_ever_fit, 'generation': gen,
                               'weights': best_ever}, bf, indent=2, sort_keys=True)
            # next generation
            new_pop = [pop[i] for i in order[:args.elite]]
            while len(new_pop) < args.pop:
                child = crossover(tournament(pop, fit, rng), tournament(pop, fit, rng), rng)
                new_pop.append(mutate(child, args.sigma, rng))
            pop = new_pop
    print("best fitness %.3f, weights saved in %s" % (best_ever_fit, args.out))


if __name__ == '__main__':
    main()
