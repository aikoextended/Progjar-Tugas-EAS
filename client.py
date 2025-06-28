import pygame
import socket
import json
import threading
import sys
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
        self.socket = None
        self.player_id = None
        self.game_state = GameState.WAITING
        self.board = [[None for _ in range(8)] for _ in range(8)]
        self.current_player = 1
        self.selected_piece = None
        self.score = {"player1": 0, "player2": 0}
        self.lives = {"player1": 12, "player2": 12}
        self.game_time = 0
        
        # Pygame setup
        pygame.init()
        self.BOARD_SIZE = 640
        self.CELL_SIZE = self.BOARD_SIZE // 8
        self.screen = pygame.display.set_mode((self.BOARD_SIZE + 200, self.BOARD_SIZE + 100))
        pygame.display.set_caption("Checkers Game")
        
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
        
        # Initialize board
        self.initialize_board()
        
    def initialize_board(self):
        """Initialize the checkers board with pieces"""
        for row in range(8):
            for col in range(8):
                if (row + col) % 2 == 1:  # Dark squares only
                    if row < 3:
                        self.board[row][col] = {"player": 1, "type": PieceType.REGULAR}
                    elif row > 4:
                        self.board[row][col] = {"player": 2, "type": PieceType.REGULAR}
                        
    def connect_to_server(self):
        """Connect to the game server"""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((self.host, self.port))
            
            # Start receiving thread
            receive_thread = threading.Thread(target=self.receive_messages)
            receive_thread.daemon = True
            receive_thread.start()
            
            # Send join game request
            self.send_message({"type": "join_game"})
            return True
        except Exception as e:
            print(f"Failed to connect to server: {e}")
            return False
            
    def send_message(self, message):
        """Send message to server"""
        try:
            if self.socket:
                message_str = json.dumps(message) + '\n'
                self.socket.send(message_str.encode())
        except Exception as e:
            print(f"Error sending message: {e}")
            
    def receive_messages(self):
        """Receive messages from server"""
        buffer = ""
        while True:
            try:
                data = self.socket.recv(1024).decode()
                if not data:
                    break
                    
                buffer += data
                while '\n' in buffer:
                    line, buffer = buffer.split('\n', 1)
                    if line.strip():
                        message = json.loads(line.strip())
                        self.handle_server_message(message)
                        
            except Exception as e:
                print(f"Error receiving message: {e}")
                break
                
    def handle_server_message(self, message):
        """Handle messages from server"""
        msg_type = message.get("type")
        
        if msg_type == "player_assigned":
            self.player_id = message["player_id"]
            print(f"Assigned as Player {self.player_id}")
            
        elif msg_type == "game_start":
            self.game_state = GameState.PLAYING
            self.board = message["board"]
            self.current_player = message["current_player"]
            print("Game started!")
            
        elif msg_type == "game_update":
            self.board = message["board"]
            self.current_player = message["current_player"]
            self.score = message.get("score", self.score)
            self.lives = message.get("lives", self.lives)
            self.game_time = message.get("game_time", self.game_time)
            
        elif msg_type == "game_over":
            self.game_state = GameState.GAME_OVER
            self.winner = message["winner"]
            print(f"Game Over! Winner: Player {self.winner}")
            
        elif msg_type == "invalid_move":
            print("Invalid move!")
   
    def get_pieces_with_mandatory_moves(self):
        """Get all pieces that have mandatory jumps available"""
        mandatory_pieces = []
        if self.game_state != GameState.PLAYING or self.current_player != self.player_id:
            return mandatory_pieces
            
        for row in range(8):
            for col in range(8):
                if (self.board[row][col] and 
                    self.board[row][col]["player"] == self.player_id):
                    moves = self.get_valid_moves(row, col)
                    # Check if any move is a jump
                    if any(abs(move[0] - row) > 1 for move in moves):
                        mandatory_pieces.append((row, col))
        return mandatory_pieces

    def get_movable_pieces(self):
        """Get all pieces that can move (either mandatory jumps or regular moves)"""
        movable_pieces = []
        if self.game_state != GameState.PLAYING or self.current_player != self.player_id:
            return movable_pieces
            
        for row in range(8):
            for col in range(8):
                if (self.board[row][col] and 
                    self.board[row][col]["player"] == self.player_id):
                    if self.get_valid_moves(row, col):  # If piece has any valid moves
                        movable_pieces.append((row, col))
        return movable_pieces

    def draw_board(self):
        """Draw the checkers board with visual cues for movable pieces"""
        mandatory_pieces = self.get_pieces_with_mandatory_moves()
        movable_pieces = self.get_movable_pieces()
        
        for row in range(8):
            for col in range(8):
                x = col * self.CELL_SIZE
                y = row * self.CELL_SIZE
                
                # Draw square
                if (row + col) % 2 == 0:
                    color = self.LIGHT_BROWN
                else:
                    color = self.DARK_BROWN
                    
                pygame.draw.rect(self.screen, color, (x, y, self.CELL_SIZE, self.CELL_SIZE))
                
                # Highlight pieces based on move rules
                if (row, col) in mandatory_pieces:
                    # Red outline for pieces with mandatory jumps
                    pygame.draw.rect(self.screen, self.YELLOW, (x, y, self.CELL_SIZE, self.CELL_SIZE), 3)
                elif not mandatory_pieces and (row, col) in movable_pieces:
                    # Blue outline for movable pieces when no mandatory jumps
                    pygame.draw.rect(self.screen, self.YELLOW, (x, y, self.CELL_SIZE, self.CELL_SIZE), 3)
                
                # Draw piece
                if self.board[row][col]:
                    piece = self.board[row][col]
                    center_x = x + self.CELL_SIZE // 2
                    center_y = y + self.CELL_SIZE // 2
                    
                    # Piece color
                    if piece["player"] == 1:
                        piece_color = self.RED
                    else:
                        piece_color = self.BLUE
                        
                    # Draw piece
                    pygame.draw.circle(self.screen, piece_color, (center_x, center_y), 30)
                    pygame.draw.circle(self.screen, self.BLACK, (center_x, center_y), 30, 3)
                    
                    # Draw king crown
                    if piece["type"] == "king":
                        pygame.draw.circle(self.screen, self.YELLOW, (center_x, center_y), 15)
                        
        if self.selected_piece and self.current_player == self.player_id:
            row, col = self.selected_piece
            x = col * self.CELL_SIZE
            y = row * self.CELL_SIZE
            
            # Highlight selected piece with thick green border
            pygame.draw.rect(self.screen, self.GREEN, (x, y, self.CELL_SIZE, self.CELL_SIZE), 5)
            
            # Draw valid moves with more visible indicators
            valid_moves = self.get_valid_moves(row, col)
            for move_row, move_col in valid_moves:
                move_x = move_col * self.CELL_SIZE
                move_y = move_row * self.CELL_SIZE
                pygame.draw.circle(self.screen, self.GREEN, 
                                (move_x + self.CELL_SIZE//2, move_y + self.CELL_SIZE//2), 10)

    def handle_click(self, pos):
        """Handle mouse click with move enforcement"""
        if pos[0] >= self.BOARD_SIZE:  # Click outside board
            return
            
        col = pos[0] // self.CELL_SIZE
        row = pos[1] // self.CELL_SIZE
        
        if 0 <= row < 8 and 0 <= col < 8:
            mandatory_pieces = self.get_pieces_with_mandatory_moves()
            movable_pieces = self.get_movable_pieces()
            
            if self.selected_piece is None:
                # Select piece - enforce move rules
                if (self.board[row][col] and 
                    self.board[row][col]["player"] == self.player_id and
                    self.current_player == self.player_id and
                    self.game_state == GameState.PLAYING):
                    
                    # Check if piece is movable
                    if (row, col) not in movable_pieces:
                        print("This piece cannot move!")
                        return
                    
                    # If there are mandatory pieces, only allow selecting them
                    if mandatory_pieces:
                        if (row, col) in mandatory_pieces:
                            self.selected_piece = (row, col)
                            print(f"Selected mandatory piece at ({row}, {col})")
                        else:
                            print("You must select a piece with mandatory moves first!")
                            return
                    else:
                        self.selected_piece = (row, col)
                        print(f"Selected piece at ({row}, {col})")
            else:
                # Try to move
                if self.selected_piece == (row, col):
                    # Deselect
                    self.selected_piece = None
                    print("Deselected piece")
                else:
                    # Attempt move
                    valid_moves = self.get_valid_moves(*self.selected_piece)
                    if (row, col) in [(move[0], move[1]) for move in valid_moves]:
                        print(f"Making move from {self.selected_piece} to ({row}, {col})")
                        self.make_move(self.selected_piece, (row, col))
                    else:
                        print(f"Invalid move to ({row}, {col})")
                    self.selected_piece = None

    def get_valid_moves(self, row, col):
        """Get valid moves for a piece, prioritizing jumps and detecting multiple jumps"""
        if not self.board[row][col]:
            return []
            
        piece = self.board[row][col]
        valid_moves = []
        mandatory_jumps = []
        
        # Direction depends on player and piece type
        if piece["type"] == "king":
            directions = [(-1, -1), (-1, 1), (1, -1), (1, 1)]
        else:
            if piece["player"] == 1:
                directions = [(1, -1), (1, 1)]
            else:
                directions = [(-1, -1), (-1, 1)]
                
        # First check for jumps
        for dr, dc in directions:
            new_row, new_col = row + dr, col + dc
            
            # Check bounds
            if 0 <= new_row < 8 and 0 <= new_col < 8:
                if (self.board[new_row][new_col] and 
                    self.board[new_row][new_col]["player"] != piece["player"]):
                    # Check for jump space
                    jump_row, jump_col = new_row + dr, new_col + dc
                    if (0 <= jump_row < 8 and 0 <= jump_col < 8 and 
                        not self.board[jump_row][jump_col]):
                        # This is a valid jump
                        mandatory_jumps.append((jump_row, jump_col))
                        
        # If there are jumps available, only return jumps
        if mandatory_jumps:
            return mandatory_jumps
            
        # If no jumps, return regular moves
        for dr, dc in directions:
            new_row, new_col = row + dr, col + dc
            
            # Check bounds
            if 0 <= new_row < 8 and 0 <= new_col < 8:
                if not self.board[new_row][new_col]:
                    valid_moves.append((new_row, new_col))
                    
        return valid_moves
        
    def make_move(self, from_pos, to_pos):
        """Make a move"""
        if self.game_state != GameState.PLAYING or self.current_player != self.player_id:
            return False
            
        move_data = {
            "type": "make_move",
            "from": from_pos,
            "to": to_pos
        }
        self.send_message(move_data)
        return True
        
    def draw_ui(self):
        """Draw the user interface"""
        # Game info panel
        info_x = self.BOARD_SIZE + 10
        
        # Current player
        player_text = f"Current Player: {self.current_player}"
        text_surface = self.font.render(player_text, True, self.BLACK)
        self.screen.blit(text_surface, (info_x, 20))
        
        # Your player
        your_player_text = f"You are: Player {self.player_id if self.player_id else 'None'}"
        text_surface = self.small_font.render(your_player_text, True, self.BLACK)
        self.screen.blit(text_surface, (info_x, 60))
        
        # Score
        score_text = f"Score:"
        text_surface = self.font.render(score_text, True, self.BLACK)
        self.screen.blit(text_surface, (info_x, 100))
        
        p1_score = f"Player 1: {self.score.get('player1', 0)}"
        text_surface = self.small_font.render(p1_score, True, self.RED)
        self.screen.blit(text_surface, (info_x, 130))
        
        p2_score = f"Player 2: {self.score.get('player2', 0)}"
        text_surface = self.small_font.render(p2_score, True, self.BLUE)
        self.screen.blit(text_surface, (info_x, 150))
        
        # Lives
        lives_text = f"Pieces Left:"
        text_surface = self.font.render(lives_text, True, self.BLACK)
        self.screen.blit(text_surface, (info_x, 190))
        
        p1_lives = f"Player 1: {self.lives.get('player1', 12)}"
        text_surface = self.small_font.render(p1_lives, True, self.RED)
        self.screen.blit(text_surface, (info_x, 220))
        
        p2_lives = f"Player 2: {self.lives.get('player2', 12)}"
        text_surface = self.small_font.render(p2_lives, True, self.BLUE)
        self.screen.blit(text_surface, (info_x, 240))
        
        # Game time
        time_text = f"Time: {self.game_time//60:02d}:{self.game_time%60:02d}"
        text_surface = self.small_font.render(time_text, True, self.BLACK)
        self.screen.blit(text_surface, (info_x, 280))
        
        # Game state
        if self.game_state == GameState.WAITING:
            state_text = "Waiting for opponent..."
            color = self.GRAY
        elif self.game_state == GameState.PLAYING:
            if self.current_player == self.player_id:
                state_text = "Your turn!"
                color = self.GREEN
            else:
                state_text = "Opponent's turn"
                color = self.YELLOW
        else:
            if hasattr(self, 'winner'):
                if self.winner == self.player_id:
                    state_text = "You Win!"
                    color = self.GREEN
                else:
                    state_text = "You Lose!"
                    color = self.RED
            else:
                state_text = "Game Over"
                color = self.GRAY
                
        text_surface = self.font.render(state_text, True, color)
        self.screen.blit(text_surface, (info_x, 320))
        
    def run(self):
        """Main game loop"""
        if not self.connect_to_server():
            print("Failed to connect to server")
            return
            
        clock = pygame.time.Clock()
        running = True
        
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    if event.button == 1:  # Left click
                        self.handle_click(event.pos)
                        
            # Clear screen
            self.screen.fill(self.WHITE)
            
            # Draw game
            self.draw_board()
            self.draw_ui()
            
            # Update display
            pygame.display.flip()
            clock.tick(60)
            
        # Cleanup
        if self.socket:
            self.socket.close()
        pygame.quit()

if __name__ == "__main__":
    if len(sys.argv) > 2:
        host = sys.argv[1]
        port = int(sys.argv[2])
        client = CheckersClient(host, port)
    else:
        client = CheckersClient()
    
    client.run()