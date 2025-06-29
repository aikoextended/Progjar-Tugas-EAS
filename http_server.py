import sys
import os.path
import uuid
from glob import glob
from datetime import datetime
import json
import time
import queue
import copy
from enum import Enum

class GameState(Enum):
    WAITING = "waiting"
    PLAYING = "playing"
    GAME_OVER = "game_over"

class PieceType(Enum):
    REGULAR = "regular"
    KING = "king"

class CheckersGame:
    def __init__(self, game_id):
        self.game_id = game_id
        self.players = {}
        self.board = [[None for _ in range(8)] for _ in range(8)]
        self.current_player = 1
        self.state = GameState.WAITING
        self.score = {"player1": 0, "player2": 0}
        self.lives = {"player1": 12, "player2": 12}
        self.start_time = None
        self.game_time = 0
        self.winner = None
        self.restart_requests = set()  # Track which players want to restart

        self.initialize_board()

    def initialize_board(self):
        for row in range(8):
            for col in range(8):
                if (row + col) % 2 == 1:
                    if row < 3:
                        self.board[row][col] = {"player": 1, "type": PieceType.REGULAR.value}
                    elif row > 4:
                        self.board[row][col] = {"player": 2, "type": PieceType.REGULAR.value}

    def add_player(self, player_id):
        if len(self.players) < 2:
            game_position = len(self.players) + 1
            self.players[player_id] = {"id": player_id, "game_position": game_position}
            if len(self.players) == 2:
                self.start_game()
            return True
        return False

    def start_game(self):
        self.state = GameState.PLAYING
        self.start_time = time.time()
        self.current_player = 1 

    def restart_game(self):
        """Restart the game with the same players"""
        # Reset game state
        self.board = [[None for _ in range(8)] for _ in range(8)]
        self.current_player = 1
        self.state = GameState.PLAYING
        self.score = {"player1": 0, "player2": 0}
        self.lives = {"player1": 12, "player2": 12}
        self.start_time = time.time()
        self.game_time = 0
        self.winner = None
        self.restart_requests.clear()  # Clear restart requests
        
        # Reinitialize board with pieces
        self.initialize_board()
        
        print(f"Game {self.game_id} restarted with players: {list(self.players.keys())}")

    def request_restart(self, player_id):
        """Handle restart request from a player"""
        if player_id not in self.players:
            return {"status": "error", "message": "Player not in this game"}
        
        # Add player to restart requests
        self.restart_requests.add(player_id)
        
        # Check if both players want to restart
        if len(self.restart_requests) == 2:
            # Both players agreed, restart the game
            self.restart_game()
            return {"status": "game_restarted"}
        else:
            # Still waiting for other player
            return {"status": "restart_requested", "waiting_for": len(self.players) - len(self.restart_requests)}

    def get_state(self, player_id=None):
        self.update_game_time()
        board_serializable = copy.deepcopy(self.board)

        player_info = self.players.get(player_id)
        my_game_position = player_info.get('game_position') if player_info else None

        return {
            "type": "game_update",
            "game_id": self.game_id,
            "board": board_serializable,
            "current_player": self.current_player,
            "score": self.score,
            "lives": self.lives,
            "game_time": self.game_time,
            "game_state": self.state.value,
            "winner": self.winner,
            "player_id": player_id,
            "my_player_number": my_game_position,
            "your_turn": self.current_player == my_game_position if my_game_position else False,
            "restart_requests": len(self.restart_requests),  # Include restart status
            "restart_requested_by_me": player_id in self.restart_requests if player_id else False
        }
    
    def update_game_time(self):
        if self.start_time and self.state != GameState.GAME_OVER:
            self.game_time = int(time.time() - self.start_time)


    def get_valid_moves(self, row, col):
        if not self.board[row][col]:
            return []

        piece = self.board[row][col]
        valid_moves = []
        mandatory_jumps = []

        if piece["type"] == PieceType.KING.value:
            directions = [(-1, -1), (-1, 1), (1, -1), (1, 1)]
        else:
            if piece["player"] == 1:
                directions = [(1, -1), (1, 1)]
            else:
                directions = [(-1, -1), (-1, 1)]

        for dr, dc in directions:
            new_row, new_col = row + dr, col + dc
            if 0 <= new_row < 8 and 0 <= new_col < 8:
                if (self.board[new_row][new_col] and
                        self.board[new_row][new_col]["player"] != piece["player"]):
                    jump_row, jump_col = new_row + dr, new_col + dc
                    if (0 <= jump_row < 8 and 0 <= jump_col < 8 and
                            not self.board[jump_row][jump_col]):
                        mandatory_jumps.append((jump_row, jump_col, True))

        if mandatory_jumps:
            return mandatory_jumps

        for dr, dc in directions:
            new_row, new_col = row + dr, col + dc
            if 0 <= new_row < 8 and 0 <= new_col < 8:
                if not self.board[new_row][new_col]:
                    valid_moves.append((new_row, new_col, False))

        return valid_moves


    def make_move(self, player_id, from_pos, to_pos):
        player_info = self.players.get(player_id)
        if not player_info or self.state != GameState.PLAYING or player_info['game_position'] != self.current_player:
            return False

        from_row, from_col = from_pos
        to_row, to_col = to_pos

        has_mandatory_jumps = False
        for r in range(8):
            for c in range(8):
                if self.board[r][c] and self.board[r][c]["player"] == self.current_player:
                    moves = self.get_valid_moves(r, c)
                    if any(move[2] for move in moves):
                        has_mandatory_jumps = True
                        break
            if has_mandatory_jumps:
                break

        valid_moves = self.get_valid_moves(from_row, from_col)
        
        is_jump = False
        move_found = False
        for move_row, move_col, jump in valid_moves:
            if move_row == to_row and move_col == to_col:
                is_jump = jump
                move_found = True
                break

        if not move_found:
            return False

        if has_mandatory_jumps and not is_jump:
            return False

        piece = self.board[from_row][from_col]
        self.board[to_row][to_col] = piece
        self.board[from_row][from_col] = None

        if is_jump:
            captured_row = (from_row + to_row) // 2
            captured_col = (from_col + to_col) // 2
            captured_piece = self.board[captured_row][captured_col]
            self.board[captured_row][captured_col] = None

            if captured_piece:
                opponent_position = 2 if self.current_player == 1 else 1
                self.score[f"player{self.current_player}"] += 1
                self.lives[f"player{opponent_position}"] -= 1

            additional_jumps = [move for move in self.get_valid_moves(to_row, to_col) if move[2]]
            if additional_jumps:
                self.broadcast_game_update()
                return True

        if piece["player"] == 1 and to_row == 7:
            piece["type"] = PieceType.KING.value
        elif piece["player"] == 2 and to_row == 0:
            piece["type"] = PieceType.KING.value

        if self.lives["player1"] == 0:
            self.end_game(2)
        elif self.lives["player2"] == 0:
            self.end_game(1)
        else:
            self.current_player = 2 if self.current_player == 1 else 1
        
        self.broadcast_game_update()
        return True

    def end_game(self, winner):
        self.state = GameState.GAME_OVER
        self.winner = winner

    def broadcast_game_update(self):
        pass


