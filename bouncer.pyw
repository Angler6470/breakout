import pygame
import sys
import os
import wave
import struct
import math
import random

# Generate the bounce sound if it's missing
if not os.path.exists("bounce.wav"):
    sample_rate = 44100
    duration = 0.10
    start_freq = 1410.0
    end_freq = 1350.0
    decay_constant = 0.03
    
    with wave.open("bounce.wav", "w") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        phase = 0.0
        for i in range(int(sample_rate * duration)):
            progress = i / (sample_rate * duration)
            current_freq = start_freq + (end_freq - start_freq) * progress
            phase += 2.0 * math.pi * current_freq / sample_rate
            value = math.sin(phase)
            decay = math.exp(-i / (sample_rate * decay_constant))
            sample = int(value * decay * 32767.0)
            wav_file.writeframesraw(struct.pack('<h', sample))

# Start the engine, fonts, and audio mixer
pygame.init()
pygame.mixer.init()

is_fullscreen = False
screen = pygame.display.set_mode((800, 600))
render_surf = pygame.Surface((800, 600)) 
pygame.display.set_caption("Corner Critters Breakout")
clock = pygame.time.Clock()

font = pygame.font.SysFont(None, 36)
overlay_font = pygame.font.SysFont(None, 24)
game_over_font = pygame.font.SysFont('impact', 100) 
button_font = pygame.font.SysFont('impact', 36)

# Load Status Icons and set up animation tracking
status_icons = {}
icon_filenames = {
    'walrus': 'walrus_icon.png',
    'tomato': 'tomato_icon.png',
    'shark': 'shark_icon.png',
    'raccoon': 'raccoon_icon.png',
    'stego': 'stego_icon.png',
    'trex': 'trex_icon.png',
    'triceratops': 'triceratops_icon.png',
    'pumpkin': 'pumpkin_icon.png',
    'elephant': 'elephant_icon.png'
}

icon_anim_state = {}
for key, filename in icon_filenames.items():
    icon_anim_state[key] = {'offset': 0, 'angle': 0, 'was_active': False}
    icon_path = os.path.join("icons", filename)
    try:
        if os.path.exists(icon_path):
            img = pygame.image.load(icon_path).convert_alpha()
            status_icons[key] = pygame.transform.smoothscale(img, (32, 32))
        else:
            raise FileNotFoundError
    except Exception:
        # Generate a pink placeholder if the icon file is missing
        temp_surf = pygame.Surface((32, 32))
        temp_surf.fill((255, 0, 255))
        status_icons[key] = temp_surf

try:
    bounce_sound = pygame.mixer.Sound("bounce.wav")
except FileNotFoundError:
    class DummySound:
        def play(self): pass
    bounce_sound = DummySound()

# Colors
BG_COLOR = (30, 30, 30)
PADDLE_COLOR = (200, 200, 200)
BTN_COLOR = (100, 200, 100)
BTN_HOVER = (150, 255, 150)

# UI & State Variables
score = 0
lives = 3
rows_remaining = 3
game_state = "PLAYING"
game_over_y = -120 
ball_trail = [] 

# Power-up Trackers
walrus_timer = 0 
tomato_timer = 0 
raccoon_timer = 0 
bulldog_timer = 0
stego_timer = 0 
trex_timer = 0 
triceratops_timer = 0
pumpkin_timer = 0
shake_timer = 0
elephant_msg_timer = 0
triceratops_drift = 0
shark_missiles = 0
active_missiles = []
dirt_blocks = []
extra_balls = []

# Grid Drop Timer
GRID_DROP_EVENT = pygame.USEREVENT + 1
pygame.time.set_timer(GRID_DROP_EVENT, 15000)
last_drop_time = pygame.time.get_ticks()

# Set up the actors
paddle = pygame.Rect(350, 550, 100, 15)
base_paddle_speed = 7

# Dynamic Ball Setup
ball_size = 20
ball = pygame.Rect(390, 300, ball_size, ball_size)
ball_dx = 5 
ball_dy = -5
ball_angle = 0

