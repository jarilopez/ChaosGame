import socket
import threading
import json
import pygame
import time
import math

# ----------------------------------------------------------------
#                   CONFIGURACIÓN INICIAL
# ----------------------------------------------------------------
SERVER_IP = '192.168.33.68'
SERVER_PORT = 5555

pygame.init()
SCREEN_WIDTH, SCREEN_HEIGHT = 1441, 768
CAR_WIDTH, CAR_HEIGHT = 30, 20
FPS = 60

# ----------------------------------------------------------------
#                   CARGA DE IMÁGENES
# ----------------------------------------------------------------
bomb_image = pygame.image.load('bomb.png')
bomb_image = pygame.transform.scale(bomb_image, (20, 20))
explosion_image = pygame.image.load('explosion.png')
explosion_image = pygame.transform.scale(explosion_image, (40, 40))

# Explosión
explosion_pos = None
explosion_start = 0
EXPLOSION_DURATION = 0.5

# ----------------------------------------------------------------
#                   FUENTES (más pequeñas)
# ----------------------------------------------------------------
font = pygame.font.SysFont("Arial", 20)        # Texto general
title_font = pygame.font.SysFont("Arial", 28, bold=True)  # Título reducido
data_font = pygame.font.SysFont("Arial", 18)   # Texto pequeño para UI

# ----------------------------------------------------------------
#                   COLORES
# ----------------------------------------------------------------
# Fondo degradado
BG_TOP = (20, 20, 40)
BG_BOTTOM = (40, 40, 80)

# Header y texto
HEADER_BG = (0, 0, 0, 150)      # Semitransparente para header
TITLE_COLOR = (0, 220, 255)     # Color cian para el título
TEXT_COLOR = (220, 220, 220)    # Texto principal
ACCENT_COLOR = (0, 255, 180)    # Acento neón
GOLD = (255, 215, 0)

# UI
UI_BG = (30, 30, 30, 180)
UI_BORDER = (0, 255, 180)

# Pista y otros
TRACK_COLOR = (40, 40, 40)
TRACK_BORDER_COLOR = (0, 255, 180)
GRASS_COLOR = (20, 120, 50)
WHITE = (240, 240, 240)
RED = (230, 57, 70)
BLUE = (66, 135, 245)
YELLOW = (255, 241, 118)
BLACK = (36, 36, 36)
GREEN = (0, 200, 80)           

# ----------------------------------------------------------------
#                   FÍSICA
# ----------------------------------------------------------------
ACCELERATION = 0.1
TURNING_SPEED = 4.0
FRICTION = 0.01
MAX_SPEED = 9.5
DRIFT_FACTOR = 0.55
GRASS_SLOWDOWN = 0.4

# ----------------------------------------------------------------
#                   FUNCIÓN DEGRADADO
# ----------------------------------------------------------------
def draw_vertical_gradient(surface, color_top, color_bottom):
    width = surface.get_width()
    height = surface.get_height()
    for y in range(height):
        ratio = y / float(height)
        r = int(color_top[0] * (1 - ratio) + color_bottom[0] * ratio)
        g = int(color_top[1] * (1 - ratio) + color_bottom[1] * ratio)
        b = int(color_top[2] * (1 - ratio) + color_bottom[2] * ratio)
        pygame.draw.line(surface, (r, g, b), (0, y), (width, y))

# ----------------------------------------------------------------
#                   CLASE COCHE
# ----------------------------------------------------------------
class Car:
    def __init__(self, x, y):
        self.position = [x, y]
        self.velocity = [0, 0]
        self.angle = 0
        self.speed = 0
        self.acceleration_time = 0
        self.checkpoint_times = []
        self.best_lap = float('inf')
        self.current_lap_start = time.time()
        self.last_lap_time = 0
        self.id = str(time.time())  # Unique ID for each car
        

# ----------------------------------------------------------------
#                   DEFINICIÓN DE PISTA CON OFFSET
# ----------------------------------------------------------------
offset_y = 70  # Reservamos 70px arriba para el header

