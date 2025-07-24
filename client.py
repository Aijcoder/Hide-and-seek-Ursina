from ursina import *
from ursina.prefabs.first_person_controller import FirstPersonController
from ursina.shaders import lit_with_shadows_shader
import websocket
import threading
import uuid
import json
import time
import tkinter as tk
from tkinter import simpledialog

# === TKINTER LAUNCHER ===
root = tk.Tk()
root.withdraw()

player_name = simpledialog.askstring("Player Name", "Enter your name:") or "Player"
SERVER_IP = simpledialog.askstring("Server IP", "Enter server IP:", initialvalue="ws://134.226.108.225:8765") or "ws://134.226.108.225:8765"

# === Multiplayer Setup ===
client_id = str(uuid.uuid4())

try:
    ws = websocket.WebSocket()
    ws.connect(SERVER_IP)
    print("[+] Connected to server.")
except Exception as e:
    print("[!] Could not connect to server:", e)
    exit()

# === Ursina Init ===
app = Ursina()
Entity.default_shader = lit_with_shadows_shader
Sky()
DirectionalLight().look_at(Vec3(1, -1, -1))
window.size = (1600, 900)

# === Global Vars ===
platforms = []
scoreboard = {"easy": [], "medium": [], "hard": []}

# === Platform Helper ===
def create_platform(pos, color=color.white, scale=(3, 0.5, 3), name=''):
    plat = Entity(model='cube', color=color, scale=scale, position=pos, collider='box', name=name)
    platforms.append(plat)
    return plat

# === Layout ===
spawn = create_platform(Vec3(0, 0, 0), color=color.azure, name='spawn')
for i in range(1, 10):
    create_platform(Vec3(0, 0.5 * i, i * 5), color=color.white, name=f'intro_{i}')

hub_pos = Vec3(0, 5, 50)
main_hub = create_platform(hub_pos, color=color.yellow, scale=(18, 0.5, 18), name='hub')

# Decoration
for i in range(-4, 5):
    for j in range(-4, 5):
        if i == 0 and j == 0:
            continue
        create_platform(hub_pos + Vec3(i*3, 0, j*3), color=color.gray, scale=(2.8, 0.3, 2.8))

easy_start = hub_pos + Vec3(-10, 0, 15)
medium_start = hub_pos + Vec3(0, 0, 15)
hard_start = hub_pos + Vec3(10, 0, 15)

easy_lane = [create_platform(easy_start + Vec3(0, i * 1.2, i * 4), color=color.green, name='easy') for i in range(6)]
medium_lane = [create_platform(medium_start + Vec3(0, i * 1.5, i * 4), color=color.orange, name='medium') for i in range(6)]
hard_lane = [create_platform(hard_start + Vec3(0, i * 2, i * 5), color=color.red, name='hard') for i in range(6)]