def create_ball_surface(size):
    surf = pygame.Surface((size, size), pygame.SRCALPHA)
    radius = size // 2
    line_w = max(2, size // 6)
    pygame.draw.circle(surf, (255, 100, 100), (radius, radius), radius)
    pygame.draw.line(surf, (255, 255, 255), (radius, 0), (radius, size), line_w)
    pygame.draw.line(surf, (255, 255, 255), (0, radius), (size, radius), line_w)
    return surf

ball_surface = create_ball_surface(ball_size)
restart_btn = pygame.Rect(300, 350, 200, 60)

# Build the Grid
critter_files = [
    "aggressive-shark.png", "armored-walrus.png", "bandit-raccoon.png",
    "basic-blueberry.png", "bulldog-retriever.png", "charging-gorilla.png",
    "heavy-pumpkin.png", "smashing-stegosaurus.png", "sneaky-t-rex.png",
    "stampeding-elephant.png", "tough-tomato.png", "treading-triceratops.png"
]

block_w, block_h = 42, 42
loaded_critters = []
for f in critter_files:
    try:
        # Updated to pull from the 'images' folder
        image_path = os.path.join("images", f)
        img = pygame.image.load(image_path).convert_alpha()
        w, h = img.get_size()
        crop_size = min(w, h) 
        left = (w - crop_size) // 2
        crop_rect = pygame.Rect(left, 0, crop_size, crop_size)
        cropped_img = img.subsurface(crop_rect)
        final_img = pygame.transform.smoothscale(cropped_img, (block_w, block_h))
        loaded_critters.append({'img': final_img, 'name': f})
    except FileNotFoundError:
        pass 

generic_block = pygame.Surface((block_w, block_h))
generic_block.fill((100, 150, 200)) 
pygame.draw.rect(generic_block, (50, 100, 150), generic_block.get_rect(), 3) 

dirt_surface = pygame.Surface((block_w, block_h))
dirt_surface.fill((120, 80, 40)) 
pygame.draw.rect(dirt_surface, (80, 50, 20), dirt_surface.get_rect(), 3)

def build_level():
    blocks_list = []
    for row in range(6):
        for col in range(16):
            rect = pygame.Rect(col * (block_w + 5) + 24, row * (block_h + 5) + 50, block_w, block_h)
            
            if random.random() < 0.15 and loaded_critters:
                weights = []
                for c in loaded_critters:
                    if c['name'] == "basic-blueberry.png":
                        if row < 2:
                            weights.append(70)
                        elif row < 4:
                            weights.append(20)
                        else:
                            weights.append(10)
                    else:
                        weights.append(10)
                        
                critter = random.choices(loaded_critters, weights=weights)[0]
                blocks_list.append({'rect': rect, 'image': critter['img'], 'is_powerup': True, 'type': critter['name']})
            else:
                blocks_list.append({'rect': rect, 'image': generic_block, 'is_powerup': False, 'type': 'generic'})
    return blocks_list

blocks = build_level()

def process_powerup(block_type, current_time, block_rect):
    global lives, walrus_timer, tomato_timer, raccoon_timer, bulldog_timer, stego_timer, trex_timer, triceratops_timer, pumpkin_timer, elephant_msg_timer
    global triceratops_drift, ball_size, ball_surface, ball, shark_missiles, score, dirt_blocks, blocks, extra_balls
    
    if block_type == "basic-blueberry.png":
        lives += 1
    elif block_type == "armored-walrus.png":
        walrus_timer = current_time + 10000
    elif block_type == "tough-tomato.png":
        ball_size = int(ball_size * 1.3)
        old_center = ball.center
        ball.width = ball_size
        ball.height = ball_size
        ball.center = old_center
        
        for e_ball in extra_balls:
            old_c = e_ball['rect'].center
            e_ball['rect'].width = ball_size
            e_ball['rect'].height = ball_size
            e_ball['rect'].center = old_c
            
        ball_surface = create_ball_surface(ball_size)
        tomato_timer = current_time + 10000
    elif block_type == "aggressive-shark.png":
        shark_missiles += 3
    elif block_type == "bandit-raccoon.png":
        raccoon_timer = current_time + 5000
    elif block_type == "bulldog-retriever.png":
        bulldog_timer = current_time + 10000
        dirt_blocks.clear()
        for _ in range(5):
            rx = random.randint(50, 750 - block_w)
            ry = random.randint(200, 450)
            dirt_blocks.append(pygame.Rect(rx, ry, block_w, block_h))
    elif block_type == "smashing-stegosaurus.png":
        stego_timer = current_time + 10000
    elif block_type == "sneaky-t-rex.png":
        trex_timer = current_time + 4000
    elif block_type == "treading-triceratops.png":
        triceratops_timer = current_time + 6000
        triceratops_drift = random.choice([-5, 5])
    elif block_type == "charging-gorilla.png":
        smash_rect = block_rect.inflate((block_w + 10) * 2, (block_h + 10) * 2)
        for b in blocks[:]:
            if b['rect'].colliderect(smash_rect):
                if b in blocks:
                    blocks.remove(b)
                    score += 10
    elif block_type == "heavy-pumpkin.png":
        pumpkin_timer = current_time + 10000
    elif block_type == "stampeding-elephant.png":
        elephant_msg_timer = current_time + 3000
        for _ in range(3):
            new_dx = random.choice([-5, -4, 4, 5])
            new_dy = random.choice([-5, -4])
            extra_balls.append({
                'rect': pygame.Rect(block_rect.centerx, block_rect.centery, ball_size, ball_size),
                'dx': new_dx,
                'dy': new_dy,
                'trail': [],
                'angle': 0
            })
    else:
        score += 50 

def check_level_clear(current_time):
    global blocks, ball_size, ball, ball_surface, ball_dy, ball_dx, rows_remaining
    global last_drop_time, tomato_timer, raccoon_timer, bulldog_timer, stego_timer, trex_timer, triceratops_timer, pumpkin_timer
    global active_missiles, dirt_blocks, extra_balls
    
    if not blocks:
        blocks = build_level()
        ball_size = 20
        ball.width = ball_size
        ball.height = ball_size
        ball_surface = create_ball_surface(ball_size)
        tomato_timer = 0
        raccoon_timer = 0
        bulldog_timer = 0
        stego_timer = 0
        trex_timer = 0
        triceratops_timer = 0
        pumpkin_timer = 0
        dirt_blocks.clear()
        extra_balls.clear()
        ball.x, ball.y = 390, 300
        ball_dy = -5
        active_missiles.clear()
        rows_remaining = 3 
        last_drop_time = current_time
        pygame.time.set_timer(GRID_DROP_EVENT, 15000) 

# Main Game Loop
while True:
    current_time = pygame.time.get_ticks()
    mouse_pos = pygame.mouse.get_pos()
    mouse_clicked = False
    
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            pygame.quit()
            sys.exit()
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mouse_clicked = True
        
        # Handle the 15-second grid drop
        if event.type == GRID_DROP_EVENT and game_state == "PLAYING":
            last_drop_time = current_time 
            if rows_remaining > 0:
                for block in blocks:
                    block['rect'].y += (block_h + 5)
                    if block['rect'].bottom >= paddle.top:
                        game_state = "GAME_OVER"
                        game_over_y = -120
                
                if game_state == "PLAYING":
                    for col in range(16):
                        rect = pygame.Rect(col * (block_w + 5) + 24, 50, block_w, block_h)
                        if random.random() < 0.15 and loaded_critters:
                            weights = []
                            for c in loaded_critters:
                                if c['name'] == "basic-blueberry.png":
                                    weights.append(70)
                                else:
                                    weights.append(10)
                            critter = random.choices(loaded_critters, weights=weights)[0]
                            blocks.append({'rect': rect, 'image': critter['img'], 'is_powerup': True, 'type': critter['name']})
                        else:
                            blocks.append({'rect': rect, 'image': generic_block, 'is_powerup': False, 'type': 'generic'})
                    
                    rows_remaining -= 1

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_SPACE:
                if game_state == "PLAYING":
                    game_state = "PAUSED"
                elif game_state == "PAUSED":
                    game_state = "PLAYING"
            if event.key == pygame.K_f:
                is_fullscreen = not is_fullscreen
                if is_fullscreen:
                    screen = pygame.display.set_mode((800, 600), pygame.FULLSCREEN)
                else:
                    screen = pygame.display.set_mode((800, 600))
            if event.key == pygame.K_1:
                if game_state == "PLAYING" and shark_missiles > 0:
                    shark_missiles -= 1
                    active_missiles.append(pygame.Rect(paddle.centerx - 2, paddle.top - 15, 4, 15))
                    bounce_sound.play()

    if game_state == "PLAYING":
        keys = pygame.key.get_pressed()
        
        current_speed = base_paddle_speed * 2 if keys[pygame.K_LSHIFT] else base_paddle_speed
        
        controls_inverted = current_time < raccoon_timer
        left_key = pygame.K_RIGHT if controls_inverted else pygame.K_LEFT
        right_key = pygame.K_LEFT if controls_inverted else pygame.K_RIGHT
        
        # Apply standard movement
        if keys[left_key]:
            paddle.x -= current_speed
        if keys[right_key]:
            paddle.x += current_speed

        # Apply Triceratops Drift
        if current_time < triceratops_timer:
            paddle.x += triceratops_drift

        # Enforce paddle screen boundaries
        if paddle.left < 0:
            paddle.left = 0
        if paddle.right > 800:
            paddle.right = 800

        if tomato_timer > 0 and current_time > tomato_timer:
            tomato_timer = 0
            ball_size = 20
            
            old_center = ball.center
            ball.width = ball_size
            ball.height = ball_size
            ball.center = old_center
            
            for e_ball in extra_balls:
                old_c = e_ball['rect'].center
                e_ball['rect'].width = ball_size
                e_ball['rect'].height = ball_size
                e_ball['rect'].center = old_c
                
            ball_surface = create_ball_surface(ball_size)

        if bulldog_timer > 0 and current_time > bulldog_timer:
            bulldog_timer = 0
            dirt_blocks.clear()

        # Paddle Hitbox Calculation 
        is_walrus_active = current_time < walrus_timer
        is_stego_active = current_time < stego_timer
        
        paddle_hitboxes = []
        if is_walrus_active:
            paddle_hitboxes.append(pygame.Rect(paddle.centerx - 100, paddle.top - 10, 200, 30))
        elif is_stego_active:
            paddle_hitboxes.append(pygame.Rect(paddle.left, paddle.top, 20, 15))
            paddle_hitboxes.append(pygame.Rect(paddle.centerx - 10, paddle.top, 20, 15))
            paddle_hitboxes.append(pygame.Rect(paddle.right - 20, paddle.top, 20, 15))
        else:
            paddle_hitboxes.append(paddle)

        # Missile Physics
        for missile in active_missiles[:]:
            missile.y -= 12 
            if missile.bottom < 0:
                active_missiles.remove(missile)
                continue
                
            hit_dirt = False
            for dirt in dirt_blocks:
                if missile.colliderect(dirt):
                    hit_dirt = True
                    break
            if hit_dirt:
                active_missiles.remove(missile)
                continue

            hit_block = False
            for block in blocks[:]:
                if missile.colliderect(block['rect']):
                    if block['is_powerup']:
                        process_powerup(block['type'], current_time, block['rect'])
                    else:
                        score += 10
                        
                    if block in blocks:
                        blocks.remove(block)
                    hit_block = True
                    break 
            if hit_block:
                active_missiles.remove(missile)
                check_level_clear(current_time)

        # Main Ball Physics
        ball_trail.append((ball.center, ball_angle))
        if len(ball_trail) > 6:
            ball_trail.pop(0)

        ball.x += ball_dx
        ball.y += ball_dy
        ball_angle -= 5

        if ball.left <= 0 or ball.right >= 800:
            ball_dx *= -1
            bounce_sound.play()
            if ball.left < 0: ball.left = 0
            if ball.right > 800: ball.right = 800
            
        if ball.top <= 0:
            ball_dy *= -1
            ball.top = 0
            bounce_sound.play()
            
        if ball.bottom >= 600:
            if extra_balls:
                replacement = extra_balls.pop(0)
                ball.x = replacement['rect'].x
                ball.y = replacement['rect'].y
                ball_dx = replacement['dx']
                ball_dy = replacement['dy']
                ball_trail = replacement['trail']
                ball_angle = replacement['angle']
            else:
                lives -= 1
                ball_size = 20 
                ball.width = ball_size
                ball.height = ball_size
                ball_surface = create_ball_surface(ball_size)
                ball.x, ball.y = 390, 300 
                ball_dy = -5
                tomato_timer = 0 
                raccoon_timer = 0
                bulldog_timer = 0
                stego_timer = 0
                trex_timer = 0
                triceratops_timer = 0
                pumpkin_timer = 0
                dirt_blocks.clear()
                extra_balls.clear()
                ball_trail.clear()
                
                if lives <= 0:
                    game_state = "GAME_OVER"
                    game_over_y = -120 
                else:
                    last_drop_time = current_time
                    pygame.time.set_timer(GRID_DROP_EVENT, 15000)

        for hit_box in paddle_hitboxes:
            if ball.colliderect(hit_box) and ball_dy > 0:
                hit_pos = (ball.centerx - hit_box.centerx) / (hit_box.width / 2)
                ball_dx = hit_pos * 7 
                ball_dy *= -1 
                bounce_sound.play()
                
                if current_time < pumpkin_timer:
                    shake_timer = current_time + 300
                    destroyed = 0
                    while destroyed < 3 and blocks:
                        target = random.choice(blocks)
                        if target['is_powerup']:
                            score += 50
                        else:
                            score += 10
                        blocks.remove(target)
                        destroyed += 1
                    check_level_clear(current_time)
                break 

        for dirt in dirt_blocks:
            if ball.colliderect(dirt):
                ball_dy *= -1
                bounce_sound.play()
                break 

        for block in blocks[:]:
            if ball.colliderect(block['rect']):
                ball_dy *= -1
                bounce_sound.play()
                
                if block['is_powerup']:
                    process_powerup(block['type'], current_time, block['rect'])
                else:
                    score += 10
                
                if block in blocks:
                    blocks.remove(block)
                    
                check_level_clear(current_time)
                break 

        # Extra Balls Physics
        for e_ball in extra_balls[:]:
            e_ball['trail'].append((e_ball['rect'].center, e_ball['angle']))
            if len(e_ball['trail']) > 6:
                e_ball['trail'].pop(0)
            
            e_ball['rect'].x += e_ball['dx']
            e_ball['rect'].y += e_ball['dy']
            e_ball['angle'] -= 5

            if e_ball['rect'].left <= 0 or e_ball['rect'].right >= 800:
                e_ball['dx'] *= -1
                bounce_sound.play()
                if e_ball['rect'].left < 0: e_ball['rect'].left = 0
                if e_ball['rect'].right > 800: e_ball['rect'].right = 800
            
            if e_ball['rect'].top <= 0:
                e_ball['dy'] *= -1
                e_ball['rect'].top = 0
                bounce_sound.play()

            if e_ball['rect'].bottom >= 600:
                extra_balls.remove(e_ball)
                continue

            for hit_box in paddle_hitboxes:
                if e_ball['rect'].colliderect(hit_box) and e_ball['dy'] > 0:
                    hit_pos = (e_ball['rect'].centerx - hit_box.centerx) / (hit_box.width / 2)
                    e_ball['dx'] = hit_pos * 7 
                    e_ball['dy'] *= -1 
                    bounce_sound.play()
                    if current_time < pumpkin_timer:
                        shake_timer = current_time + 300
                        destroyed = 0
                        while destroyed < 3 and blocks:
                            target = random.choice(blocks)
                            if target['is_powerup']:
                                score += 50
                            else:
                                score += 10
                            blocks.remove(target)
                            destroyed += 1
                        check_level_clear(current_time)
                    break 

            for dirt in dirt_blocks:
                if e_ball['rect'].colliderect(dirt):
                    e_ball['dy'] *= -1
                    bounce_sound.play()
                    break 

            for block in blocks[:]:
                if e_ball['rect'].colliderect(block['rect']):
                    e_ball['dy'] *= -1
                    bounce_sound.play()
                    if block['is_powerup']:
                        process_powerup(block['type'], current_time, block['rect'])
                    else:
                        score += 10
                    if block in blocks:
                        blocks.remove(block)
                    check_level_clear(current_time)
                    break 

    # Draw everything to Master Surface first
    render_surf.fill(BG_COLOR)
    
    if game_state in ["PLAYING", "PAUSED"]:
        
        if current_time < stego_timer:
            pygame.draw.rect(render_surf, PADDLE_COLOR, (paddle.left, paddle.top, 20, 15))
            pygame.draw.rect(render_surf, PADDLE_COLOR, (paddle.centerx - 10, paddle.top, 20, 15))
            pygame.draw.rect(render_surf, PADDLE_COLOR, (paddle.right - 20, paddle.top, 20, 15))
        else:
            pygame.draw.rect(render_surf, PADDLE_COLOR, paddle)
        
        is_walrus_active = current_time < walrus_timer
        if is_walrus_active:
            pulse = int(175 + 80 * math.sin(current_time / 100.0))
            shield_surf = pygame.Surface((200, 30), pygame.SRCALPHA)
            pygame.draw.ellipse(shield_surf, (0, 255, 255, pulse), shield_surf.get_rect())
            render_surf.blit(shield_surf, (paddle.centerx - 100, paddle.top - 10))
            
        for missile in active_missiles:
            pygame.draw.rect(render_surf, (255, 100, 50), missile)
        
        time_since_drop = current_time - last_drop_time
        is_blinking = time_since_drop > 12000 and rows_remaining > 0 and game_state == "PLAYING"
        
        if is_blinking:
            pulse_alpha = int(abs(math.sin(current_time / 100.0)) * 100)
            blink_surf = pygame.Surface((block_w, block_h), pygame.SRCALPHA)
            blink_surf.fill((255, 255, 255, pulse_alpha))

        for dirt in dirt_blocks:
            render_surf.blit(dirt_surface, dirt)

        for block in blocks:
            render_surf.blit(block['image'], block['rect'])
            if is_blinking:
                render_surf.blit(blink_surf, block['rect'])
        
        # Draw Main Ball 
        for i, (pos, angle) in enumerate(ball_trail):
            radius = int((ball_size / 2) * (i / len(ball_trail)))
            if radius > 0:
                pygame.draw.circle(render_surf, (200, 50, 50), pos, radius)
        
        if current_time >= trex_timer:
            rotated_ball = pygame.transform.rotate(ball_surface, ball_angle)
            ball_rect = rotated_ball.get_rect(center=ball.center)
            render_surf.blit(rotated_ball, ball_rect.topleft)

        # Draw Extra Balls
        for e_ball in extra_balls:
            for i, (pos, angle) in enumerate(e_ball['trail']):
                radius = int((ball_size / 2) * (i / len(e_ball['trail'])))
                if radius > 0:
                    pygame.draw.circle(render_surf, (200, 50, 50), pos, radius)
            if current_time >= trex_timer:
                e_rotated = pygame.transform.rotate(ball_surface, e_ball['angle'])
                e_rect = e_rotated.get_rect(center=e_ball['rect'].center)
                render_surf.blit(e_rotated, e_rect.topleft)

        # Draw UI Overlays (Foreground Layer)
        lives_text = font.render(f"Lives: {lives}", True, (255, 255, 255))
        score_text = font.render(f"Score: {score}", True, (255, 255, 255))
        render_surf.blit(lives_text, (20, 20)) 
        render_surf.blit(score_text, (800 - score_text.get_width() - 20, 20)) 
        
        rows_text = overlay_font.render(f"New Rows Remaining: {rows_remaining}", True, (200, 200, 255))
        render_surf.blit(rows_text, (400 - rows_text.get_width() // 2, 20))
        
        # Determine currently active states for icon UI
        current_active = []
        if current_time < walrus_timer: current_active.append('walrus')
        if current_time < tomato_timer: current_active.append('tomato')
        if current_time < raccoon_timer: current_active.append('raccoon')
        if current_time < stego_timer: current_active.append('stego')
        if current_time < trex_timer: current_active.append('trex')
        if current_time < triceratops_timer: current_active.append('triceratops')
        if current_time < pumpkin_timer: current_active.append('pumpkin')
        if current_time < elephant_msg_timer: current_active.append('elephant')
        if shark_missiles > 0: current_active.append('shark')

        icon_x = 20
        icon_y = 60
        
        for key in icon_filenames.keys():
            if key in current_active:
                state = icon_anim_state[key]
                if not state['was_active']:
                    state['offset'] = 40  # Initialize slide-up distance
                    state['angle'] = 0
                    state['was_active'] = True
                
                # Animate Offset and Rotation
                if state['offset'] > 0:
                    state['offset'] -= 4
                    if state['offset'] < 0: 
                        state['offset'] = 0
                elif state['angle'] > -10:
                    state['angle'] -= 2
                
                # Rotate and Draw
                base_surf = status_icons[key]
                if state['angle'] != 0:
                    surf = pygame.transform.rotate(base_surf, state['angle'])
                else:
                    surf = base_surf
                    
                rect = surf.get_rect(center=(icon_x + 16, icon_y + 16 + state['offset']))
                render_surf.blit(surf, rect.topleft)
                
                if key == 'shark':
                    missile_text = overlay_font.render(f"[1] x {shark_missiles}", True, (200, 200, 200))
                    render_surf.blit(missile_text, (icon_x + 40, icon_y + 8 + state['offset']))
                    
                icon_y += 36
            else:
                icon_anim_state[key]['was_active'] = False
        
        # Dynamic Stackable Hazard Warnings
        warnings = []
        if current_time < elephant_msg_timer:
            warnings.append(("THE HERD! (MULTI-BALL)", (50, 255, 255)))
        if current_time < pumpkin_timer:
            warnings.append(("SEISMIC PADDLE!", (255, 140, 0)))
        if current_time < raccoon_timer:
            warnings.append(("CONTROLS INVERTED!", (255, 50, 50)))
        if current_time < trex_timer:
            warnings.append(("BALL CLOAKED!", (100, 255, 100)))
        if current_time < triceratops_timer:
            warnings.append(("STAMPEDE DRIFT!", (255, 150, 0)))
            
        for i, (text, color) in enumerate(warnings):
            warn_surf = font.render(text, True, color)
            render_surf.blit(warn_surf, (400 - warn_surf.get_width() // 2, 80 + (i * 40)))
        
        shift_text = overlay_font.render("SHIFT: Sprint | SPACE: Pause | F: Fullscreen", True, (150, 150, 150))
        render_surf.blit(shift_text, (400 - shift_text.get_width() // 2, 570))
        
        if game_state == "PAUSED":
            pause_text = game_over_font.render("PAUSED", True, (255, 200, 0))
            render_surf.blit(pause_text, (400 - pause_text.get_width() // 2, 250))
        
    elif game_state == "GAME_OVER":
        if game_over_y < 150:
            game_over_y += 5
            
        dead_text = game_over_font.render("YOU DIED", True, (255, 50, 50))
        render_surf.blit(dead_text, (400 - dead_text.get_width() // 2, game_over_y))
        
        if game_over_y >= 150:
            if restart_btn.collidepoint(mouse_pos):
                pygame.draw.rect(render_surf, BTN_HOVER, restart_btn)
                if mouse_clicked:
                    lives = 3
                    score = 0
                    rows_remaining = 3
                    blocks = build_level()
                    ball_size = 20
                    ball.width = ball_size
                    ball.height = ball_size
                    ball_surface = create_ball_surface(ball_size)
                    ball.x, ball.y = 390, 300
                    ball_dy = -5
                    ball_dx = 5
                    paddle.x = 350
                    ball_trail.clear()
                    
                    # Reset all trackers
                    walrus_timer = 0
                    tomato_timer = 0
                    raccoon_timer = 0
                    bulldog_timer = 0
                    stego_timer = 0
                    trex_timer = 0
                    triceratops_timer = 0
                    pumpkin_timer = 0
                    shark_missiles = 0
                    active_missiles.clear()
                    dirt_blocks.clear()
                    extra_balls.clear()
                    
                    # Reset animation tracker states
                    for state in icon_anim_state.values():
                        state['was_active'] = False
                    
                    last_drop_time = current_time
                    pygame.time.set_timer(GRID_DROP_EVENT, 15000) 
                    game_state = "PLAYING"
            else:
                pygame.draw.rect(render_surf, BTN_COLOR, restart_btn)
                
            btn_text = button_font.render("NEW GAME", True, (0, 0, 0))
            render_surf.blit(btn_text, (restart_btn.centerx - btn_text.get_width() // 2, restart_btn.centery - btn_text.get_height() // 2))

    # Apply Screen Shake offset if active
    shake_x, shake_y = 0, 0
    if current_time < shake_timer:
        shake_x = random.randint(-8, 8)
        shake_y = random.randint(-8, 8)
        
    screen.fill((0, 0, 0)) 
    screen.blit(render_surf, (shake_x, shake_y))
    pygame.display.flip()
    clock.tick(60)