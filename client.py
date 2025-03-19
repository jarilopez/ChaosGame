import socket
import threading
import json
import pygame
import time
import math

# Server Connection
SERVER_IP = '127.0.0.1'
SERVER_PORT = 5555

# Pygame setup
# After pygame.init() and before the game loop
pygame.init()
SCREEN_WIDTH, SCREEN_HEIGHT = 1441, 768
CAR_WIDTH, CAR_HEIGHT = 20, 20
FPS = 60

# Load game images
bomb_image = pygame.image.load('bomb.png')
bomb_image = pygame.transform.scale(bomb_image, (20, 20))
explosion_image = pygame.image.load('explosion.png')
explosion_image = pygame.transform.scale(explosion_image, (40, 40))

# Add explosion state variables
explosion_pos = None
explosion_start = 0
EXPLOSION_DURATION = 0.5  # seconds

# Add font initialization here
font = pygame.font.SysFont(None, 26)
title_font = pygame.font.SysFont(None, 38)  # Larger font for titles
data_font = pygame.font.SysFont(None, 26)   # Font for data display

# Paleta de colores mejorada (futurista/UX 2025)

WHITE = (240, 240, 240)            # Blanco suave, menos duro que el 255,255,255
RED = (230, 57, 70)                # Rojo intenso y moderno
GREEN = (67, 160, 71)              # Verde vibrante y agradable
BLUE = (66, 135, 245)              # Azul con un ligero tono pastel
YELLOW = (255, 241, 118)           # Amarillo cálido y luminoso
BLACK = (36, 36, 36)               # Negro suave, ideal para fondos oscuros

TRACK_COLOR = (50, 50, 50)         # Gris oscuro para la pista
TRACK_BORDER_COLOR = (0, 255, 180) # Borde neón (verde azulado) para resaltar
GRASS_COLOR = (16, 150, 84)        # Verde ligeramente más brillante y moderno
CHECKPOINT_COLOR = (255, 214, 10)  # Dorado/amarillo para destacar checkpoints
FINISH_LINE_COLOR = (255, 255, 255)# Blanco puro para la línea de meta


# Physics constants
ACCELERATION = 0.08      # Reduced from 0.2 for slower acceleration
TURNING_SPEED = 3.0
FRICTION = 0.01         # Reduced from 0.02 for smoother deceleration
MAX_SPEED = 6.0
DRIFT_FACTOR = 0.95
GRASS_SLOWDOWN = 0.4  # Reduced from 0.7 for more forgiving gameplay

# Car class definition
class Car:
    def __init__(self, x, y):
        self.position = [x, y]
        self.velocity = [0, 0]
        self.angle = 0  # Angle in degrees
        self.speed = 0
        self.checkpoint_times = []
        self.best_lap = float('inf')
        self.current_lap_start = time.time()
        self.last_lap_time = 0

# Define track as a list of points (outer and inner boundaries)
track_outer = [
    (50, 50), (1350, 50), (1350, 300),
    (1050, 300), (1050, 400), (1350, 400),
    (1350, 600), (550, 600), (400, 450),
    (250, 450), (150, 550), (50, 450),
    (50, 50)
]

track_inner = [
    (150, 150), (1250, 150), (1250, 200),
    (950, 200), (950, 500), (1250, 500),
    (1250, 500), (550, 500), (450, 400),
    (350, 400), (200, 400), (150, 350),
    (150, 150)
]

# Car starting position - placed at the start/finish line on the track
start_position = [120, 100]  # Positioned on the track near the finish line

# Create a surface for the track
track_surface = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
track_surface.fill(GRASS_COLOR)  # Fill with grass color

# Draw the track on the surface
pygame.draw.polygon(track_surface, TRACK_COLOR, track_outer)
pygame.draw.polygon(track_surface, GRASS_COLOR, track_inner)

# Draw track borders
pygame.draw.lines(track_surface, TRACK_BORDER_COLOR, True, track_outer, 5)
pygame.draw.lines(track_surface, TRACK_BORDER_COLOR, True, track_inner, 5)

