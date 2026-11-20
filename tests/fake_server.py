"""
Minimal imitation of the official Java server (same framing + JSON format),
used only to test the networking code offline. The real Server.jar remains
the reference: always test with it in the VM too.
  python3 tests/fake_server.py [timeout]
"""
import json, os, socket, struct, sys, time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import rules as R
from player import read_string, write_string

NAMES = {R.EMPTY: 'EMPTY', R.WHITE: 'WHITE', R.BLACK: 'BLACK', R.KING: 'KING'}

def state_json(board, turn_name):
    rows = []
    for r in range(9):
        row = []
        for c in range(9):
            i = r * 9 + c
            v = NAMES[board[i]]
            if i == R.THRONE and board[i] == R.EMPTY:
                v = 'THRONE'
            row.append(v)
        rows.append(row)
    return json.dumps({'board': rows, 'turn': turn_name})

def main():
    timeout = float(sys.argv[1]) if len(sys.argv) > 1 else 5
    socks = []
    for port in (5800, 5801):
        s = socket.socket(); s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(('127.0.0.1', port)); s.listen(1); socks.append(s)
    w, _ = socks[0].accept(); wname = json.loads(read_string(w))
    b, _ = socks[1].accept(); bname = json.loads(read_string(b))
    print("white:", wname, "black:", bname, flush=True)
    board = R.initial_board(); turn = R.WHITE_TURN
    seen = {R.position_key(board, turn)}
    names = {R.WHITE_TURN: 'WHITE', R.BLACK_TURN: 'BLACK'}
    for c in (w, b): write_string(c, state_json(board, 'WHITE'))
    ply = 0
    while True:
        conn = w if turn == R.WHITE_TURN else b
        t0 = time.time()
        conn.settimeout(timeout)
        try:
            act = json.loads(read_string(conn))
        except socket.timeout:
            print("TIMEOUT by", names[turn]); result = 'BLACKWIN' if turn == R.WHITE_TURN else 'WHITEWIN'
            for c in (w, b): write_string(c, state_json(board, result))
            break
        dt = time.time() - t0
        mv = (R.parse_cell(act['from']), R.parse_cell(act['to']))
        assert act['turn'] == names[turn], act
        if mv not in R.gen_moves(board, turn):
            print("ILLEGAL", act); break
        board, res = R.apply_move(board, mv, turn)
        ply += 1
        turn = R.BLACK_TURN if turn == R.WHITE_TURN else R.WHITE_TURN
        if res == R.WHITE_WIN: tn = 'WHITEWIN'
        elif res == R.BLACK_WIN: tn = 'BLACKWIN'
        elif R.position_key(board, turn) in seen: tn = 'DRAW'
        elif not R.gen_moves(board, turn): tn = 'BLACKWIN' if turn == R.WHITE_TURN else 'WHITEWIN'
        else: tn = names[turn]
        seen.add(R.position_key(board, turn))
        print(ply, act['turn'], act['from'], act['to'], "%.2fs" % dt, flush=True)
        for c in (w, b): write_string(c, state_json(board, tn))
        if tn not in ('WHITE', 'BLACK'):
            print("RESULT", tn, flush=True); break
        if ply >= 400:
            print("too long"); break
    time.sleep(0.5)

main()
