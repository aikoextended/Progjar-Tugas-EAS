import pygame
import http.client
import json
import threading
import sys
import time
from enum import Enum

class GameState(Enum):
    WAITING = "waiting"
    PLAYING = "playing"
    GAME_OVER = "game_over"

class PieceType(Enum):
    REGULAR = "regular"
    KING = "king"

class CheckersClient:
    def __init__(self, host='localhost', port=8080):
        self.host = host
        self.port = port
        self.player_id = None
        self.game_id = None
        self.is_my_turn = False
        self.my_player_number = None
        
        self.game_state = GameState.WAITING
        self.board = [[None for _ in range(8)] for _ in range(8)]
        self.current_player = 1
        self.selected_piece = None
        self.score = {"player1": 0, "player2": 0}
        self.lives = {"player1": 12, "player2": 12}
        self.game_time = 0
        self.winner = None
        self.status_message = "Connecting to server..."
        
        # Pygame setup
        pygame.init()
        self.BOARD_SIZE = 640
        self.CELL_SIZE = self.BOARD_SIZE // 8
        self.screen = pygame.display.set_mode((self.BOARD_SIZE + 200, self.BOARD_SIZE))
        pygame.display.set_caption("Checkers Game (HTTP Client)")
        
        # Colors
        self.WHITE = (255, 255, 255)
        self.BLACK = (0, 0, 0)
        self.RED = (255, 0, 0)
        self.BLUE = (0, 0, 255)
        self.GREEN = (0, 255, 0)
        self.YELLOW = (255, 255, 0)
        self.GRAY = (128, 128, 128)
        self.LIGHT_BROWN = (240, 217, 181)
        self.DARK_BROWN = (181, 136, 99)
        
        self.font = pygame.font.Font(None, 36)
        self.small_font = pygame.font.Font(None, 24)
        
        self.initialize_board()

    def initialize_board(self):
        """Initialize the checkers board with pieces"""
        for row in range(8):
            for col in range(8):
                if (row + col) % 2 == 1:  # Dark squares only
                    if row < 3:
                        self.board[row][col] = {"player": 1, "type": PieceType.REGULAR.value}
                    elif row > 4:
                        self.board[row][col] = {"player": 2, "type": PieceType.REGULAR.value}

    def http_request(self, method, path, payload=None):
        """Helper function to make HTTP requests."""
        try:
            conn = http.client.HTTPConnection(self.host, self.port)
            headers = {'Content-type': 'application/json'}
            body = json.dumps(payload) if payload else None
            
            conn.request(method, path, body, headers)
            response = conn.getresponse()
            
            data = response.read()
            conn.close()
            
            if response.status >= 200 and response.status < 300:
                return json.loads(data.decode())
            else:
                print(f"Error: {response.status} {response.reason} - {data.decode()}")
                return None
        except Exception as e:
            print(f"HTTP request failed: {e}")
            self.status_message = "Server connection failed."
            return None

    def join_game(self):
        """Send a request to join a game."""
        self.status_message = "Finding a match..."
        response = self.http_request('POST', '/join_game')
        if response:
            self.player_id = response.get('player_id')
            self.game_id = response.get('game_id')
            print(f"Joined game. Player ID: {self.player_id}, Game ID: {self.game_id}")
            return True
        return False

    def background_updater(self):
        """Handles background polling for game start and game state."""
        while True:
            if not self.player_id:
                time.sleep(0.2)
                continue

            # --- Stage 1: Check if the game has started ---
            if self.game_id is None:
                self.status_message = "Finding a match..."
                path = f"/check_status?player_id={self.player_id}"
                response = self.http_request('GET', path)
                if response and response.get('status') == 'game_started':
                    self.game_id = response.get('game_id')
                    print(f"Game found! Game ID: {self.game_id}")

            # --- Stage 2: Once in a game, poll for its state ---
            else:
                path = f"/game_state?game_id={self.game_id}&player_id={self.player_id}"
                state = self.http_request('GET', path)
                if state:
                    self.update_local_state(state)

            time.sleep(0.2)

    def update_local_state(self, state):
        """Update the client's game state from server data."""
        self.board = state.get("board", self.board)
        self.current_player = state.get("current_player", self.current_player)
        self.score = state.get("score", self.score)
        self.lives = state.get("lives", self.lives)
        self.game_time = state.get("game_time", self.game_time)
        self.game_state = GameState(state.get("game_state", "waiting"))
        self.winner = state.get("winner")
        self.is_my_turn = state.get("your_turn", False)
        self.my_player_number = state.get("my_player_number")

    def make_move(self, from_pos, to_pos):
        """Send a move to the server."""
        if not self.game_id or not self.player_id:
            return

        payload = {
            "game_id": self.game_id,
            "player_id": self.player_id,
            "from": from_pos,
            "to": to_pos
        }
        
        state = self.http_request('POST', '/make_move', payload)
        if state:
            self.update_local_state(state)
        else:
            print("Invalid move refused by server.")
        self.selected_piece = None

    def get_pieces_with_mandatory_moves(self):
        mandatory_pieces = []
        is_my_turn = self.game_state == GameState.PLAYING and self.current_player == (1 if self.player_id and '1' in self.player_id else 2) 
        
        if self.game_state != GameState.PLAYING:
            return mandatory_pieces
            
        for row in range(8):
            for col in range(8):
                if (self.board[row][col] and 
                    self.board[row][col]["player"] == self.current_player): # Check current player's pieces
                    moves = self.get_valid_moves(row, col)
                    if any(abs(move[0] - row) > 1 for move in moves):
                        mandatory_pieces.append((row, col))
        return mandatory_pieces

    def get_movable_pieces(self):
        movable_pieces = []
        if self.game_state != GameState.PLAYING:
             return movable_pieces
        
        for row in range(8):
            for col in range(8):
                if (self.board[row][col] and 
                    self.board[row][col]["player"] == self.current_player):
                    if self.get_valid_moves(row, col):
                        movable_pieces.append((row, col))
        return movable_pieces

    def draw_board(self):
        mandatory_pieces = self.get_pieces_with_mandatory_moves()
        movable_pieces = self.get_movable_pieces()
        
        for row in range(8):
            for col in range(8):
                x, y = col * self.CELL_SIZE, row * self.CELL_SIZE
                color = self.LIGHT_BROWN if (row + col) % 2 == 0 else self.DARK_BROWN
                pygame.draw.rect(self.screen, color, (x, y, self.CELL_SIZE, self.CELL_SIZE))

                if (row, col) in mandatory_pieces:
                    pygame.draw.rect(self.screen, self.YELLOW, (x, y, self.CELL_SIZE, self.CELL_SIZE), 3)
                elif not mandatory_pieces and (row, col) in movable_pieces:
                    pygame.draw.rect(self.screen, self.YELLOW, (x, y, self.CELL_SIZE, self.CELL_SIZE), 3)

                piece = self.board[row][col]
                if piece:
                    center_x, center_y = x + self.CELL_SIZE // 2, y + self.CELL_SIZE // 2
                    piece_color = self.RED if piece["player"] == 1 else self.BLUE
                    pygame.draw.circle(self.screen, piece_color, (center_x, center_y), 30)
                    pygame.draw.circle(self.screen, self.BLACK, (center_x, center_y), 30, 3)
                    
                    if piece["type"] == PieceType.KING.value:
                        pygame.draw.circle(self.screen, self.YELLOW, (center_x, center_y), 15)

        if self.selected_piece:
            row, col = self.selected_piece
            x, y = col * self.CELL_SIZE, row * self.CELL_SIZE
            pygame.draw.rect(self.screen, self.GREEN, (x, y, self.CELL_SIZE, self.CELL_SIZE), 5)

            valid_moves = self.get_valid_moves(row, col)
            for move_row, move_col in valid_moves:
                move_x, move_y = move_col * self.CELL_SIZE, move_row * self.CELL_SIZE
                pygame.draw.circle(self.screen, self.GREEN, (move_x + self.CELL_SIZE // 2, move_y + self.CELL_SIZE // 2), 10)

    def get_valid_moves(self, row, col):
        if not self.board[row][col]:
            return []
        
        piece = self.board[row][col]
        valid_moves = []
        mandatory_jumps = []
        
        if piece["type"] == "king":
            directions = [(-1, -1), (-1, 1), (1, -1), (1, 1)]
        else:
            directions = [(1, -1), (1, 1)] if piece["player"] == 1 else [(-1, -1), (-1, 1)]
            
        for dr, dc in directions:
            new_row, new_col = row + dr, col + dc
            if 0 <= new_row < 8 and 0 <= new_col < 8:
                if (self.board[new_row][new_col] and 
                    self.board[new_row][new_col]["player"] != piece["player"]):
                    jump_row, jump_col = new_row + dr, new_col + dc
                    if 0 <= jump_row < 8 and 0 <= jump_col < 8 and not self.board[jump_row][jump_col]:
                        mandatory_jumps.append((jump_row, jump_col))
                        
        if mandatory_jumps:
            return mandatory_jumps
            
        for dr, dc in directions:
            new_row, new_col = row + dr, col + dc
            if 0 <= new_row < 8 and 0 <= new_col < 8 and not self.board[new_row][new_col]:
                valid_moves.append((new_row, new_col))
                
        return valid_moves

    def handle_click(self, pos):
        if pos[0] >= self.BOARD_SIZE: return
            
        col = pos[0] // self.CELL_SIZE
        row = pos[1] // self.CELL_SIZE
        
        if not self.is_my_turn:
            print("Not your turn!")
            return

        if 0 <= row < 8 and 0 <= col < 8:
            mandatory_pieces = self.get_pieces_with_mandatory_moves()
            
            if self.selected_piece is None:
                if (self.board[row][col] and self.board[row][col]["player"] == self.current_player):
                    if mandatory_pieces and (row, col) not in mandatory_pieces:
                        print("You must make a mandatory jump.")
                        return
                    self.selected_piece = (row, col)
            else:
                if self.selected_piece == (row, col):
                    self.selected_piece = None
                else:
                    valid_moves = self.get_valid_moves(*self.selected_piece)
                    if (row, col) in valid_moves:
                        self.make_move(self.selected_piece, (row, col))
                    else:
                        print("Invalid move.")
                        self.selected_piece = None


    def draw_ui(self):
        info_x = self.BOARD_SIZE + 10
        
        # Game State
        state_text = f"Status: {self.game_state.value.replace('_', ' ').title()}"
        if self.game_state == GameState.WAITING:
            state_text = self.status_message
        elif self.game_state == GameState.GAME_OVER:
            state_text = f"Game Over! Winner: Player {self.winner}"

        text_surface = self.font.render(state_text, True, self.BLACK)
        self.screen.blit(text_surface, (info_x, 20))

        # Player Info
        player_text = f"You are Player {self.my_player_number}" if self.my_player_number else "You are a spectator"

        text_surface = self.small_font.render(player_text, True, self.BLACK)
        self.screen.blit(text_surface, (info_x, 60))
        
        # Turn Info
        turn_text = f"Turn: Player {self.current_player}"
        color = self.RED if self.current_player == 1 else self.BLUE
        text_surface = self.font.render(turn_text, True, color)
        self.screen.blit(text_surface, (info_x, 100))
        
        # Score and Lives
        p1_lives = f"Player 1 Pieces: {self.lives.get('player1', 12)}"
        self.screen.blit(self.small_font.render(p1_lives, True, self.RED), (info_x, 140))
        p2_lives = f"Player 2 Pieces: {self.lives.get('player2', 12)}"
        self.screen.blit(self.small_font.render(p2_lives, True, self.BLUE), (info_x, 160))

        # Game Time
        time_text = f"Time: {self.game_time//60:02d}:{self.game_time%60:02d}"
        self.screen.blit(self.small_font.render(time_text, True, self.BLACK), (info_x, 200))


    def run(self):
        """Main game loop"""
        if not self.join_game():
            print("Failed to join game. Exiting.")
            return
            
        # Start polling thread
        poll_thread = threading.Thread(target=self.background_updater)
        poll_thread.daemon = True
        poll_thread.start()
        
        clock = pygame.time.Clock()
        running = True
        
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    self.handle_click(event.pos)
                    
            self.screen.fill(self.WHITE)
            self.draw_board()
            self.draw_ui()
            pygame.display.flip()
            clock.tick(30)
            
        pygame.quit()

if __name__ == "__main__":
    host = sys.argv[1] if len(sys.argv) > 1 else 'localhost'
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 8080
    client = CheckersClient(host, port)
    client.run()
