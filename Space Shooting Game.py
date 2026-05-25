import math
import os
import sqlite3
import hashlib
import kivy.app
import kivy.clock
import kivy.core.window
import kivy.graphics
import kivy.uix.widget
import kivy.uix.label
import kivy.uix.button
import kivy.uix.floatlayout
import kivy.uix.textinput
import kivy.uix.boxlayout
import kivy.uix.spinner
import kivy.core.audio
import kivy.utils
import kivy.core.text
import kivy.core.image
from datetime import datetime

SCREEN_WIDTH = 900
SCREEN_HEIGHT = 700
FPS = 60
PIXEL_SIZE = 4
POWERUP_DROP_CHANCE = 0.70

WHITE = (1, 1, 1, 1)
BLACK = (0, 0, 0, 1)
RED = (1, 0.2, 0.2, 1)
GREEN = (0.2, 1, 0.2, 1)
BLUE = (0.2, 0.4, 1, 1)
YELLOW = (1, 1, 0.2, 1)
PURPLE = (0.8, 0.2, 1, 1)
ORANGE = (1, 0.5, 0, 1)
CYAN = (0.2, 1, 1, 1)


class SimpleRandom:
    """Enhanced random number generator with better distribution"""
    _seed = 123456789

    @classmethod
    def seed(cls, value=None):
        if value is not None:
            cls._seed = value
        else:
            import time
            cls._seed = int(time.time() * 1000) % 233280

    @classmethod
    def random(cls):
        cls._seed = (cls._seed * 1103515245 + 12345) & 0x7fffffff
        return (cls._seed >> 16) / 32768.0

    @classmethod
    def randint(cls, a, b):
        return int(a + (cls.random() * (b - a + 1)))

    @classmethod
    def choice(cls, seq):
        return seq[cls.randint(0, len(seq) - 1)] if seq else None

    @classmethod
    def uniform(cls, a, b):
        return a + (cls.random() * (b - a))


