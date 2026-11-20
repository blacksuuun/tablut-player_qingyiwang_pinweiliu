#!/usr/bin/env python3
"""
Tablut player for the UniBo Tablut Challenge.

Usage:
    python3 player.py <WHITE|BLACK> <timeout_seconds> <server_ip> [options]

Mandatory parameters (in this order, role is case-insensitive):
    role       WHITE or BLACK
    timeout    seconds available for each move (as given by the referee)
    server_ip  IP address of the server

Optional parameters (all have defaults used during the competition):
    --name NAME      player name sent to the server
    --margin SEC     safety margin subtracted from the timeout (default: auto)
    --verbose        print search information to stderr
"""
import argparse
import json
import socket
import struct
import sys
import time

import rules
from search import Searcher

DEFAULT_NAME = "aBC4"
WHITE_PORT = 5800
BLACK_PORT = 5801


# ---------------- networking (same framing as the Java client) ----------------

def recv_all(sock, n):
    data = b''
    while len(data) < n:
        packet = sock.recv(n - len(data))
        if not packet:
            raise ConnectionError("server closed the connection")
        data += packet
    return data


def read_string(sock):
    length = struct.unpack('>i', recv_all(sock, 4))[0]
    return recv_all(sock, length).decode('utf-8')


def write_string(sock, s):
    data = s.encode('utf-8')
    sock.sendall(struct.pack('>i', len(data)) + data)


# ---------------------------------------------------------------------------

def parse_args(argv):
    p = argparse.ArgumentParser(description="Tablut player (alpha-beta)")
    p.add_argument('role', help="WHITE or BLACK (case-insensitive)")
    p.add_argument('timeout', type=float, help="seconds per move")
    p.add_argument('server_ip', help="server IP address")
    p.add_argument('--name', default=DEFAULT_NAME)
    p.add_argument('--margin', type=float, default=None)
    p.add_argument('--verbose', action='store_true')
    args = p.parse_args(argv)
    role = args.role.strip().upper()
    if role not in ('WHITE', 'BLACK'):
        p.error("role must be WHITE or BLACK, got %r" % args.role)
    args.role = role
    if args.timeout <= 0:
        p.error("timeout must be positive")
    return args


def time_budget(timeout, margin):
    """Seconds we allow the search to use for one move."""
    if margin is None:
        # keep ~12% + 1.5s for communication, process scheduling, GC...
        margin = 0.12 * timeout + 1.5
    return max(0.3, timeout - margin)


def log(verbose, *a):
    if verbose:
        print(*a, file=sys.stderr, flush=True)


def play(args):
    my_turn = rules.WHITE_TURN if args.role == 'WHITE' else rules.BLACK_TURN
    port = WHITE_PORT if my_turn == rules.WHITE_TURN else BLACK_PORT
    budget = time_budget(args.timeout, args.margin)
    searcher = Searcher(verbose=args.verbose)
    seen_positions = set()

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        sock.connect((args.server_ip, port))
        write_string(sock, json.dumps(args.name))
        log(args.verbose, "connected as %s (%s), budget %.1fs" % (args.name, args.role, budget))

        while True:
            state = json.loads(read_string(sock))
            board = rules.board_from_json(state)
            turn = rules.turn_from_json(state)
            seen_positions.add(rules.position_key(board, turn))

            if turn in (rules.WHITE_WIN, rules.BLACK_WIN, rules.DRAW):
                log(args.verbose, "game over:", state['turn'])
                return
            if turn != my_turn:
                continue  # opponent's turn: just wait for the next state

            t0 = time.time()
            move = None
            try:
                move = searcher.choose_move(board, turn, budget, seen_positions)
            except Exception as e:  # never lose because of a bug in the search
                log(args.verbose, "search error:", repr(e))
            if move is None:
                legal = rules.gen_moves(board, turn)
                if not legal:
                    log(args.verbose, "no legal moves")
                    return
                move = legal[0]
            write_string(sock, json.dumps(rules.move_to_json(move, turn)))
            log(args.verbose, "move %s->%s depth %s nodes %s in %.2fs" % (
                rules.cell_name(move[0]), rules.cell_name(move[1]),
                getattr(searcher, 'last_depth', '?'), getattr(searcher, 'last_nodes', '?'),
                time.time() - t0))


def main(argv=None):
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        play(args)
    except (ConnectionError, OSError) as e:
        log(args.verbose, "connection ended:", repr(e))


if __name__ == '__main__':
    main()