track_outer_original = [
    (50, 50), (1350, 50), (1350, 300),
    (1050, 300), (1050, 400), (1350, 400),
    (1350, 600), (550, 600), (400, 450),
    (250, 450), (150, 550), (50, 450),
    (50, 50)
]
track_inner_original = [
    (150, 150), (1250, 150), (1250, 200),
    (950, 200), (950, 500), (1250, 500),
    (1250, 500), (550, 500), (450, 400),
    (350, 400), (200, 400), (150, 350),
    (150, 150)
]

# Aplicamos offset vertical
track_outer = [(x, y + offset_y) for x, y in track_outer_original]
track_inner = [(x, y + offset_y) for x, y in track_inner_original]

# Posición inicial del coche
start_position_original = [120, 100]
start_position = [start_position_original[0], start_position_original[1] + offset_y]

# Checkpoints
checkpoints_original = [
    pygame.Rect(350, 50, 40, 40),
    pygame.Rect(750, 110, 40, 40),
    pygame.Rect(950, 350, 40, 40),
    pygame.Rect(900, 500, 40, 40),
    pygame.Rect(550, 500, 40, 40),
    pygame.Rect(350, 400, 40, 50),
    pygame.Rect(50, 300, 40, 40),
]
checkpoints = []
for rect in checkpoints_original:
    new_rect = pygame.Rect(rect.x, rect.y + offset_y, rect.width, rect.height)
    checkpoints.append(new_rect)

# Línea de meta
finish_line_original = pygame.Rect(50, 150, 50, 50)
finish_line = pygame.Rect(
    finish_line_original.x,
    finish_line_original.y + offset_y,
    finish_line_original.width,
    finish_line_original.height
)

# Bombas
bombs_original = [
    pygame.Rect(300, 100, 10, 10),
    pygame.Rect(1000, 500, 10, 10),
    pygame.Rect(700, 530, 10, 10),
]
bombs = []
for rect in bombs_original:
    new_rect = pygame.Rect(rect.x, rect.y + offset_y, rect.width, rect.height)
    bombs.append(new_rect)

# ----------------------------------------------------------------
#                   SUPERFICIE DE LA PISTA
# ----------------------------------------------------------------
track_surface = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
track_surface.fill((0, 0, 0, 0))

pygame.draw.rect(track_surface, GRASS_COLOR, (0, 0, SCREEN_WIDTH, SCREEN_HEIGHT))
pygame.draw.polygon(track_surface, TRACK_COLOR, track_outer)
pygame.draw.polygon(track_surface, GRASS_COLOR, track_inner)
pygame.draw.lines(track_surface, TRACK_BORDER_COLOR, True, track_outer, 5)
pygame.draw.lines(track_surface, TRACK_BORDER_COLOR, True, track_inner, 5)

track_mask = pygame.mask.from_threshold(track_surface, TRACK_COLOR, (1, 1, 1, 255))

def is_on_track(pos, car_width, car_height, angle):
    car_surface = pygame.Surface((car_width * 0.8, car_height * 0.8), pygame.SRCALPHA)
    pygame.draw.rect(car_surface, (255, 255, 255, 128), (0, 0, car_width * 0.8, car_height * 0.8))
    rotated_car = pygame.transform.rotate(car_surface, angle)
    car_rect = rotated_car.get_rect(center=pos)
    car_mask = pygame.mask.from_surface(rotated_car)
    offset = (car_rect.x, car_rect.y)
    overlap = track_mask.overlap_area(car_mask, offset)
    return overlap > (car_width * car_height * 0.3)

# ----------------------------------------------------------------
#                   MULTIJUGADOR
# ----------------------------------------------------------------
players = {}
client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
try:
    client_socket.connect((SERVER_IP, SERVER_PORT))
except:
    print("Could not connect to server. Running in single player mode.")

# Add near the top with other global variables
game_winner = None
race_positions = []

