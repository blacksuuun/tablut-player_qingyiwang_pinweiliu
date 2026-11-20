"""
Offline tests (no server needed):
  python3 tests/selfplay.py random  [budget]   -> our player vs random, both colours
  python3 tests/selfplay.py self    [budget]   -> our player vs itself
"""
import os
import random
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import rules as R
from search import Searcher


def play_game(white_agent, black_agent, budget, max_plies=300, show=False):
    board = R.initial_board()
    turn = R.WHITE_TURN
    seen = {R.position_key(board, turn)}
    max_t = 0.0
    for ply in range(max_plies):
        agent = white_agent if turn == R.WHITE_TURN else black_agent
        legal = R.gen_moves(board, turn)
        if not legal:
            return ('BLACKWIN' if turn == R.WHITE_TURN else 'WHITEWIN'), ply, max_t
        t0 = time.time()
        move = agent(board, turn, budget, seen)
        dt = time.time() - t0
        max_t = max(max_t, dt)
        assert move in legal, "ILLEGAL MOVE %r" % (move,)
        board, res = R.apply_move(board, move, turn)
        if show:
            print(ply, R.cell_name(move[0]), R.cell_name(move[1]), "%.2fs" % dt)
        if res == R.WHITE_WIN:
            return 'WHITEWIN', ply + 1, max_t
        if res == R.BLACK_WIN:
            return 'BLACKWIN', ply + 1, max_t
        turn = R.BLACK_TURN if turn == R.WHITE_TURN else R.WHITE_TURN
        key = R.position_key(board, turn)
        if key in seen:
            return 'DRAW', ply + 1, max_t
        seen.add(key)
    return 'MAXPLIES', max_plies, max_t


def random_agent(board, turn, budget, seen):
    return random.choice(R.gen_moves(board, turn))


def make_ab_agent():
    s = Searcher()
    def agent(board, turn, budget, seen):
        return s.choose_move(board, turn, budget, seen)
    agent.searcher = s
    return agent


if __name__ == '__main__':
    mode = sys.argv[1] if len(sys.argv) > 1 else 'random'
    budget = float(sys.argv[2]) if len(sys.argv) > 2 else 1.0
    games = int(sys.argv[3]) if len(sys.argv) > 3 else 4
    random.seed(1)
    if mode == 'random':
        for g in range(games):
            r1 = play_game(make_ab_agent(), random_agent, budget)
            r2 = play_game(random_agent, make_ab_agent(), budget)
            print("AB as WHITE vs random:", r1, "| AB as BLACK vs random:", r2, flush=True)
    else:
        print(play_game(make_ab_agent(), make_ab_agent(), budget, show=True))