# Add checkered pattern at start/finish line


# Create track mask for collision detection
track_mask = pygame.mask.from_threshold(track_surface, TRACK_COLOR, (1, 1, 1, 255))

# Function to check if car is on track
def is_on_track(pos, car_width, car_height, angle):
    # Create a smaller hitbox for more forgiving track limits
    car_surface = pygame.Surface((car_width * 0.8, car_height * 0.8), pygame.SRCALPHA)
    pygame.draw.rect(car_surface, (255, 255, 255, 128), (0, 0, car_width * 0.8, car_height * 0.8))
    rotated_car = pygame.transform.rotate(car_surface, angle)
    
    car_rect = rotated_car.get_rect(center=pos)
    car_mask = pygame.mask.from_surface(rotated_car)
    offset = (car_rect.x, car_rect.y)
    
    # Check for collision with track
    if hasattr(pygame.mask, 'overlap_area'):
        overlap = pygame.mask.overlap_area(track_mask, car_mask, offset)
    else:
        # Fallback for older Pygame versions
        overlap = track_mask.overlap_area(car_mask, offset)
    
    # More forgiving track limits (require less overlap)
    return overlap > (car_width * car_height * 0.3)

# Multiplayer Data
players = {}

# Connect to Server
client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
try:
    client_socket.connect((SERVER_IP, SERVER_PORT))
except:
    print("Could not connect to server. Running in single player mode.")

def receive_data(sock):
    """Receives player data from server."""
    global players
    while True:
        try:
            data = sock.recv(1024)
            if not data:
                break
            players = json.loads(data.decode())
        except:
            break

threading.Thread(target=receive_data, args=(client_socket,), daemon=True).start()

# **Lap System**
lap_count = 0
max_laps = 5
current_checkpoint_index = 0  # Initialize checkpoint index
checkpoint_hit = False
lap_times = []

# Define checkpoints around the track - positioned ON the track as shown in the image
checkpoints = [
    pygame.Rect(350, 50, 40, 40),   # Checkpoint 1 - after start
    pygame.Rect(750, 110, 40, 40),   # Checkpoint 2 - top straight
    pygame.Rect(950, 350, 40, 40),  # Checkpoint 3 - right turn
    pygame.Rect(900, 500, 40, 40),   # Checkpoint 4 - bottom right
    pygame.Rect(550, 500, 40, 40),   # Checkpoint 5 - bottom middle
    pygame.Rect(350, 400, 40, 50),   # Checkpoint 6 - left curve
    pygame.Rect(50, 300, 40, 40),   # Checkpoint 7 - final turn
]

# Finish line - positioned at the start/finish line
finish_line = pygame.Rect(50, 150, 50, 50)

# Define bombs before the game loop
bombs = [
    pygame.Rect(300, 100, 10, 10),   # First straight
    pygame.Rect(1000, 500, 10, 10),   # Right side
    pygame.Rect(700, 530, 10, 10),   # Bottom curve
]

# Initialize player car with correct orientation (facing right along the track)
player_car = Car(start_position[0], start_position[1])
player_car.angle = 90  # Changed from 270 to 90 to face the opposite direction

# Pygame Setup
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
pygame.display.set_caption("Racing Game")
clock = pygame.time.Clock()