# Modify the receive_data function to handle game end
def receive_data(sock):
    global players, game_winner, race_positions, game_finished
    buffer = ""
    while True:
        try:
            data = sock.recv(4096)
            if not data:
                break
            
            try:
                buffer += data.decode()
                while buffer:
                    try:
                        response = json.loads(buffer)
                        if "players" in response:
                            players = response["players"]
                        if "winner" in response:
                            game_winner = response["winner"]
                            race_positions = response.get("positions", [])
                            game_finished = True
                        buffer = ""
                        break
                    except json.JSONDecodeError as e:
                        if "Extra data" in str(e):
                            # Try to find the end of the first complete JSON object
                            pos = buffer.find("}")
                            if pos != -1:
                                first_json = buffer[:pos+1]
                                buffer = buffer[pos+1:]
                                try:
                                    response = json.loads(first_json)
                                    if "players" in response:
                                        players = response["players"]
                                except:
                                    buffer = ""
                            else:
                                buffer = ""
                        else:
                            buffer = ""
                            break
                        
            except UnicodeDecodeError:
                buffer = ""
                continue
                
        except Exception as e:
            print(f"Connection error: {e}")
            break

threading.Thread(target=receive_data, args=(client_socket,), daemon=True).start()

# ----------------------------------------------------------------
#                   SISTEMA DE LAPS
# ----------------------------------------------------------------
lap_count = 0
max_laps = 3
current_checkpoint_index = 0
checkpoint_hit = False
lap_times = []
game_finished = False
total_time = 0

# ----------------------------------------------------------------
#                   CREAR COCHE
# ----------------------------------------------------------------
player_car = Car(start_position[0], start_position[1])
player_car.angle = 90

# ----------------------------------------------------------------
#                   PYGAME DISPLAY
# ----------------------------------------------------------------
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
pygame.display.set_caption("RACING GAME: VELOCITY UNLEASHED")
pygame.display.set_icon(bomb_image)  # Set window icon
clock = pygame.time.Clock()

