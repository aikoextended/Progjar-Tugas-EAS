import socket
import threading
import json
import time
import queue
import multiprocessing
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
from enum import Enum
import copy
import argparse

class ProcessingModel(Enum):
    THREAD = "thread"
    PROCESS = "process"
    POOL = "pool"

class PieceType(Enum):
    REGULAR = "regular"
    KING = "king"

class GameState(Enum):
    WAITING = "waiting"
    PLAYING = "playing"
    GAME_OVER = "game_over"

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
        self.lock = threading.Lock()
        
        # Initialize board
        self.initialize_board()
        
    def initialize_board(self):
        """Initialize the checkers board with pieces"""
        for row in range(8):
            for col in range(8):
                if (row + col) % 2 == 1:  # Dark squares only
                    if row < 3:
                        self.board[row][col] = {"player": 1, "type": "regular"}
                    elif row > 4:
                        self.board[row][col] = {"player": 2, "type": "regular"}
                        
    def add_player(self, player_id, client_socket):
        """Add a player to the game"""
        with self.lock:
            if len(self.players) < 2:
                # Assign game position (1 or 2) based on order
                game_position = len(self.players) + 1
                self.players[player_id] = {
                    "socket": client_socket,
                    "id": player_id,
                    "game_position": game_position
                }
                
                if len(self.players) == 2:
                    self.start_game()
                    
                return True
            return False
            
    def start_game(self):
        """Start the game"""
        self.state = GameState.PLAYING
        self.start_time = time.time()
        
        # Get first player (whoever joined first)
        first_player_id = list(self.players.keys())[0]
        self.current_player = first_player_id
        
        # Notify all players
        for player_id, player in self.players.items():
            message = {
                "type": "game_start",
                "board": self.board,
                "current_player": self.current_player
            }
            self.send_to_player(player_id, message)
            
    def update_game_time(self):
        """Update game time"""
        if self.start_time:
            self.game_time = int(time.time() - self.start_time)
            
    def get_valid_moves(self, row, col):
        """Get valid moves for a piece"""
        if not self.board[row][col]:
            return []
            
        piece = self.board[row][col]
        valid_moves = []
        
        # Direction depends on player and piece type
        if piece["type"] == "king":  # Changed from PieceType.KING.value
            directions = [(-1, -1), (-1, 1), (1, -1), (1, 1)]
        else:
            if piece["player"] == 1:
                directions = [(1, -1), (1, 1)]
            else:
                directions = [(-1, -1), (-1, 1)]
                
        for dr, dc in directions:
            new_row, new_col = row + dr, col + dc
            
            # Check bounds
            if 0 <= new_row < 8 and 0 <= new_col < 8:
                if not self.board[new_row][new_col]:
                    # Simple move
                    valid_moves.append((new_row, new_col, False))
                elif (self.board[new_row][new_col]["player"] != piece["player"]):
                    # Check for jump
                    jump_row, jump_col = new_row + dr, new_col + dc
                    if (0 <= jump_row < 8 and 0 <= jump_col < 8 and 
                        not self.board[jump_row][jump_col]):
                        valid_moves.append((jump_row, jump_col, True))
                        
        return valid_moves
        
    def make_move(self, player_id, from_pos, to_pos):
        """Process a move"""
        with self.lock:
            if (self.state != GameState.PLAYING or 
                self.current_player != player_id):
                return False
                
            from_row, from_col = from_pos
            to_row, to_col = to_pos
            
            # Validate move
            valid_moves = self.get_valid_moves(from_row, from_col)
            
            is_jump = False
            for move_row, move_col, jump in valid_moves:
                if move_row == to_row and move_col == to_col:
                    is_jump = jump
                    break
            else:
                return False  # Invalid move
                
            # Make the move
            piece = self.board[from_row][from_col]
            self.board[to_row][to_col] = piece
            self.board[from_row][from_col] = None
            
            # Handle jump
            if is_jump:
                # Remove captured piece
                captured_row = (from_row + to_row) // 2
                captured_col = (from_col + to_col) // 2
                captured_piece = self.board[captured_row][captured_col]
                self.board[captured_row][captured_col] = None
                
                # Update score and lives
                if captured_piece:
                    opponent = 2 if player_id == 1 else 1
                    self.score[f"player{player_id}"] += 1
                    self.lives[f"player{opponent}"] -= 1
                    
            # Check for king promotion
            if piece["player"] == 1 and to_row == 7:
                piece["type"] = "king"  # Changed from PieceType.KING.value
            elif piece["player"] == 2 and to_row == 0:
                piece["type"] = "king"  # Changed from PieceType.KING.value
                
            # Check for game over
            if self.lives["player1"] == 0:
                self.state = GameState.GAME_OVER
                self.end_game(2)
            elif self.lives["player2"] == 0:
                self.state = GameState.GAME_OVER
                self.end_game(1)
            else:
                # Switch player
                self.current_player = 2 if self.current_player == 1 else 1
                
            # Update game time
            self.update_game_time()
            
            # Send update to all players
            self.broadcast_game_update()
            return True
            
    def end_game(self, winner):
        """End the game"""
        message = {
            "type": "game_over",
            "winner": winner,
            "final_score": self.score
        }
        
        for player_id in self.players:
            self.send_to_player(player_id, message)
            
    def broadcast_game_update(self):
        """Broadcast game update to all players"""
        message = {
            "type": "game_update",
            "board": self.board,
            "current_player": self.current_player,
            "score": self.score,
            "lives": self.lives,
            "game_time": self.game_time
        }
        
        for player_id in self.players:
            self.send_to_player(player_id, message)
            
    def send_to_player(self, player_id, message):
        """Send message to a specific player"""
        try:
            if player_id in self.players:
                socket = self.players[player_id]["socket"]
                message_str = json.dumps(message) + '\n'
                socket.send(message_str.encode())
        except Exception as e:
            print(f"Error sending message to player {player_id}: {e}")
            self.remove_player(player_id)
            
    def remove_player(self, player_id):
        """Remove a player from the game"""
        with self.lock:
            if player_id in self.players:
                del self.players[player_id]
                if self.state == GameState.PLAYING:
                    # End game if a player disconnects
                    winner = 2 if player_id == 1 else 1
                    self.end_game(winner)

