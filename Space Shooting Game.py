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
from datetime import datetime

# ------------------------------
#  CONFIGURATION
# ------------------------------
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

# ------------------------------
#  SIMPLE RANDOM (deterministic)
# ------------------------------
class SimpleRandom:
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

# ------------------------------
#  BACKGROUND STARFIELD
# ------------------------------
class StarField:
    def __init__(self):
        self.stars = []
        self.layers = [
            {'count': 80, 'speed': 0.5, 'size': 1},
            {'count': 50, 'speed': 1, 'size': 2},
            {'count': 20, 'speed': 2, 'size': 3}
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
                brightness = 0.5 + (SimpleRandom.random() * 0.5)
                kivy.graphics.Color(brightness, brightness, brightness, 1)
                px = int(star['x'] // PIXEL_SIZE) * PIXEL_SIZE
                py = int(star['y'] // PIXEL_SIZE) * PIXEL_SIZE
                size = star['size'] * PIXEL_SIZE
                kivy.graphics.Rectangle(pos=(px, py), size=(size, size))

# ------------------------------
#  PARTICLE EFFECT
# ------------------------------
class EnhancedParticle:
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

# ------------------------------
#  MAIN GAME CLASS
# ------------------------------
class SpaceShooterGame(kivy.uix.widget.Widget):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.size = (SCREEN_WIDTH, SCREEN_HEIGHT)
        kivy.core.window.Window.size = (SCREEN_WIDTH, SCREEN_HEIGHT)
        kivy.core.window.Window.resizable = True
        kivy.core.window.Window.bind(size=self._on_window_resize)
        self.game_canvas = self.canvas.before

        SimpleRandom.seed()

        # Game state
        self.game_state = "login"
        self.score = 0
        self.wave = 1
        self.enemies_killed = 0
        self.high_score = 0
        self.screen_shake = 0
        self.shake_offset = (0, 0)

        # Account / database (fallback to :memory: if file not writable)
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

        # Game objects
        self.enemies = []
        self.bullets = []
        self.enemy_bullets = []
        self.powerups = []
        self.particles = []
        self.starfield = StarField()

        # Power‑up timers
        self.shield_active = False
        self.shield_timer = 0
        self.rapid_fire = False
        self.rapid_timer = 0
        self.double_score = False
        self.double_score_timer = 0
        self.shot_timer = 0

        # Stage system
        self.max_stages = 10
        self.stage_phase = "enemies"
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
        self.bg_clouds = []
        for _ in range(30):
            self.bg_meteor_chunks.append({
                'x': SimpleRandom.randint(0, SCREEN_WIDTH),
                'y': SimpleRandom.randint(0, SCREEN_HEIGHT),
                'size': SimpleRandom.randint(8, 24),
                'speed': SimpleRandom.uniform(0.2, 0.8)
            })
        for _ in range(5):
            self.bg_clouds.append({
                'x': SimpleRandom.randint(0, SCREEN_WIDTH),
                'y': SimpleRandom.randint(0, SCREEN_HEIGHT),
                'width': SimpleRandom.randint(100, 200),
                'height': SimpleRandom.randint(40, 80),
                'speed': SimpleRandom.uniform(0.1, 0.3)
            })

        # Fullscreen nebula / stars
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
        nebula_colors = [(0.2, 0.35, 0.8, 0.08), (0.55, 0.2, 0.8, 0.07), (0.8, 0.3, 0.5, 0.06), (0.25, 0.6, 0.9, 0.06)]
        for _ in range(6):
            self.fullscreen_nebula.append({
                'x': SimpleRandom.random(),
                'y': SimpleRandom.random(),
                'size': SimpleRandom.uniform(0.25, 0.55),
                'color': SimpleRandom.choice(nebula_colors)
            })

        # Keyboard
        self.setup_keyboard()

        # Login / exit UI
        self.build_login_ui()
        self.build_exit_ui()

        # Start game loop
        kivy.clock.Clock.schedule_interval(self.update, 1.0 / FPS)

    # --------------------------
    #  WINDOW & UI HELPERS
    # --------------------------
    def _on_window_resize(self, _window, size):
        self.size = size
        if hasattr(self, "login_layout"):
            self.login_layout.size = size
        if hasattr(self, "exit_layout"):
            self.exit_layout.size = size

    def px(self, value):
        return int(value // PIXEL_SIZE) * PIXEL_SIZE

    def draw_text(self, text, center_x, center_y, color=WHITE, font_size=26):
        label = kivy.core.text.Label(text=text, font_size=font_size, color=color)
        label.refresh()
        tex = label.texture
        kivy.graphics.Color(*color)
        kivy.graphics.Rectangle(texture=tex,
                                pos=(center_x - tex.width / 2, center_y - tex.height / 2),
                                size=tex.size)

    def draw_text_left(self, text, x, y, color=WHITE, font_size=22):
        label = kivy.core.text.Label(text=text, font_size=font_size, color=color)
        label.refresh()
        tex = label.texture
        kivy.graphics.Color(*color)
        kivy.graphics.Rectangle(texture=tex, pos=(x, y), size=tex.size)

    def draw_pixel_sprite(self, center_x, center_y, pattern, palette, scale=PIXEL_SIZE):
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

    # --------------------------
    #  DATABASE (fallback to in‑memory)
    # --------------------------
    def init_db(self):
        try:
            with sqlite3.connect(self.db_path) as conn:
                cur = conn.cursor()
                cur.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE NOT NULL, password_hash TEXT, created_at TEXT NOT NULL)")
                cur.execute("PRAGMA table_info(users)")
                cols = [row[1] for row in cur.fetchall()]
                if "password_hash" not in cols:
                    cur.execute("ALTER TABLE users ADD COLUMN password_hash TEXT")
                cur.execute("CREATE TABLE IF NOT EXISTS game_records (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, score INTEGER NOT NULL, wave INTEGER NOT NULL, enemies_killed INTEGER NOT NULL, created_at TEXT NOT NULL, FOREIGN KEY(user_id) REFERENCES users(id))")
                conn.commit()
        except Exception:
            # Fallback to in‑memory database if file system is read‑only
            self.db_path = ":memory:"
            with sqlite3.connect(self.db_path) as conn:
                cur = conn.cursor()
                cur.execute("CREATE TABLE users (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE NOT NULL, password_hash TEXT, created_at TEXT NOT NULL)")
                cur.execute("CREATE TABLE game_records (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, score INTEGER NOT NULL, wave INTEGER NOT NULL, enemies_killed INTEGER NOT NULL, created_at TEXT NOT NULL)")

    def now_iso(self):
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def hash_password(self, password):
        return hashlib.sha256(password.encode("utf-8")).hexdigest()

    def authenticate_user(self, username, password):
        username = username.strip()
        password = password.strip()
        if not username or not password:
            return None, "Username and password required."
        if len(password) < 4:
            return None, "Password must be at least 4 characters."
        if len(username) > 24:
            return None, "Username too long (max 24)."
        try:
            with sqlite3.connect(self.db_path) as conn:
                cur = conn.cursor()
                cur.execute("SELECT id, password_hash FROM users WHERE username = ?", (username,))
                row = cur.fetchone()
                if not row:
                    return None, "Account not found. Please register."
                user_id, stored_hash = row
                if stored_hash and stored_hash != self.hash_password(password):
                    return None, "Incorrect password."
                if not stored_hash:
                    cur.execute("UPDATE users SET password_hash = ? WHERE id = ?", (self.hash_password(password), user_id))
                    conn.commit()
                return user_id, None
        except Exception as e:
            return None, f"DB error: {e}"

    def create_user(self, username, password):
        username = username.strip()
        password = password.strip()
        if not username or not password:
            return None, "Username and password required."
        if len(password) < 4:
            return None, "Password must be at least 4 characters."
        if len(username) > 24:
            return None, "Username too long (max 24)."
        try:
            with sqlite3.connect(self.db_path) as conn:
                cur = conn.cursor()
                cur.execute("SELECT id FROM users WHERE username = ?", (username,))
                if cur.fetchone():
                    return None, "Username already exists."
                cur.execute("INSERT INTO users (username, password_hash, created_at) VALUES (?, ?, ?)",
                            (username, self.hash_password(password), self.now_iso()))
                conn.commit()
                return cur.lastrowid, None
        except Exception as e:
            return None, f"DB error: {e}"

    def load_user_stats(self):
        if not self.current_user_id:
            return
        try:
            with sqlite3.connect(self.db_path) as conn:
                cur = conn.cursor()
                cur.execute("SELECT MAX(score) FROM game_records WHERE user_id = ?", (self.current_user_id,))
                row = cur.fetchone()
                self.high_score = row[0] if row and row[0] is not None else 0
                cur.execute("SELECT score, wave, enemies_killed, created_at FROM game_records WHERE user_id = ? ORDER BY id DESC LIMIT 1", (self.current_user_id,))
                last = cur.fetchone()
                if last:
                    self.user_last_score, self.user_last_wave, self.user_last_kills, self.user_last_played = last
                cur.execute("SELECT COUNT(*) FROM game_records WHERE user_id = ?", (self.current_user_id,))
                self.user_games_played = cur.fetchone()[0]
        except Exception:
            pass

    def save_game_record(self):
        if not self.current_user_id:
            return
        try:
            with sqlite3.connect(self.db_path) as conn:
                cur = conn.cursor()
                cur.execute("INSERT INTO game_records (user_id, score, wave, enemies_killed, created_at) VALUES (?, ?, ?, ?, ?)",
                            (self.current_user_id, self.score, self.wave, self.enemies_killed, self.now_iso()))
                conn.commit()
        except Exception:
            pass

    def finalize_game_result(self):
        if self.game_session_saved or not self.current_user_id:
            return
        if self.score <= 0 and self.enemies_killed <= 0:
            return
        self.new_high_score = self.score > self.high_score
        self.save_game_record()
        self.load_user_stats()
        self.game_session_saved = True

    # --------------------------
    #  LOGIN UI
    # --------------------------
    def build_login_ui(self):
        self.login_layout = kivy.uix.floatlayout.FloatLayout(size_hint=(1, 1))
        with self.login_layout.canvas.before:
            kivy.graphics.Color(0.02, 0.05, 0.08, 0.25)
            self.login_bg_rect = kivy.graphics.Rectangle(pos=(0, 0), size=self.size)

        self.login_card = kivy.uix.boxlayout.BoxLayout(orientation="vertical", size_hint=(0.6, 0.65),
                                                       pos_hint={"center_x": 0.5, "center_y": 0.52},
                                                       padding=26, spacing=16)
        with self.login_card.canvas.before:
            kivy.graphics.Color(0.06, 0.12, 0.18, 0.38)
            self.login_card_rect = kivy.graphics.RoundedRectangle(pos=self.login_card.pos, size=self.login_card.size, radius=14)
            kivy.graphics.Color(0.2, 1, 1, 0.28)
            self.login_card_border = kivy.graphics.Line(rounded_rectangle=(self.login_card.pos[0], self.login_card.pos[1], self.login_card.size[0], self.login_card.size[1], 14), width=1.2)

        self.login_title = kivy.uix.label.Label(text="Welcome Back", font_size=28, size_hint=(1, None), height=36, color=WHITE)
        self.login_subtitle = kivy.uix.label.Label(text="Enter your credentials.", font_size=14, size_hint=(1, None), height=20, color=WHITE)
        self.account_label = kivy.uix.label.Label(text="Existing Accounts", font_size=14, size_hint=(1, None), height=20, color=WHITE)
        self.account_spinner = kivy.uix.spinner.Spinner(text="Select account", values=[], size_hint=(1, None), height=40,
                                                        background_normal="", background_color=(0.08, 0.16, 0.22, 0.4), color=WHITE)
        self.account_spinner.bind(text=self._on_account_selected)
        self.username_input = kivy.uix.textinput.TextInput(hint_text="New username (for register)", multiline=False, size_hint=(1, None), height=40,
                                                           background_normal="", background_active="", background_color=(0.08, 0.16, 0.22, 0.35),
                                                           foreground_color=WHITE, cursor_color=WHITE, hint_text_color=(0.7, 0.85, 1, 0.7))
        self.password_input = kivy.uix.textinput.TextInput(hint_text="Enter your password", multiline=False, password=True, size_hint=(1, None), height=40,
                                                           background_normal="", background_active="", background_color=(0.08, 0.16, 0.22, 0.35),
                                                           foreground_color=WHITE, cursor_color=WHITE, hint_text_color=(0.7, 0.85, 1, 0.7))
        self.login_button = kivy.uix.button.Button(text="Login", size_hint=(1, None), height=42, background_normal="", background_color=(0.12, 0.24, 0.32, 0.7), color=WHITE)
        self.login_button.bind(on_press=self.handle_login_existing)
        self.register_button = kivy.uix.button.Button(text="Register", size_hint=(1, None), height=42, background_normal="", background_color=(0.1, 0.2, 0.28, 0.62), color=WHITE)
        self.register_button.bind(on_press=self.handle_register)
        self.login_message = kivy.uix.label.Label(text="", font_size=16, size_hint=(1, None), height=24, color=WHITE)

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
        is_login = (self.game_state == "login")
        self.login_layout.opacity = 1 if is_login else 0
        self.login_layout.disabled = not is_login
        self.login_layout.size = self.size
        self.login_layout.pos = (0, 0)
        if is_login:
            self.refresh_account_list()
            if not getattr(self, "_keyboard", None):
                self.setup_keyboard()
        else:
            if getattr(self, "_keyboard", None):
                self._keyboard.unbind(on_key_down=self._on_key_down)
                self._keyboard.unbind(on_key_up=self._on_key_up)
                self._keyboard.release()
                self._keyboard = None

    def _update_login_canvas(self, *_args):
        if hasattr(self, "login_bg_rect"):
            self.login_bg_rect.pos = (0, 0)
            self.login_bg_rect.size = self.size

    def _update_login_card(self, *_args):
        if hasattr(self, "login_card_rect"):
            self.login_card_rect.pos = self.login_card.pos
            self.login_card_rect.size = self.login_card.size
        if hasattr(self, "login_card_border"):
            self.login_card_border.rounded_rectangle = (self.login_card.pos[0], self.login_card.pos[1], self.login_card.size[0], self.login_card.size[1], 14)

    def refresh_account_list(self):
        if not hasattr(self, "account_spinner"):
            return
        try:
            with sqlite3.connect(self.db_path) as conn:
                cur = conn.cursor()
                cur.execute("SELECT username FROM users ORDER BY username COLLATE NOCASE")
                usernames = [row[0] for row in cur.fetchall()]
        except Exception:
            usernames = []
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
        if selection not in ("Select account", "No accounts yet"):
            self.username_input.text = selection

    def handle_login_existing(self, *_args):
        username = self.username_input.text
        password = self.password_input.text
        selected = self.account_spinner.text
        if selected not in ("Select account", "No accounts yet"):
            username = selected
        user_id, error = self.authenticate_user(username, password)
        if error:
            self.login_message.color = RED
            self.login_message.text = error
            return
        self.current_user = username.strip()
        self.current_user_id = user_id
        self.load_user_stats()
        self.game_state = "menu"
        self.game_session_saved = False
        self.new_high_score = False
        self.login_message.color = GREEN
        self.login_message.text = f"Welcome, {self.current_user}!"
        self.username_input.text = ""
        self.password_input.text = ""
        self.account_spinner.text = "Select account"
        self.update_login_visibility()

    def handle_register(self, *_args):
        username = self.username_input.text
        password = self.password_input.text
        user_id, error = self.create_user(username, password)
        if error:
            self.login_message.color = RED
            self.login_message.text = error
            return
        self.current_user = username.strip()
        self.current_user_id = user_id
        self.load_user_stats()
        self.game_state = "menu"
        self.game_session_saved = False
        self.new_high_score = False
        self.login_message.color = GREEN
        self.login_message.text = f"Welcome, {self.current_user}!"
        self.username_input.text = ""
        self.password_input.text = ""
        self.account_spinner.text = "Select account"
        self.refresh_account_list()
        self.update_login_visibility()

    # --------------------------
    #  EXIT BUTTON
    # --------------------------
    def build_exit_ui(self):
        self.exit_layout = kivy.uix.floatlayout.FloatLayout(size_hint=(1, 1))
        self.exit_button = kivy.uix.button.Button(text="Exit Game", size_hint=(0.2, None), height=40, pos_hint={"right": 0.98, "y": 0.02})
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

    # --------------------------
    #  KEYBOARD
    # --------------------------
    def setup_keyboard(self):
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
        self.setup_stage(self.wave)

    def get_pause_menu_layout(self):
        button_w, button_h = 280, 38
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
                'x': center_x - button_w / 2,
                'y': center_y - button_h / 2,
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
                if item['x'] <= gx <= item['x'] + item['w'] and item['y'] <= gy <= item['y'] + item['h']:
                    self.pause_menu_index = idx
                    self.activate_pause_menu()
                    return True
        return super().on_touch_down(touch)

    # --------------------------
    #  GAME FLOW
    # --------------------------
    def start_game(self):
        if not self.current_user_id:
            self.game_state = "login"
            self.update_login_visibility()
            return
        self.game_session_saved = False
        self.new_high_score = False
        self.game_state = "playing"
        self.ultra_boss_active = False
        self.pending_ultra_spawn = False
        self.setup_stage(1)

    def reset_game(self):
        self.finalize_game_result()
        self.game_state = "menu"
        self.new_high_score = False
        self.score = 0
        self.wave = 1
        self.enemies_killed = 0
        self.player = {
            'x': SCREEN_WIDTH // 2, 'y': 100, 'width': 30, 'height': 30,
            'lives': 3, 'max_lives': 5, 'invulnerable': False, 'invulnerable_timer': 0,
            'speed': 6, 'weapon_level': 1, 'vertical_movement_enabled': True
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
        self.boss_warning_timer = 0
        self.player_departing = False
        self.ultra_boss_active = False
        self.pending_ultra_spawn = False
        self.update_login_visibility()
        self.update_exit_visibility()

    def get_stage_profile(self, stage):
        profiles = {
            1: {'theme': 'space', 'enemy_mode': 'alien', 'boss_kind': 'octopus', 'arrival': "Deep Space Sector", 'difficulty': 1},
            2: {'theme': 'kong', 'enemy_mode': 'meteor', 'boss_kind': 'grozilla', 'arrival': "Kong Universe", 'difficulty': 1.2},
            3: {'theme': 'saturn', 'enemy_mode': 'hybrid', 'boss_kind': 'growly', 'arrival': "Saturn Rings", 'difficulty': 1.4},
            4: {'theme': 'nebula', 'enemy_mode': 'nebula', 'boss_kind': 'manta', 'arrival': "Nebula Rift", 'difficulty': 1.6},
            5: {'theme': 'ember', 'enemy_mode': 'ember', 'boss_kind': 'scorpion', 'arrival': "Ember Forge", 'difficulty': 1.8},
            6: {'theme': 'frost', 'enemy_mode': 'frost', 'boss_kind': 'wyvern', 'arrival': "Frozen Expanse", 'difficulty': 2.0},
            7: {'theme': 'toxic', 'enemy_mode': 'toxic', 'boss_kind': 'serpent', 'arrival': "Toxic Wasteland", 'difficulty': 2.2},
            8: {'theme': 'quantum', 'enemy_mode': 'quantum', 'boss_kind': 'warden', 'arrival': "Quantum Citadel", 'difficulty': 2.4},
            9: {'theme': 'void', 'enemy_mode': 'void', 'boss_kind': 'behemoth', 'arrival': "Void Abyss", 'difficulty': 2.6},
            10: {'theme': 'eclipse', 'enemy_mode': 'eclipse', 'boss_kind': 'overseer', 'arrival': "Eclipse Throne", 'difficulty': 3.0},
        }
        return profiles.get(stage, profiles[10]).copy()

    def setup_stage(self, stage):
        self.wave = stage
        self.current_profile = self.get_stage_profile(stage)
        self.stage_enemy_target = min(12 + (stage * 3), 45)
        self.stage_phase = "enemies"
        self.stage_enemy_kills = 0
        self.spawn_timer = 0
        self.clear_banner_timer = 0
        self.arrival_timer = 0
        self.arrival_text = ""
        self.boss_warning_timer = 0
        self.boss_warning_text = ""
        self.player_departing = False
        self.enemies.clear()
        self.enemy_bullets.clear()
        self.powerups.clear()
        self.shot_timer = 0
        self.player['x'] = SCREEN_WIDTH // 2
        self.player['y'] = 100
        self.player['invulnerable'] = True
        self.player['invulnerable_timer'] = 40
        if stage > 1:
            self.stage_phase = "arrival"
            self.arrival_timer = 2.8
            self.arrival_text = f"Arrived at {self.current_profile.get('arrival', f'Stage {stage}')}"
            self.player['y'] = -80

    # --------------------------
    #  ENEMY SPAWN
    # --------------------------
    def spawn_stage_enemy(self):
        if self.game_state != "playing" or self.stage_phase != "enemies":
            return
        mode = self.current_profile.get('enemy_mode', 'alien')
        difficulty = self.current_profile.get('difficulty', 1.0)
        variant = SimpleRandom.choice(['basic', 'fast', 'tank', 'swoop', 'chase'])
        enemy = {
            'x': SimpleRandom.randint(40, SCREEN_WIDTH - 40),
            'y': SCREEN_HEIGHT + SimpleRandom.randint(10, 60),
            'width': 30, 'height': 30, 'type': 'enemy', 'variant': variant,
            'sprite_mode': mode, 'health': 1, 'speed': 2 + (difficulty * 1.2),
            'points': 10 + (self.wave * 3), 'shoot_chance': 0.006 * difficulty,
            'angle': 0, 'amplitude': 0, 'drift': SimpleRandom.uniform(-0.8, 0.8),
            'color': RED
        }
        if variant == 'fast':
            enemy['width'] = 20; enemy['height'] = 20
            enemy['speed'] += 2.5; enemy['points'] += 8
        elif variant == 'tank':
            enemy['width'] = 40; enemy['height'] = 40
            enemy['health'] = 3 + (self.wave // 3); enemy['speed'] = max(1.0, enemy['speed'] - 1.6)
            enemy['points'] += 16; enemy['shoot_chance'] = 0.012
        elif variant == 'swoop':
            enemy['width'] = 28; enemy['height'] = 28; enemy['health'] = 2
            enemy['speed'] = 2.8; enemy['points'] += 12
            enemy['amplitude'] = SimpleRandom.uniform(40, 80)
            enemy['frequency'] = SimpleRandom.uniform(0.02, 0.05)
        elif variant == 'chase':
            enemy['width'] = 28; enemy['height'] = 28; enemy['health'] = 2
            enemy['speed'] = 1.8; enemy['points'] += 15
            enemy['chase_speed'] = 1.2

        if mode == 'meteor':
            enemy['speed'] += 1.5; enemy['drift'] = SimpleRandom.uniform(-1.5, 1.5); enemy['shoot_chance'] = 0.0
        elif mode == 'hybrid':
            enemy['drift'] = SimpleRandom.uniform(-1.2, 1.2)
        elif mode in ('nebula', 'quantum'):
            enemy['drift'] = SimpleRandom.uniform(-1.8, 1.8); enemy['speed'] += 0.8
        elif mode in ('ember', 'toxic', 'void'):
            enemy['drift'] = SimpleRandom.uniform(-1.2, 1.2); enemy['speed'] += 1.2
        elif mode in ('frost', 'eclipse'):
            enemy['drift'] = SimpleRandom.uniform(-0.8, 0.8)

        # set colors for theme
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

    def start_boss_warning(self, boss_kind=None, next_phase="boss"):
        if boss_kind is None:
            boss_kind = self.current_profile.get('boss_kind', 'boss')
        boss_name = boss_kind.replace('_', ' ').title()
        self.boss_warning_text = f"{boss_name} Incoming!"
        self.boss_warning_timer = 3.0
        self.boss_warning_next = next_phase
        self.stage_phase = "boss_warning"

    def spawn_stage_boss(self):
        boss_kind = self.current_profile.get('boss_kind', 'octopus')
        difficulty = self.current_profile.get('difficulty', 1.0)
        boss = {
            'x': SCREEN_WIDTH // 2, 'y': SCREEN_HEIGHT - 120, 'type': 'boss', 'boss_kind': boss_kind,
            'width': 84, 'height': 96, 'health': 80 + int(self.wave * 18 * difficulty),
            'max_health': 80 + int(self.wave * 18 * difficulty), 'speed': 2.4 + (difficulty * 0.5),
            'points': 700 + (self.wave * 50), 'attack_timer': 0, 'attack_mode': 0, 'phase': 1,
            'phase_health': 0, 'spawn_immunity': 1.5, 'color': RED
        }
        boss['phase_health'] = boss['health'] / 3
        self.enemies.append(boss)
        self.stage_phase = "boss"
        # spawn minions
        for idx in range(4 + (self.wave // 3)):
            self.enemies.append({
                'x': boss['x'] - 120 + (idx * 80), 'y': boss['y'] - 40 - (idx % 2) * 20,
                'width': 22, 'height': 22, 'type': 'minion', 'variant': 'escort',
                'health': 1 + (self.wave // 4), 'speed': 2.2 + (difficulty * 0.5),
                'points': 20 + (self.wave * 2), 'color': ORANGE if boss_kind == 'grozilla' else (GREEN if boss_kind == 'growly' else PURPLE)
            })

    def start_ultra_boss_encounter(self):
        self.ultra_boss_active = True
        self.pending_ultra_spawn = True
        self.stage_phase = "arrival"
        self.arrival_timer = 3.2
        self.arrival_text = "Entering Tyrant Dominion"
        self.player['y'] = -100
        self.player['invulnerable'] = True
        self.player['invulnerable_timer'] = 120
        self.enemies.clear()
        self.enemy_bullets.clear()

    def spawn_ultra_boss_trio(self):
        self.pending_ultra_spawn = False
        self.stage_phase = "ultra_boss"
        tyrant = {'x': SCREEN_WIDTH//2, 'y': SCREEN_HEIGHT-140, 'type':'boss', 'boss_kind':'tyrant',
                  'width':110, 'height':108, 'health':420, 'max_health':420, 'speed':3.4,
                  'points':5000, 'attack_timer':0, 'attack_mode':0, 'phase':1, 'phase_health':140,
                  'spawn_immunity':2.0, 'color':RED}
        self.enemies.append(tyrant)
        for idx, kind in enumerate(['octopus', 'overseer']):
            w, h = 84, 96
            self.enemies.append({
                'x': SCREEN_WIDTH//2 + (-180 if idx==0 else 180), 'y': SCREEN_HEIGHT-180,
                'type':'boss', 'boss_kind':kind, 'width':w, 'height':h, 'health':180,
                'max_health':180, 'speed':2.6 if idx==0 else -2.6, 'points':1200,
                'attack_timer':0, 'attack_mode':0, 'phase':1, 'phase_health':60,
                'spawn_immunity':1.5, 'color':PURPLE
            })

    def trigger_stage_clear(self, message="LEVEL Cleared"):
        for _ in range(20):
            self.particles.append(EnhancedParticle(SCREEN_WIDTH//2, SCREEN_HEIGHT//2, YELLOW, size=5, speed_range=(5,12), life=1.5))
        self.screen_shake = 15
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
        if self.player['weapon_level'] < 4:
            self.player['weapon_level'] = min(4, self.player['weapon_level'] + 1)

    # --------------------------
    #  SHOOTING
    # --------------------------
    def shoot(self):
        wl = self.player['weapon_level']
        if wl == 1:
            self.bullets.append({'x': self.player['x'], 'y': self.player['y']+20, 'width':4, 'height':12, 'speed':12, 'color':YELLOW, 'damage':1})
        elif wl == 2:
            for offset in (-8,8):
                self.bullets.append({'x': self.player['x']+offset, 'y': self.player['y']+20, 'width':4, 'height':12, 'speed':12, 'color':CYAN, 'damage':1})
        elif wl == 3:
            for offset, sx in [(-10,-1),(0,0),(10,1)]:
                self.bullets.append({'x': self.player['x']+offset, 'y': self.player['y']+20, 'width':4, 'height':12, 'speed':12, 'speed_x':sx, 'color':GREEN if sx==0 else ORANGE, 'damage':2 if sx==0 else 1})
        else:  # lv4
            for ao in [-0.3,-0.15,0,0.15,0.3]:
                sx = ao*4
                self.bullets.append({'x': self.player['x']+(ao*20), 'y': self.player['y']+20, 'width':4, 'height':12, 'speed':12, 'speed_x':sx, 'color':YELLOW if ao==0 else ORANGE, 'damage':2 if ao==0 else 1})

    def create_explosion(self, x, y, color=ORANGE, explosion_type='normal'):
        count = 15 if explosion_type == 'normal' else 25
        for _ in range(count):
            self.particles.append(EnhancedParticle(x, y, color, size=3, speed_range=(3,10), gravity=-0.1, life=0.8, fade=True))
        if explosion_type == 'big':
            self.screen_shake = 5

    # --------------------------
    #  MAIN UPDATE
    # --------------------------
    def update(self, dt):
        # screen shake
        if self.screen_shake > 0:
            self.screen_shake -= 1
            self.shake_offset = (SimpleRandom.randint(-3,3), SimpleRandom.randint(-3,3))
        else:
            self.shake_offset = (0,0)

        if self.game_state == "playing":
            # stage transitions
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
                        self.finalize_game_result()
                    elif self.wave >= self.max_stages:
                        self.start_ultra_boss_encounter()
                    else:
                        self.setup_stage(self.wave + 1)
            else:
                if self.stage_phase == "boss_warning":
                    self.boss_warning_timer = max(0, self.boss_warning_timer - dt)
                    if self.boss_warning_timer <= 0:
                        if self.boss_warning_next == "ultra_boss":
                            self.spawn_ultra_boss_trio()
                        else:
                            self.spawn_stage_boss()

                # player movement
                ms = self.player['speed']
                if 'left' in self.keys_pressed:
                    self.player['x'] = max(25, self.player['x'] - ms)
                if 'right' in self.keys_pressed:
                    self.player['x'] = min(SCREEN_WIDTH - 25, self.player['x'] + ms)
                if self.player['vertical_movement_enabled']:
                    if 'up' in self.keys_pressed:
                        self.player['y'] = min(SCREEN_HEIGHT - 50, self.player['y'] + ms)
                    if 'down' in self.keys_pressed:
                        self.player['y'] = max(50, self.player['y'] - ms)

                # shooting
                if self.shot_timer > 0:
                    self.shot_timer -= dt
                delay = 0.08 if self.rapid_fire else max(0.12, 0.28 - self.player['weapon_level']*0.025)
                if self.shot_timer <= 0 and ('spacebar' in self.keys_pressed or 'z' in self.keys_pressed):
                    self.shoot()
                    self.shot_timer = delay

                # invincibility
                if self.player['invulnerable']:
                    self.player['invulnerable_timer'] -= 1
                    if self.player['invulnerable_timer'] <= 0:
                        self.player['invulnerable'] = False

                # power‑up timers
                if self.shield_active:
                    self.shield_timer -= dt
                    if self.shield_timer <= 0: self.shield_active = False
                if self.rapid_fire:
                    self.rapid_timer -= dt
                    if self.rapid_timer <= 0: self.rapid_fire = False
                if self.double_score:
                    self.double_score_timer -= dt
                    if self.double_score_timer <= 0: self.double_score = False

                # enemy spawn
                if self.stage_phase == "enemies":
                    regular = [e for e in self.enemies if e['type'] == 'enemy']
                    max_on = min(8 + self.wave, 18)
                    if self.stage_enemy_kills < self.stage_enemy_target:
                        self.spawn_timer -= dt
                        if len(regular) < max_on and self.spawn_timer <= 0:
                            self.spawn_stage_enemy()
                            self.spawn_timer = max(0.2, 0.6 - self.wave * 0.02)
                    elif not regular:
                        self.start_boss_warning()

                # enemies update
                for enemy in self.enemies[:]:
                    if enemy['type'] == 'boss':
                        enemy['x'] += enemy['speed']
                        if enemy['x'] <= 70 or enemy['x'] >= SCREEN_WIDTH - 70:
                            enemy['speed'] = -enemy['speed']
                            enemy['x'] = max(70, min(SCREEN_WIDTH-70, enemy['x']))
                        if enemy.get('spawn_immunity',0) > 0:
                            enemy['spawn_immunity'] -= dt
                        # phase change
                        hp_pct = enemy['health'] / enemy['max_health']
                        if hp_pct < 0.66 and enemy['phase'] == 1:
                            enemy['phase'] = 2
                            self.create_explosion(enemy['x'], enemy['y'], YELLOW, 'big')
                        elif hp_pct < 0.33 and enemy['phase'] == 2:
                            enemy['phase'] = 3
                            self.create_explosion(enemy['x'], enemy['y'], RED, 'big')
                        # boss attack
                        enemy['attack_timer'] += dt
                        if enemy['attack_timer'] >= max(0.5, 1.0 - self.wave*0.02):
                            enemy['attack_timer'] = 0
                            for _ in range(3 + enemy['phase']):
                                vx = SimpleRandom.uniform(-4,4)
                                self.enemy_bullets.append({'x':enemy['x'], 'y':enemy['y']-20, 'width':6, 'height':12, 'speed':-6, 'speed_x':vx, 'color':RED, 'damage':1, 'kind':'normal'})
                    elif enemy['type'] == 'minion':
                        dx = self.player['x'] - enemy['x']
                        dy = self.player['y'] - enemy['y']
                        dist = abs(dx)+abs(dy)
                        if dist>0:
                            move = min(enemy['speed'], max(-enemy['speed'], (dx/dist)*enemy['speed']))
                            enemy['x'] += move
                            movey = min(enemy['speed'], max(-enemy['speed'], (dy/dist)*enemy['speed']))
                            enemy['y'] += movey
                        if SimpleRandom.random() < 0.015:
                            self.enemy_bullets.append({'x':enemy['x'], 'y':enemy['y']-8, 'width':5, 'height':10, 'speed':-5, 'speed_x':0, 'color':ORANGE, 'damage':1})
                    else:  # regular enemy
                        enemy['x'] += enemy.get('drift',0)
                        if enemy.get('variant') == 'swoop':
                            enemy['angle'] += enemy.get('frequency',0.03)
                            enemy['x'] += SimpleRandom.uniform(-1,1) * enemy.get('amplitude',50) * 0.02
                        if enemy.get('variant') == 'chase':
                            dx = self.player['x'] - enemy['x']
                            if abs(dx) > 20:
                                enemy['x'] += min(enemy.get('chase_speed',1), max(-enemy.get('chase_speed',1), dx*0.05))
                        enemy['y'] -= enemy['speed']
                        if SimpleRandom.random() < enemy.get('shoot_chance',0):
                            self.enemy_bullets.append({'x':enemy['x'], 'y':enemy['y']-10, 'width':4, 'height':8, 'speed':-5, 'speed_x':0, 'color':RED, 'damage':1})
                        if enemy['y'] < -80 or enemy['x'] < -80 or enemy['x'] > SCREEN_WIDTH+80:
                            self.enemies.remove(enemy)

                # bullets
                for b in self.bullets[:]:
                    b['y'] += b['speed']
                    b['x'] += b.get('speed_x',0)
                    if b['y'] > SCREEN_HEIGHT+40 or b['x'] < -40 or b['x'] > SCREEN_WIDTH+40:
                        self.bullets.remove(b)
                for b in self.enemy_bullets[:]:
                    b['y'] += b['speed']
                    b['x'] += b.get('speed_x',0)
                    if b['y'] < -60 or b['y'] > SCREEN_HEIGHT+60 or b['x'] < -80 or b['x'] > SCREEN_WIDTH+80:
                        self.enemy_bullets.remove(b)

                # power‑ups
                for p in self.powerups[:]:
                    p['y'] -= p.get('fall_speed',1.0)
                    p['x'] += p.get('drift',0)
                    if p['y'] < -30:
                        self.powerups.remove(p)

                # collisions: bullets vs enemies
                for bullet in self.bullets[:]:
                    for enemy in self.enemies[:]:
                        if (bullet['x'] > enemy['x'] - enemy['width']//2 and bullet['x'] < enemy['x'] + enemy['width']//2 and
                            bullet['y'] > enemy['y'] - enemy['height']//2 and bullet['y'] < enemy['y'] + enemy['height']//2):
                            if bullet in self.bullets:
                                self.bullets.remove(bullet)
                            if enemy.get('spawn_immunity',0) > 0:
                                break
                            enemy['health'] -= bullet['damage']
                            self.particles.append(EnhancedParticle(bullet['x'], bullet['y'], YELLOW, size=2, speed_range=(1,4), life=0.3))
                            if enemy['health'] <= 0:
                                pts = enemy['points']
                                if self.double_score:
                                    pts *= 2
                                self.score += pts
                                self.enemies_killed += 1
                                self.create_explosion(enemy['x'], enemy['y'], enemy.get('color',ORANGE))
                                if enemy in self.enemies:
                                    self.enemies.remove(enemy)
                                if enemy['type'] == 'enemy':
                                    self.stage_enemy_kills += 1
                                    if SimpleRandom.random() < POWERUP_DROP_CHANCE:
                                        types = ['health','weapon','shield','rapid']
                                        if self.wave >= 5:
                                            types.append('double_score')
                                        self.powerups.append({'x':enemy['x'], 'y':enemy['y'], 'type':SimpleRandom.choice(types), 'width':20, 'height':20, 'fall_speed':0.8+SimpleRandom.random()*0.7, 'drift':SimpleRandom.random()*0.5-0.25})
                                elif enemy['type'] == 'boss':
                                    if self.stage_phase == "ultra_boss":
                                        if not [e for e in self.enemies if e.get('type')=='boss']:
                                            self.trigger_stage_clear("The Tyrant Has Fallen")
                                    else:
                                        self.trigger_stage_clear()
                            break

                # player hits
                if not self.player['invulnerable'] and not self.shield_active:
                    # enemy bullets
                    for b in self.enemy_bullets[:]:
                        if (b['x'] > self.player['x']-30 and b['x'] < self.player['x']+30 and
                            b['y'] > self.player['y']-30 and b['y'] < self.player['y']+30):
                            self.enemy_bullets.remove(b)
                            self.player['lives'] -= 1
                            self.player['invulnerable'] = True
                            self.player['invulnerable_timer'] = 120
                            self.create_explosion(self.player['x'], self.player['y'], RED, 'big')
                            if self.player['lives'] <= 0:
                                self.game_state = "game_over"
                                self.finalize_game_result()
                            break
                    # enemy collision
                    for enemy in self.enemies[:]:
                        if (self.player['x']-30 < enemy['x']+enemy['width']//2 and self.player['x']+30 > enemy['x']-enemy['width']//2 and
                            self.player['y']-30 < enemy['y']+enemy['height']//2 and self.player['y']+30 > enemy['y']-enemy['height']//2):
                            if enemy['type'] != 'boss' and enemy in self.enemies:
                                self.enemies.remove(enemy)
                            self.player['lives'] -= 1
                            self.player['invulnerable'] = True
                            self.player['invulnerable_timer'] = 120
                            self.create_explosion(self.player['x'], self.player['y'], RED, 'big')
                            if self.player['lives'] <= 0:
                                self.game_state = "game_over"
                                self.finalize_game_result()
                            break

                # power‑up collection
                for p in self.powerups[:]:
                    if (self.player['x']-30 < p['x']+10 and self.player['x']+30 > p['x']-10 and
                        self.player['y']-30 < p['y']+10 and self.player['y']+30 > p['y']-10):
                        self.powerups.remove(p)
                        if p['type'] == 'health':
                            self.player['lives'] = min(self.player['max_lives'], self.player['lives']+1)
                        elif p['type'] == 'weapon':
                            self.player['weapon_level'] = min(4, self.player['weapon_level']+1)
                        elif p['type'] == 'shield':
                            self.shield_active = True; self.shield_timer = 6
                        elif p['type'] == 'rapid':
                            self.rapid_fire = True; self.rapid_timer = 8
                        elif p['type'] == 'double_score':
                            self.double_score = True; self.double_score_timer = 10

        # background updates
        self.starfield.update()
        self.particles = [p for p in self.particles if p.update()]
        for cloud in self.bg_clouds:
            cloud['x'] -= cloud['speed']
            if cloud['x'] < -cloud['width']:
                cloud['x'] = SCREEN_WIDTH
                cloud['y'] = SimpleRandom.randint(0, SCREEN_HEIGHT)
        for chunk in self.bg_meteor_chunks:
            chunk['x'] -= chunk['speed']
            if chunk['x'] < -50:
                chunk['x'] = SCREEN_WIDTH+50
                chunk['y'] = SimpleRandom.randint(0, SCREEN_HEIGHT)

        self.update_login_visibility()
        self.update_exit_visibility()
        self.game_canvas.clear()
        self.draw()

    # --------------------------
    #  DRAWING
    # --------------------------
    def draw_fullscreen_backdrop(self):
        w, h = self.size
        if w<=0 or h<=0: return
        steps = 6
        band_h = h/steps
        for i in range(steps):
            t = i/(steps-1)
            kivy.graphics.Color(0.02+0.04*t, 0.02+0.03*t, 0.05+0.08*t, 1)
            kivy.graphics.Rectangle(pos=(0, band_h*i), size=(w, band_h+1))
        for blob in self.fullscreen_nebula:
            size = blob['size']*min(w,h)
            x = blob['x']*w
            y = blob['y']*h
            kivy.graphics.Color(*blob['color'])
            kivy.graphics.Rectangle(pos=(x-size/2, y-size/2), size=(size,size))
        for star in self.fullscreen_stars:
            bright = 0.4+0.6*(0.5+0.5*math.sin(star['twinkle']))
            kivy.graphics.Color(bright,bright,bright,1)
            kivy.graphics.Rectangle(pos=(star['x']*w, star['y']*h), size=(star['size'],star['size']))

    def draw_stage_background(self):
        theme = self.current_profile.get('theme','space')
        if theme == 'space':
            self.starfield.draw(self.game_canvas)
        elif theme == 'kong':
            kivy.graphics.Color(0.09,0.05,0.03,1)
            kivy.graphics.Rectangle(pos=(0,0), size=(SCREEN_WIDTH,SCREEN_HEIGHT))
            for chunk in self.bg_meteor_chunks:
                kivy.graphics.Color(0.25,0.18,0.14,1)
                kivy.graphics.Rectangle(pos=(self.px(chunk['x']), self.px(chunk['y'])), size=(chunk['size'],chunk['size']))
        elif theme == 'saturn':
            kivy.graphics.Color(0.04,0.02,0.08,1)
            kivy.graphics.Rectangle(pos=(0,0), size=(SCREEN_WIDTH,SCREEN_HEIGHT))
            for cloud in self.bg_clouds:
                kivy.graphics.Color(0.2,0.15,0.3,0.3)
                kivy.graphics.Rectangle(pos=(self.px(cloud['x']), self.px(cloud['y'])), size=(cloud['width'],cloud['height']))
        else:
            kivy.graphics.Color(0,0,0.1,1)
            kivy.graphics.Rectangle(pos=(0,0), size=(SCREEN_WIDTH,SCREEN_HEIGHT))
            self.starfield.draw(self.game_canvas)

    def draw(self):
        with self.game_canvas:
            kivy.graphics.PushMatrix()
            kivy.graphics.Translate(self.shake_offset[0], self.shake_offset[1], 0)
            self.draw_fullscreen_backdrop()
            scale = min(self.width / SCREEN_WIDTH, self.height / SCREEN_HEIGHT)
            offset_x = (self.width - (SCREEN_WIDTH * scale)) / 2
            offset_y = (self.height - (SCREEN_HEIGHT * scale)) / 2
            kivy.graphics.PushMatrix()
            kivy.graphics.Translate(offset_x, offset_y, 0)
            kivy.graphics.Scale(scale, scale, 1)

            self.draw_stage_background()

            if self.game_state == "menu":
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

    def draw_menu(self):
        self.draw_text("SPACE SHOOTER", SCREEN_WIDTH//2, 560, color=CYAN, font_size=56)
        self.draw_text("Press SPACE to Start", SCREEN_WIDTH//2, 440, color=WHITE, font_size=32)
        self.draw_text("Arrow Keys to Move", SCREEN_WIDTH//2, 380, color=WHITE, font_size=24)
        self.draw_text("Z or SPACE to Shoot (Hold)", SCREEN_WIDTH//2, 340, color=WHITE, font_size=24)
        self.draw_text("ESC/P to Pause | V to Toggle Vertical", SCREEN_WIDTH//2, 300, color=YELLOW, font_size=20)
        self.draw_text("Clear all 10 stages and defeat every boss", SCREEN_WIDTH//2, 260, color=ORANGE, font_size=20)
        if self.current_user:
            self.draw_text(f"Player: {self.current_user}", SCREEN_WIDTH//2, 230, color=CYAN, font_size=22)
            self.draw_text(f"Best Score: {self.high_score}", SCREEN_WIDTH//2, 200, color=GREEN, font_size=22)
            if self.user_last_score is not None:
                self.draw_text(f"Last Score: {self.user_last_score} (Wave {self.user_last_wave})", SCREEN_WIDTH//2, 170, color=WHITE, font_size=20)
            self.draw_text(f"Games Played: {self.user_games_played}", SCREEN_WIDTH//2, 140, color=WHITE, font_size=18)

    def draw_paused(self):
        kivy.graphics.Color(0,0,0,0.7)
        kivy.graphics.Rectangle(pos=(0,0), size=(SCREEN_WIDTH,SCREEN_HEIGHT))
        self.draw_text("PAUSED", SCREEN_WIDTH//2, SCREEN_HEIGHT//2+120, color=CYAN, font_size=48)
        for idx, item in enumerate(self.get_pause_menu_layout()):
            if idx == self.pause_menu_index:
                kivy.graphics.Color(0.2,0.8,1,0.35)
            else:
                kivy.graphics.Color(0.1,0.1,0.1,0.5)
            kivy.graphics.Rectangle(pos=(item['x'],item['y']), size=(item['w'],item['h']))
            col = CYAN if idx == self.pause_menu_index else WHITE
            self.draw_text(item['label'], item['center_x'], item['center_y'], color=col, font_size=24)
        self.draw_text("ESC to Resume | ENTER to Select", SCREEN_WIDTH//2, SCREEN_HEIGHT//2-120, color=WHITE, font_size=20)

    def draw_game(self):
        # power‑ups
        for p in self.powerups:
            if p['type'] == 'health':
                pat = ["..11..", ".1221.", "122221", ".1221.", "..11.."]
                pal = {"1":(0.45,1,0.45,1),"2":(0.12,0.72,0.12,1)}
            elif p['type'] == 'weapon':
                pat = ["3....3", ".3333.", "..33..", ".3333.", "3....3"]
                pal = {"3":(0.2,0.6,1,1)}
            elif p['type'] == 'shield':
                pat = ["..44..", ".4444.", "444444", ".4444.", "..44.."]
                pal = {"4":(0.6,0.6,1,1)}
            elif p['type'] == 'double_score':
                pat = ["..66..", ".6666.", "666666", ".6666.", "..66.."]
                pal = {"6":(1,0.8,0.2,1)}
            else:
                pat = ["5....5", ".5555.", "..55..", ".5555.", "5....5"]
                pal = {"5":(1,0.62,0.12,1)}
            self.draw_pixel_sprite(p['x'], p['y'], pat, pal, scale=3)

        # enemies
        for e in self.enemies:
            if e['type'] == 'boss':
                kivy.graphics.Color(*e.get('color',RED))
                kivy.graphics.Rectangle(pos=(self.px(e['x']-e['width']//2), self.px(e['y']-e['height']//2)), size=(e['width'],e['height']))
                hp = e['health']/e['max_health']
                bar_col = GREEN if hp>0.66 else (YELLOW if hp>0.33 else RED)
                kivy.graphics.Color(1,0,0,1)
                kivy.graphics.Rectangle(pos=(self.px(e['x']-40), self.px(e['y']-52)), size=(80,8))
                kivy.graphics.Color(*bar_col)
                kivy.graphics.Rectangle(pos=(self.px(e['x']-40), self.px(e['y']-52)), size=(80*hp,8))
            else:
                kivy.graphics.Color(*e.get('color',RED))
                kivy.graphics.Rectangle(pos=(self.px(e['x']-e['width']//2), self.px(e['y']-e['height']//2)), size=(e['width'],e['height']))
                if e.get('variant') == 'tank':
                    hp = e['health']/3
                    kivy.graphics.Color(1,0,0,1)
                    kivy.graphics.Rectangle(pos=(self.px(e['x']-20), self.px(e['y']-28)), size=(40,6))
                    kivy.graphics.Color(0,1,0,1)
                    kivy.graphics.Rectangle(pos=(self.px(e['x']-20), self.px(e['y']-28)), size=(40*hp,6))

        # bullets
        for b in self.bullets:
            kivy.graphics.Color(*b['color'])
            kivy.graphics.Rectangle(pos=(self.px(b['x']-2), self.px(b['y'])), size=(4,12))
        for b in self.enemy_bullets:
            kivy.graphics.Color(*b['color'])
            kivy.graphics.Rectangle(pos=(self.px(b['x']-4), self.px(b['y']-8)), size=(8,12))

        # particles
        for p in self.particles:
            p.draw(self.game_canvas)

        # player
        if not self.player['invulnerable'] or (self.player['invulnerable_timer']//10 % 2 == 0):
            # shield effect
            if self.shield_active:
                kivy.graphics.Color(0.2,0.5,1,0.3)
                for ang in range(8):
                    rad = 35
                    cx, cy = self.player['x'], self.player['y']
                    x1 = cx + rad*math.cos(ang*math.pi/4)
                    y1 = cy + rad*math.sin(ang*math.pi/4)
                    x2 = cx + rad*math.cos((ang+1)*math.pi/4)
                    y2 = cy + rad*math.sin((ang+1)*math.pi/4)
                    kivy.graphics.Color(0.2,0.5,1,0.3)
                    kivy.graphics.Rectangle(pos=(self.px(min(x1,x2)), self.px(min(y1,y2))), size=(abs(x2-x1)+2, abs(y2-y1)+2))
            # player sprite (pixel art)
            ship = [".....ooo.....","....ooooo....","...ooooooo...","..ooooooooo..",".ooooooooooo.","ooooooooooooo",".oooooo.oooo.","..oooo.oooo..","...oo...oo..."]
            self.draw_pixel_sprite(self.player['x'], self.player['y'], ship, {"o":(0.65,0.9,1,1)}, scale=4)
            # engine
            if 'up' in self.keys_pressed:
                kivy.graphics.Color(1,0.5,0,1)
                kivy.graphics.Rectangle(pos=(self.px(self.player['x']-8), self.px(self.player['y']-22)), size=(16,12))

        # HUD
        self.draw_text_left(f"❤️ {self.player['lives']}", 20, SCREEN_HEIGHT-44, color=(1,0.35,0.35,1), font_size=22)
        self.draw_text_left(f"Level: {self.wave}", 20, SCREEN_HEIGHT-74, color=WHITE, font_size=20)
        self.draw_text_left(f"Kills: {self.enemies_killed}", 20, SCREEN_HEIGHT-104, color=(0.7,1,0.7,1), font_size=20)
        self.draw_text_left(f"Score: {self.score}", 20, SCREEN_HEIGHT-134, color=WHITE, font_size=18)
        wtext = "Weapon: " + "★"*self.player['weapon_level'] + "☆"*(4-self.player['weapon_level'])
        self.draw_text_left(wtext, 20, SCREEN_HEIGHT-164, color=CYAN, font_size=16)
        yoff = SCREEN_HEIGHT-194
        if self.rapid_fire:
            self.draw_text_left(f"⚡ Rapid Fire: {int(self.rapid_timer)}s", 20, yoff, color=YELLOW, font_size=14); yoff-=22
        if self.shield_active:
            self.draw_text_left(f"🛡️ Shield: {int(self.shield_timer)}s", 20, yoff, color=BLUE, font_size=14); yoff-=22
        if self.double_score:
            self.draw_text_left(f"2x Score: {int(self.double_score_timer)}s", 20, yoff, color=GREEN, font_size=14)
        if not self.player['vertical_movement_enabled']:
            self.draw_text_left("Mode: Horizontal Only", SCREEN_WIDTH-150, 20, color=YELLOW, font_size=14)

        if self.stage_phase == "arrival":
            self.draw_text(self.arrival_text, SCREEN_WIDTH//2, SCREEN_HEIGHT//2, color=CYAN, font_size=40)
        elif self.stage_phase == "boss_warning":
            self.draw_text(self.boss_warning_text, SCREEN_WIDTH//2, SCREEN_HEIGHT//2, color=ORANGE, font_size=42)
        elif self.stage_phase == "clear_anim":
            self.draw_text(self.clear_message, SCREEN_WIDTH//2, SCREEN_HEIGHT//2, color=GREEN, font_size=44)

    def draw_game_over(self):
        self.draw_text("GAME OVER", SCREEN_WIDTH//2, 520, color=RED, font_size=56)
        if self.current_user:
            self.draw_text(f"Player: {self.current_user}", SCREEN_WIDTH//2, 470, color=CYAN, font_size=24)
        self.draw_text(f"Final Score: {self.score}", SCREEN_WIDTH//2, 420, color=WHITE, font_size=30)
        self.draw_text(f"Level Reached: {self.wave}", SCREEN_WIDTH//2, 370, color=WHITE, font_size=24)
        self.draw_text(f"Enemies Destroyed: {self.enemies_killed}", SCREEN_WIDTH//2, 320, color=WHITE, font_size=24)
        if self.new_high_score:
            self.draw_text("NEW HIGH SCORE!", SCREEN_WIDTH//2, 270, color=GREEN, font_size=28)
        self.draw_text("Press R to Restart or Q for Main Menu", SCREEN_WIDTH//2, 220, color=WHITE, font_size=22)

    def draw_victory(self):
        self.draw_text("VICTORY!", SCREEN_WIDTH//2, 540, color=GREEN, font_size=58)
        self.draw_text("You cleared all 10 stages", SCREEN_WIDTH//2, 450, color=WHITE, font_size=28)
        if self.current_user:
            self.draw_text(f"Player: {self.current_user}", SCREEN_WIDTH//2, 420, color=CYAN, font_size=22)
        self.draw_text(f"Final Score: {self.score}", SCREEN_WIDTH//2, 390, color=WHITE, font_size=28)
        self.draw_text(f"Total Enemies Destroyed: {self.enemies_killed}", SCREEN_WIDTH//2, 340, color=WHITE, font_size=24)
        if self.new_high_score:
            self.draw_text("NEW HIGH SCORE!", SCREEN_WIDTH//2, 290, color=GREEN, font_size=28)
        self.draw_text("Press R to Play Again or Q to Quit", SCREEN_WIDTH//2, 230, color=WHITE, font_size=22)

# ------------------------------
#  APP ENTRY POINT
# ------------------------------
class NewShootingGameApp(kivy.app.App):
    def build(self):
        return SpaceShooterGame()

if __name__ == "__main__":
    NewShootingGameApp().run()