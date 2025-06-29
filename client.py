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
        self.restart_button = None
        self.restart_requested = False  # Track if restart was requested
        
        # Pygame setup
        pygame.init()
        self.BOARD_SIZE = 640
        self.CELL_SIZE = self.BOARD_SIZE // 8
        self.screen = pygame.display.set_mode((self.BOARD_SIZE + 250, self.BOARD_SIZE))
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
        
        # Clear selected piece if game is over
        if self.game_state == GameState.GAME_OVER:
            self.selected_piece = None
            
        # Reset restart_requested if game started again
        if self.game_state == GameState.PLAYING and self.restart_requested:
            self.restart_requested = False
            print("Game restarted successfully!")

    def restart_game(self):
        """Request restart for the current game (same players)"""
        if not self.game_id or not self.player_id:
            print("Cannot restart: no active game")
            return
            
        self.status_message = "Requesting restart..."
        self.restart_requested = True
        self.selected_piece = None
        
        payload = {
            "game_id": self.game_id,
            "player_id": self.player_id
        }
        
        response = self.http_request('POST', '/restart_game', payload)
        if response:
            if response.get('status') == 'restart_requested':
                self.status_message = "Waiting for opponent to agree..."
                print("Restart requested. Waiting for opponent...")
            elif response.get('status') == 'game_restarted':
                self.status_message = "Game restarted!"
                # The background updater will handle the state update
                print("Both players agreed! Game restarted.")
            else:
                self.status_message = "Restart failed"
                self.restart_requested = False
        else:
            print("Failed to request restart.")
            self.status_message = "Restart request failed."
            self.restart_requested = False

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
        """Get pieces that have mandatory jump moves - only for current player's turn"""
        mandatory_pieces = []
        
        # Only show mandatory moves if it's my turn and game is playing
        if not (self.game_state == GameState.PLAYING and self.is_my_turn):
            return mandatory_pieces
            
        for row in range(8):
            for col in range(8):
                if (self.board[row][col] and 
                    self.board[row][col]["player"] == self.my_player_number):
                    moves = self.get_valid_moves(row, col)
                    if any(abs(move[0] - row) > 1 for move in moves):
                        mandatory_pieces.append((row, col))
        return mandatory_pieces

    def get_movable_pieces(self):
        """Get pieces that can move - only for current player's turn"""
        movable_pieces = []
        
        # Only show movable pieces if it's my turn and game is playing
        if not (self.game_state == GameState.PLAYING and self.is_my_turn):
            return movable_pieces
        
        for row in range(8):
            for col in range(8):
                if (self.board[row][col] and 
                    self.board[row][col]["player"] == self.my_player_number):
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

                # Only show borders if it's my turn and game is still playing
                if self.is_my_turn and self.game_state == GameState.PLAYING:
                    if (row, col) in mandatory_pieces:
                        pygame.draw.rect(self.screen, self.YELLOW, (x, y, self.CELL_SIZE, self.CELL_SIZE), 3)
                    elif not mandatory_pieces and (row, col) in movable_pieces:
                        pygame.draw.rect(self.screen, self.YELLOW, (x, y, self.CELL_SIZE, self.CELL_SIZE), 3)

                piece = self.board[row][col]
                if piece:
                    center_x, center_y = x + self.CELL_SIZE // 2, y + self.CELL_SIZE // 2
                    piece_color = self.BLUE if piece["player"] == 1 else self.RED
                    pygame.draw.circle(self.screen, piece_color, (center_x, center_y), 30)
                    pygame.draw.circle(self.screen, self.BLACK, (center_x, center_y), 30, 3)
                    
                    if piece["type"] == PieceType.KING.value:
                        pygame.draw.circle(self.screen, self.YELLOW, (center_x, center_y), 15)

        # Don't show selected piece and valid moves if game is over
        if self.selected_piece and self.game_state == GameState.PLAYING:
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
        # Check if restart button was clicked
        if (self.game_state == GameState.GAME_OVER and 
            hasattr(self, 'restart_button') and 
            self.restart_button and 
            self.restart_button.collidepoint(pos)):
            self.restart_game()
            return
            
        if pos[0] >= self.BOARD_SIZE: return
        
        # Don't allow board clicks if game is over
        if self.game_state == GameState.GAME_OVER:
            print("Game is over! Click RESTART GAME to play again.")
            return
            
        col = pos[0] // self.CELL_SIZE
        row = pos[1] // self.CELL_SIZE
        
        if not self.is_my_turn:
            print("Not your turn!")
            return

        if 0 <= row < 8 and 0 <= col < 8:
            mandatory_pieces = self.get_pieces_with_mandatory_moves()
            
            if self.selected_piece is None:
                if (self.board[row][col] and 
                    self.board[row][col]["player"] == self.my_player_number):
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
        if self.game_state == GameState.WAITING:
            state_text = self.status_message
        elif self.game_state == GameState.GAME_OVER:
            if self.winner == self.my_player_number:
                state_text = "🎉 YOU WIN! 🎉"
                state_color = self.GREEN
            else:
                state_text = "💀 YOU LOSE 💀"
                state_color = self.RED
        else:
            state_text = f"Status: {self.game_state.value.replace('_', ' ').title()}"
            state_color = self.BLACK

        if self.game_state == GameState.GAME_OVER:
            text_surface = self.font.render(state_text, True, state_color)
        else:
            text_surface = self.font.render(state_text, True, self.BLACK)
        self.screen.blit(text_surface, (info_x, 20))

        # Player Info
        if self.my_player_number:
            player_text = f"You are Player {self.my_player_number}"
            player_color = self.BLUE if self.my_player_number == 1 else self.RED
        else:
            player_text = "You are a spectator"
            player_color = self.GRAY

        text_surface = self.small_font.render(player_text, True, player_color)
        self.screen.blit(text_surface, (info_x, 60))
        
        # Turn Info
        if self.game_state == GameState.PLAYING:
            if self.is_my_turn:
                turn_text = "🔥 YOUR TURN 🔥"
                turn_color = self.GREEN
            else:
                turn_text = f"Opponent's Turn (Player {self.current_player})"
                turn_color = self.GRAY
        else:
            turn_text = f"Turn: Player {self.current_player}"
            turn_color = self.BLUE if self.current_player == 1 else self.RED
            
        text_surface = self.font.render(turn_text, True, turn_color)
        self.screen.blit(text_surface, (info_x, 100))
        
        # Score and Lives
        p1_lives = f"Player 1 Pieces: {self.lives.get('player1', 12)}"
        self.screen.blit(self.small_font.render(p1_lives, True, self.BLUE), (info_x, 140))
        p2_lives = f"Player 2 Pieces: {self.lives.get('player2', 12)}"
        self.screen.blit(self.small_font.render(p2_lives, True, self.RED), (info_x, 160))

        # Game Time
        time_text = f"Time: {self.game_time//60:02d}:{self.game_time%60:02d}"
        self.screen.blit(self.small_font.render(time_text, True, self.BLACK), (info_x, 200))
        
        # Show restart status if waiting for opponent
        if self.restart_requested and "Waiting for opponent" in self.status_message:
            restart_status = self.small_font.render("Restart requested...", True, self.YELLOW)
            self.screen.blit(restart_status, (info_x, 220))
        
        # Restart Button (only show when game is over)
        if self.game_state == GameState.GAME_OVER:
            restart_button = pygame.Rect(info_x, 240, 150, 40)
            pygame.draw.rect(self.screen, self.GREEN, restart_button)
            pygame.draw.rect(self.screen, self.BLACK, restart_button, 2)
            
            restart_text = self.small_font.render("RESTART GAME", True, self.WHITE)
            text_rect = restart_text.get_rect(center=restart_button.center)
            self.screen.blit(restart_text, text_rect)
            
            # Store button rect for click detection
            self.restart_button = restart_button
        else:
            self.restart_button = None

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