class CheckersServer:
    def __init__(self, host='localhost', port=8080, processing_model=ProcessingModel.THREAD):
        self.host = host
        self.port = port
        self.processing_model = processing_model
        self.games = {}
        self.client_games = {}  # Track which game each client is in
        self.waiting_players = queue.Queue()
        self.next_game_id = 1
        self.next_player_id = 1
        self.running = False
        
        # Initialize processing resources
        if processing_model == ProcessingModel.POOL:
            self.thread_pool = ThreadPoolExecutor(max_workers=10)
            
    def start_server(self):
        """Start the server"""
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(5)
        
        self.running = True
        print(f"Checkers server started on {self.host}:{self.port}")
        print(f"Processing model: {self.processing_model.value}")
        
        # Start matchmaking thread
        matchmaking_thread = threading.Thread(target=self.matchmaking_loop)
        matchmaking_thread.daemon = True
        matchmaking_thread.start()
        
        try:
            while self.running:
                try:
                    client_socket, address = self.server_socket.accept()
                    print(f"New connection from {address}")
                    
                    if self.processing_model == ProcessingModel.THREAD:
                        # Create new thread for each client
                        client_thread = threading.Thread(
                            target=self.handle_client,
                            args=(client_socket, address)
                        )
                        client_thread.daemon = True
                        client_thread.start()
                        
                    elif self.processing_model == ProcessingModel.PROCESS:
                        # Create new process for each client
                        client_process = multiprocessing.Process(
                            target=self.handle_client,
                            args=(client_socket, address)
                        )
                        client_process.start()
                        
                    elif self.processing_model == ProcessingModel.POOL:
                        # Submit to thread pool
                        self.thread_pool.submit(
                            self.handle_client,
                            client_socket, address
                        )
                        
                except socket.error as e:
                    if self.running:
                        print(f"Socket error: {e}")
                        
        except KeyboardInterrupt:
            print("Server shutting down...")
            
        finally:
            self.shutdown()
            
    def handle_client(self, client_socket, address):
        """Handle a client connection"""
        player_id = None
        game = None
        
        try:
            while True:
                data = client_socket.recv(1024).decode()
                if not data:
                    break
                    
                try:
                    message = json.loads(data.strip())
                    msg_type = message.get("type")
                    
                    if msg_type == "join_game":
                        player_id = self.next_player_id
                        self.next_player_id += 1
                        
                        # Send player assignment
                        response = {
                            "type": "player_assigned",
                            "player_id": player_id
                        }
                        message_str = json.dumps(response) + '\n'
                        client_socket.send(message_str.encode())
                        
                        # Add to waiting players
                        self.waiting_players.put((player_id, client_socket))
                        
                    elif msg_type == "make_move" and player_id:
                        # Find the game this player is in
                        game = self.client_games.get(player_id)
                        if game:
                            from_pos = tuple(message["from"])
                            to_pos = tuple(message["to"])
                            
                            if not game.make_move(player_id, from_pos, to_pos):
                                # Send invalid move message
                                response = {"type": "invalid_move"}
                                message_str = json.dumps(response) + '\n'
                                client_socket.send(message_str.encode())
                            
                except json.JSONDecodeError:
                    print(f"Invalid JSON from {address}")
                    continue
                    
        except Exception as e:
            print(f"Error handling client {address}: {e}")
            
        finally:
            # Cleanup
            if player_id and player_id in self.client_games:
                game = self.client_games[player_id]
                game.remove_player(player_id)
                del self.client_games[player_id]
            client_socket.close()
            
    def matchmaking_loop(self):
        """Matchmaking loop to pair players"""
        while self.running:
            try:
                # Wait for at least one player
                player1_id, player1_socket = self.waiting_players.get(timeout=1)
                
                try:
                    # Try to get second player (with timeout)
                    player2_id, player2_socket = self.waiting_players.get(timeout=0.1)
                    
                    # Create new game
                    game_id = self.next_game_id
                    self.next_game_id += 1
                    
                    game = CheckersGame(game_id)
                    self.games[game_id] = game
                    
                    # Add players to game (use actual player IDs, but map to game positions)
                    success1 = game.add_player(player1_id, player1_socket)  # This will be position 1
                    success2 = game.add_player(player2_id, player2_socket)  # This will be position 2
                    
                    # Track which game each player is in
                    self.client_games[player1_id] = game
                    self.client_games[player2_id] = game
                    
                    print(f"Game {game_id} started with players {player1_id} and {player2_id}")
                    
                except queue.Empty:
                    # Put player back in queue if no match found
                    self.waiting_players.put((player1_id, player1_socket))
                    
            except queue.Empty:
                continue
                
    def shutdown(self):
        """Shutdown the server"""
        self.running = False
        if hasattr(self, 'server_socket'):
            self.server_socket.close()
        if hasattr(self, 'thread_pool'):
            self.thread_pool.shutdown(wait=True)

def main():
    parser = argparse.ArgumentParser(description='Checkers Multiplayer Server')
    parser.add_argument('--host', default='localhost', help='Server host')
    parser.add_argument('--port', type=int, default=8080, help='Server port')
    parser.add_argument('--processing', choices=['thread', 'process', 'pool'], 
                        default='thread', help='Processing model')
    
    args = parser.parse_args()
    
    processing_model = ProcessingModel(args.processing)
    server = CheckersServer(args.host, args.port, processing_model)
    server.start_server()

if __name__ == "__main__":
    main()