class HttpServer:
    def __init__(self):
        self.sessions = {}
        self.types = {'.pdf': 'application/pdf', '.jpg': 'image/jpeg', '.txt': 'text/plain', '.html': 'text/html'}
        self.games = {}
        self.waiting_players = queue.Queue()
        self.client_games = {}
        self.next_game_id = 1

    def response(self, kode=404, message='Not Found', messagebody=b'', headers={}):
        tanggal = datetime.now().strftime('%c')
        resp = [
            f"HTTP/1.0 {kode} {message}\r\n",
            f"Date: {tanggal}\r\n",
            "Connection: close\r\n",
            "Server: myserver/1.0\r\n",
            f"Content-Length: {len(messagebody)}\r\n"
        ]
        for kk, vv in headers.items():
            resp.append(f"{kk}: {vv}\r\n")
        resp.append("\r\n")

        response_headers = "".join(resp)
        
        if isinstance(messagebody, str):
            messagebody = messagebody.encode()
            
        return response_headers.encode() + messagebody

    def proses(self, data):
        requests = data.split("\r\n")
        baris = requests[0]
        all_headers = [n for n in requests[1:] if n]
        
        try:
            method, object_address, _ = baris.split(" ")
            if method.upper() == 'GET':
                return self.http_get(object_address, all_headers)
            if method.upper() == 'POST':
                content_length = 0
                for header in all_headers:
                    if header.lower().startswith('content-length'):
                        content_length = int(header.split(':')[1].strip())
                
                body_start = data.find('\r\n\r\n') + 4
                body = data[body_start:body_start + content_length]
                return self.http_post(object_address, all_headers, body)
            else:
                return self.response(400, 'Bad Request', '', {})
        except ValueError:
            return self.response(400, 'Bad Request', '', {})

    def http_get(self, object_address, headers):
        if object_address.startswith('/game_state'):
            params = self.parse_query_params(object_address)
            game_id = params.get('game_id')
            player_id = params.get('player_id')
            game = self.games.get(game_id)
            if game:
                return self.response(200, 'OK', json.dumps(game.get_state(player_id)), {'Content-Type': 'application/json'})
            return self.response(404, 'Not Found', 'Game not found', {})

        elif object_address.startswith('/check_status'):
            params = self.parse_query_params(object_address)
            player_id = params.get('player_id')

            # Check if this player has been assigned to a game
            game_id = self.client_games.get(player_id)

            if game_id:
                response_data = {'status': 'game_started', 'game_id': game_id}
            else:
                response_data = {'status': 'waiting'}

            return self.response(200, 'OK', json.dumps(response_data), {'Content-Type': 'application/json'})

        # Default GET handling
        if object_address == '/':
            return self.response(200, 'OK', 'Checkers Game Server is running.', {})

        return self.response(404, 'Not Found', '', {})

    def http_post(self, object_address, headers, body):
        try:
            payload = json.loads(body) if body else {}
        except json.JSONDecodeError:
            return self.response(400, 'Bad Request', 'Invalid JSON', {})

        if object_address == '/join_game':
            player_id = str(uuid.uuid4())
            self.waiting_players.put(player_id)

            if self.waiting_players.qsize() >= 2:
                p1_id = self.waiting_players.get()
                p2_id = self.waiting_players.get()
                
                game_id = str(self.next_game_id)
                self.next_game_id += 1
                game = CheckersGame(game_id)
                game.add_player(p1_id)
                game.add_player(p2_id)
                self.games[game_id] = game
                self.client_games[p1_id] = game_id
                self.client_games[p2_id] = game_id
                
                response_data = {'player_id': player_id, 'game_id': game_id, 'status': 'game_started'}
            else:
                response_data = {'player_id': player_id, 'status': 'waiting_for_opponent'}
            
            return self.response(200, 'OK', json.dumps(response_data), {'Content-Type': 'application/json'})

        elif object_address == '/make_move':
            game_id = payload.get('game_id')
            player_id = payload.get('player_id')
            from_pos = payload.get('from')
            to_pos = payload.get('to')
            game = self.games.get(game_id)

            if game and game.make_move(player_id, tuple(from_pos), tuple(to_pos)):
                return self.response(200, 'OK', json.dumps(game.get_state(player_id)), {'Content-Type': 'application/json'})
            else:
                return self.response(400, 'Bad Request', 'Invalid move', {})

        elif object_address == '/restart_game':
            game_id = payload.get('game_id')
            player_id = payload.get('player_id')
            
            # Validate that the game exists and player is part of it
            game = self.games.get(game_id)
            if not game:
                return self.response(404, 'Not Found', 'Game not found', {})
            
            if player_id not in game.players:
                return self.response(403, 'Forbidden', 'Player not in this game', {})
            
            # Request restart (requires both players' consent)
            result = game.request_restart(player_id)
            
            if result["status"] == "game_restarted":
                print(f"Game {game_id} restarted - both players agreed")
                # Return the new game state
                return self.response(200, 'OK', json.dumps(game.get_state(player_id)), {'Content-Type': 'application/json'})
            elif result["status"] == "restart_requested":
                print(f"Game {game_id}: Player {player_id} requested restart, waiting for other player")
                return self.response(200, 'OK', json.dumps(result), {'Content-Type': 'application/json'})
            else:
                return self.response(400, 'Bad Request', json.dumps(result), {'Content-Type': 'application/json'})
        
        return self.response(404, 'Not Found', '', {})

    def parse_query_params(self, path):
        params = {}
        if '?' in path:
            query_string = path.split('?')[1]
            for part in query_string.split('&'):
                key, value = part.split('=')
                params[key] = value
        return params

if __name__ == "__main__":
    httpserver = HttpServer()
    join_request = 'POST /join_game HTTP/1.0\r\n\r\n'
    response = httpserver.proses(join_request)
    print(response.decode(errors='ignore'))