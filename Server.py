# Server.py
import uvicorn
import uuid
import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from typing import Dict, List

app = FastAPI()

# ----- Helper classes -----
class PlayerConnection:
    def __init__(self, websocket: WebSocket, player_id: str, name: str = ""):
        self.websocket = websocket
        self.player_id = player_id
        self.name = name

class GameState:
    def __init__(self, game_id: str, p1: PlayerConnection, p2: PlayerConnection):
        self.game_id = game_id
        self.board = [["" for _ in range(3)] for _ in range(3)]
        self.turn = p1.player_id
        self.players = {
            p1.player_id: {"conn": p1, "mark": "X"},
            p2.player_id: {"conn": p2, "mark": "O"}
        }
        self.over = False
        self.winner = None

    def to_dict(self):
        return {
            "game_id": self.game_id,
            "board": self.board,
            "turn": self.turn,
            "over": self.over,
            "winner": self.winner
        }

# ----- In-memory storage (prototype only) -----
waiting_queue: List[PlayerConnection] = []
games: Dict[str, GameState] = {}
player_game_map: Dict[str, str] = {}  # player_id -> game_id

# ----- Utility funcs -----
def check_winner(board):
    lines = []
    for i in range(3):
        lines.append(board[i])  # row
        lines.append([board[0][i], board[1][i], board[2][i]])  # column
    lines.append([board[0][0], board[1][1], board[2][2]])
    lines.append([board[0][2], board[1][1], board[2][0]])
    for line in lines:
        if line[0] != "" and line[0] == line[1] == line[2]:
            return line[0]
    if all(board[r][c] != "" for r in range(3) for c in range(3)):
        return "DRAW"
    return None

async def send_json(ws: WebSocket, data: dict):
    await ws.send_json(data)

# ----- WebSocket endpoint -----
#hello
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    player_id = str(uuid.uuid4())
    player = PlayerConnection(websocket=websocket, player_id=player_id)
    await send_json(websocket, {"type": "connected", "player_id": player_id})
    try:
        while True:
            msg = await websocket.receive_json()
            msg_type = msg.get("type")
            if msg_type == "find_match":
                player.name = msg.get("name", "Anon")
                await handle_find_match(player)
            elif msg_type == "make_move":
                await handle_make_move(player, msg)
            elif msg_type == "leave":
                await handle_leave(player)
            else:
                await send_json(websocket, {"type":"error", "message":"unknown message type"})
    except WebSocketDisconnect:
        await handle_disconnect(player)
    except Exception as e:
        # unexpected exceptions
        try:
            await send_json(websocket, {"type":"error", "message": str(e)})
        except:
            pass
        await handle_disconnect(player)

# ----- Handlers -----
async def handle_find_match(player: PlayerConnection):
    if player.player_id in player_game_map:
        await send_json(player.websocket, {"type":"error","message":"Already in a game"})
        return
    if waiting_queue:
        other = waiting_queue.pop(0)
        game_id = str(uuid.uuid4())
        game = GameState(game_id, other, player)
        games[game_id] = game
        player_game_map[player.player_id] = game_id
        player_game_map[other.player_id] = game_id
        await send_json(other.websocket, {"type":"match_found", "game": game.to_dict(), "you": {"id": other.player_id, "mark":"X"}})
        await send_json(player.websocket, {"type":"match_found", "game": game.to_dict(), "you": {"id": player.player_id, "mark":"O"}})
    else:
        waiting_queue.append(player)
        await send_json(player.websocket, {"type":"waiting", "message":"Waiting for opponent..."})

async def handle_make_move(player: PlayerConnection, msg: dict):
    game_id = player_game_map.get(player.player_id)
    if not game_id:
        await send_json(player.websocket, {"type":"error", "message":"Not in a game"})
        return
    game = games.get(game_id)
    if not game or game.over:
        await send_json(player.websocket, {"type":"error", "message":"Game not available"})
        return
    if game.turn != player.player_id:
        await send_json(player.websocket, {"type":"error", "message":"Not your turn"})
        return
    r = int(msg.get("row"))
    c = int(msg.get("col"))
    if not (0 <= r < 3 and 0 <= c < 3):
        await send_json(player.websocket, {"type":"error", "message":"Invalid cell"})
        return
    if game.board[r][c] != "":
        await send_json(player.websocket, {"type":"error", "message":"Cell already taken"})
        return
    mark = game.players[player.player_id]["mark"]
    game.board[r][c] = mark
    win = check_winner(game.board)
    if win:
        game.over = True
        game.winner = "DRAW" if win == "DRAW" else mark
    else:
        other_id = [pid for pid in game.players if pid != player.player_id][0]
        game.turn = other_id
    # broadcast
    for pid, info in game.players.items():
        try:
            await send_json(info["conn"].websocket, {"type":"game_update", "game": game.to_dict()})
        except Exception:
            pass
    if game.over:
        # cleanup after small delay so clients receive message
        await asyncio.sleep(0.5)
        for pid in list(game.players.keys()):
            player_game_map.pop(pid, None)
        games.pop(game_id, None)

async def handle_leave(player: PlayerConnection):
    for i, p in enumerate(waiting_queue):
        if p.player_id == player.player_id:
            waiting_queue.pop(i)
            await send_json(player.websocket, {"type":"left_queue"})
            return
    game_id = player_game_map.get(player.player_id)
    if not game_id:
        await send_json(player.websocket, {"type":"ok", "message":"Not in a game"})
        return
    game = games.get(game_id)
    if not game:
        return
    other_id = [pid for pid in game.players if pid != player.player_id][0]
    game.over = True
    game.winner = game.players[other_id]["mark"]
    for pid, info in game.players.items():
        try:
            await send_json(info["conn"].websocket, {"type":"game_update", "game": game.to_dict()})
        except:
            pass
    for pid in list(game.players.keys()):
        player_game_map.pop(pid, None)
    games.pop(game_id, None)

async def handle_disconnect(player: PlayerConnection):
    for i, p in enumerate(waiting_queue):
        if p.player_id == player.player_id:
            waiting_queue.pop(i)
            return
    game_id = player_game_map.get(player.player_id)
    if not game_id:
        return
    game = games.get(game_id)
    if not game:
        return
    other_id = [pid for pid in game.players if pid != player.player_id][0]
    game.over = True
    game.winner = game.players[other_id]["mark"]
    for pid, info in game.players.items():
        try:
            await send_json(info["conn"].websocket, {"type":"game_update", "game": game.to_dict()})
        except:
            pass
    for pid in list(game.players.keys()):
        player_game_map.pop(pid, None)
    games.pop(game_id, None)

if __name__ == "__main__":
    uvicorn.run("Server:app", host="0.0.0.0", port=8000)