running = True
while running:
    clock.tick(FPS)
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

    # 1. Dibujar fondo con degradado
    background = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
    draw_vertical_gradient(background, BG_TOP, BG_BOTTOM)
    screen.blit(background, (0, 0))

    # 2. Dibujar la pista (incluyendo césped y bordes)
    screen.blit(track_surface, (0, 0))

    # 3. Header semitransparente
    header_surface = pygame.Surface((SCREEN_WIDTH, offset_y), pygame.SRCALPHA)
    header_surface.fill((0, 0, 0, 180))  # Made slightly more opaque
    screen.blit(header_surface, (0, 0))

    # 4. Título centrado
    title_str = "RACING GAME: VELOCITY UNLEASHED"
    # Changed from TITLE_COLOR to a bright white with slight blue tint
    title_surf = title_font.render(title_str, True, (240, 250, 255))
    title_rect = title_surf.get_rect(center=(SCREEN_WIDTH // 2, offset_y // 2))
    screen.blit(title_surf, title_rect)

    # 5. Dibujar bombas
    for bomb in bombs:
        bomb_rect = bomb_image.get_rect(center=bomb.center)
        screen.blit(bomb_image, bomb_rect)

    # 6. Controles del coche
    keys = pygame.key.get_pressed()
    if keys[pygame.K_LEFT]:
        player_car.angle += TURNING_SPEED * 1.2
    if keys[pygame.K_RIGHT]:
        player_car.angle -= TURNING_SPEED * 1.2
    if keys[pygame.K_UP]:
        player_car.acceleration_time += 1/FPS
        acceleration = ACCELERATION * min(player_car.acceleration_time, 3.0)
        player_car.speed = min(player_car.speed + acceleration, MAX_SPEED)
    elif keys[pygame.K_DOWN]:
        player_car.acceleration_time += 1/FPS
        deceleration = ACCELERATION * min(player_car.acceleration_time, 2.0)
        player_car.speed = max(player_car.speed - deceleration, -MAX_SPEED / 2.5)
    else:
        player_car.acceleration_time = 0
        player_car.speed *= (1 - FRICTION * 1.5)

    # 7. Aplicar física de pista/césped
    on_track = is_on_track(player_car.position, CAR_WIDTH, CAR_HEIGHT, player_car.angle)
    if on_track:
        player_car.speed *= (1 - FRICTION)
    else:
        player_car.speed *= (1 - FRICTION - GRASS_SLOWDOWN)

    # Actualizar posición
    angle_rad = math.radians(player_car.angle)
    player_car.velocity[0] = math.sin(angle_rad) * player_car.speed
    player_car.velocity[1] = math.cos(angle_rad) * player_car.speed
    player_car.position[0] += player_car.velocity[0]
    player_car.position[1] += player_car.velocity[1]

    # Limitar a la pantalla
    player_car.position[0] = max(0, min(player_car.position[0], SCREEN_WIDTH))
    player_car.position[1] = max(0, min(player_car.position[1], SCREEN_HEIGHT))

    # 8. Dibujar línea de meta y checkpoints
    for i in range(10):
        c = BLACK if i % 2 == 0 else WHITE
        pygame.draw.rect(screen, c, (finish_line.x + i*10, finish_line.y, 10, finish_line.height))

    for i, checkpoint in enumerate(checkpoints):
        color = GREEN if i < current_checkpoint_index else YELLOW
        pygame.draw.rect(screen, color, checkpoint, 3)
        num_surf = font.render(str(i+1), True, color)
        # Get the text size to center it properly
        text_rect = num_surf.get_rect()
        text_rect.center = checkpoint.center
        screen.blit(num_surf, text_rect)

    # 9. Rect del coche para colisiones
    player_rect = pygame.Rect(
        player_car.position[0] - CAR_WIDTH/2,
        player_car.position[1] - CAR_HEIGHT/2,
        CAR_WIDTH,
        CAR_HEIGHT
    )

    # Checkpoints
    if current_checkpoint_index < len(checkpoints):
        checkpoint = checkpoints[current_checkpoint_index]
        if player_rect.colliderect(checkpoint):
            if not checkpoint_hit:
                checkpoint_hit = True
                current_checkpoint_index += 1
                print(f"Checkpoint {current_checkpoint_index} reached!")
        else:
            checkpoint_hit = False

    # Meta
    if current_checkpoint_index >= len(checkpoints) and player_rect.colliderect(finish_line):
        lap_count += 1
        current_lap_time = time.time() - player_car.current_lap_start
        player_car.last_lap_time = current_lap_time
        lap_times.append(current_lap_time)

        if current_lap_time < player_car.best_lap:
            player_car.best_lap = current_lap_time

        print(f"Lap {lap_count} completed in {current_lap_time:.2f} seconds!")
        current_checkpoint_index = 0
        player_car.current_lap_start = time.time()

        if lap_count >= max_laps:
            game_finished = True
            total_time = sum(lap_times)
            player_car.speed = 0
            print(f"Race finished! Total time: {total_time:.2f}s, Best lap: {player_car.best_lap:.2f}s")

    # 10. Colisión con bombas y explosión
    current_time = time.time()
    for bomb in bombs:
        if player_rect.colliderect(bomb) and explosion_pos is None:
            player_car.speed = 0
            player_car.position = start_position.copy()
            player_car.angle = 90
            explosion_pos = bomb.center
            explosion_start = current_time
            print("Hit a bomb! Back to start.")

    if explosion_pos is not None:
        if current_time - explosion_start < EXPLOSION_DURATION:
            exp_rect = explosion_image.get_rect(center=explosion_pos)
            screen.blit(explosion_image, exp_rect)
        else:
            explosion_pos = None

    # 11. Dibujar el coche
    car_surf = pygame.Surface((CAR_WIDTH, CAR_HEIGHT), pygame.SRCALPHA)
    pygame.draw.rect(car_surf, BLUE, (0, 0, CAR_WIDTH, CAR_HEIGHT))
    pygame.draw.polygon(car_surf, RED, [
        (CAR_WIDTH-5, CAR_HEIGHT//2),
        (CAR_WIDTH, CAR_HEIGHT//2-5),
        (CAR_WIDTH, CAR_HEIGHT//2+5)
    ])
    # Move this to the image loading section at the top of the file
    car_images = {
        'blue': pygame.transform.rotate(pygame.transform.scale(pygame.image.load('car_blue.png'), (CAR_WIDTH, CAR_HEIGHT)), 270),
        'red': pygame.transform.rotate(pygame.transform.scale(pygame.image.load('car_red.png'), (CAR_WIDTH, CAR_HEIGHT)), 270),
        'green': pygame.transform.rotate(pygame.transform.scale(pygame.image.load('car_green.png'), (CAR_WIDTH, CAR_HEIGHT)), 270),
        'yellow': pygame.transform.rotate(pygame.transform.scale(pygame.image.load('car_yellow.png'), (CAR_WIDTH, CAR_HEIGHT)), 270),
    }
    
    PLAYER_COLORS = ['blue', 'red', 'green', 'yellow']
    rotated_car = pygame.transform.rotate(car_images['blue'], player_car.angle)
    car_rect = rotated_car.get_rect(center=player_car.position)
    screen.blit(rotated_car, car_rect)

    # Draw other players
    for player_id, player_data in players.items():
        if str(player_id) != str(player_car.id):
            try:
                other_pos = player_data["position"]
                other_angle = player_data["angle"]
                
                # Get color based on player_id
                color_index = (int(player_id) - 1) % len(PLAYER_COLORS)
                player_color = PLAYER_COLORS[color_index]
                
                # Draw other player's car with their color
                other_car = pygame.transform.rotate(car_images[player_color], other_angle)
                other_rect = other_car.get_rect(center=other_pos)
                screen.blit(other_car, other_rect)
                
                # Draw player ID and lap info with matching color
                player_info = f"P{player_id} - Lap {player_data.get('lap', 0)}"
                player_label = font.render(player_info, True, player_color)
                label_rect = player_label.get_rect(center=(other_pos[0], other_pos[1] - 30))
                screen.blit(player_label, label_rect)
            except (KeyError, TypeError):
                continue

    # 12. UI BOX (más pequeña)
    ui_box_width = 320
    ui_box_height = 80
    ui_box_x = 10
    ui_box_y = SCREEN_HEIGHT - ui_box_height - 10

    ui_surface = pygame.Surface((ui_box_width, ui_box_height), pygame.SRCALPHA)
    ui_surface.fill(UI_BG)
    pygame.draw.rect(ui_surface, UI_BORDER, (0, 0, ui_box_width, ui_box_height), 2)
    
    # All three titles in the same row with bold text
    label_lap = pygame.font.SysFont("Arial", 18, bold=True).render("LAP", True, TEXT_COLOR)
    label_current = pygame.font.SysFont("Arial", 18, bold=True).render("CURRENT", True, TEXT_COLOR)
    label_best = pygame.font.SysFont("Arial", 18, bold=True).render("BEST", True, TEXT_COLOR)
    
    # Position the three titles evenly
    ui_surface.blit(label_lap, (30, 10))
    ui_surface.blit(label_current, (120, 10))
    ui_surface.blit(label_best, (230, 10))
    
    # Values below their respective titles
    lap_text = title_font.render(f"{lap_count}/{max_laps}", True, ACCENT_COLOR)
    time_val = time.time() - player_car.current_lap_start
    current_lap_text = data_font.render(f"{time_val:.2f}s", True, WHITE)
    best_lap_val = player_car.best_lap if player_car.best_lap != float('inf') else 0
    best_lap_text = data_font.render(f"{best_lap_val:.2f}s", True, GOLD)
    
    # Position the values below their titles
    ui_surface.blit(lap_text, (30, 40))
    ui_surface.blit(current_lap_text, (120, 40))
    ui_surface.blit(best_lap_text, (230, 40))

    screen.blit(ui_surface, (ui_box_x, ui_box_y))

    # Indicador ON/OFF TRACK
    status_txt = font.render("ON TRACK" if on_track else "OFF TRACK", True, GREEN if on_track else RED)
    screen.blit(status_txt, (SCREEN_WIDTH - 150, offset_y + 10))

    # 13. Leaderboard si terminó la carrera
    if game_finished:
        lb_surf = pygame.Surface((360, 280), pygame.SRCALPHA)
        lb_surf.fill((0, 0, 0, 160))
        pygame.draw.rect(lb_surf, ACCENT_COLOR, (0, 0, 360, 280), 2)

        lb_title = title_font.render("RACE FINISHED!", True, ACCENT_COLOR)
        lb_title_rect = lb_title.get_rect(center=(180, 30))
        lb_surf.blit(lb_title, lb_title_rect)

        total_txt = data_font.render(f"Total Time: {total_time:.2f}s", True, WHITE)
        lb_surf.blit(total_txt, (20, 70))

        best_txt = data_font.render(f"Best Lap: {player_car.best_lap:.2f}s", True, GOLD)
        lb_surf.blit(best_txt, (20, 100))

        laps_title = data_font.render("Lap Times:", True, WHITE)
        lb_surf.blit(laps_title, (20, 140))

        for i, lt in enumerate(lap_times):
            lt_txt = data_font.render(f"Lap {i+1}: {lt:.2f}s", True, WHITE)
            lb_surf.blit(lt_txt, (40, 165 + i*25))

        exit_txt = data_font.render("Press ESC to exit", True, ACCENT_COLOR)
        exit_rect = exit_txt.get_rect(center=(180, 250))
        lb_surf.blit(exit_txt, exit_rect)

        lb_rect = lb_surf.get_rect(center=(SCREEN_WIDTH//2, SCREEN_HEIGHT//2))
        screen.blit(lb_surf, lb_rect)

        # Salir con ESC
        if keys[pygame.K_ESCAPE]:
            running = False

    # ----------------------------------------------------------------
    #                   ACTUALIZAR MULTIJUGADOR
    # ----------------------------------------------------------------
    player_data = {
        "position": player_car.position,
        "angle": player_car.angle,
        "lap": lap_count,
        "checkpoints": current_checkpoint_index,
        "id": player_car.id  # Add this to Car class initialization
    }
    try:
        # Update multiplayer section in game loop
        message = json.dumps(player_data) + "\n"
        client_socket.sendall(message.encode())
    except:
        pass

    pygame.display.flip()

pygame.quit()
try:
    client_socket.close()
except:
    pass

# Modify the game finish section
    if game_finished:
        lb_surf = pygame.Surface((400, 320), pygame.SRCALPHA)
        lb_surf.fill((0, 0, 0, 180))
        pygame.draw.rect(lb_surf, ACCENT_COLOR, (0, 0, 400, 320), 2)

        if game_winner == player_car.id:
            lb_title = title_font.render("YOU WIN!", True, GOLD)
        else:
            lb_title = title_font.render("RACE FINISHED!", True, ACCENT_COLOR)
        lb_title_rect = lb_title.get_rect(center=(200, 30))
        lb_surf.blit(lb_title, lb_title_rect)

        if game_winner:
            winner_txt = data_font.render(f"Winner: Player {game_winner}", True, GOLD)
            lb_surf.blit(winner_txt, (20, 70))

        # Show positions
        pos_title = data_font.render("Final Positions:", True, WHITE)
        lb_surf.blit(pos_title, (20, 110))

        for i, player_id in enumerate(race_positions):
            position_txt = data_font.render(
                f"{i+1}. Player {player_id}" + (" (You)" if player_id == player_car.id else ""),
                True,
                GOLD if player_id == game_winner else WHITE
            )
            lb_surf.blit(position_txt, (40, 140 + i*25))

        # Show your stats if you finished
        if player_car.id == game_winner:
            total_txt = data_font.render(f"Your Time: {total_time:.2f}s", True, WHITE)
            lb_surf.blit(total_txt, (20, 220))
            best_txt = data_font.render(f"Best Lap: {player_car.best_lap:.2f}s", True, GOLD)
            lb_surf.blit(best_txt, (20, 250))

        exit_txt = data_font.render("Press ESC to exit", True, ACCENT_COLOR)
        exit_rect = exit_txt.get_rect(center=(200, 290))
        lb_surf.blit(exit_txt, exit_rect)

        lb_rect = lb_surf.get_rect(center=(SCREEN_WIDTH//2, SCREEN_HEIGHT//2))
        screen.blit(lb_surf, lb_rect)

# Modify the multiplayer update section to include game finish
    player_data = {
        "position": player_car.position,
        "angle": player_car.angle,
        "lap": lap_count,
        "checkpoints": current_checkpoint_index,
        "id": player_car.id,
        "finished": game_finished,
        "total_time": total_time if game_finished else 0
    }
