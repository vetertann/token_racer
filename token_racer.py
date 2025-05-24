import os
import sys
import time
import threading
import termios
import tty
import random
from openai import OpenAI

# ---- LLM SETUP ----
LLM_API_KEY =   # <- Your OpenRouter API key

client = OpenAI(
    base_url="https://openrouter.ai/api/v1/",
    api_key=LLM_API_KEY,
)

# ---- GAME CONFIG ----
ROAD_WIDTH = 25
DISPLAY_HEIGHT = 25
PLAYER_CHAR = "🏎"
OBSTACLE_CHARS = ["#", "*", "~", "@"]
BASE_FPS = 12
ROAD_CHUNK_SIZE = 30

# Console width for centering
try:
    CONSOLE_WIDTH = os.get_terminal_size().columns
except Exception:
    CONSOLE_WIDTH = 120  # fallback if can't detect

# Game state variables
game_over = False
score = 0
current_gear = 1
max_gear = 10
player_x = ROAD_WIDTH // 2
player_y = DISPLAY_HEIGHT - 3
road_buffer = []
input_queue = []
input_lock = threading.Lock()
tokens_generated = 0

# Gear system - affects both speed and movement responsiveness
GEAR_SPEEDS = {
    1: {"fps_mult": 0.5, "move_speed": 1, "name": "1st"},
    2: {"fps_mult": 0.7, "move_speed": 1, "name": "2nd"},
    3: {"fps_mult": 1.0, "move_speed": 2, "name": "3rd"},
    4: {"fps_mult": 1.3, "move_speed": 2, "name": "4th"},
    5: {"fps_mult": 1.8, "move_speed": 3, "name": "5th"},
    6: {"fps_mult": 2.0, "move_speed": 4, "name": "6th"},
    7: {"fps_mult": 2.2, "move_speed": 5, "name": "7th"},
    8: {"fps_mult": 2.6, "move_speed": 6, "name": "8th"},
    9: {"fps_mult": 2.8, "move_speed": 7, "name": "9th"},
    10: {"fps_mult": 3.0, "move_speed": 8, "name": "10th"}
}

def create_safe_road_line(obstacle_positions=None):
    if obstacle_positions is None:
        obstacle_positions = []
    road_chars = [" "] * ROAD_WIDTH
    for pos in obstacle_positions:
        if 0 <= pos < ROAD_WIDTH:
            road_chars[pos] = random.choice(OBSTACLE_CHARS)
    return "|" + "".join(road_chars) + "|"

def validate_and_fix_road_line(line):
    if not line or not (line.startswith("|") and line.endswith("|")):
        return create_safe_road_line()
    interior = line[1:-1]
    if len(interior) != ROAD_WIDTH:
        return create_safe_road_line()
    safe_interior = ""
    for char in interior:
        if char in OBSTACLE_CHARS or char == " ":
            safe_interior += char
        else:
            safe_interior += random.choice(OBSTACLE_CHARS) if char != " " else " "
    return "|" + safe_interior + "|"

