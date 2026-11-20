"""
Offline opening-book generator.

The first moves of a game are always searched from the same few positions,
so we can analyse them once, offline, with much more time than the 60 s
available during a match, and store the answers in opening_book.json.

Positions analysed:
  1. the start position (White to move)                        ->  1 search
  2. every position after one White move (Black to move)       -> 56 searches
  3. after OUR book first move, every Black reply (White to move) -> ~80 searches

Run from the repository root (e.g. overnight on a multi-core PC):
  python3 tests/make_book.py --seconds 120 --workers 8

The player loads opening_book.json automatically if it exists (and checks
that every book move is legal before playing it).
"""
import argparse
import json
import os
import sys
import time
from multiprocessing import Pool

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..')
sys.path.insert(0, ROOT)

import rules as R
from search import Searcher


def analyse(job):
    key_hex, board_bytes, turn, seconds = job
    board = bytearray(board_bytes)
    s = Searcher()
    move = s.choose_move(board, turn, seconds, {R.position_key(board, turn)})
    return key_hex, R.cell_name(move[0]), R.cell_name(move[1]), s.last_depth


def run(pool, jobs, book, out_path, label):
    t0 = time.time()
    done = 0
    for key_hex, frm, to, depth in pool.imap_unordered(analyse, jobs):
        book[key_hex] = [frm, to]
        done += 1
        print("%s %d/%d  %s->%s (depth %d)  %.0fs" % (
            label, done, len(jobs), frm, to, depth, time.time() - t0), flush=True)
        with open(out_path, 'w') as f:  # save progress after every position
            json.dump(book, f)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--seconds', type=float, default=120, help="search time per position")
    ap.add_argument('--workers', type=int, default=os.cpu_count() or 2)
    ap.add_argument('--out', default=os.path.join(ROOT, 'opening_book.json'))
    args = ap.parse_args()

    book = {}
    start = R.initial_board()
    W, B = R.WHITE_TURN, R.BLACK_TURN

    with Pool(args.workers) as pool:
        # 1) our first move as White (alone: it can use the whole machine time)
        key0 = R.position_key(start, W).hex()
        run(pool, [(key0, bytes(start), W, args.seconds * 2)], book, args.out, "white-1")
        first = (R.parse_cell(book[key0][0]), R.parse_cell(book[key0][1]))

        # 2) our reply as Black to every White first move
        jobs = []
        for m in R.gen_moves(start, W):
            b1, _ = R.apply_move(start, m, W)
            jobs.append((R.position_key(b1, B).hex(), bytes(b1), B, args.seconds))
        run(pool, jobs, book, args.out, "black-1")

        # 3) our second move as White after our book move and every Black reply
        b1, _ = R.apply_move(start, first, W)
        jobs = []
        for m in R.gen_moves(b1, B):
            b2, res = R.apply_move(b1, m, B)
            if res is None:
                jobs.append((R.position_key(b2, W).hex(), bytes(b2), W, args.seconds))
        run(pool, jobs, book, args.out, "white-2")

    print("book with %d positions written to %s" % (len(book), args.out))


if __name__ == '__main__':
    main()