class StarField:
    """Enhanced background stars with parallax"""

    def __init__(self):
        self.stars = []
        self.layers = [
            {'count': 80, 'speed': 0.5, 'size': 1},  # distant stars
            {'count': 50, 'speed': 1, 'size': 2},  # medium stars
            {'count': 20, 'speed': 2, 'size': 3}  # close stars
        ]

        for layer_idx, layer in enumerate(self.layers):
            for _ in range(layer['count']):
                self.stars.append({
                    'x': SimpleRandom.randint(0, SCREEN_WIDTH),
                    'y': SimpleRandom.randint(0, SCREEN_HEIGHT),
                    'size': layer['size'],
                    'speed': layer['speed'],
                    'layer': layer_idx,
                    'twinkle': SimpleRandom.random() * 6.28
                })

    def update(self):
        for star in self.stars:
            star['y'] -= star['speed']
            star['twinkle'] += 0.05
            if star['twinkle'] > 6.28:
                star['twinkle'] -= 6.28

            if star['y'] < 0:
                star['y'] = SCREEN_HEIGHT
                star['x'] = SimpleRandom.randint(0, SCREEN_WIDTH)

    def draw(self, canvas):
        with canvas:
            for star in self.stars:
                # Twinkling effect
                brightness = 0.5 + (SimpleRandom.random() * 0.5)
                kivy.graphics.Color(brightness, brightness, brightness, 1)
                px = int(star['x'] // PIXEL_SIZE) * PIXEL_SIZE
                py = int(star['y'] // PIXEL_SIZE) * PIXEL_SIZE
                size = star['size'] * PIXEL_SIZE
                kivy.graphics.Rectangle(pos=(px, py), size=(size, size))


class EnhancedParticle:
    """Enhanced particle effect with more features"""

    def __init__(self, x, y, color, size=3, speed_range=(2, 8), gravity=-0.2, life=1.0, fade=True):
        self.x = x
        self.y = y
        angle = SimpleRandom.random() * 6.28318
        speed = SimpleRandom.uniform(speed_range[0], speed_range[1])
        self.vx = SimpleRandom.uniform(-speed, speed)
        self.vy = SimpleRandom.uniform(-speed, speed)
        self.life = life
        self.max_life = life
        self.color = color
        self.size = SimpleRandom.randint(size - 1, size + 1)
        self.gravity = gravity
        self.fade = fade

    def update(self):
        self.x += self.vx
        self.y += self.vy
        self.vy += self.gravity
        self.life -= 0.02
        return self.life > 0

    def draw(self, canvas):
        with canvas:
            if self.fade:
                alpha = self.life / self.max_life
                kivy.graphics.Color(self.color[0], self.color[1], self.color[2], alpha)
            else:
                kivy.graphics.Color(*self.color)
            size = max(PIXEL_SIZE, int(self.size) * PIXEL_SIZE)
            px = int((self.x - size / 2) // PIXEL_SIZE) * PIXEL_SIZE
            py = int((self.y - size / 2) // PIXEL_SIZE) * PIXEL_SIZE
            kivy.graphics.Rectangle(pos=(px, py), size=(size, size))


class SpaceShooterGame(kivy.uix.widget.Widget):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.size = (SCREEN_WIDTH, SCREEN_HEIGHT)
        kivy.core.window.Window.size = (SCREEN_WIDTH, SCREEN_HEIGHT)
        kivy.core.window.Window.fullscreen = 'auto'  # Auto fullscreen
        kivy.core.window.Window.resizable = True
        kivy.core.window.Window.bind(size=self._on_window_resize)
        self.game_canvas = self.canvas.before

        # Seed random
        SimpleRandom.seed()

        # Game state
        self.game_state = "login"  # login, menu, playing, game_over, victory, paused
        self.score = 0
        self.wave = 1
        self.enemies_killed = 0
        self.high_score = 0
        self.screen_shake = 0
        self.shake_offset = (0, 0)

        # Account / database
        self.db_path = os.path.join(os.path.dirname(__file__), "game_records.db")
        self.current_user = None
        self.current_user_id = None
        self.user_last_score = None
        self.user_last_wave = None
        self.user_last_kills = None
        self.user_last_played = None
        self.user_games_played = 0
        self.new_high_score = False
        self.game_session_saved = False

        # Initialize database and load stats (if user is set later)
        self.init_db()
        self.load_high_score()

        # Player
        self.player = {
            'x': SCREEN_WIDTH // 2,
            'y': 100,
            'width': 30,
            'height': 30,
            'lives': 3,
            'max_lives': 5,
            'invulnerable': False,
            'invulnerable_timer': 0,
            'speed': 6,
            'weapon_level': 1,
            'vertical_movement_enabled': True
        }

        # Load spaceship texture
        self.spaceship_textures = []
        self.spaceship_emissive_textures = []

        # Load main spaceship image from pics folder only
        try:
            spaceship_img = kivy.core.image.Image('pics/Spaceship.png').texture
            self.spaceship_textures.append(spaceship_img)
            # Create emissive effect using the same texture with transparency
            self.spaceship_emissive_textures.append(spaceship_img)
        except Exception as e:
            print(f"Could not load spaceship image: {e}")
            # Create fallback pixel art spaceship
            self.spaceship_textures = None
            self.spaceship_emissive_textures = None

        self.spaceship_frame = 0
        self.animation_timer = 0

        # Load boss images (using BOSS images as requested)
        self.boss_textures = {}
        try:
            # Load BOSS images as bosses - assign unique BOSS to each stage
            boss_boss_mapping = {
                1: 'Boss1.png',   # Stage 1 - Deep Space Sector
                2: 'Boss2.png',   # Stage 2 - Kong Universe
                3: 'Boss3.png',   # Stage 3 - Saturn Rings
                4: 'Boss4.png',   # Stage 4 - Nebula Rift
                5: 'Boss5.png',   # Stage 5 - Ember Forge
                6: 'Boss6.png',   # Stage 6 - Frozen Expanse
                7: 'Boss6.png',   # Stage 7 - Toxic Wasteland (reuse)
                8: 'Boss6.png',   # Stage 8 - Quantum Citadel (reuse)
                9: 'Boss6.png',   # Stage 9 - Void Abyss (reuse)
                10: 'Boss6.png'   # Stage 10 - Eclipse Throne (reuse)
            }
            
            for stage, filename in boss_boss_mapping.items():
                try:
                    boss_img = kivy.core.image.Image(f'pics/{filename}').texture
                    self.boss_textures[f'boss_{stage}'] = boss_img
                except Exception as e:
                    print(f"Could not load BOSS boss {stage}: {e}")
                        
        except Exception as e:
            print(f"Could not initialize BOSS boss textures: {e}")
            pass  # Boss images will use fallback rectangles
        
        # Load powerup textures (using powerups folder images)
        self.powerup_textures = {}
        try:
            # Load powerup images from powerups folder
            powerup_files = {
                'health': 'powerups/Health.png',
                'weapon': 'powerups/Weapon_Upgrade.png',
                'shield': 'powerups/Shield.png',
                'rapid': 'powerups/Rapid_Fire.png',
                'double_score': 'powerups/Double_Score.png'
            }
            
            for powerup_type, filename in powerup_files.items():
                try:
                    powerup_img = kivy.core.image.Image(filename).texture
                    self.powerup_textures[powerup_type] = powerup_img
                except Exception as e:
                    print(f"Could not load powerup {powerup_type}: {e}")
                    
        except Exception as e:
            print(f"Could not initialize powerup textures: {e}")
            pass  # Powerup images will use fallback pixel sprites
        
        # Load mob textures (using boss images as regular enemies with duplicates for variety)
        self.mob_textures = {}
        try:
            # Load boss images and create duplicates for more variety
            boss_mob_files = [
                'Boss1.png', 'Boss2.png', 'Boss3.png', 'Boss4.png', 
                'Boss5.png', 'Boss6.png',
                # Add duplicates for more variety
                'Boss1.png', 'Boss2.png', 'Boss3.png', 'Boss4.png'
            ]
            for i, filename in enumerate(boss_mob_files):
                try:
                    mob_img = kivy.core.image.Image(f'pics/{filename}').texture
                    self.mob_textures[f'mob_{i+1}'] = mob_img
                except Exception as e:
                    print(f"Could not load boss mob {i+1}: {e}")
                    
        except Exception as e:
            print(f"Could not initialize boss mob textures: {e}")
            pass  # Mob images will use fallback rectangles

        # Game objects
        self.enemies = []
        self.bullets = []
        self.enemy_bullets = []
        self.powerups = []
        self.particles = []
        self.starfield = StarField()

        # Power-up timers
        self.shield_active = False
        self.shield_timer = 0
        self.rapid_fire = False
        self.rapid_timer = 0
        self.double_score = False
        self.double_score_timer = 0
        self.shot_timer = 0
        self.shoot_delay = 0.25

        # Stage system
        self.max_stages = 10
        self.stage_phase = "enemies"  # enemies, boss_warning, boss, clear_anim
        self.stage_enemy_target = 12
        self.stage_enemy_kills = 0
        self.spawn_timer = 0
        self.clear_banner_timer = 0
        self.arrival_timer = 0
        self.arrival_text = ""
        self.clear_message = "LEVEL Cleared"
        self.player_departing = False
        self.ultra_boss_active = False
        self.pending_ultra_spawn = False
        self.current_profile = {}
        self.boss_warning_timer = 0
        self.boss_warning_text = ""
        self.boss_warning_next = None

        # Pause menu
        self.pause_menu_items = ["Game Menu", "Restart Stage", "Back to Game"]
        self.pause_menu_index = 2

        # Background elements
        self.bg_meteor_chunks = []
        self.bg_saturn_stars = []
        self.bg_clouds = []
        for _ in range(30):
            self.bg_meteor_chunks.append({
                'x': SimpleRandom.randint(0, SCREEN_WIDTH),
                'y': SimpleRandom.randint(0, SCREEN_HEIGHT),
                'size': SimpleRandom.randint(8, 24),
                'speed': SimpleRandom.uniform(0.2, 0.8)
            })
        for _ in range(80):
            self.bg_saturn_stars.append({
                'x': SimpleRandom.randint(0, SCREEN_WIDTH),
                'y': SimpleRandom.randint(0, SCREEN_HEIGHT),
                'size': SimpleRandom.randint(1, 3),
            })
        for _ in range(5):
            self.bg_clouds.append({
                'x': SimpleRandom.randint(0, SCREEN_WIDTH),
                'y': SimpleRandom.randint(0, SCREEN_HEIGHT),
                'width': SimpleRandom.randint(100, 200),
                'height': SimpleRandom.randint(40, 80),
                'speed': SimpleRandom.uniform(0.1, 0.3)
            })

        # Fullscreen background elements
        self.fullscreen_stars = []
        self.fullscreen_nebula = []
        for _ in range(140):
            self.fullscreen_stars.append({
                'x': SimpleRandom.random(),
                'y': SimpleRandom.random(),
                'size': SimpleRandom.randint(1, 2),
                'speed': SimpleRandom.uniform(0.01, 0.05),
                'twinkle': SimpleRandom.random() * 6.28318
            })
        nebula_colors = [
            (0.2, 0.35, 0.8, 0.08),
            (0.55, 0.2, 0.8, 0.07),
            (0.8, 0.3, 0.5, 0.06),
            (0.25, 0.6, 0.9, 0.06),
        ]
        for _ in range(6):
            self.fullscreen_nebula.append({
                'x': SimpleRandom.random(),
                'y': SimpleRandom.random(),
                'size': SimpleRandom.uniform(0.25, 0.55),
                'color': SimpleRandom.choice(nebula_colors)
            })

        # Keyboard
        self.setup_keyboard()

        # Audio
        self.sounds = {}
        self.bgm = None
        self.boss_bgm = None
        self.current_music = None
        self.load_audio()

        # Login UI
        self.build_login_ui()
        self.build_exit_ui()

        # Start game loop
        kivy.clock.Clock.schedule_interval(self.update, 1.0 / FPS)

    def _on_window_resize(self, _window, size):
        self.size = size
        if hasattr(self, "login_layout"):
            self.login_layout.size = size
        if hasattr(self, "exit_layout"):
            self.exit_layout.size = size

    def load_high_score(self):
        """Load high score for the current user from database."""
        if not self.current_user_id:
            self.high_score = 0
            return
        try:
            with sqlite3.connect(self.db_path) as conn:
                cur = conn.cursor()
                cur.execute("SELECT MAX(score) FROM game_records WHERE user_id = ?", (self.current_user_id,))
                row = cur.fetchone()
                self.high_score = row[0] if row and row[0] is not None else 0
        except sqlite3.Error as exc:
            print(f"Database error while loading high score: {exc}")
            self.high_score = 0

    def save_high_score(self):
        """Save current game result for the logged-in user."""
        self.finalize_game_result()

    def init_db(self):
        """Initialize the database for user accounts and game records."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cur = conn.cursor()
                cur.execute(
                    "CREATE TABLE IF NOT EXISTS users ("
                    "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                    "username TEXT UNIQUE NOT NULL, "
                    "password_hash TEXT, "
                    "created_at TEXT NOT NULL)"
                )
                cur.execute("PRAGMA table_info(users)")
                cols = [row[1] for row in cur.fetchall()]
                if "password_hash" not in cols:
                    cur.execute("ALTER TABLE users ADD COLUMN password_hash TEXT")
                cur.execute(
                    "CREATE TABLE IF NOT EXISTS game_records ("
                    "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                    "user_id INTEGER NOT NULL, "
                    "score INTEGER NOT NULL, "
                    "wave INTEGER NOT NULL, "
                    "enemies_killed INTEGER NOT NULL, "
                    "created_at TEXT NOT NULL, "
                    "FOREIGN KEY(user_id) REFERENCES users(id))"
                )
                conn.commit()
        except sqlite3.Error as exc:
            print(f"Database error while initializing: {exc}")

    def now_iso(self):
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def hash_password(self, password):
        return hashlib.sha256(password.encode("utf-8")).hexdigest()

    def authenticate_user(self, username, password):
        username = username.strip()
        if not username:
            return None, "Username is required."
        password = password.strip()
        if not password:
            return None, "Password is required."
        if len(password) < 4:
            return None, "Password must be at least 4 characters."
        if len(username) > 24:
            return None, "Username must be 24 characters or less."
        try:
            with sqlite3.connect(self.db_path) as conn:
                cur = conn.cursor()
                cur.execute("SELECT id, password_hash FROM users WHERE username = ?", (username,))
                row = cur.fetchone()
                if not row:
                    return None, "Account not found. Please register."
                user_id, stored_hash = row
                provided_hash = self.hash_password(password)
                if stored_hash:
                    if stored_hash != provided_hash:
                        return None, "Incorrect password."
                else:
                    cur.execute(
                        "UPDATE users SET password_hash = ? WHERE id = ?",
                        (provided_hash, user_id)
                    )
                    conn.commit()
                return user_id, None
        except sqlite3.Error as exc:
            return None, f"Database error: {exc}"

    def create_user(self, username, password):
        username = username.strip()
        if not username:
            return None, "Username is required."
        password = password.strip()
        if not password:
            return None, "Password is required."
        if len(password) < 4:
            return None, "Password must be at least 4 characters."
        if len(username) > 24:
            return None, "Username must be 24 characters or less."
        try:
            with sqlite3.connect(self.db_path) as conn:
                cur = conn.cursor()
                cur.execute("SELECT id FROM users WHERE username = ?", (username,))
                row = cur.fetchone()
                if row:
                    return None, "Username already exists."
                password_hash = self.hash_password(password)
                cur.execute(
                    "INSERT INTO users (username, password_hash, created_at) VALUES (?, ?, ?)",
                    (username, password_hash, self.now_iso())
                )
                conn.commit()
                return cur.lastrowid, None
        except sqlite3.Error as exc:
            return None, f"Database error: {exc}"

    def load_user_stats(self):
        if not self.current_user_id:
            self.high_score = 0
            self.user_last_score = None
            self.user_last_wave = None
            self.user_last_kills = None
            self.user_last_played = None
            self.user_games_played = 0
            return
        try:
            with sqlite3.connect(self.db_path) as conn:
                cur = conn.cursor()
                cur.execute("SELECT MAX(score) FROM game_records WHERE user_id = ?", (self.current_user_id,))
                row = cur.fetchone()
                self.high_score = row[0] if row and row[0] is not None else 0

                cur.execute(
                    "SELECT score, wave, enemies_killed, created_at "
                    "FROM game_records WHERE user_id = ? ORDER BY id DESC LIMIT 1",
                    (self.current_user_id,)
                )
                last = cur.fetchone()
                if last:
                    self.user_last_score, self.user_last_wave, self.user_last_kills, self.user_last_played = last
                else:
                    self.user_last_score = None
                    self.user_last_wave = None
                    self.user_last_kills = None
                    self.user_last_played = None

                cur.execute("SELECT COUNT(*) FROM game_records WHERE user_id = ?", (self.current_user_id,))
                count_row = cur.fetchone()
                self.user_games_played = count_row[0] if count_row and count_row[0] is not None else 0
        except sqlite3.Error as exc:
            print(f"Database error while loading stats: {exc}")
            self.high_score = 0

    def get_usernames(self):
        try:
            with sqlite3.connect(self.db_path) as conn:
                cur = conn.cursor()
                cur.execute("SELECT username FROM users ORDER BY username COLLATE NOCASE")
                return [row[0] for row in cur.fetchall()]
        except sqlite3.Error as exc:
            print(f"Database error while loading usernames: {exc}")
            return []

    def save_game_record(self):
        if not self.current_user_id:
            return
        try:
            with sqlite3.connect(self.db_path) as conn:
                cur = conn.cursor()
                cur.execute(
                    "INSERT INTO game_records (user_id, score, wave, enemies_killed, created_at) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (self.current_user_id, self.score, self.wave, self.enemies_killed, self.now_iso())
                )
                conn.commit()
        except sqlite3.Error as exc:
            print(f"Database error while saving record: {exc}")

    def finalize_game_result(self):
        if self.game_session_saved:
            return
        if not self.current_user_id:
            return
        if self.score <= 0 and self.enemies_killed <= 0:
            return
        self.new_high_score = self.score > self.high_score
        self.save_game_record()
        self.load_user_stats()
        self.game_session_saved = True

    def build_login_ui(self):
        """Create a simple login form overlay."""
        self.login_layout = kivy.uix.floatlayout.FloatLayout(size_hint=(1, 1))

        with self.login_layout.canvas.before:
            # Subtle atmospheric veil to keep the game visible behind the form
            kivy.graphics.Color(0.02, 0.05, 0.08, 0.25)
            self.login_bg_rect = kivy.graphics.Rectangle(pos=(0, 0), size=self.size)

        self.login_card_radius = 14
        self.login_card = kivy.uix.boxlayout.BoxLayout(
            orientation="vertical",
            size_hint=(0.6, 0.65),
            pos_hint={"center_x": 0.5, "center_y": 0.52},
            padding=[26, 26, 26, 26],
            spacing=16
        )
        with self.login_card.canvas.before:
            # Glassy card that blends with the space backdrop
            kivy.graphics.Color(0.06, 0.12, 0.18, 0.38)
            self.login_card_rect = kivy.graphics.RoundedRectangle(
                pos=self.login_card.pos,
                size=self.login_card.size,
                radius=[
                    self.login_card_radius,
                    self.login_card_radius,
                    self.login_card_radius,
                    self.login_card_radius
                ]
            )
            kivy.graphics.Color(0.2, 1, 1, 0.28)
            self.login_card_border = kivy.graphics.Line(
                rounded_rectangle=(
                    self.login_card.pos[0],
                    self.login_card.pos[1],
                    self.login_card.size[0],
                    self.login_card.size[1],
                    self.login_card_radius
                ),
                width=1.2
            )

        self.login_title = kivy.uix.label.Label(
            text="Welcome Back",
            font_size=28,
            size_hint=(1, None),
            height=36,
            color=WHITE
        )
        self.login_subtitle = kivy.uix.label.Label(
            text="Enter your credentials to continue.",
            font_size=14,
            size_hint=(1, None),
            height=20,
            color=WHITE
        )
        self.account_label = kivy.uix.label.Label(
            text="Existing Accounts",
            font_size=14,
            size_hint=(1, None),
            height=20,
            color=WHITE
        )
        self.account_spinner = kivy.uix.spinner.Spinner(
            text="Select account",
            values=[],
            size_hint=(1, None),
            height=40,
            background_normal="",
            background_color=(0.08, 0.16, 0.22, 0.4),
            color=WHITE
        )
        self.account_spinner.bind(text=self._on_account_selected)
        self.username_input = kivy.uix.textinput.TextInput(
            hint_text="New username (for register)",
            multiline=False,
            size_hint=(1, None),
            height=40,
            background_normal="",
            background_active="",
            background_color=(0.08, 0.16, 0.22, 0.35),
            foreground_color=WHITE,
            cursor_color=WHITE,
            hint_text_color=(0.7, 0.85, 1, 0.7)
        )
        self.password_input = kivy.uix.textinput.TextInput(
            hint_text="Enter your password",
            multiline=False,
            password=True,
            size_hint=(1, None),
            height=40,
            background_normal="",
            background_active="",
            background_color=(0.08, 0.16, 0.22, 0.35),
            foreground_color=WHITE,
            cursor_color=WHITE,
            hint_text_color=(0.7, 0.85, 1, 0.7)
        )
        self.username_input.bind(on_text_validate=self.handle_login_existing)
        self.password_input.bind(on_text_validate=self.handle_login_existing)
        self.login_button = kivy.uix.button.Button(
            text="Login",
            size_hint=(1, None),
            height=42,
            background_normal="",
            background_down="",
            background_color=(0.12, 0.24, 0.32, 0.7),
            color=WHITE
        )
        self.login_button.bind(on_press=self.handle_login_existing)
        self.register_button = kivy.uix.button.Button(
            text="Register",
            size_hint=(1, None),
            height=42,
            background_normal="",
            background_down="",
            background_color=(0.1, 0.2, 0.28, 0.62),
            color=WHITE
        )
        self.register_button.bind(on_press=self.handle_register)
        self.login_message = kivy.uix.label.Label(
            text="",
            font_size=16,
            size_hint=(1, None),
            height=24,
            color=WHITE
        )

        self.login_card.add_widget(self.login_title)
        self.login_card.add_widget(self.login_subtitle)
        self.login_card.add_widget(self.account_label)
        self.login_card.add_widget(self.account_spinner)
        self.login_card.add_widget(self.username_input)
        self.login_card.add_widget(self.password_input)
        self.login_card.add_widget(self.login_button)
        self.login_card.add_widget(self.register_button)
        self.login_card.add_widget(self.login_message)

        self.login_layout.add_widget(self.login_card)
        self.add_widget(self.login_layout)
        self.login_layout.bind(pos=self._update_login_canvas, size=self._update_login_canvas)
        self.login_card.bind(pos=self._update_login_card, size=self._update_login_card)
        self.refresh_account_list()
        self.update_login_visibility()

    def update_login_visibility(self):
        if not hasattr(self, "login_layout"):
            return
        is_login = self.game_state == "login"
        self.login_layout.opacity = 1 if is_login else 0
        self.login_layout.disabled = not is_login
        self.login_layout.size = self.size
        self.login_layout.pos = (0, 0)
        if is_login:
            has_username = hasattr(self, "username_input")
            has_password = hasattr(self, "password_input")
            username_focus = self.username_input.focus if has_username else False
            password_focus = self.password_input.focus if has_password else False
            if has_username and not (username_focus or password_focus):
                self.username_input.focus = True
            self.refresh_account_list()
        if is_login:
            if getattr(self, "_keyboard", None):
                self._keyboard.unbind(on_key_down=self._on_key_down)
                self._keyboard.unbind(on_key_up=self._on_key_up)
                self._keyboard.release()
                self._keyboard = None
        else:
            if not getattr(self, "_keyboard", None):
                self.setup_keyboard()

    def _update_login_canvas(self, *_args):
        if hasattr(self, "login_bg_rect"):
            self.login_bg_rect.pos = (0, 0)
            self.login_bg_rect.size = self.size

    def _update_login_card(self, *_args):
        if hasattr(self, "login_card_rect"):
            self.login_card_rect.pos = self.login_card.pos
            self.login_card_rect.size = self.login_card.size
        if hasattr(self, "login_card_border"):
            self.login_card_border.rounded_rectangle = (
                self.login_card.pos[0],
                self.login_card.pos[1],
                self.login_card.size[0],
                self.login_card.size[1],
                self.login_card_radius
            )

    def refresh_account_list(self):
        if not hasattr(self, "account_spinner"):
            return
        usernames = self.get_usernames()
        if usernames:
            self.account_spinner.values = usernames
            if self.account_spinner.text not in usernames:
                self.account_spinner.text = "Select account"
            self.account_spinner.disabled = False
        else:
            self.account_spinner.values = ["No accounts yet"]
            self.account_spinner.text = "No accounts yet"
            self.account_spinner.disabled = True

    def _on_account_selected(self, _spinner, selection):
        if selection in ("Select account", "No accounts yet"):
            return
        if hasattr(self, "username_input"):
            self.username_input.text = selection

    def handle_login_existing(self, *_args):
        username = ""
        password = ""
        if hasattr(self, "username_input"):
            username = self.username_input.text
        if hasattr(self, "password_input"):
            password = self.password_input.text
        if hasattr(self, "account_spinner"):
            selected = self.account_spinner.text
            if selected not in ("Select account", "No accounts yet"):
                username = selected
        user_id, error = self.authenticate_user(username, password)
        if error:
            if hasattr(self, "login_message"):
                self.login_message.color = RED
                self.login_message.text = error
            return
        self.current_user = username.strip()
        self.current_user_id = user_id
        self.load_user_stats()
        self.game_state = "menu"
        self.game_session_saved = False
        self.new_high_score = False
        if hasattr(self, "login_message"):
            self.login_message.color = GREEN
            self.login_message.text = f"Welcome, {self.current_user}!"
        if hasattr(self, "username_input"):
            self.username_input.text = ""
        if hasattr(self, "password_input"):
            self.password_input.text = ""
        if hasattr(self, "account_spinner"):
            self.account_spinner.text = "Select account"
        self.update_login_visibility()

    def handle_register(self, *_args):
        username = ""
        password = ""
        if hasattr(self, "username_input"):
            username = self.username_input.text
        if hasattr(self, "password_input"):
            password = self.password_input.text
        user_id, error = self.create_user(username, password)
        if error:
            if hasattr(self, "login_message"):
                self.login_message.color = RED
                self.login_message.text = error
            return
        self.current_user = username.strip()
        self.current_user_id = user_id
        self.load_user_stats()
        self.game_state = "menu"
        self.game_session_saved = False
        self.new_high_score = False
        if hasattr(self, "login_message"):
            self.login_message.color = GREEN
            self.login_message.text = f"Welcome, {self.current_user}!"
        if hasattr(self, "username_input"):
            self.username_input.text = ""
        if hasattr(self, "password_input"):
            self.password_input.text = ""
        if hasattr(self, "account_spinner"):
            self.account_spinner.text = "Select account"
        self.refresh_account_list()
        self.update_login_visibility()

    def build_exit_ui(self):
        """Create an exit button overlay."""
        self.exit_layout = kivy.uix.floatlayout.FloatLayout(size_hint=(1, 1))
        self.exit_button = kivy.uix.button.Button(
            text="Exit Game",
            size_hint=(0.2, None),
            height=40,
            pos_hint={"right": 0.98, "y": 0.02}
        )
        self.exit_button.bind(on_press=self.handle_exit)
        self.exit_layout.add_widget(self.exit_button)
        self.add_widget(self.exit_layout)
        self.update_exit_visibility()

    def update_exit_visibility(self):
        if not hasattr(self, "exit_layout"):
            return
        show_exit = self.game_state in ("login", "menu", "paused", "game_over", "victory")
        self.exit_layout.opacity = 1 if show_exit else 0
        self.exit_layout.disabled = not show_exit
        self.exit_layout.size = self.size
        self.exit_layout.pos = (0, 0)

    def handle_exit(self, *_args):
        kivy.app.App.get_running_app().stop()

    def setup_keyboard(self):
        """Setup keyboard handling"""
        self._keyboard = kivy.core.window.Window.request_keyboard(self._keyboard_closed, self)
        self._keyboard.bind(on_key_down=self._on_key_down)
        self._keyboard.bind(on_key_up=self._on_key_up)
        self.keys_pressed = set()

    def _keyboard_closed(self):
        self._keyboard.unbind(on_key_down=self._on_key_down)
        self._keyboard.unbind(on_key_up=self._on_key_up)
        self._keyboard = None

    def _on_key_down(self, keyboard, keycode, text, modifiers):
        if self.game_state == "login":
            if keycode[1] in ('enter', 'numpadenter'):
                self.handle_login_existing()
            return

        self.keys_pressed.add(keycode[1])

        if self.game_state == "menu":
            if keycode[1] == 'spacebar':
                self.start_game()
        elif self.game_state == "paused":
            if keycode[1] in ('escape', 'esc', 'p'):
                self.resume_game()
            elif keycode[1] in ('up', 'down'):
                direction = -1 if keycode[1] == 'up' else 1
                self.pause_menu_index = (self.pause_menu_index + direction) % len(self.pause_menu_items)
            elif keycode[1] in ('enter', 'numpadenter', 'spacebar'):
                self.activate_pause_menu()
        elif self.game_state == "game_over":
            if keycode[1] == 'r':
                self.reset_game()
            elif keycode[1] == 'q':
                self.reset_game()
        elif self.game_state == "victory":
            if keycode[1] == 'r':
                self.reset_game()
        elif self.game_state == "playing":
            if keycode[1] in ('escape', 'esc', 'p'):
                self.enter_pause()
            elif keycode[1] == 'v':
                self.player['vertical_movement_enabled'] = not self.player['vertical_movement_enabled']

    def _on_key_up(self, keyboard, keycode):
        self.keys_pressed.discard(keycode[1])

    def enter_pause(self):
        self.game_state = "paused"
        self.pause_menu_index = min(self.pause_menu_index, len(self.pause_menu_items) - 1)
        self.keys_pressed.clear()

    def resume_game(self):
        self.game_state = "playing"

    def activate_pause_menu(self, index=None):
        if index is None:
            index = self.pause_menu_index
        action = self.pause_menu_items[index]
        if action == "Back to Game":
            self.resume_game()
        elif action == "Restart Stage":
            self.restart_current_stage()
        elif action == "Game Menu":
            self.reset_game()

    def restart_current_stage(self):
        current_stage = self.wave
        self.game_state = "playing"
        self.setup_stage(current_stage)

    def get_pause_menu_layout(self):
        button_w = 280
        button_h = 38
        start_y = SCREEN_HEIGHT // 2 + 40
        spacing = 50
        layout = []
        for idx, label in enumerate(self.pause_menu_items):
            center_x = SCREEN_WIDTH // 2
            center_y = start_y - (idx * spacing)
            layout.append({
                'label': label,
                'center_x': center_x,
                'center_y': center_y,
                'x': center_x - (button_w / 2),
                'y': center_y - (button_h / 2),
                'w': button_w,
                'h': button_h
            })
        return layout

    def window_to_game(self, x, y):
        scale = min(self.width / SCREEN_WIDTH, self.height / SCREEN_HEIGHT)
        if scale <= 0:
            return 0, 0
        offset_x = (self.width - (SCREEN_WIDTH * scale)) / 2
        offset_y = (self.height - (SCREEN_HEIGHT * scale)) / 2
        return (x - offset_x) / scale, (y - offset_y) / scale

    def on_touch_down(self, touch):
        if self.game_state == "paused":
            gx, gy = self.window_to_game(touch.x, touch.y)
            for idx, item in enumerate(self.get_pause_menu_layout()):
                if (item['x'] <= gx <= item['x'] + item['w'] and
                        item['y'] <= gy <= item['y'] + item['h']):
                    self.pause_menu_index = idx
                    self.activate_pause_menu()
                    return True
        return super().on_touch_down(touch)

    def start_game(self):
        """Start new game"""
        if not self.current_user_id:
            self.game_state = "login"
            self.update_login_visibility()
            return
        self.game_session_saved = False
        self.new_high_score = False
        self.game_state = "playing"
        self.ultra_boss_active = False
        self.pending_ultra_spawn = False
        self.boss_warning_timer = 0
        self.boss_warning_text = ""
        self.boss_warning_next = None
        self.pause_menu_index = 2
        self.start_background_music()
        self.setup_stage(1)

    def reset_game(self):
        """Reset game to initial state"""
        self.save_high_score()
        self.game_state = "menu"
        self.new_high_score = False
        self.update_login_visibility()
        self.score = 0
        self.wave = 1
        self.enemies_killed = 0
        self.player = {
            'x': SCREEN_WIDTH // 2,
            'y': 100,
            'width': 30,
            'height': 30,
            'lives': 3,
            'max_lives': 5,
            'invulnerable': False,
            'invulnerable_timer': 0,
            'speed': 6,
            'weapon_level': 1,
            'vertical_movement_enabled': True
        }
        self.enemies.clear()
        self.bullets.clear()
        self.enemy_bullets.clear()
        self.powerups.clear()
        self.particles.clear()
        self.shield_active = False
        self.rapid_fire = False
        self.double_score = False
        self.shot_timer = 0
        self.stage_phase = "enemies"
        self.stage_enemy_kills = 0
        self.spawn_timer = 0
        self.clear_banner_timer = 0
        self.arrival_timer = 0
        self.arrival_text = ""
        self.clear_message = "LEVEL Cleared"
        self.boss_warning_timer = 0
        self.boss_warning_text = ""
        self.boss_warning_next = None
        self.player_departing = False
        self.ultra_boss_active = False
        self.pending_ultra_spawn = False
        self.pause_menu_index = 2
        self.start_background_music()

    def get_stage_profile(self, stage):
        """Return stage profile (theme, enemies, boss) for stages 1..10."""
        profiles = {
            1: {'theme': 'space', 'enemy_mode': 'alien', 'boss_kind': 'octopus', 'arrival': "Deep Space Sector",
                'difficulty': 1},
            2: {'theme': 'kong', 'enemy_mode': 'meteor', 'boss_kind': 'grozilla', 'arrival': "Kong Universe",
                'difficulty': 1.2},
            3: {'theme': 'saturn', 'enemy_mode': 'hybrid', 'boss_kind': 'growly', 'arrival': "Saturn Rings",
                'difficulty': 1.4},
            4: {'theme': 'nebula', 'enemy_mode': 'nebula', 'boss_kind': 'manta', 'arrival': "Nebula Rift",
                'difficulty': 1.6},
            5: {'theme': 'ember', 'enemy_mode': 'ember', 'boss_kind': 'scorpion', 'arrival': "Ember Forge",
                'difficulty': 1.8},
            6: {'theme': 'frost', 'enemy_mode': 'frost', 'boss_kind': 'wyvern', 'arrival': "Frozen Expanse",
                'difficulty': 2.0},
            7: {'theme': 'toxic', 'enemy_mode': 'toxic', 'boss_kind': 'serpent', 'arrival': "Toxic Wasteland",
                'difficulty': 2.2},
            8: {'theme': 'quantum', 'enemy_mode': 'quantum', 'boss_kind': 'warden', 'arrival': "Quantum Citadel",
                'difficulty': 2.4},
            9: {'theme': 'void', 'enemy_mode': 'void', 'boss_kind': 'behemoth', 'arrival': "Void Abyss",
                'difficulty': 2.6},
            10: {'theme': 'eclipse', 'enemy_mode': 'eclipse', 'boss_kind': 'overseer', 'arrival': "Eclipse Throne",
                 'difficulty': 3.0},
        }
        profile = profiles.get(stage, profiles[10]).copy()
        profile['stage'] = stage
        return profile

    def setup_stage(self, stage):
        """Initialize a new stage."""
        self.wave = stage
        self.current_profile = self.get_stage_profile(stage)

        # Adjust enemy count based on difficulty
        base_enemies = 12 + (stage * 3)
        self.stage_enemy_target = min(base_enemies, 45)  # Extended mob fight before boss

        self.stage_phase = "enemies"
        self.stage_enemy_kills = 0
        self.spawn_timer = 0
        self.clear_banner_timer = 0
        self.arrival_timer = 0
        self.arrival_text = ""
        self.boss_warning_timer = 0
        self.boss_warning_text = ""
        self.boss_warning_next = None
        self.player_departing = False

        self.enemies.clear()
        self.enemy_bullets.clear()
        self.powerups.clear()
        self.shot_timer = 0
        self.player['x'] = SCREEN_WIDTH // 2
        self.player['y'] = 100
        self.player['invulnerable'] = True
        self.player['invulnerable_timer'] = 40

        if stage == 1:
            self.stage_phase = "enemies"
        else:
            self.stage_phase = "arrival"
            self.arrival_timer = 2.8
            self.arrival_text = f"Arrived at {self.current_profile.get('arrival', f'Stage {stage}')}"
            self.player['y'] = -80

        self.start_background_music()

    def spawn_stage_enemy(self):
        """Spawn enhanced stage-themed regular enemy."""
        if self.game_state != "playing":
            return
        if self.stage_phase != "enemies":
            return

        mode = self.current_profile.get('enemy_mode', 'alien')
        difficulty = self.current_profile.get('difficulty', 1.0)
        variant_pool = ['basic', 'fast', 'tank', 'swoop', 'chase']

        # Add more challenging variants for higher stages
        if self.wave >= 5:
            variant_pool.append('swoop')
        if self.wave >= 7:
            variant_pool.append('chase')

        variant = SimpleRandom.choice(variant_pool)
        
        # Assign a consistent mob image to this enemy
        mob_type = SimpleRandom.randint(1, 10)  # Assign mob type 1-10 (with duplicates)
        use_mob_image = True  # 100% chance to use mob image - all enemies have pictures

        enemy = {
            'x': SimpleRandom.randint(40, SCREEN_WIDTH - 40),
            'y': SCREEN_HEIGHT + SimpleRandom.randint(10, 60),
            'width': 30,
            'height': 30,
            'type': 'enemy',
            'variant': variant,
            'sprite_mode': mode,
            'health': 1,
            'speed': 2 + (difficulty * 1.2),
            'points': 10 + (self.wave * 3),
            'shoot_chance': 0.006 * difficulty,
            'angle': 0,
            'amplitude': 0,
            'mob_type': mob_type,  # Store the assigned mob type
            'use_mob_image': use_mob_image,  # Store whether to use mob image
        }

        if variant == 'fast':
            enemy['width'] = 20
            enemy['height'] = 20
            enemy['speed'] += 2.5
            enemy['points'] += 8
            enemy['shoot_chance'] = 0.004
        elif variant == 'tank':
            enemy['width'] = 40
            enemy['height'] = 40
            enemy['health'] = 3 + (self.wave // 3)
            enemy['speed'] = max(1.0, enemy['speed'] - 1.6)
            enemy['points'] += 16
            enemy['shoot_chance'] = 0.012
        elif variant == 'swoop':
            enemy['width'] = 28
            enemy['height'] = 28
            enemy['health'] = 2
            enemy['speed'] = 2.8
            enemy['points'] += 12
            enemy['shoot_chance'] = 0.008
            enemy['angle'] = 0
            enemy['amplitude'] = SimpleRandom.uniform(40, 80)
            enemy['frequency'] = SimpleRandom.uniform(0.02, 0.05)
        elif variant == 'chase':
            enemy['width'] = 28
            enemy['height'] = 28
            enemy['health'] = 2
            enemy['speed'] = 1.8
            enemy['points'] += 15
            enemy['shoot_chance'] = 0.015
            enemy['chase_speed'] = 1.2

        if mode == 'meteor':
            enemy['speed'] += 1.5
            enemy['drift'] = SimpleRandom.uniform(-1.5, 1.5)
            enemy['shoot_chance'] = 0.0
        elif mode == 'hybrid':
            enemy['drift'] = SimpleRandom.uniform(-1.2, 1.2)
            enemy['shoot_chance'] = 0.01
        elif mode in ['nebula', 'quantum']:
            enemy['drift'] = SimpleRandom.uniform(-1.8, 1.8)
            enemy['shoot_chance'] = 0.014
            enemy['speed'] += 0.8
        elif mode in ['ember', 'toxic', 'void']:
            enemy['drift'] = SimpleRandom.uniform(-1.2, 1.2)
            enemy['shoot_chance'] = 0.006
            enemy['speed'] += 1.2
        elif mode in ['frost', 'eclipse']:
            enemy['drift'] = SimpleRandom.uniform(-0.8, 0.8)
            enemy['shoot_chance'] = 0.012
        else:
            enemy['drift'] = SimpleRandom.uniform(-0.8, 0.8)

        # Set color based on mode
        if mode == 'meteor':
            enemy['color'] = ORANGE
        elif mode == 'hybrid':
            enemy['color'] = CYAN
        elif mode == 'nebula':
            enemy['color'] = PURPLE
        elif mode == 'ember':
            enemy['color'] = (1, 0.4, 0.15, 1)
        elif mode == 'frost':
            enemy['color'] = (0.65, 0.9, 1, 1)
        elif mode == 'toxic':
            enemy['color'] = (0.45, 1, 0.35, 1)
        elif mode == 'quantum':
            enemy['color'] = (0.6, 0.5, 1, 1)
        elif mode == 'void':
            enemy['color'] = (0.35, 0.35, 0.45, 1)
        elif mode == 'eclipse':
            enemy['color'] = (0.95, 0.78, 0.2, 1)
        else:
            enemy['color'] = RED if variant == 'basic' else (YELLOW if variant == 'fast' else PURPLE)

        self.enemies.append(enemy)

    def get_boss_display_name(self, boss_kind):
        boss_names = {
            'octopus': 'Abyssal Octopus',
            'grozilla': 'Grozilla',
            'growly': 'Growly',
            'manta': 'Nebula Manta',
            'scorpion': 'Ember Scorpion',
            'wyvern': 'Frost Wyvern',
            'serpent': 'Toxic Serpent',
            'warden': 'Quantum Warden',
            'behemoth': 'Void Behemoth',
            'overseer': 'Eclipse Overseer',
            'tyrant': 'The Tyrant',
        }
        name = boss_names.get(boss_kind, boss_kind)
        return name.title() if boss_kind == name else name

    def start_boss_warning(self, boss_kind=None, next_phase="boss"):
        if boss_kind is None:
            boss_kind = self.current_profile.get('boss_kind', 'boss')
        boss_name = self.get_boss_display_name(boss_kind)
        self.boss_warning_text = f"{boss_name} Incoming!"
        self.boss_warning_timer = 4.0
        self.boss_warning_next = next_phase
        self.stage_phase = "boss_warning"
        self.play_sound('boss_roar')

    def get_boss_size(self, boss_kind):
        sizes = {
            'octopus': (84, 96),
            'grozilla': (96, 96),
            'growly': (90, 92),
            'manta': (96, 84),
            'scorpion': (96, 92),
            'wyvern': (98, 96),
            'serpent': (92, 96),
            'warden': (96, 98),
            'behemoth': (110, 100),
            'overseer': (108, 108),
            'tyrant': (130, 128),
        }
        return sizes.get(boss_kind, (84, 96))

    def spawn_stage_boss(self):
        """Spawn enhanced stage boss with phases."""
        boss_kind = self.current_profile.get('boss_kind', 'octopus')
        difficulty = self.current_profile.get('difficulty', 1.0)
        boss_w, boss_h = self.get_boss_size(boss_kind)

        boss = {
            'x': SCREEN_WIDTH // 2,
            'y': SCREEN_HEIGHT - 120,
            'type': 'boss',
            'boss_kind': boss_kind,
            'width': boss_w,
            'height': boss_h,
            'health': 80 + int(self.wave * 18 * difficulty),
            'max_health': 80 + int(self.wave * 18 * difficulty),
            'speed': 2.4 + (difficulty * 0.5),
            'points': 700 + (self.wave * 50),
            'attack_timer': 0,
            'attack_mode': 0,
            'phase': 1,  # Boss phase (1-3)
            'phase_health': 0,  # Health threshold for phase change
            'spawn_immunity': 1.5,
        }

        # Set phase thresholds
        boss['phase_health'] = boss['health'] / 3

        self.enemies.append(boss)
        self.start_boss_music()
        self.stage_phase = "boss"

        # Spawn minions
        minion_count = 4 + (self.wave // 3)
        for idx in range(minion_count):
            minion = {
                'x': boss['x'] - 120 + (idx * 80),
                'y': boss['y'] - 40 - (idx % 2) * 20,
                'width': 22,
                'height': 22,
                'type': 'minion',
                'variant': 'escort',
                'sprite_mode': self.current_profile.get('enemy_mode', 'alien'),
                'health': 1 + (self.wave // 4),
                'speed': 2.2 + (difficulty * 0.5),
                'points': 20 + (self.wave * 2),
                'color': ORANGE if boss_kind == 'grozilla' else (GREEN if boss_kind == 'growly' else PURPLE),
            }
            self.enemies.append(minion)

    def start_ultra_boss_encounter(self):
        """Prepare Ultra encounter."""
        self.ultra_boss_active = True
        self.pending_ultra_spawn = True
        self.stage_phase = "arrival"
        self.arrival_timer = 3.2
        self.arrival_text = "Entering Tyrant Dominion"
        self.player['x'] = SCREEN_WIDTH // 2
        self.player['y'] = -100
        self.player['invulnerable'] = True
        self.player['invulnerable_timer'] = 120

        self.enemies.clear()
        self.enemy_bullets.clear()
        self.powerups.clear()

    def spawn_ultra_boss_trio(self):
        """Spawn ultra bosses."""
        self.pending_ultra_spawn = False
        self.stage_phase = "ultra_boss"
        self.start_boss_music()

        tyrant_w, tyrant_h = self.get_boss_size('tyrant')
        tyrant = {
            'x': SCREEN_WIDTH // 2,
            'y': SCREEN_HEIGHT - 140,
            'type': 'boss',
            'boss_kind': 'tyrant',
            'width': tyrant_w,
            'height': tyrant_h,
            'health': 420,
            'max_health': 420,
            'speed': 3.4,
            'points': 5000,
            'attack_timer': 0,
            'attack_mode': 0,
            'phase': 1,
            'phase_health': 140,
            'spawn_immunity': 2.0,
        }
        self.enemies.append(tyrant)

        # Spawn supporting bosses
        for idx, kind in enumerate(['octopus', 'overseer']):
            w, h = self.get_boss_size(kind)
            ally = {
                'x': SCREEN_WIDTH // 2 + (-180 if idx == 0 else 180),
                'y': SCREEN_HEIGHT - 180,
                'type': 'boss',
                'boss_kind': kind,
                'width': w,
                'height': h,
                'health': 180,
                'max_health': 180,
                'speed': 2.6 if idx == 0 else -2.6,
                'points': 1200,
                'attack_timer': 0,
                'attack_mode': 0,
                'phase': 1,
                'phase_health': 60,
                'spawn_immunity': 1.5,
            }
            self.enemies.append(ally)

    def trigger_stage_clear(self, message="LEVEL Cleared"):
        """Start clear animation."""
        # Create victory explosion effect
        for _ in range(20):
            self.particles.append(EnhancedParticle(
                SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2,
                YELLOW, size=5, speed_range=(5, 12), life=1.5
            ))

        # Screen shake
        self.screen_shake = 15

        # Clear minions
        for enemy in self.enemies[:]:
            if enemy['type'] == 'minion':
                self.create_explosion(enemy['x'], enemy['y'], ORANGE, explosion_type='small')
                self.enemies.remove(enemy)

        self.enemy_bullets.clear()
        self.stage_phase = "clear_anim"
        self.clear_banner_timer = 2.0
        self.clear_message = message
        self.player_departing = True
        self.player['invulnerable'] = True
        self.start_background_music()

        # Award weapon upgrade
        if self.player['weapon_level'] < 4:
            self.player['weapon_level'] = min(4, self.player['weapon_level'] + 1)

    def shoot(self):
        """Enhanced shooting with different weapon levels."""
        self.play_sound('shoot')

        if self.player['weapon_level'] == 1:
            # Single shot
            bullet = {
                'x': self.player['x'],
                'y': self.player['y'] + 20,
                'width': 4,
                'height': 12,
                'speed': 12,
                'color': YELLOW,
                'damage': 1
            }
            self.bullets.append(bullet)

        elif self.player['weapon_level'] == 2:
            # Double shot
            for offset in [-8, 8]:
                bullet = {
                    'x': self.player['x'] + offset,
                    'y': self.player['y'] + 20,
                    'width': 4,
                    'height': 12,
                    'speed': 12,
                    'color': CYAN,
                    'damage': 1
                }
                self.bullets.append(bullet)

        elif self.player['weapon_level'] == 3:
            # Triple shot
            for offset, speed_x in [(-10, -1), (0, 0), (10, 1)]:
                bullet = {
                    'x': self.player['x'] + offset,
                    'y': self.player['y'] + 20,
                    'width': 4,
                    'height': 12,
                    'speed': 12,
                    'speed_x': speed_x,
                    'color': GREEN if speed_x == 0 else ORANGE,
                    'damage': 2 if speed_x == 0 else 1
                }
                self.bullets.append(bullet)

        elif self.player['weapon_level'] >= 4:
            # Spread shot (5 bullets)
            for angle_offset in [-0.3, -0.15, 0, 0.15, 0.3]:
                speed_x = angle_offset * 4
                bullet = {
                    'x': self.player['x'] + (angle_offset * 20),
                    'y': self.player['y'] + 20,
                    'width': 4,
                    'height': 12,
                    'speed': 12,
                    'speed_x': speed_x,
                    'color': YELLOW if angle_offset == 0 else ORANGE,
                    'damage': 2 if angle_offset == 0 else 1
                }
                self.bullets.append(bullet)

    def load_audio(self):
        """Load sound effects and music."""
        # Create dummy sounds if files don't exist (to avoid errors)
        self.sounds['shoot'] = None
        self.sounds['explosion'] = None
        self.sounds['powerup'] = None
        self.sounds['boss_roar'] = None

        # Try to load actual sounds
        shoot_sound = kivy.core.audio.SoundLoader.load("sounds/shooting.wav.wav")
        if shoot_sound is None:
            shoot_sound = kivy.core.audio.SoundLoader.load("sounds/shoot.wav")
        if shoot_sound:
            self.sounds['shoot'] = shoot_sound

        explosion_sound = kivy.core.audio.SoundLoader.load("sounds/explosion.wav")
        if explosion_sound:
            self.sounds['explosion'] = explosion_sound

        powerup_sound = kivy.core.audio.SoundLoader.load("sounds/powerup.wav")
        if powerup_sound:
            self.sounds['powerup'] = powerup_sound

        boss_roar = kivy.core.audio.SoundLoader.load("sounds/Boss_Roar.wav")
        if boss_roar:
            self.sounds['boss_roar'] = boss_roar

        self.bgm = kivy.core.audio.SoundLoader.load("sounds/background.wav")
        self.boss_bgm = kivy.core.audio.SoundLoader.load("sounds/boss_battle.wav")
        if self.bgm:
            self.bgm.loop = True
        if self.boss_bgm:
            self.boss_bgm.loop = True

    def play_sound(self, name):
        sound = self.sounds.get(name)
        if sound:
            sound.play()

    def _switch_music(self, music):
        if self.current_music is music:
            return
        if self.current_music:

            
            self.current_music.stop()
        self.current_music = music
        if self.current_music:
            self.current_music.play()

    def start_background_music(self):
        self._switch_music(self.bgm)

    def start_boss_music(self):
        self._switch_music(self.boss_bgm if self.boss_bgm else self.bgm)

    def create_explosion(self, x, y, color=ORANGE, explosion_type='normal'):
        """Create enhanced explosion particles."""
        particle_count = 15 if explosion_type == 'normal' else 25
        particle_size = 3 if explosion_type == 'normal' else 5

        for _ in range(particle_count):
            self.particles.append(EnhancedParticle(
                x, y, color,
                size=particle_size,
                speed_range=(3, 10),
                gravity=-0.1,
                life=0.8,
                fade=True
            ))

        self.play_sound('explosion')

        # Small screen shake for big explosions
        if explosion_type == 'big':
            self.screen_shake = 5

    def update_fullscreen_background(self, dt):
        for star in self.fullscreen_stars:
            star['y'] -= star['speed'] * dt
            star['twinkle'] += dt * 2.0
            if star['y'] < 0:
                star['y'] = 1
                star['x'] = SimpleRandom.random()

    def update_ui(self):
        """Update UI (no widgets needed)"""
        pass

    def update(self, dt):
        """Main update loop with enhanced features"""
        # Update spaceship animation (disabled for single image)
        self.animation_timer += dt
        # Only animate if we have multiple frames
        if self.spaceship_textures and len(self.spaceship_textures) > 1:
            if self.animation_timer >= 0.1:  # Change frame every 0.1 seconds
                self.animation_timer = 0
                self.spaceship_frame = (self.spaceship_frame + 1) % len(self.spaceship_textures)

        # Update screen shake
        if self.screen_shake > 0:
            self.screen_shake -= 1
            self.shake_offset = (
                SimpleRandom.randint(-3, 3),
                SimpleRandom.randint(-3, 3)
            )
        else:
            self.shake_offset = (0, 0)

        if self.game_state == "playing":
            if self.stage_phase == "arrival":
                self.arrival_timer = max(0, self.arrival_timer - dt)
                self.player['y'] = min(100, self.player['y'] + 6.5)
                if self.arrival_timer <= 0:
                    if self.pending_ultra_spawn:
                        self.start_boss_warning(boss_kind='tyrant', next_phase="ultra_boss")
                    else:
                        self.stage_phase = "enemies"

            elif self.stage_phase == "clear_anim":
                self.clear_banner_timer = max(0, self.clear_banner_timer - dt)
                if self.player_departing:
                    self.player['y'] += 8 + (self.wave * 0.15)
                if self.player['y'] > SCREEN_HEIGHT + 120:
                    self.player_departing = False
                    if self.ultra_boss_active:
                        self.game_state = "victory"
                        self.save_high_score()
                    elif self.wave >= self.max_stages:
                        self.start_ultra_boss_encounter()
                    else:
                        self.setup_stage(self.wave + 1)
            else:
                if self.stage_phase == "boss_warning":
                    self.boss_warning_timer = max(0, self.boss_warning_timer - dt)
                    if self.boss_warning_timer <= 0:
                        next_phase = self.boss_warning_next
                        self.boss_warning_next = None
                        if next_phase == "ultra_boss":
                            self.spawn_ultra_boss_trio()
                        else:
                            self.spawn_stage_boss()

                # Player movement
                move_speed = self.player['speed']

                if 'left' in self.keys_pressed:
                    self.player['x'] = max(25, self.player['x'] - move_speed)
                if 'right' in self.keys_pressed:
                    self.player['x'] = min(SCREEN_WIDTH - 25, self.player['x'] + move_speed)

                # Vertical movement (optional)
                if self.player['vertical_movement_enabled']:
                    if 'up' in self.keys_pressed:
                        self.player['y'] = min(SCREEN_HEIGHT - 50, self.player['y'] + move_speed)
                    if 'down' in self.keys_pressed:
                        self.player['y'] = max(50, self.player['y'] - move_speed)

                # Auto shooting
                if self.shot_timer > 0:
                    self.shot_timer -= dt

                delay = 0.08 if self.rapid_fire else max(0.12, 0.28 - self.player['weapon_level'] * 0.025)
                if self.shot_timer <= 0 and ('spacebar' in self.keys_pressed or 'z' in self.keys_pressed):
                    self.shoot()
                    self.shot_timer = delay

                # Timers
                if self.player['invulnerable']:
                    self.player['invulnerable_timer'] -= 1
                    if self.player['invulnerable_timer'] <= 0:
                        self.player['invulnerable'] = False

                if self.shield_active:
                    self.shield_timer -= dt
                    if self.shield_timer <= 0:
                        self.shield_active = False

                if self.rapid_fire:
                    self.rapid_timer -= dt
                    if self.rapid_timer <= 0:
                        self.rapid_fire = False

                if self.double_score:
                    self.double_score_timer -= dt
                    if self.double_score_timer <= 0:
                        self.double_score = False

                # Enemy spawn
                if self.stage_phase == "enemies":
                    regular_enemies = [e for e in self.enemies if e['type'] == 'enemy']
                    max_on_screen = min(8 + self.wave, 18)

                    if self.stage_enemy_kills < self.stage_enemy_target:
                        self.spawn_timer -= dt
                        if len(regular_enemies) < max_on_screen and self.spawn_timer <= 0:
                            self.spawn_stage_enemy()
                            self.spawn_timer = max(0.2, 0.6 - self.wave * 0.02)
                    elif len(regular_enemies) == 0:
                        self.start_boss_warning()

                # Update enemies
                for enemy in self.enemies[:]:
                    enemy_type = enemy['type']

                    if enemy_type == 'boss':
                        # Boss movement
                        enemy['x'] += enemy['speed']
                        if enemy['x'] <= 70:
                            enemy['x'] = 70
                            enemy['speed'] = abs(enemy['speed'])
                        elif enemy['x'] >= SCREEN_WIDTH - 70:
                            enemy['x'] = SCREEN_WIDTH - 70
                            enemy['speed'] = -abs(enemy['speed'])

                        if enemy.get('spawn_immunity', 0) > 0:
                            enemy['spawn_immunity'] -= dt

                        # Boss phase check
                        health_percent = enemy['health'] / enemy['max_health']
                        if health_percent < 0.66 and enemy['phase'] == 1:
                            enemy['phase'] = 2
                            self.create_explosion(enemy['x'], enemy['y'], YELLOW, explosion_type='big')
                        elif health_percent < 0.33 and enemy['phase'] == 2:
                            enemy['phase'] = 3
                            self.create_explosion(enemy['x'], enemy['y'], RED, explosion_type='big')

                        enemy['attack_timer'] += dt
                        attack_delay = max(0.5, 1.0 - self.wave * 0.02)

                        if enemy['attack_timer'] >= attack_delay:
                            enemy['attack_timer'] = 0
                            boss_kind = enemy.get('boss_kind', 'octopus')
                            phase = enemy['phase']

                            # Enhanced boss attacks based on phase
                            if boss_kind == 'octopus':
                                bullet_count = 3 + (phase * 2)
                                for i in range(bullet_count):
                                    angle = (i - bullet_count // 2) * 0.8
                                    self.enemy_bullets.append({
                                        'x': enemy['x'],
                                        'y': enemy['y'] - 20,
                                        'width': 6,
                                        'height': 12,
                                        'speed': -6,
                                        'speed_x': angle,
                                        'color': RED,
                                        'damage': 1,
                                        'kind': 'normal',
                                    })
                            elif boss_kind == 'grozilla':
                                if enemy['attack_mode'] == 0:
                                    # Meteor shower
                                    for vx in [-3.5, -1.8, 0, 1.8, 3.5]:
                                        self.enemy_bullets.append({
                                            'x': enemy['x'],
                                            'y': enemy['y'] - 28,
                                            'width': 12,
                                            'height': 12,
                                            'speed': -6.5,
                                            'speed_x': vx,
                                            'color': ORANGE,
                                            'damage': 1,
                                            'kind': 'meteor_throw',
                                        })
                                else:
                                    # Sound wave (larger in higher phases)
                                    wave_count = 5 + (phase * 2)
                                    for i in range(wave_count):
                                        vx = -4 + (i * 8 / (wave_count - 1)) if wave_count > 1 else 0
                                        self.enemy_bullets.append({
                                            'x': enemy['x'],
                                            'y': enemy['y'] - 16,
                                            'width': 8 + phase,
                                            'height': 8 + phase,
                                            'speed': -4.5,
                                            'speed_x': vx,
                                            'growth': 0.3,
                                            'life': 1.5,
                                            'color': CYAN,
                                            'damage': 1,
                                            'kind': 'sound_wave',
                                        })
                                enemy['attack_mode'] = (enemy['attack_mode'] + 1) % 2
                            elif boss_kind == 'tyrant':
                                # Tyrant uses more attacks in higher phases
                                mode = (enemy['attack_mode'] + phase) % 3
                                if mode == 0:
                                    for vx in [-5, -3, -1, 1, 3, 5]:
                                        self.enemy_bullets.append({
                                            'x': enemy['x'],
                                            'y': enemy['y'] - 24,
                                            'width': 9,
                                            'height': 12,
                                            'speed': -6.5,
                                            'speed_x': vx,
                                            'color': RED,
                                            'damage': 1,
                                            'kind': 'normal',
                                        })
                                elif mode == 1:
                                    for vx in [-5.5, -3.5, -1.5, 0, 1.5, 3.5, 5.5]:
                                        self.enemy_bullets.append({
                                            'x': enemy['x'],
                                            'y': enemy['y'] - 18,
                                            'width': 10,
                                            'height': 10,
                                            'speed': -5.0,
                                            'speed_x': vx,
                                            'growth': 0.45,
                                            'life': 1.8,
                                            'color': CYAN,
                                            'damage': 1,
                                            'kind': 'sound_wave',
                                        })
                                else:
                                    for hand in [-1, 1]:
                                        self.enemy_bullets.append({
                                            'x': enemy['x'] + hand * 34,
                                            'y': enemy['y'] - 18,
                                            'width': 12,
                                            'height': 12,
                                            'speed': -4.5,
                                            'speed_x': hand * 7,
                                            'color': WHITE,
                                            'damage': 1,
                                            'kind': 'boomerang',
                                            'phase': 'out',
                                            'timer': 0,
                                            'out_time': 1.1,
                                            'owner': enemy,
                                        })
                                enemy['attack_mode'] = (enemy['attack_mode'] + 1) % 3
                            else:
                                # Generic boss attack pattern
                                bullet_count = 3 + phase
                                for i in range(bullet_count):
                                    vx = -3 + (i * 6 / (bullet_count - 1)) if bullet_count > 1 else 0
                                    self.enemy_bullets.append({
                                        'x': enemy['x'],
                                        'y': enemy['y'] - 20,
                                        'width': 7,
                                        'height': 10,
                                        'speed': -6,
                                        'speed_x': vx,
                                        'color': RED,
                                        'damage': 1,
                                        'kind': 'normal',
                                    })

                    elif enemy_type == 'minion':
                        # Minion AI
                        dx = self.player['x'] - enemy['x']
                        dy = self.player['y'] - enemy['y']
                        dist = abs(dx) + abs(dy)
                        if dist > 0:
                            move_x = min(enemy['speed'], max(-enemy['speed'], dx / dist * enemy['speed']))
                            move_y = min(enemy['speed'], max(-enemy['speed'], dy / dist * enemy['speed']))
                            enemy['x'] += move_x
                            enemy['y'] += move_y

                        if SimpleRandom.random() < 0.015:
                            self.enemy_bullets.append({
                                'x': enemy['x'],
                                'y': enemy['y'] - 8,
                                'width': 5,
                                'height': 10,
                                'speed': -5,
                                'speed_x': 0,
                                'color': ORANGE,
                                'damage': 1,
                                'kind': 'normal',
                            })

                        if enemy['y'] < -80 or enemy['y'] > SCREEN_HEIGHT + 80:
                            self.enemies.remove(enemy)

                    else:
                        # Regular enemy movement
                        enemy['x'] += enemy.get('drift', 0)

                        # Special movement for swoop enemies
                        if enemy.get('variant') == 'swoop':
                            enemy['angle'] += enemy.get('frequency', 0.03)
                            enemy['x'] += SimpleRandom.uniform(-1, 1) * enemy.get('amplitude',
                                                                                  50) * SimpleRandom.random() * 0.02

                        # Special movement for chase enemies
                        if enemy.get('variant') == 'chase':
                            dx = self.player['x'] - enemy['x']
                            if abs(dx) > 20:
                                enemy['x'] += min(enemy.get('chase_speed', 1),
                                                  max(-enemy.get('chase_speed', 1), dx * 0.05))

                        enemy['y'] -= enemy['speed']

                        if enemy['sprite_mode'] != 'meteor' and SimpleRandom.random() < enemy.get('shoot_chance', 0):
                            self.enemy_bullets.append({
                                'x': enemy['x'],
                                'y': enemy['y'] - 10,
                                'width': 4,
                                'height': 8,
                                'speed': -5,
                                'speed_x': 0,
                                'color': RED,
                                'damage': 1,
                                'kind': 'normal',
                            })

                        if enemy['y'] < -80 or enemy['x'] < -80 or enemy['x'] > SCREEN_WIDTH + 80:
                            self.enemies.remove(enemy)

                # Update bullets
                for bullet in self.bullets[:]:
                    bullet['y'] += bullet['speed']
                    if 'speed_x' in bullet:
                        bullet['x'] += bullet['speed_x']
                    if bullet['y'] > SCREEN_HEIGHT + 40 or bullet['x'] < -40 or bullet['x'] > SCREEN_WIDTH + 40:
                        self.bullets.remove(bullet)

                # Update enemy bullets
                for bullet in self.enemy_bullets[:]:
                    kind = bullet.get('kind', 'normal')
                    if kind == 'boomerang':
                        bullet['timer'] += dt
                        if bullet.get('phase') == 'out':
                            bullet['x'] += bullet['speed_x']
                            bullet['y'] += bullet['speed']
                            if bullet['timer'] >= bullet.get('out_time', 0.55):
                                bullet['phase'] = 'back'
                        else:
                            owner = bullet.get('owner')
                            target_x = owner['x'] if owner in self.enemies else SCREEN_WIDTH // 2
                            target_y = owner['y'] if owner in self.enemies else SCREEN_HEIGHT - 80
                            dx = target_x - bullet['x']
                            dy = target_y - bullet['y']
                            bullet['x'] += dx * 0.22
                            bullet['y'] += dy * 0.22
                            if abs(dx) < 8 and abs(dy) < 8:
                                self.enemy_bullets.remove(bullet)
                                continue
                    else:
                        bullet['y'] += bullet['speed']
                        bullet['x'] += bullet.get('speed_x', 0)
                        if kind == 'sound_wave':
                            bullet['width'] = min(28, bullet['width'] + bullet.get('growth', 0))
                            bullet['height'] = min(28, bullet['height'] + bullet.get('growth', 0))
                            bullet['life'] = bullet.get('life', 0) - dt
                            if bullet['life'] <= 0:
                                self.enemy_bullets.remove(bullet)
                                continue

                    if (bullet['y'] < -60 or bullet['y'] > SCREEN_HEIGHT + 60 or
                            bullet['x'] < -80 or bullet['x'] > SCREEN_WIDTH + 80):
                        self.enemy_bullets.remove(bullet)

                # Update powerups
                for powerup in self.powerups[:]:
                    powerup['y'] -= powerup.get('fall_speed', 1.0)
                    powerup['x'] += powerup.get('drift', 0.0)
                    if powerup['y'] < -30:
                        self.powerups.remove(powerup)

                # Collisions - Player bullets vs Enemies
                player_rect = {
                    'x': self.player['x'] - 30,  # Updated for larger spaceship (60x60)
                    'y': self.player['y'] - 30,
                    'width': 60,
                    'height': 60
                }

                for bullet in self.bullets[:]:
                    for enemy in self.enemies[:]:
                        if (bullet['x'] > enemy['x'] - enemy['width'] // 2 and
                                bullet['x'] < enemy['x'] + enemy['width'] // 2 and
                                bullet['y'] > enemy['y'] - enemy['height'] // 2 and
                                bullet['y'] < enemy['y'] + enemy['height'] // 2):

                            if bullet in self.bullets:
                                self.bullets.remove(bullet)

                            if enemy['type'] == 'boss' and enemy.get('spawn_immunity', 0) > 0:
                                break

                            enemy['health'] -= bullet['damage']
                            # Hit effect
                            self.particles.append(EnhancedParticle(
                                bullet['x'], bullet['y'],
                                YELLOW, size=2, speed_range=(1, 4), life=0.3, fade=True
                            ))

                            if enemy['health'] <= 0:
                                # Score with multiplier
                                points = enemy['points']
                                if self.double_score:
                                    points *= 2
                                self.score += points
                                self.enemies_killed += 1
                                self.create_explosion(enemy['x'], enemy['y'], enemy.get('color', ORANGE))

                                if enemy in self.enemies:
                                    self.enemies.remove(enemy)

                                if enemy['type'] == 'enemy':
                                    self.stage_enemy_kills += 1
                                    if SimpleRandom.random() < POWERUP_DROP_CHANCE:
                                        powerup_types = ['health', 'weapon', 'shield', 'rapid']
                                        # Add double score powerup for higher stages
                                        if self.wave >= 5:
                                            powerup_types.append('double_score')
                                        self.powerups.append({
                                            'x': enemy['x'],
                                            'y': enemy['y'],
                                            'type': SimpleRandom.choice(powerup_types),
                                            'width': 20,
                                            'height': 20,
                                            'fall_speed': 0.8 + (SimpleRandom.random() * 0.7),
                                            'drift': (SimpleRandom.random() * 0.5) - 0.25,
                                        })
                                elif enemy['type'] == 'boss':
                                    if self.stage_phase == "ultra_boss":
                                        remaining_bosses = [e for e in self.enemies if e.get('type') == 'boss']
                                        if len(remaining_bosses) == 0:
                                            self.trigger_stage_clear("The Tyrant Has Fallen")
                                    else:
                                        self.trigger_stage_clear()
                            break

                # Collisions - Enemy bullets vs Player
                if not self.player['invulnerable'] and not self.shield_active:
                    for bullet in self.enemy_bullets[:]:
                        if (bullet['x'] > player_rect['x'] and
                                bullet['x'] < player_rect['x'] + player_rect['width'] and
                                bullet['y'] > player_rect['y'] and
                                bullet['y'] < player_rect['y'] + player_rect['height']):
                            self.enemy_bullets.remove(bullet)
                            self.player['lives'] -= 1
                            self.player['invulnerable'] = True
                            self.player['invulnerable_timer'] = 120
                            self.create_explosion(self.player['x'], self.player['y'], RED, explosion_type='big')
                            if self.player['lives'] <= 0:
                                self.game_state = "game_over"
                                self.save_high_score()
                                if self.current_music:
                                    self.current_music.stop()
                            break

                # Collisions - Player vs Enemies
                if not self.player['invulnerable'] and not self.shield_active:
                    for enemy in self.enemies[:]:
                        if (self.player['x'] - 30 < enemy['x'] + enemy['width'] // 2 and  # Updated for larger ship
                                self.player['x'] + 30 > enemy['x'] - enemy['width'] // 2 and
                                self.player['y'] - 30 < enemy['y'] + enemy['height'] // 2 and
                                self.player['y'] + 30 > enemy['y'] - enemy['height'] // 2):
                            if enemy['type'] != 'boss' and enemy in self.enemies:
                                self.enemies.remove(enemy)
                            self.player['lives'] -= 1
                            self.player['invulnerable'] = True
                            self.player['invulnerable_timer'] = 120
                            self.create_explosion(self.player['x'], self.player['y'], RED, explosion_type='big')
                            if self.player['lives'] <= 0:
                                self.game_state = "game_over"
                                self.save_high_score()
                            break

                # Power-up collection
                for powerup in self.powerups[:]:
                    if (self.player['x'] - 30 < powerup['x'] + 10 and  # Updated for larger ship
                            self.player['x'] + 30 > powerup['x'] - 10 and
                            self.player['y'] - 30 < powerup['y'] + 10 and
                            self.player['y'] + 30 > powerup['y'] - 10):
                        self.powerups.remove(powerup)
                        self.play_sound('powerup')

                        if powerup['type'] == 'health':
                            self.player['lives'] = min(self.player['max_lives'], self.player['lives'] + 1)
                        elif powerup['type'] == 'weapon':
                            self.player['weapon_level'] = min(4, self.player['weapon_level'] + 1)
                        elif powerup['type'] == 'shield':
                            self.shield_active = True
                            self.shield_timer = 6
                        elif powerup['type'] == 'rapid':
                            self.rapid_fire = True
                            self.rapid_timer = 8
                        elif powerup['type'] == 'double_score':
                            self.double_score = True
                            self.double_score_timer = 10

        # Update fullscreen backdrop, particles, and starfield
        self.update_fullscreen_background(dt)
        self.starfield.update()
        self.particles = [p for p in self.particles if p.update()]

        # Update background elements
        for cloud in self.bg_clouds:
            cloud['x'] -= cloud['speed']
            if cloud['x'] < -cloud['width']:
                cloud['x'] = SCREEN_WIDTH
                cloud['y'] = SimpleRandom.randint(0, SCREEN_HEIGHT)

        for chunk in self.bg_meteor_chunks:
            chunk['x'] -= chunk['speed']
            if chunk['x'] < -50:
                chunk['x'] = SCREEN_WIDTH + 50
                chunk['y'] = SimpleRandom.randint(0, SCREEN_HEIGHT)

        # Redraw
        self.update_login_visibility()
        self.update_exit_visibility()
        self.game_canvas.clear()
        self.draw()

    def draw_fullscreen_backdrop(self):
        width, height = self.size
        if width <= 0 or height <= 0:
            return

        # Gradient base
        steps = 6
        band_h = height / steps
        for i in range(steps):
            t = i / (steps - 1)
            r = 0.02 + (0.04 * t)
            g = 0.02 + (0.03 * t)
            b = 0.05 + (0.08 * t)
            kivy.graphics.Color(r, g, b, 1)
            kivy.graphics.Rectangle(pos=(0, band_h * i), size=(width, band_h + 1))

        # Nebula glow
        min_dim = min(width, height)
        for blob in self.fullscreen_nebula:
            size = blob['size'] * min_dim
            x = blob['x'] * width
            y = blob['y'] * height
            kivy.graphics.Color(*blob['color'])
            kivy.graphics.Rectangle(
                pos=(x - (size / 2), y - (size / 2)),
                size=(size, size)
            )

        # Stars
        for star in self.fullscreen_stars:
            brightness = 0.4 + 0.6 * (0.5 + 0.5 * math.sin(star['twinkle']))
            kivy.graphics.Color(brightness, brightness, brightness, 1)
            x = star['x'] * width
            y = star['y'] * height
            size = star['size']
            kivy.graphics.Rectangle(pos=(int(x), int(y)), size=(size, size))

    def draw(self):
        """Draw everything with screen shake effect"""
        with self.game_canvas:
            # Apply screen shake
            kivy.graphics.PushMatrix()
            kivy.graphics.Translate(self.shake_offset[0], self.shake_offset[1], 0)

            # Fill background
            self.draw_fullscreen_backdrop()

            # Render game with scaling
            scale = min(self.width / SCREEN_WIDTH, self.height / SCREEN_HEIGHT)
            offset_x = (self.width - (SCREEN_WIDTH * scale)) / 2
            offset_y = (self.height - (SCREEN_HEIGHT * scale)) / 2

            kivy.graphics.PushMatrix()
            kivy.graphics.Translate(offset_x, offset_y, 0)
            kivy.graphics.Scale(scale, scale, 1)

            self.draw_stage_background()

            if self.game_state == "login":
                self.draw_login()
            elif self.game_state == "menu":
                self.draw_menu()
            elif self.game_state == "playing":
                self.draw_game()
            elif self.game_state == "paused":
                self.draw_game()
                self.draw_paused()
            elif self.game_state == "game_over":
                self.draw_game_over()
            elif self.game_state == "victory":
                self.draw_victory()

            kivy.graphics.PopMatrix()
            kivy.graphics.PopMatrix()

    def draw_stage_background(self):
        """Draw enhanced stage-dependent scenery."""
        theme = self.current_profile.get('theme', 'space')

        # Base gradient background
        if theme == 'space':
            kivy.graphics.Color(0, 0, 0.1, 1)
            kivy.graphics.Rectangle(pos=(0, 0), size=(SCREEN_WIDTH, SCREEN_HEIGHT))
            self.starfield.draw(self.game_canvas)

        elif theme == 'kong':
            kivy.graphics.Color(0.09, 0.05, 0.03, 1)
            kivy.graphics.Rectangle(pos=(0, 0), size=(SCREEN_WIDTH, SCREEN_HEIGHT))

            # Animated meteor belt
            for chunk in self.bg_meteor_chunks:
                kivy.graphics.Color(0.25, 0.18, 0.14, 1)
                kivy.graphics.Rectangle(
                    pos=(self.px(chunk['x']), self.px(chunk['y'])),
                    size=(chunk['size'], chunk['size'])
                )

        elif theme == 'ember':
            # Lava-like space background for Ember Forge
            kivy.graphics.Color(0.15, 0.02, 0.01, 1)  # Dark red base
            kivy.graphics.Rectangle(pos=(0, 0), size=(SCREEN_WIDTH, SCREEN_HEIGHT))
            
            # Add lava glow effect
            kivy.graphics.Color(0.8, 0.2, 0.1, 0.3)  # Red glow
            kivy.graphics.Rectangle(pos=(0, 0), size=(SCREEN_WIDTH, SCREEN_HEIGHT))
            
            # Moving lava clouds
            for cloud in self.bg_clouds:
                kivy.graphics.Color(0.9, 0.3, 0.1, 0.4)  # Orange lava clouds
                kivy.graphics.Rectangle(
                    pos=(self.px(cloud['x']), self.px(cloud['y'])),
                    size=(cloud['width'], cloud['height'])
                )
            
            # Add some glowing lava particles
            for chunk in self.bg_meteor_chunks[:15]:  # Use half of meteor chunks as lava particles
                kivy.graphics.Color(1.0, 0.4, 0.1, 0.6)  # Bright orange lava
                kivy.graphics.Rectangle(
                    pos=(self.px(chunk['x']), self.px(chunk['y'])),
                    size=(chunk['size'] // 2, chunk['size'] // 2)
                )

        elif theme == 'saturn':
            kivy.graphics.Color(0.04, 0.02, 0.08, 1)
            kivy.graphics.Rectangle(pos=(0, 0), size=(SCREEN_WIDTH, SCREEN_HEIGHT))

            # Moving clouds
            for cloud in self.bg_clouds:
                kivy.graphics.Color(0.2, 0.15, 0.3, 0.3)
                kivy.graphics.Rectangle(
                    pos=(self.px(cloud['x']), self.px(cloud['y'])),
                    size=(cloud['width'], cloud['height'])
                )

        elif theme == 'toxic':
            # Toxic/gases background for Toxic Wasteland
            kivy.graphics.Color(0.05, 0.15, 0.05, 1)  # Dark green toxic base
            kivy.graphics.Rectangle(pos=(0, 0), size=(SCREEN_WIDTH, SCREEN_HEIGHT))
            
            # Add toxic gas layers
            kivy.graphics.Color(0.3, 0.8, 0.2, 0.2)  # Green toxic gas
            kivy.graphics.Rectangle(pos=(0, 0), size=(SCREEN_WIDTH, SCREEN_HEIGHT))
            
            # Moving toxic clouds
            for cloud in self.bg_clouds:
                kivy.graphics.Color(0.6, 1.0, 0.3, 0.5)  # Bright toxic green clouds
                kivy.graphics.Rectangle(
                    pos=(self.px(cloud['x']), self.px(cloud['y'])),
                    size=(cloud['width'], cloud['height'])
                )
            
            # Add toxic gas particles
            for chunk in self.bg_meteor_chunks[:12]:  # Use some meteor chunks as toxic particles
                kivy.graphics.Color(0.8, 1.0, 0.4, 0.7)  # Bright toxic green
                kivy.graphics.Rectangle(
                    pos=(self.px(chunk['x']), self.px(chunk['y'])),
                    size=(chunk['size'] // 3, chunk['size'] // 3)
                )

        elif theme == 'void':
            # Blackhole background for Void Abyss
            kivy.graphics.Color(0, 0, 0, 1)  # Pure black
            kivy.graphics.Rectangle(pos=(0, 0), size=(SCREEN_WIDTH, SCREEN_HEIGHT))
            
            # Add blackhole center
            blackhole_x = SCREEN_WIDTH // 2
            blackhole_y = SCREEN_HEIGHT // 2
            blackhole_radius = 80
            
            # Event horizon (black center)
            kivy.graphics.Color(0, 0, 0, 1)
            for i in range(blackhole_radius):
                circle_size = (blackhole_radius - i) * 2
                kivy.graphics.Rectangle(
                    pos=(self.px(blackhole_x - (blackhole_radius - i)), self.px(blackhole_y - (blackhole_radius - i))),
                    size=(circle_size, circle_size)
                )
            
            # Accretion disk (orange glow)
            kivy.graphics.Color(1.0, 0.4, 0.1, 0.6)
            for i in range(20):
                angle = (i / 20) * 6.28318
                radius = blackhole_radius + 20 + (i * 3)
                # Use kivy's built-in math - approximate cos/sin using angle
                x = blackhole_x + radius * (1 - (angle * angle) / 2)  # cos approximation
                y = blackhole_y + radius * (angle - (angle * angle * angle) / 6)  # sin approximation
                kivy.graphics.Rectangle(
                    pos=(self.px(x - 2), self.px(y - 2)),
                    size=(4, 4)
                )
            
            # Swirling particles
            for chunk in self.bg_meteor_chunks[:8]:
                kivy.graphics.Color(0.8, 0.3, 0.1, 0.8)  # Orange particles
                kivy.graphics.Rectangle(
                    pos=(self.px(chunk['x']), self.px(chunk['y'])),
                    size=(chunk['size'] // 2, chunk['size'] // 2)
                )

        elif theme == 'frost':
            # Frozen ice background for Frozen Expanse
            kivy.graphics.Color(0.05, 0.1, 0.15, 1)  # Ice blue base
            kivy.graphics.Rectangle(pos=(0, 0), size=(SCREEN_WIDTH, SCREEN_HEIGHT))
            
            # Add ice crystal effect
            kivy.graphics.Color(0.7, 0.9, 1.0, 0.3)  # Light blue ice
            kivy.graphics.Rectangle(pos=(0, 0), size=(SCREEN_WIDTH, SCREEN_HEIGHT))
            
            # Ice clouds
            for cloud in self.bg_clouds:
                kivy.graphics.Color(0.8, 0.95, 1.0, 0.4)  # Frozen clouds
                kivy.graphics.Rectangle(
                    pos=(self.px(cloud['x']), self.px(cloud['y'])),
                    size=(cloud['width'], cloud['height'])
                )
            
            # Ice particles/snow
            for chunk in self.bg_meteor_chunks[:10]:
                kivy.graphics.Color(0.9, 0.98, 1.0, 0.8)  # Bright ice crystals
                kivy.graphics.Rectangle(
                    pos=(self.px(chunk['x']), self.px(chunk['y'])),
                    size=(chunk['size'] // 4, chunk['size'] // 4)
                )

        elif theme == 'quantum':
            # Quantum space background for Quantum Citadel
            kivy.graphics.Color(0.1, 0, 0.15, 1)  # Deep purple base
            kivy.graphics.Rectangle(pos=(0, 0), size=(SCREEN_WIDTH, SCREEN_HEIGHT))
            
            # Quantum energy field
            kivy.graphics.Color(0.6, 0.2, 1.0, 0.2)  # Purple energy
            kivy.graphics.Rectangle(pos=(0, 0), size=(SCREEN_WIDTH, SCREEN_HEIGHT))
            
            # Quantum particles
            for chunk in self.bg_meteor_chunks:
                kivy.graphics.Color(0.8, 0.4, 1.0, 0.9)  # Bright quantum particles
                kivy.graphics.Rectangle(
                    pos=(self.px(chunk['x']), self.px(chunk['y'])),
                    size=(chunk['size'] // 3, chunk['size'] // 3)
                )
            
            # Energy waves
            for cloud in self.bg_clouds[:3]:
                kivy.graphics.Color(0.9, 0.6, 1.0, 0.3)  # Quantum waves
                kivy.graphics.Rectangle(
                    pos=(self.px(cloud['x']), self.px(cloud['y'])),
                    size=(cloud['width'], cloud['height'] // 3)
                )

        elif theme == 'eclipse':
            # Eclipse background for Eclipse Throne
            kivy.graphics.Color(0.05, 0.02, 0.08, 1)  # Dark purple base
            kivy.graphics.Rectangle(pos=(0, 0), size=(SCREEN_WIDTH, SCREEN_HEIGHT))
            
            # Eclipse effect (darkened center)
            eclipse_x = SCREEN_WIDTH // 2
            eclipse_y = SCREEN_HEIGHT // 2
            eclipse_radius = 120
            
            # Dark eclipse shadow
            kivy.graphics.Color(0, 0, 0, 0.8)
            for i in range(eclipse_radius):
                circle_size = (eclipse_radius - i) * 2
                kivy.graphics.Rectangle(
                    pos=(self.px(eclipse_x - (eclipse_radius - i)), self.px(eclipse_y - (eclipse_radius - i))),
                    size=(circle_size, circle_size)
                )
            
            # Corona effect
            kivy.graphics.Color(1.0, 0.8, 0.2, 0.4)  # Golden corona
            for i in range(30):
                angle = (i / 30) * 6.28318
                radius = eclipse_radius + 10 + (i * 2)
                # Use kivy's built-in math - approximate cos/sin using angle
                x = eclipse_x + radius * (1 - (angle * angle) / 2)  # cos approximation
                y = eclipse_y + radius * (angle - (angle * angle * angle) / 6)  # sin approximation
                kivy.graphics.Rectangle(
                    pos=(self.px(x - 1), self.px(y - 1)),
                    size=(2, 2)
                )

        else:
            kivy.graphics.Color(0, 0, 0.1, 1)
            kivy.graphics.Rectangle(pos=(0, 0), size=(SCREEN_WIDTH, SCREEN_HEIGHT))
            self.starfield.draw(self.game_canvas)

    def draw_text(self, text, center_x, center_y, color=WHITE, font_size=26):
        """Draw centered text."""
        core_label = kivy.core.text.Label(text=text, font_size=font_size, color=color)
        core_label.refresh()
        texture = core_label.texture
        kivy.graphics.Color(*color)
        kivy.graphics.Rectangle(
            texture=texture,
            pos=(center_x - texture.width / 2, center_y - texture.height / 2),
            size=texture.size
        )

    def draw_text_left(self, text, x, y, color=WHITE, font_size=22):
        """Draw left-aligned text."""
        core_label = kivy.core.text.Label(text=text, font_size=font_size, color=color)
        core_label.refresh()
        texture = core_label.texture
        kivy.graphics.Color(*color)
        kivy.graphics.Rectangle(texture=texture, pos=(x, y), size=texture.size)

    def px(self, value):
        """Convert to pixel-aligned coordinates."""
        return int(value // PIXEL_SIZE) * PIXEL_SIZE

    def draw_pixel_sprite(self, center_x, center_y, pattern, palette, scale=PIXEL_SIZE):
        """Draw pixel-art sprite."""
        height = len(pattern)
        width = max(len(row) for row in pattern)
        origin_x = self.px(center_x - (width * scale) / 2)
        origin_y = self.px(center_y - (height * scale) / 2)

        for row_idx, row in enumerate(pattern):
            row = row.ljust(width, ".")
            for col_idx, pixel in enumerate(row):
                color = palette.get(pixel)
                if color:
                    kivy.graphics.Color(*color)
                    x = origin_x + (col_idx * scale)
                    y = origin_y + ((height - 1 - row_idx) * scale)
                    kivy.graphics.Rectangle(pos=(x, y), size=(scale, scale))

    def darken(self, color, amount=0.35):
        r, g, b, a = color
        return (max(0, r - amount), max(0, g - amount), max(0, b - amount), a)

    def draw_login(self):
        """Draw login screen text (form is a widget overlay)."""
        pass

    def draw_menu(self):
        """Draw enhanced menu screen."""
        with self.game_canvas:
            self.draw_text("SPACE SHOOTER", SCREEN_WIDTH // 2, 560, color=CYAN, font_size=56)
            self.draw_text("Press SPACE to Start", SCREEN_WIDTH // 2, 440, color=WHITE, font_size=32)
            self.draw_text("Arrow Keys to Move", SCREEN_WIDTH // 2, 380, color=WHITE, font_size=24)
            self.draw_text("Z or SPACE to Shoot (Hold SPACEBAR to Auto Shoot)", SCREEN_WIDTH // 2, 340, color=WHITE, font_size=24)
            self.draw_text("ESC or P to Pause | V to Toggle Vertical Movement", SCREEN_WIDTH // 2, 300, color=YELLOW,
                           font_size=20)
            self.draw_text("Clear all 10 stages and defeat every boss", SCREEN_WIDTH // 2, 260, color=ORANGE,
                           font_size=20)
            if self.current_user:
                self.draw_text(f"Player: {self.current_user}", SCREEN_WIDTH // 2, 230, color=CYAN, font_size=22)
                if self.user_games_played > 0:
                    self.draw_text(f"Best Score: {self.high_score}", SCREEN_WIDTH // 2, 200, color=GREEN,
                                   font_size=22)
                    if self.user_last_score is not None:
                        self.draw_text(
                            f"Last Score: {self.user_last_score} (Wave {self.user_last_wave})",
                            SCREEN_WIDTH // 2,
                            170,
                            color=WHITE,
                            font_size=20
                        )
                    self.draw_text(f"Games Played: {self.user_games_played}", SCREEN_WIDTH // 2, 140, color=WHITE,
                                   font_size=18)
                else:
                    self.draw_text("No games recorded yet", SCREEN_WIDTH // 2, 200, color=GREEN, font_size=22)

    def draw_paused(self):
        """Draw pause screen overlay."""
        with self.game_canvas:
            kivy.graphics.Color(0, 0, 0, 0.7)
            kivy.graphics.Rectangle(pos=(0, 0), size=(SCREEN_WIDTH, SCREEN_HEIGHT))
            self.draw_text("PAUSED", SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 + 120, color=CYAN, font_size=48)

            for idx, item in enumerate(self.get_pause_menu_layout()):
                is_selected = idx == self.pause_menu_index
                if is_selected:
                    kivy.graphics.Color(0.2, 0.8, 1, 0.35)
                else:
                    kivy.graphics.Color(0.1, 0.1, 0.1, 0.5)
                kivy.graphics.Rectangle(
                    pos=(item['x'], item['y']),
                    size=(item['w'], item['h'])
                )
                text_color = CYAN if is_selected else WHITE
                self.draw_text(item['label'], item['center_x'], item['center_y'], color=text_color, font_size=24)

            self.draw_text("ESC to Resume | ENTER to Select", SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 - 120,
                           color=WHITE, font_size=20)

    def draw_game(self):
        """Draw game screen with HUD."""
        with self.game_canvas:
            # Draw power-ups
            for powerup in self.powerups:
                # Try to draw powerup image
                if powerup['type'] in self.powerup_textures:
                    powerup_tex = self.powerup_textures[powerup['type']]
                    kivy.graphics.Color(1, 1, 1, 1)  # Full white for texture
                    kivy.graphics.Rectangle(
                        texture=powerup_tex,
                        pos=(self.px(powerup['x'] - 10), self.px(powerup['y'] - 10)),
                        size=(20, 20)
                    )
                else:
                    # Fallback to pixelated sprite
                    if powerup['type'] == 'health':
                        icon_pattern = ["..11..", ".1221.", "122221", ".1221.", "..11.."]
                        icon_palette = {"1": (0.45, 1.0, 0.45, 1), "2": (0.12, 0.72, 0.12, 1)}
                    elif powerup['type'] == 'weapon':
                        icon_pattern = ["3....3", ".3333.", "..33..", ".3333.", "3....3"]
                        icon_palette = {"3": (0.20, 0.60, 1.0, 1)}
                    elif powerup['type'] == 'shield':
                        icon_pattern = ["..44..", ".4444.", "444444", ".4444.", "..44.."]
                        icon_palette = {"4": (0.60, 0.60, 1.0, 1)}
                    elif powerup['type'] == 'double_score':
                        icon_pattern = ["..66..", ".6666.", "666666", ".6666.", "..66.."]
                        icon_palette = {"6": (1.0, 0.8, 0.2, 1)}
                    else:  # rapid
                        icon_pattern = ["5....5", ".5555.", "..55..", ".5555.", "5....5"]
                        icon_palette = {"5": (1.0, 0.62, 0.12, 1)}

                    self.draw_pixel_sprite(powerup['x'], powerup['y'], icon_pattern, icon_palette, scale=3)

            # Draw enemies
            for enemy in self.enemies:
                if enemy['type'] == 'boss':
                    # Try to draw specific boss image for the current stage
                    boss_key = f'boss_{self.wave}'
                    if boss_key in self.boss_textures:
                        boss_tex = self.boss_textures[boss_key]
                        kivy.graphics.Color(1, 1, 1, 1)  # Full white for texture
                        kivy.graphics.Rectangle(
                            texture=boss_tex,
                            pos=(self.px(enemy['x'] - enemy['width'] // 2), self.px(enemy['y'] - enemy['height'] // 2)),
                            size=(enemy['width'], enemy['height'])
                        )
                    else:
                        # Fallback to colored rectangle
                        kivy.graphics.Color(*enemy.get('color', RED))
                        kivy.graphics.Rectangle(
                            pos=(self.px(enemy['x'] - enemy['width'] // 2), self.px(enemy['y'] - enemy['height'] // 2)),
                            size=(enemy['width'], enemy['height'])
                        )

                    # Health bar with phase colors
                    health_percent = enemy['health'] / enemy['max_health']
                    if health_percent > 0.66:
                        bar_color = GREEN
                    elif health_percent > 0.33:
                        bar_color = YELLOW
                    else:
                        bar_color = RED

                    kivy.graphics.Color(1, 0, 0, 1)
                    kivy.graphics.Rectangle(pos=(self.px(enemy['x'] - 40), self.px(enemy['y'] - 52)), size=(80, 8))
                    kivy.graphics.Color(*bar_color)
                    kivy.graphics.Rectangle(pos=(self.px(enemy['x'] - 40), self.px(enemy['y'] - 52)),
                                            size=(80 * health_percent, 8))

                    # Phase indicator
                    if enemy.get('phase', 1) > 1:
                        kivy.graphics.Color(1, 0.5, 0, 0.8)
                        kivy.graphics.Rectangle(pos=(self.px(enemy['x'] - 45), self.px(enemy['y'] - 60)),
                                                size=(5, 5 * enemy['phase']))
                else:
                    # Draw regular enemies with consistent boss images as mobs
                    if enemy.get('use_mob_image', False) and 'mob_type' in enemy:
                        mob_key = f'mob_{enemy["mob_type"]}'  # Use the stored mob type
                        if mob_key in self.mob_textures:
                            mob_tex = self.mob_textures[mob_key]
                            kivy.graphics.Color(1, 1, 1, 1)  # Full white for texture
                            kivy.graphics.Rectangle(
                                texture=mob_tex,
                                pos=(self.px(enemy['x'] - enemy['width'] // 2), self.px(enemy['y'] - enemy['height'] // 2)),
                                size=(enemy['width'], enemy['height'])
                            )
                        else:
                            # Fallback to colored rectangle
                            kivy.graphics.Color(*enemy.get('color', RED))
                            kivy.graphics.Rectangle(
                                pos=(self.px(enemy['x'] - enemy['width'] // 2), self.px(enemy['y'] - enemy['height'] // 2)),
                                size=(enemy['width'], enemy['height'])
                            )
                    else:
                        # Fallback to colored rectangle
                        kivy.graphics.Color(*enemy.get('color', RED))
                        kivy.graphics.Rectangle(
                            pos=(self.px(enemy['x'] - enemy['width'] // 2), self.px(enemy['y'] - enemy['height'] // 2)),
                            size=(enemy['width'], enemy['height'])
                        )

                    # Health bar for tank enemies
                    if enemy.get('variant') == 'tank':
                        health_percent = enemy['health'] / 3
                        kivy.graphics.Color(1, 0, 0, 1)
                        kivy.graphics.Rectangle(pos=(self.px(enemy['x'] - 20), self.px(enemy['y'] - 28)), size=(40, 6))
                        kivy.graphics.Color(0, 1, 0, 1)
                        kivy.graphics.Rectangle(pos=(self.px(enemy['x'] - 20), self.px(enemy['y'] - 28)),
                                                size=(40 * health_percent, 6))

            # Draw bullets
            for bullet in self.bullets:
                kivy.graphics.Color(*bullet['color'])
                kivy.graphics.Rectangle(pos=(self.px(bullet['x'] - 2), self.px(bullet['y'])), size=(4, 12))

            for bullet in self.enemy_bullets:
                kivy.graphics.Color(*bullet['color'])
                if bullet.get('kind') == 'sound_wave':
                    width = bullet.get('width', 8)
                    height = bullet.get('height', 8)
                    kivy.graphics.Rectangle(pos=(self.px(bullet['x'] - width / 2), self.px(bullet['y'] - height / 2)),
                                            size=(width, height))
                else:
                    kivy.graphics.Rectangle(pos=(self.px(bullet['x'] - 4), self.px(bullet['y'] - 8)), size=(8, 12))

            # Draw particles
            for particle in self.particles:
                particle.draw(self.game_canvas)

            # Draw player
            if not self.player['invulnerable'] or (self.player['invulnerable_timer'] // 10 % 2 == 0):
                # Shield effect - circular shield
                if self.shield_active:
                    kivy.graphics.Color(0.2, 0.5, 1, 0.3)
                    shield_radius = 35
                    shield_center_x = self.player['x']
                    shield_center_y = self.player['y']
                    
                    # Draw circle using octagon approximation (more reliable)
                    num_sides = 8  # Octagon for better circle approximation
                    for i in range(num_sides):
                        angle = (i / num_sides) * 6.28318  # 2 * PI
                        
                        # Calculate octagon vertices using simpler approximations
                        if i == 0:  # Right
                            x1 = shield_center_x + shield_radius
                            y1 = shield_center_y
                        elif i == 1:  # Top-right
                            x1 = shield_center_x + shield_radius * 0.707
                            y1 = shield_center_y + shield_radius * 0.707
                        elif i == 2:  # Top
                            x1 = shield_center_x
                            y1 = shield_center_y + shield_radius
                        elif i == 3:  # Top-left
                            x1 = shield_center_x - shield_radius * 0.707
                            y1 = shield_center_y + shield_radius * 0.707
                        elif i == 4:  # Left
                            x1 = shield_center_x - shield_radius
                            y1 = shield_center_y
                        elif i == 5:  # Bottom-left
                            x1 = shield_center_x - shield_radius * 0.707
                            y1 = shield_center_y - shield_radius * 0.707
                        elif i == 6:  # Bottom
                            x1 = shield_center_x
                            y1 = shield_center_y - shield_radius
                        else:  # Bottom-right
                            x1 = shield_center_x + shield_radius * 0.707
                            y1 = shield_center_y - shield_radius * 0.707
                        
                        # Next vertex
                        next_i = (i + 1) % num_sides
                        if next_i == 0:  # Right
                            x2 = shield_center_x + shield_radius
                            y2 = shield_center_y
                        elif next_i == 1:  # Top-right
                            x2 = shield_center_x + shield_radius * 0.707
                            y2 = shield_center_y + shield_radius * 0.707
                        elif next_i == 2:  # Top
                            x2 = shield_center_x
                            y2 = shield_center_y + shield_radius
                        elif next_i == 3:  # Top-left
                            x2 = shield_center_x - shield_radius * 0.707
                            y2 = shield_center_y + shield_radius * 0.707
                        elif next_i == 4:  # Left
                            x2 = shield_center_x - shield_radius
                            y2 = shield_center_y
                        elif next_i == 5:  # Bottom-left
                            x2 = shield_center_x - shield_radius * 0.707
                            y2 = shield_center_y - shield_radius * 0.707
                        elif next_i == 6:  # Bottom
                            x2 = shield_center_x
                            y2 = shield_center_y - shield_radius
                        else:  # Bottom-right
                            x2 = shield_center_x + shield_radius * 0.707
                            y2 = shield_center_y - shield_radius * 0.707
                        
                        # Draw line segment
                        kivy.graphics.Color(0.2, 0.5, 1, 0.5)
                        kivy.graphics.Rectangle(
                            pos=(self.px(min(x1, x2)), self.px(min(y1, y2))),
                            size=(abs(x2 - x1) + 2, abs(y2 - y1) + 2)
                        )
                    
                    # Add glow points at key positions
                    glow_positions = [
                        (shield_center_x + shield_radius, shield_center_y),  # Right
                        (shield_center_x, shield_center_y + shield_radius),  # Top
                        (shield_center_x - shield_radius, shield_center_y),  # Left
                        (shield_center_x, shield_center_y - shield_radius),  # Bottom
                        (shield_center_x + shield_radius * 0.707, shield_center_y + shield_radius * 0.707),  # Top-right
                        (shield_center_x - shield_radius * 0.707, shield_center_y + shield_radius * 0.707),  # Top-left
                        (shield_center_x - shield_radius * 0.707, shield_center_y - shield_radius * 0.707),  # Bottom-left
                        (shield_center_x + shield_radius * 0.707, shield_center_y - shield_radius * 0.707),  # Bottom-right
                    ]
                    
                    kivy.graphics.Color(0.4, 0.7, 1, 0.3)
                    for glow_x, glow_y in glow_positions:
                        kivy.graphics.Rectangle(
                            pos=(self.px(glow_x - 2), self.px(glow_y - 2)),
                            size=(4, 4)
                        )

                # Player ship - make it larger and ensure proper display
                if self.spaceship_textures and self.spaceship_textures[0]:
                    current_tex = self.spaceship_textures[0]
                    ship_size = 60  # Make spaceship twice as large
                    
                    # Ensure proper color and texture binding
                    kivy.graphics.Color(1, 1, 1, 1)  # Full white for proper texture display
                    kivy.graphics.Rectangle(
                        texture=current_tex,
                        pos=(self.px(self.player['x'] - ship_size // 2), self.px(self.player['y'] - ship_size // 2)),
                        size=(ship_size, ship_size)
                    )
                    
                    # Emissive glow when invulnerable
                    if self.player['invulnerable']:
                        if self.spaceship_emissive_textures and self.spaceship_emissive_textures[0]:
                            emissive_tex = self.spaceship_emissive_textures[0]
                            kivy.graphics.Color(1, 1, 1, 0.7)  # Brighter glow effect
                            kivy.graphics.Rectangle(
                                texture=emissive_tex,
                                pos=(self.px(self.player['x'] - ship_size // 2), self.px(self.player['y'] - ship_size // 2)),
                                size=(ship_size, ship_size)
                            )
                        kivy.graphics.Color(1, 1, 1, 1)  # Reset color
                else:
                    # Enhanced fallback pixel sprite if textures not loaded
                    ship_pattern = [
                        ".....ooo.....",
                        "....ooooo....",
                        "...ooooooo...",
                        "..ooooooooo..",
                        ".ooooooooooo.",
                        "ooooooooooooo",
                        ".oooooo.oooo.",
                        "..oooo.oooo..",
                        "...oo...oo...",
                    ]
                    ship_palette = {"o": (0.65, 0.9, 1.0, 1)}
                    self.draw_pixel_sprite(self.player['x'], self.player['y'], ship_pattern, ship_palette, scale=4)

                # Engine effect
                if 'up' in self.keys_pressed:
                    kivy.graphics.Color(1, 0.5, 0, 1)
                    kivy.graphics.Rectangle(
                        pos=(self.px(self.player['x'] - 8), self.px(self.player['y'] - 22)),
                        size=(16, 12)
                    )

            # HUD
            self.draw_text_left(f"❤️ {self.player['lives']}", 20, SCREEN_HEIGHT - 44, color=(1, 0.35, 0.35, 1),
                                font_size=22)
            self.draw_text_left(f"Level: {self.wave}", 20, SCREEN_HEIGHT - 74, color=WHITE, font_size=20)
            self.draw_text_left(f"Kills: {self.enemies_killed}", 20, SCREEN_HEIGHT - 104, color=(0.7, 1, 0.7, 1),
                                font_size=20)
            self.draw_text_left(f"Score: {self.score}", 20, SCREEN_HEIGHT - 134, color=WHITE, font_size=18)

            # Weapon level indicator
            weapon_text = "Weapon: " + "★" * self.player['weapon_level'] + "☆" * (4 - self.player['weapon_level'])
            self.draw_text_left(weapon_text, 20, SCREEN_HEIGHT - 164, color=CYAN, font_size=16)

            # Active power-ups
            powerup_y = SCREEN_HEIGHT - 194
            if self.rapid_fire:
                self.draw_text_left(f"⚡ Rapid Fire: {int(self.rapid_timer)}s", 20, powerup_y, color=YELLOW,
                                    font_size=14)
                powerup_y -= 22
            if self.shield_active:
                self.draw_text_left(f"🛡️ Shield: {int(self.shield_timer)}s", 20, powerup_y, color=BLUE, font_size=14)
                powerup_y -= 22
            if self.double_score:
                self.draw_text_left(f"2x Score: {int(self.double_score_timer)}s", 20, powerup_y, color=GREEN,
                                    font_size=14)

            # Movement mode indicator
            if not self.player['vertical_movement_enabled']:
                self.draw_text_left("Mode: Horizontal Only", SCREEN_WIDTH - 150, 20, color=YELLOW, font_size=14)

            # Stage messages
            if self.stage_phase == "arrival":
                self.draw_text(self.arrival_text, SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2, color=CYAN, font_size=40)
            elif self.stage_phase == "boss_warning":
                self.draw_text(self.boss_warning_text, SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2, color=ORANGE,
                               font_size=42)
            elif self.stage_phase == "clear_anim":
                self.draw_text(self.clear_message, SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2, color=GREEN, font_size=44)

    def draw_game_over(self):
        """Draw game over screen."""
        with self.game_canvas:
            self.draw_text("GAME OVER", SCREEN_WIDTH // 2, 520, color=RED, font_size=56)
            if self.current_user:
                self.draw_text(f"Player: {self.current_user}", SCREEN_WIDTH // 2, 470, color=CYAN, font_size=24)
            self.draw_text(f"Final Score: {self.score}", SCREEN_WIDTH // 2, 420, color=WHITE, font_size=30)
            self.draw_text(f"Level Reached: {self.wave}", SCREEN_WIDTH // 2, 370, color=WHITE, font_size=24)
            self.draw_text(f"Enemies Destroyed: {self.enemies_killed}", SCREEN_WIDTH // 2, 320, color=WHITE,
                           font_size=24)
            if self.new_high_score:
                self.draw_text("NEW HIGH SCORE!", SCREEN_WIDTH // 2, 270, color=GREEN, font_size=28)
            self.draw_text("Press R to Restart or Q for Main Menu", SCREEN_WIDTH // 2, 220, color=WHITE, font_size=22)

    def draw_victory(self):
        """Draw victory screen."""
        with self.game_canvas:
            self.draw_text("VICTORY!", SCREEN_WIDTH // 2, 540, color=GREEN, font_size=58)
            self.draw_text("You cleared all 10 stages", SCREEN_WIDTH // 2, 450, color=WHITE, font_size=28)
            if self.current_user:
                self.draw_text(f"Player: {self.current_user}", SCREEN_WIDTH // 2, 420, color=CYAN, font_size=22)
            self.draw_text(f"Final Score: {self.score}", SCREEN_WIDTH // 2, 390, color=WHITE, font_size=28)
            self.draw_text(f"Total Enemies Destroyed: {self.enemies_killed}", SCREEN_WIDTH // 2, 340, color=WHITE,
                           font_size=24)
            if self.new_high_score:
                self.draw_text("NEW HIGH SCORE!", SCREEN_WIDTH // 2, 290, color=GREEN, font_size=28)
            self.draw_text("Press R to Play Again or Q to Quit", SCREEN_WIDTH // 2, 230, color=WHITE, font_size=22)


class NewShootingGameApp(kivy.app.App):
    def build(self):
        return SpaceShooterGame()


if __name__ == "__main__":
    NewShootingGameApp().run()