running = True
while running:
    clock.tick(FPS)
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
    
    # Draw background and track
    screen.fill(GRASS_COLOR)
    screen.blit(track_surface, (0, 0))
    
    # Draw finish line with alternating pattern
    for i in range(10):
        color = BLACK if i % 2 == 0 else WHITE
        pygame.draw.rect(screen, color, (finish_line.x + i*10, finish_line.y, 10, finish_line.height))
    # Draw checkpoints with better visibility
    for i, checkpoint in enumerate(checkpoints):
        color = GREEN if i < current_checkpoint_index else YELLOW
        pygame.draw.rect(screen, color, checkpoint, 3)  # Thicker border
        # Add checkpoint number for clarity
        checkpoint_num = font.render(str(i+1), True, color)
        screen.blit(checkpoint_num, checkpoint.center)
    
    # Controls
    keys = pygame.key.get_pressed()
    
    # Steering
    if keys[pygame.K_LEFT]:
        player_car.angle += TURNING_SPEED * 1.2
    if keys[pygame.K_RIGHT]:
        player_car.angle -= TURNING_SPEED * 1.2
    
    # Acceleration and braking with time-based mechanics
    if keys[pygame.K_UP]:
        player_car.acceleration_time += 1/FPS
        acceleration = ACCELERATION * min(player_car.acceleration_time, 3.0)  # Increased time to reach max speed
        player_car.speed = min(player_car.speed + acceleration, MAX_SPEED)
    elif keys[pygame.K_DOWN]:
        player_car.acceleration_time += 1/FPS
        deceleration = ACCELERATION * min(player_car.acceleration_time, 2.0)  # Smoother braking
        player_car.speed = max(player_car.speed - deceleration, -MAX_SPEED / 2.5)  # Reduced reverse speed
    else:
        player_car.acceleration_time = 0
        player_car.speed *= (1 - FRICTION * 1.5)  # Adjusted natural deceleration
    
    # Check if car is on track and apply physics
    on_track = is_on_track(player_car.position, CAR_WIDTH, CAR_HEIGHT, player_car.angle)
    
    if on_track:
        player_car.speed *= (1 - FRICTION)
    else:
        player_car.speed *= (1 - FRICTION - GRASS_SLOWDOWN)
    
    # Update car position
    angle_rad = math.radians(player_car.angle)
    player_car.velocity[0] = math.sin(angle_rad) * player_car.speed
    player_car.velocity[1] = math.cos(angle_rad) * player_car.speed
    
    player_car.position[0] += player_car.velocity[0]
    player_car.position[1] += player_car.velocity[1]
    
    # Keep car within screen bounds
    player_car.position[0] = max(0, min(player_car.position[0], SCREEN_WIDTH))
    player_car.position[1] = max(0, min(player_car.position[1], SCREEN_HEIGHT))
    
    # Create player_rect for collision detection
    player_rect = pygame.Rect(
        player_car.position[0] - CAR_WIDTH/2,
        player_car.position[1] - CAR_HEIGHT/2,
        CAR_WIDTH,
        CAR_HEIGHT
    )
    
    # Draw checkpoints
    for i, checkpoint in enumerate(checkpoints):
        color = GREEN if i < current_checkpoint_index else YELLOW
        pygame.draw.rect(screen, color, checkpoint, 2)
    
    # Draw finish line with alternating pattern
    for i in range(10):
        color = BLACK if i % 2 == 0 else WHITE
        pygame.draw.rect(screen, color, (finish_line.x + i*10, finish_line.y, 10, finish_line.height))
    
    # Checkpoint detection with proper ordering
    if current_checkpoint_index < len(checkpoints):
        checkpoint = checkpoints[current_checkpoint_index]
        if player_rect.colliderect(checkpoint):
            if not checkpoint_hit:
                checkpoint_hit = True
                current_checkpoint_index += 1
                print(f"Checkpoint {current_checkpoint_index} reached!")
        else:
            checkpoint_hit = False
    
    # Finish line detection (only if all checkpoints have been passed)
    if current_checkpoint_index >= len(checkpoints) and player_rect.colliderect(finish_line):
        lap_count += 1
        current_lap_time = time.time() - player_car.current_lap_start
        player_car.last_lap_time = current_lap_time
        lap_times.append(current_lap_time)
        
        # Update best lap time
        if current_lap_time < player_car.best_lap:
            player_car.best_lap = current_lap_time
            
        print(f"Lap {lap_count} completed in {current_lap_time:.2f} seconds!")
        
        # Reset for next lap
        current_checkpoint_index = 0
        player_car.current_lap_start = time.time()
        
        # End game if max laps reached
        if lap_count >= max_laps:
            print(f"Race finished! Best lap: {player_car.best_lap:.2f}s")
    
    # Draw car
    car_surface = pygame.Surface((CAR_WIDTH, CAR_HEIGHT), pygame.SRCALPHA)
    pygame.draw.rect(car_surface, BLUE, (0, 0, CAR_WIDTH, CAR_HEIGHT))
    # Add a direction indicator
    pygame.draw.polygon(car_surface, RED, [(CAR_WIDTH-5, CAR_HEIGHT//2), (CAR_WIDTH, CAR_HEIGHT//2-5), (CAR_WIDTH, CAR_HEIGHT//2+5)])
    
    rotated_car = pygame.transform.rotate(car_surface, player_car.angle)
    car_rect = rotated_car.get_rect(center=player_car.position)
    screen.blit(rotated_car, car_rect)
    
    # In the game loop, after drawing the track and before drawing the car
    # Draw bombs
    for bomb in bombs:
        bomb_rect = bomb_image.get_rect(center=bomb.center)
        screen.blit(bomb_image, bomb_rect)

    # Bomb collision and explosion
    current_time = time.time()
    for bomb in bombs:
        if player_rect.colliderect(bomb) and explosion_pos is None:
            player_car.speed = 0
            player_car.position = start_position.copy()
            player_car.angle = 90  # Reset rotation to starting angle
            explosion_pos = bomb.center
            explosion_start = current_time
            print("Hit a bomb! Back to start.")
    
    # Draw explosion animation if active
    if explosion_pos is not None:
        if current_time - explosion_start < EXPLOSION_DURATION:
            explosion_rect = explosion_image.get_rect(center=explosion_pos)
            screen.blit(explosion_image, explosion_rect)
        else:
            explosion_pos = None

    # Display UI    
    # -----------------------------------------------------------------
    # UI Box with Race Data
    # -----------------------------------------------------------------
    ui_box_width = 200
    ui_box_height = 150
    ui_box_x = 10
    ui_box_y = SCREEN_HEIGHT - ui_box_height - 10

    ui_surface = pygame.Surface((ui_box_width, ui_box_height), pygame.SRCALPHA)
    ui_surface.fill((36, 36, 36, 180))
    pygame.draw.rect(ui_surface, (0, 255, 180), (0, 0, ui_box_width, ui_box_height), 3)

    # Race data text
    lap_text = title_font.render(f"{lap_count}/{max_laps}", True, (0, 255, 180))
    label_lap = data_font.render("LAP", True, (180, 180, 180))
    ui_surface.blit(label_lap, (10, 10))
    ui_surface.blit(lap_text, (10, 35))

    current_time = time.time() - player_car.current_lap_start
    current_lap_text = data_font.render(f"{current_time:.2f}s", True, WHITE)
    label_current = data_font.render("CURRENT", True, (180, 180, 180))
    ui_surface.blit(label_current, (10, 85))
    ui_surface.blit(current_lap_text, (10, 110))

    best_lap_val = player_car.best_lap if player_car.best_lap != float('inf') else 0
    best_lap_text = data_font.render(f"{best_lap_val:.2f}s", True, (0, 255, 180))
    label_best = data_font.render("BEST", True, (180, 180, 180))
    ui_surface.blit(label_best, (140, 85))
    ui_surface.blit(best_lap_text, (140, 110))

    screen.blit(ui_surface, (ui_box_x, ui_box_y))
    
    # Track status indicator (keep this outside the UI box)
    status_text = font.render("ON TRACK" if on_track else "OFF TRACK", True, GREEN if on_track else RED)
    screen.blit(status_text, (SCREEN_WIDTH - 150, 10))
    
    # Update the multiplayer data
    player_data = {
        "position": player_car.position,
        "angle": player_car.angle,
        "lap": lap_count,
        "checkpoints": current_checkpoint_index
    }
    
    try:
        client_socket.sendall(json.dumps(player_data).encode())
    except:
        pass  # Ignore if server connection failed
    
    pygame.display.flip()

pygame.quit()
try:
    client_socket.close()
except:
    pass