# === Player Controller ===
class ParkourPlayer(Entity):
    def __init__(self):
        super().__init__()
        self.controller = FirstPersonController(model='cube', origin_y=-0.5, color=color.orange)
        self.controller.position = spawn.position + Vec3(0, 2, 0)
        self.velocity = Vec3(0, 0, 0)
        self.acceleration = 20
        self.friction = 8
        self.gravity = 0.005
        self.jump_force = 20
        self.can_jump = True
        self.checkpoint = self.controller.position
        self.timer_running = False
        self.timer_start = 0
        self.lane_started = None
        self.completed_easy = False
        self.completed_medium = False

    def update(self):
        dt = time.dt

        # Movement
        move_input = Vec3(
            held_keys['d'] - held_keys['a'],
            0,
            held_keys['w'] - held_keys['s']
        ).normalized()

        cam_forward = camera.forward
        cam_forward.y = 0
        cam_forward = cam_forward.normalized()
        cam_right = Vec3(cam_forward.z, 0, -cam_forward.x)

        move_dir = (cam_right * move_input.x + cam_forward * move_input.z).normalized()
        target_velocity = move_dir * self.acceleration

        self.velocity = lerp(self.velocity, target_velocity, dt * 10)

        if move_input == Vec3(0,0,0):
            self.velocity = lerp(self.velocity, Vec3(0,0,0), dt * self.friction)

        self.controller.position += self.velocity * dt

        # Apply gravity
        if not self.controller.grounded:
            self.controller.y -= self.gravity

        # Jump
        # Jump
        if self.controller.grounded:
            if not held_keys['space']:
                self.can_jump = True
            elif held_keys['space'] and self.can_jump:
                self.controller.jump()
                self.controller.velocity_y = self.jump_force
                self.can_jump = False


        # Respawn
        if self.controller.y < -10:
            print('[!] Respawning to last checkpoint.')
            self.controller.position = self.checkpoint

        send_position()
        self.check_progress()

    def start_timer(self, lane_name):
        self.timer_running = True
        self.timer_start = time.time()
        self.lane_started = lane_name

    def stop_timer(self):
        if self.timer_running:
            elapsed = round(time.time() - self.timer_start, 2)
            self.timer_running = False
            print(f'[TIMER] Finished {self.lane_started} in {elapsed}s')
            scoreboard[self.lane_started].append((player_name, elapsed))
            scoreboard[self.lane_started].sort(key=lambda x: x[1])
            update_scoreboard()
            self.lane_started = None
            return elapsed

    def check_progress(self):
        pos = self.controller.position

        if not self.completed_easy and distance(pos, easy_lane[-1].position) < 2:
            self.stop_timer()
            self.completed_easy = True
            self.checkpoint = easy_lane[-1].position + Vec3(0, 2, 0)

        if self.completed_easy and not self.completed_medium and distance(pos, medium_lane[-1].position) < 2:
            self.stop_timer()
            self.completed_medium = True
            self.checkpoint = medium_lane[-1].position + Vec3(0, 2, 0)

        if self.completed_medium and distance(pos, hard_lane[-1].position) < 2:
            self.stop_timer()
            self.checkpoint = hard_lane[-1].position + Vec3(0, 2, 0)

        if not self.timer_running:
            if not self.completed_easy and distance(pos, easy_lane[0].position) < 2:
                self.start_timer('easy')
            elif self.completed_easy and not self.completed_medium and distance(pos, medium_lane[0].position) < 2:
                self.start_timer('medium')
            elif self.completed_medium and distance(pos, hard_lane[0].position) < 2:
                self.start_timer('hard')

player = ParkourPlayer()

# === Scoreboard UI ===
scoreboard_text = Text(text='', position=(.55, .4), origin=(0, 0), scale=1.25, background=True, color=color.white)

def update_scoreboard():
    text = '[🏁 SCOREBOARD]\n'
    for lane in ['easy', 'medium', 'hard']:
        text += f'\n{lane.capitalize()}:\n'
        for i, (name, t) in enumerate(scoreboard[lane][:5]):
            text += f'  {i+1}. {name} - {t:.2f}s\n'
    scoreboard_text.text = text

# === Lane Access Logic ===
from ursina import Vec3

def update():
    for plat in medium_lane:
        plat.enabled = player.completed_easy
    for plat in hard_lane:
        plat.enabled = player.completed_easy and player.completed_medium

    for pid, data in other_players.items():
        if 'entity' in data and 'label' in data:
            entity = data['entity']
            label = data['label']

            # Position name tag above the sphere (adjust Y based on sphere scale)
            label.world_position = entity.world_position + Vec3(0, 1.3, 0)

            # Face the name tag toward the camera (horizontal only)
            look_pos = Vec3(camera.world_position.x, label.y, camera.world_position.z)
            label.look_at(look_pos, axis='up')
            label.rotation_y += 180






# === Multiplayer ===
other_players = {}

def send_position():
    if ws and ws.connected:
        try:
            ws.send(json.dumps({
                'type': 'pos',
                'id': client_id,
                'name': player_name,
                'x': player.controller.x,
                'y': player.controller.y,
                'z': player.controller.z
            }))
        except Exception as e:
            print("[!] Send error:", e)

def listen_to_server():
    while True:
        try:
            msg = ws.recv()
            data = json.loads(msg)
            if data['type'] == 'pos' and data['id'] != client_id:
                pid = data['id']
                pos = Vec3(data['x'], data['y'], data['z'])

                
                if pid not in other_players:
                    # Create grounded player model using a sphere
                    model = Entity(
                        model='sphere',
                        color=color.azure,
                        scale=1,
                        position=pos,
                        collider='box'
                    )

                    # Roblox-style floating name tag
                    name_tag = Text(
                        text=data.get('name', 'Player'),
                        scale=1.5,
                        origin=(0, 0),
                        color=color.white,
                        world=True
                    )

                    other_players[pid] = {
                        'entity': model,
                        'label': name_tag
                    }
                else:
                    other_players[pid]['entity'].position = pos

        except Exception as e:
            print("[!] Connection error:", e)
            break

threading.Thread(target=listen_to_server, daemon=True).start()

app.run()