def llm_generate_road_chunk(previous_lines, chunk_size=ROAD_CHUNK_SIZE, difficulty_level=1):
    road_types = [
        "straight highway with occasional obstacles",
        "city street with construction zones",
        "racing circuit with chicanes and barriers",
        "desert highway with rockfall hazards"
    ]
    road_type = road_types[min(difficulty_level - 1, len(road_types) - 1)]
    ascii_obstacles = ", ".join(OBSTACLE_CHARS)
    prompt = f"""You are generating an ASCII racing track for a high-speed car game.

CRITICAL FORMAT REQUIREMENTS:
- Each line must be EXACTLY {ROAD_WIDTH + 2} characters long
- Format: '|' + exactly {ROAD_WIDTH} characters + '|'
- Use only these obstacle characters: {ascii_obstacles}
- Use space ' ' for empty road
- NO other characters allowed (no emoji, no special symbols)

ROAD TYPE: {road_type}

OBSTACLE PLACEMENT:
- Place 0-2 obstacles per line depending on difficulty
- Create interesting patterns: clusters, narrow passages, slalom courses
- Leave clear paths for skilled players
- Use only the specified ASCII characters: {ascii_obstacles}

DIFFICULTY LEVEL: {difficulty_level}/5
- Level 1-2: Sparse obstacles, wide passages
- Level 3-4: More obstacles, tighter passages  
- Level 5: Dense obstacle courses, narrow gaps

PREVIOUS ROAD CONTEXT:
{chr(10).join(previous_lines[-5:]) if previous_lines else "Starting new road section"}

Generate {chunk_size} consecutive road lines.
Each line must be exactly: |{' ' * ROAD_WIDTH}| (with obstacles replacing some spaces)

Output ONLY the road lines, nothing else. No explanations, no extra text."""

    try:
        result = client.chat.completions.create(
            model="qwen/qwen3-32b",
            max_tokens=chunk_size * 15,
            temperature=0.7,
            extra_body={
                "provider": {"only": ["Cerebras"]},
                "top_k": 30
            },
            messages=[
                {"role": "system", "content": "You generate ASCII race tracks. Use ONLY the specified characters. Each line must be EXACTLY the specified length."},
                {"role": "user", "content": prompt}
            ]
        )
        
        global tokens_generated
        if hasattr(result, 'usage') and result.usage:
            tokens_generated += result.usage.total_tokens
        else:
            tokens_generated += len(result.choices[0].message.content.split()) * 1.3
        
        lines = []
        raw_lines = result.choices[0].message.content.strip().split("\n")
        
        for line in raw_lines:
            line = line.strip()
            if line:
                fixed_line = validate_and_fix_road_line(line)
                lines.append(fixed_line)
        while len(lines) < chunk_size:
            num_obstacles = random.randint(0, min(3, difficulty_level))
            obstacle_positions = []
            if num_obstacles > 0:
                if random.random() < 0.3:
                    left_wall = random.randint(0, ROAD_WIDTH // 3)
                    right_wall = random.randint(2 * ROAD_WIDTH // 3, ROAD_WIDTH - 1)
                    obstacle_positions = list(range(left_wall, left_wall + 5)) + list(range(right_wall, min(ROAD_WIDTH, right_wall + 5)))
                elif random.random() < 0.3:
                    center = ROAD_WIDTH // 2 + random.randint(-10, 10)
                    for i in range(num_obstacles):
                        pos = center + (i - num_obstacles//2) * 3
                        if 0 <= pos < ROAD_WIDTH:
                            obstacle_positions.append(pos)
                else:
                    for _ in range(num_obstacles):
                        pos = random.randint(0, ROAD_WIDTH - 1)
                        if pos not in obstacle_positions:
                            obstacle_positions.append(pos)
            safe_line = create_safe_road_line(obstacle_positions)
            lines.append(safe_line)
        return lines[:chunk_size]
        
    except Exception as e:
        print(f"LLM error: {e}")
        fallback_lines = []
        for i in range(chunk_size):
            num_obstacles = random.randint(0, 2)
            obstacle_positions = []
            for _ in range(num_obstacles):
                pos = random.randint(0, ROAD_WIDTH - 1)
                if pos not in obstacle_positions:
                    obstacle_positions.append(pos)
            fallback_lines.append(create_safe_road_line(obstacle_positions))
        return fallback_lines

def initialize_road():
    global road_buffer
    road_buffer = llm_generate_road_chunk([], ROAD_CHUNK_SIZE * 3, 1)

def keypress_listener():
    global game_over, input_queue, current_gear
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    tty.setcbreak(fd)
    try:
        while not game_over:
            key = sys.stdin.read(1)
            with input_lock:
                if key.lower() == 'w':
                    input_queue.append('up')
                elif key.lower() == 'a':
                    input_queue.append('left')
                elif key.lower() == 's':
                    input_queue.append('down')
                elif key.lower() == 'd':
                    input_queue.append('right')
                elif key == ' ':
                    input_queue.append('gear_up')
                elif key == '\x1b':
                    next1 = sys.stdin.read(1)
                    if next1 == '[':
                        next2 = sys.stdin.read(1)
                        if next2 == 'A':
                            input_queue.append('up')
                        elif next2 == 'B':
                            input_queue.append('down')
                        elif next2 == 'C':
                            input_queue.append('right')
                        elif next2 == 'D':
                            input_queue.append('left')
                elif key == '\x03' or key.lower() == 'q':
                    game_over = True
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

def process_input():
    global player_x, player_y, current_gear, input_queue
    with input_lock:
        moves_this_frame = min(len(input_queue), GEAR_SPEEDS[current_gear]["move_speed"])
        for _ in range(moves_this_frame):
            if input_queue:
                action = input_queue.pop(0)
                if action == 'left' and player_x > 0:
                    player_x -= 1
                elif action == 'right' and player_x < ROAD_WIDTH - 1:
                    player_x += 1
                elif action == 'up' and player_y > 0:
                    player_y -= 1
                elif action == 'down' and player_y < DISPLAY_HEIGHT - 1:
                    player_y += 1
                elif action == 'gear_up':
                    current_gear = min(max_gear, current_gear + 1)

def validate_road_buffer():
    global road_buffer
    valid_lines = []
    for line in road_buffer:
        fixed_line = validate_and_fix_road_line(line)
        valid_lines.append(fixed_line)
    road_buffer = valid_lines

def road_refiller():
    global road_buffer
    while not game_over:
        if len(road_buffer) < ROAD_CHUNK_SIZE * 2:
            difficulty = min(5, (score // 150) + 1)
            new_chunk = llm_generate_road_chunk(road_buffer[:5], ROAD_CHUNK_SIZE, difficulty)
            road_buffer = new_chunk + road_buffer
            validate_road_buffer()
        time.sleep(0.2)

def check_collision():
    global road_buffer, player_x, player_y
    road_line_index = len(road_buffer) - DISPLAY_HEIGHT + player_y
    if 0 <= road_line_index < len(road_buffer):
        road_line = road_buffer[road_line_index]
        if (road_line.startswith("|") and road_line.endswith("|") and 
            len(road_line) == ROAD_WIDTH + 2):
            if 0 <= player_x < ROAD_WIDTH:
                cell = road_line[player_x + 1]
                return cell in OBSTACLE_CHARS
    return False

def draw_game_state():
    print("\033[2J\033[H", end="")
    print("🏁" * 20)
    gear_info = GEAR_SPEEDS[current_gear]
    print(f"🏎️  TURBO RACER  🏎️    Score: {score}    Gear: {gear_info['name']}    Speed: {gear_info['fps_mult']:.1f}x")
    print(f"🤖 Tokens generated: {tokens_generated}")
    print("🏁" * 20)
    print()
    if len(road_buffer) >= DISPLAY_HEIGHT:
        start_idx = len(road_buffer) - DISPLAY_HEIGHT
        display_lines = []
        road_line_length = ROAD_WIDTH + 2
        road_offset = max(0, (CONSOLE_WIDTH - road_line_length) // 2)
        left_pad = " " * road_offset
        for i in range(DISPLAY_HEIGHT):
            line = road_buffer[start_idx + i]
            line_chars = list(line)
            if i == player_y and 0 <= player_x + 1 < len(line_chars):
                line_chars[player_x + 1] = PLAYER_CHAR
            display_lines.append(left_pad + "".join(line_chars))
        for line in display_lines:
            print(line)
    print()
    print("🎮 Controls:")
    print("  WASD or Arrow Keys: Move freely  |  SPACE: Shift gear up  |  Q: Quit")
    gear_display = ""
    for i in range(1, max_gear + 1):
        if i == current_gear:
            gear_display += f"[{i}] "
        else:
            gear_display += f" {i}  "
    print(f"Gears: {gear_display}")
    speed_level = int(gear_info['fps_mult'] * 5)
    speed_bar = "█" * speed_level + "▓" * (10 - speed_level)
    print(f"Speed: [{speed_bar}]")

# ---- MAIN GAME INITIALIZATION ----
print("🏎️  Initializing Token Racer...")
print("🛣️  Generating initial race track...")

initialize_road()
threading.Thread(target=keypress_listener, daemon=True).start()
threading.Thread(target=road_refiller, daemon=True).start()

print("🏁 Ready to race!")

print("\nPress ENTER to start...")
input()

try:
    last_move_time = time.time()
    while not game_over:
        current_time = time.time()
        process_input()
        if len(road_buffer) < DISPLAY_HEIGHT + 10:
            difficulty = min(5, (score // 150) + 1)
            new_chunk = llm_generate_road_chunk(road_buffer[:5], ROAD_CHUNK_SIZE, difficulty)
            road_buffer = new_chunk + road_buffer
            validate_road_buffer()
        if check_collision():
            game_over = True
            break
        gear_info = GEAR_SPEEDS[current_gear]
        frame_delay = 1.0 / (BASE_FPS * gear_info["fps_mult"])
        if current_time - last_move_time >= frame_delay:
            if len(road_buffer) > DISPLAY_HEIGHT + 10:
                road_buffer.pop()
            score += current_gear
            last_move_time = current_time
        draw_game_state()
        time.sleep(0.02)
except KeyboardInterrupt:
    game_over = True

print("\033[2J\033[H", end="")
print("💥" * 25)
print("🏎️ ☠️  CRASH! GAME OVER ☠️  🏎️")  
print("💥" * 25)
print()
print(f"🏆 Final Score: {score}")
print(f"⚙️  Highest Gear Reached: {GEAR_SPEEDS[current_gear]['name']}")
print(f"🚀 Top Speed: {GEAR_SPEEDS[current_gear]['fps_mult']:.1f}x")
print(f"🤖 Total Tokens Generated: {tokens_generated}")

if score > 500:
    print("🎉 Outstanding! You're a racing legend!")
elif score > 200:
    print("👏 Excellent driving! You've mastered the gears!")
elif score > 100:
    print("👍 Good run! Keep practicing those gear shifts!")
else:
    print("🆕 Not bad for a beginner! Try using higher gears for more points!")

print()
print("Thanks for playing Token Racer! 🏁")
