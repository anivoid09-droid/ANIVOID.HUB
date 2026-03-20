import sqlite3
import os
import time
from typing import Optional, List, Dict, Any

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "database.db")


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = get_conn()
    c = conn.cursor()

    c.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        first_name TEXT,
        coins INTEGER DEFAULT 0,
        bank INTEGER DEFAULT 0,
        xp INTEGER DEFAULT 0,
        level INTEGER DEFAULT 1,
        rank TEXT DEFAULT 'Bronze',
        is_dead BOOLEAN DEFAULT 0,
        dead_until REAL DEFAULT 0.0,
        selected_character_id INTEGER,
        battlepass_expiry REAL DEFAULT 0.0,
        last_daily REAL DEFAULT 0.0,
        banned INTEGER DEFAULT 0,
        join_date REAL DEFAULT 0.0,
        last_active REAL DEFAULT 0.0,
        commands_used INTEGER DEFAULT 0,
        love INTEGER DEFAULT 0,
        mood TEXT DEFAULT 'normal'
    );

    CREATE TABLE IF NOT EXISTS memory (
        user_id INTEGER,
        key TEXT,
        value TEXT,
        PRIMARY KEY (user_id, key)
    );

    CREATE TABLE IF NOT EXISTS warnings (
        user_id INTEGER,
        chat_id INTEGER,
        warns INTEGER DEFAULT 0,
        PRIMARY KEY (user_id, chat_id)
    );

    CREATE TABLE IF NOT EXISTS characters (
        char_id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        power INTEGER NOT NULL,
        skill TEXT,
        image_file_id TEXT,
        description TEXT,
        rarity TEXT DEFAULT 'Common',
        price INTEGER DEFAULT 1000
    );

    CREATE TABLE IF NOT EXISTS cards (
        card_id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        power INTEGER NOT NULL,
        skill TEXT,
        image_file_id TEXT,
        description TEXT,
        rarity TEXT DEFAULT 'Common',
        price INTEGER DEFAULT 500
    );

    CREATE TABLE IF NOT EXISTS maps (
        map_id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        boss_count INTEGER NOT NULL,
        danger_level INTEGER NOT NULL,
        reward INTEGER NOT NULL,
        image_file_id TEXT
    );

    CREATE TABLE IF NOT EXISTS bosses (
        boss_id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        power INTEGER NOT NULL,
        health INTEGER NOT NULL,
        description TEXT,
        image_file_id TEXT,
        type TEXT DEFAULT 'explore_boss',
        rewards INTEGER DEFAULT 1000,
        skills TEXT,
        level INTEGER DEFAULT 1
    );

    CREATE TABLE IF NOT EXISTS guilds (
        guild_id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        leader_id INTEGER NOT NULL,
        guild_points INTEGER DEFAULT 0,
        creation_time REAL
    );

    CREATE TABLE IF NOT EXISTS guild_members (
        guild_id INTEGER,
        user_id INTEGER,
        join_time REAL,
        role TEXT DEFAULT 'Member',
        PRIMARY KEY (guild_id, user_id)
    );

    CREATE TABLE IF NOT EXISTS tournaments (
        tournament_id INTEGER PRIMARY KEY AUTOINCREMENT,
        status TEXT DEFAULT 'Open',
        start_time REAL,
        end_time REAL,
        winner_id INTEGER,
        reward_coins INTEGER DEFAULT 50000,
        reward_xp INTEGER DEFAULT 5000,
        reward_item_type TEXT,
        reward_item_id INTEGER
    );

    CREATE TABLE IF NOT EXISTS tournament_participants (
        tournament_id INTEGER,
        user_id INTEGER,
        character_id INTEGER,
        PRIMARY KEY (tournament_id, user_id)
    );

    CREATE TABLE IF NOT EXISTS ads (
        ad_id INTEGER PRIMARY KEY AUTOINCREMENT,
        text TEXT NOT NULL,
        image_file_id TEXT,
        created_by INTEGER,
        status TEXT DEFAULT 'active'
    );

    CREATE TABLE IF NOT EXISTS groups (
        chat_id INTEGER PRIMARY KEY,
        chat_title TEXT,
        last_ad_time REAL DEFAULT 0.0
    );

    CREATE TABLE IF NOT EXISTS user_characters (
        user_id INTEGER,
        char_id INTEGER,
        current_health INTEGER DEFAULT 100,
        status TEXT DEFAULT 'Alive',
        dead_until REAL DEFAULT 0.0,
        PRIMARY KEY (user_id, char_id)
    );

    CREATE TABLE IF NOT EXISTS user_cards (
        user_id INTEGER,
        card_id INTEGER,
        PRIMARY KEY (user_id, card_id)
    );

    CREATE TABLE IF NOT EXISTS market (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        type TEXT NOT NULL,
        item_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        power INTEGER,
        skill TEXT,
        rarity TEXT,
        description TEXT,
        price INTEGER DEFAULT 1000,
        image_file_id TEXT
    );

    CREATE TABLE IF NOT EXISTS raid_bosses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        power INTEGER NOT NULL,
        skills TEXT,
        level INTEGER DEFAULT 1,
        rewards INTEGER DEFAULT 5000,
        health INTEGER DEFAULT 10000,
        image_file_id TEXT
    );

    CREATE TABLE IF NOT EXISTS active_raids (
        raid_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        boss_id INTEGER,
        char_id INTEGER,
        start_time REAL,
        end_time REAL,
        damage_dealt INTEGER DEFAULT 0,
        status TEXT DEFAULT 'active'
    );

    CREATE TABLE IF NOT EXISTS guild_raids (
        raid_id INTEGER PRIMARY KEY AUTOINCREMENT,
        guild_id INTEGER,
        boss_id INTEGER,
        status TEXT DEFAULT 'recruiting',
        start_time REAL,
        end_time REAL,
        total_damage INTEGER DEFAULT 0
    );

    CREATE TABLE IF NOT EXISTS guild_raid_participants (
        raid_id INTEGER,
        user_id INTEGER,
        char_id INTEGER,
        damage_dealt INTEGER DEFAULT 0,
        PRIMARY KEY (raid_id, user_id)
    );
    """)

    for col, col_def in [("love", "INTEGER DEFAULT 0"), ("mood", "TEXT DEFAULT 'normal'")]:
        try:
            conn.execute(f"ALTER TABLE users ADD COLUMN {col} {col_def}")
            conn.commit()
        except Exception:
            pass

    conn.commit()
    conn.close()


# ===== USER OPERATIONS =====

def get_user(user_id: int) -> Optional[Dict]:
    conn = get_conn()
    row = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def register_user(user_id: int, username: str, first_name: str) -> Dict:
    conn = get_conn()
    now = time.time()
    conn.execute("""
        INSERT OR IGNORE INTO users (user_id, username, first_name, join_date, last_active)
        VALUES (?, ?, ?, ?, ?)
    """, (user_id, username, first_name, now, now))
    conn.execute("""
        UPDATE users SET username = ?, first_name = ?, last_active = ?, commands_used = commands_used + 1
        WHERE user_id = ?
    """, (username, first_name, now, user_id))
    conn.commit()
    row = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
    conn.close()
    return dict(row)


def update_user(user_id: int, **kwargs):
    if not kwargs:
        return
    sets = ", ".join(f"{k} = ?" for k in kwargs)
    vals = list(kwargs.values()) + [user_id]
    conn = get_conn()
    conn.execute(f"UPDATE users SET {sets} WHERE user_id = ?", vals)
    conn.commit()
    conn.close()


def add_coins(user_id: int, amount: int):
    conn = get_conn()
    conn.execute("UPDATE users SET coins = coins + ? WHERE user_id = ?", (amount, user_id))
    conn.commit()
    conn.close()


def add_xp_and_level(user_id: int, xp_amount: int):
    from config import get_rank
    conn = get_conn()
    user = conn.execute("SELECT xp, level FROM users WHERE user_id = ?", (user_id,)).fetchone()
    if not user:
        conn.close()
        return
    new_xp = user["xp"] + xp_amount
    new_level = 1 + new_xp // 1000
    new_rank = get_rank(new_level)
    conn.execute("UPDATE users SET xp = ?, level = ?, rank = ? WHERE user_id = ?",
                 (new_xp, new_level, new_rank, user_id))
    conn.commit()
    conn.close()


def deduct_coins(user_id: int, amount: int) -> bool:
    conn = get_conn()
    user = conn.execute("SELECT coins, bank FROM users WHERE user_id = ?", (user_id,)).fetchone()
    if not user:
        conn.close()
        return False
    wallet = user["coins"]
    bank = user["bank"]
    if wallet + bank < amount:
        conn.close()
        return False
    if wallet >= amount:
        conn.execute("UPDATE users SET coins = coins - ? WHERE user_id = ?", (amount, user_id))
    else:
        remainder = amount - wallet
        conn.execute("UPDATE users SET coins = 0, bank = bank - ? WHERE user_id = ?", (remainder, user_id))
    conn.commit()
    conn.close()
    return True


def get_all_users() -> List[Dict]:
    conn = get_conn()
    rows = conn.execute("SELECT * FROM users ORDER BY level DESC, (coins+bank) DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_users_paginated(page: int = 0, per_page: int = 10) -> List[Dict]:
    conn = get_conn()
    rows = conn.execute("SELECT * FROM users ORDER BY user_id LIMIT ? OFFSET ?",
                        (per_page, page * per_page)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def count_users() -> int:
    conn = get_conn()
    n = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    conn.close()
    return n


# ===== CHARACTER OPERATIONS =====

def get_all_characters() -> List[Dict]:
    conn = get_conn()
    rows = conn.execute("SELECT * FROM characters ORDER BY char_id").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_character(char_id: int) -> Optional[Dict]:
    conn = get_conn()
    row = conn.execute("SELECT * FROM characters WHERE char_id = ?", (char_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def add_character(name, power, skill, image_file_id, description, rarity, price) -> int:
    conn = get_conn()
    c = conn.execute("""
        INSERT INTO characters (name, power, skill, image_file_id, description, rarity, price)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (name, power, skill, image_file_id, description, rarity, price))
    char_id = c.lastrowid
    conn.execute("""
        INSERT INTO market (type, item_id, name, power, skill, rarity, description, price, image_file_id)
        VALUES ('character', ?, ?, ?, ?, ?, ?, ?, ?)
    """, (char_id, name, power, skill, rarity, description, price, image_file_id))
    conn.commit()
    conn.close()
    return char_id


def delete_character(char_id: int):
    conn = get_conn()
    conn.execute("DELETE FROM characters WHERE char_id = ?", (char_id,))
    conn.execute("DELETE FROM market WHERE type = 'character' AND item_id = ?", (char_id,))
    conn.execute("DELETE FROM user_characters WHERE char_id = ?", (char_id,))
    conn.execute("DELETE FROM tournament_participants WHERE character_id = ?", (char_id,))
    conn.commit()
    conn.close()


def get_user_characters(user_id: int) -> List[Dict]:
    conn = get_conn()
    rows = conn.execute("""
        SELECT c.*, uc.current_health, uc.status, uc.dead_until
        FROM characters c
        JOIN user_characters uc ON c.char_id = uc.char_id
        WHERE uc.user_id = ?
        ORDER BY c.power DESC
    """, (user_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def give_character_to_user(user_id: int, char_id: int):
    conn = get_conn()
    conn.execute("""
        INSERT OR IGNORE INTO user_characters (user_id, char_id, current_health, status, dead_until)
        VALUES (?, ?, 100, 'Alive', 0.0)
    """, (user_id, char_id))
    conn.commit()
    conn.close()


def set_character_dead(user_id: int, char_id: int, hours: float = 3.0):
    dead_until = time.time() + hours * 3600
    conn = get_conn()
    conn.execute("""
        UPDATE user_characters SET status = 'Dead', dead_until = ?, current_health = 0
        WHERE user_id = ? AND char_id = ?
    """, (dead_until, user_id, char_id))
    conn.commit()
    conn.close()


def revive_dead_characters():
    now = time.time()
    conn = get_conn()
    conn.execute("""
        UPDATE user_characters SET status = 'Alive', current_health = 100, dead_until = 0.0
        WHERE status = 'Dead' AND dead_until <= ?
    """, (now,))
    conn.commit()
    conn.close()


def user_owns_character(user_id: int, char_id: int) -> bool:
    conn = get_conn()
    row = conn.execute("SELECT 1 FROM user_characters WHERE user_id = ? AND char_id = ?",
                       (user_id, char_id)).fetchone()
    conn.close()
    return row is not None


# ===== CARD OPERATIONS =====

def get_all_cards() -> List[Dict]:
    conn = get_conn()
    rows = conn.execute("SELECT * FROM cards ORDER BY card_id").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_card(card_id: int) -> Optional[Dict]:
    conn = get_conn()
    row = conn.execute("SELECT * FROM cards WHERE card_id = ?", (card_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def add_card(name, power, skill, image_file_id, description, rarity, price) -> int:
    conn = get_conn()
    c = conn.execute("""
        INSERT INTO cards (name, power, skill, image_file_id, description, rarity, price)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (name, power, skill, image_file_id, description, rarity, price))
    card_id = c.lastrowid
    conn.execute("""
        INSERT INTO market (type, item_id, name, power, skill, rarity, description, price, image_file_id)
        VALUES ('card', ?, ?, ?, ?, ?, ?, ?, ?)
    """, (card_id, name, power, skill, rarity, description, price, image_file_id))
    conn.commit()
    conn.close()
    return card_id


def delete_card(card_id: int):
    conn = get_conn()
    conn.execute("DELETE FROM cards WHERE card_id = ?", (card_id,))
    conn.execute("DELETE FROM market WHERE type = 'card' AND item_id = ?", (card_id,))
    conn.execute("DELETE FROM user_cards WHERE card_id = ?", (card_id,))
    conn.commit()
    conn.close()


def get_user_cards(user_id: int) -> List[Dict]:
    conn = get_conn()
    rows = conn.execute("""
        SELECT c.* FROM cards c
        JOIN user_cards uc ON c.card_id = uc.card_id
        WHERE uc.user_id = ?
        ORDER BY c.power DESC
    """, (user_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def give_card_to_user(user_id: int, card_id: int):
    conn = get_conn()
    conn.execute("INSERT OR IGNORE INTO user_cards (user_id, card_id) VALUES (?, ?)",
                 (user_id, card_id))
    conn.commit()
    conn.close()


def user_owns_card(user_id: int, card_id: int) -> bool:
    conn = get_conn()
    row = conn.execute("SELECT 1 FROM user_cards WHERE user_id = ? AND card_id = ?",
                       (user_id, card_id)).fetchone()
    conn.close()
    return row is not None


# ===== MAP OPERATIONS =====

def get_all_maps() -> List[Dict]:
    conn = get_conn()
    rows = conn.execute("SELECT * FROM maps ORDER BY danger_level").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_map(name, boss_count, danger_level, reward, image_file_id) -> int:
    conn = get_conn()
    c = conn.execute("""
        INSERT INTO maps (name, boss_count, danger_level, reward, image_file_id)
        VALUES (?, ?, ?, ?, ?)
    """, (name, boss_count, danger_level, reward, image_file_id))
    conn.commit()
    map_id = c.lastrowid
    conn.close()
    return map_id


# ===== BOSS OPERATIONS =====

def get_bosses_by_type(boss_type: str) -> List[Dict]:
    conn = get_conn()
    rows = conn.execute("SELECT * FROM bosses WHERE type = ? ORDER BY power",
                        (boss_type,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_boss(boss_id: int) -> Optional[Dict]:
    conn = get_conn()
    row = conn.execute("SELECT * FROM bosses WHERE boss_id = ?", (boss_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def add_boss(name, power, health, description, image_file_id, boss_type, rewards, skills="", level=1) -> int:
    conn = get_conn()
    c = conn.execute("""
        INSERT INTO bosses (name, power, health, description, image_file_id, type, rewards, skills, level)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (name, power, health, description, image_file_id, boss_type, rewards, skills, level))
    conn.commit()
    boss_id = c.lastrowid
    conn.close()
    return boss_id


# ===== RAID BOSS OPERATIONS =====

def get_all_raid_bosses() -> List[Dict]:
    conn = get_conn()
    rows = conn.execute("SELECT * FROM raid_bosses ORDER BY level").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_raid_boss(boss_id: int) -> Optional[Dict]:
    conn = get_conn()
    row = conn.execute("SELECT * FROM raid_bosses WHERE id = ?", (boss_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def add_raid_boss(name, power, skills, level, rewards, health=None) -> int:
    if health is None:
        health = power * 10
    conn = get_conn()
    c = conn.execute("""
        INSERT INTO raid_bosses (name, power, skills, level, rewards, health)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (name, power, skills, level, rewards, health))
    conn.commit()
    boss_id = c.lastrowid
    conn.close()
    return boss_id


# ===== ACTIVE RAID OPERATIONS =====

def create_active_raid(user_id, boss_id, char_id, duration_seconds) -> int:
    now = time.time()
    conn = get_conn()
    c = conn.execute("""
        INSERT INTO active_raids (user_id, boss_id, char_id, start_time, end_time, status)
        VALUES (?, ?, ?, ?, ?, 'active')
    """, (user_id, boss_id, char_id, now, now + duration_seconds))
    conn.commit()
    raid_id = c.lastrowid
    conn.close()
    return raid_id


def get_active_raid(user_id: int) -> Optional[Dict]:
    conn = get_conn()
    row = conn.execute("""
        SELECT ar.*, rb.name as boss_name, rb.power as boss_power, rb.rewards as boss_rewards
        FROM active_raids ar
        JOIN raid_bosses rb ON ar.boss_id = rb.id
        WHERE ar.user_id = ? AND ar.status = 'active'
        ORDER BY ar.raid_id DESC LIMIT 1
    """, (user_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def complete_raid(raid_id: int, won: bool):
    conn = get_conn()
    conn.execute("UPDATE active_raids SET status = ? WHERE raid_id = ?",
                 ('won' if won else 'lost', raid_id))
    conn.commit()
    conn.close()


# ===== GUILD OPERATIONS =====

def get_guild_by_leader(user_id: int) -> Optional[Dict]:
    conn = get_conn()
    row = conn.execute("SELECT * FROM guilds WHERE leader_id = ?", (user_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_user_guild(user_id: int) -> Optional[Dict]:
    conn = get_conn()
    row = conn.execute("""
        SELECT g.* FROM guilds g
        JOIN guild_members gm ON g.guild_id = gm.guild_id
        WHERE gm.user_id = ?
    """, (user_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def create_guild(name: str, leader_id: int) -> int:
    conn = get_conn()
    now = time.time()
    c = conn.execute("""
        INSERT INTO guilds (name, leader_id, creation_time) VALUES (?, ?, ?)
    """, (name, leader_id, now))
    guild_id = c.lastrowid
    conn.execute("""
        INSERT INTO guild_members (guild_id, user_id, join_time, role) VALUES (?, ?, ?, 'Leader')
    """, (guild_id, leader_id, now))
    conn.commit()
    conn.close()
    return guild_id


def get_guild_members(guild_id: int) -> List[Dict]:
    conn = get_conn()
    rows = conn.execute("""
        SELECT u.user_id, u.username, u.first_name, u.level, gm.role
        FROM guild_members gm
        JOIN users u ON gm.user_id = u.user_id
        WHERE gm.guild_id = ?
    """, (guild_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_guild_member_count(guild_id: int) -> int:
    conn = get_conn()
    n = conn.execute("SELECT COUNT(*) FROM guild_members WHERE guild_id = ?", (guild_id,)).fetchone()[0]
    conn.close()
    return n


def join_guild(guild_id: int, user_id: int):
    conn = get_conn()
    conn.execute("""
        INSERT OR IGNORE INTO guild_members (guild_id, user_id, join_time, role) VALUES (?, ?, ?, 'Member')
    """, (guild_id, user_id, time.time()))
    conn.commit()
    conn.close()


def leave_guild(guild_id: int, user_id: int):
    conn = get_conn()
    conn.execute("DELETE FROM guild_members WHERE guild_id = ? AND user_id = ?", (guild_id, user_id))
    conn.commit()
    conn.close()


def get_all_guilds() -> List[Dict]:
    conn = get_conn()
    rows = conn.execute("SELECT * FROM guilds ORDER BY guild_points DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def count_guilds() -> int:
    conn = get_conn()
    n = conn.execute("SELECT COUNT(*) FROM guilds").fetchone()[0]
    conn.close()
    return n


def update_guild_points(guild_id: int, points: int):
    conn = get_conn()
    conn.execute("UPDATE guilds SET guild_points = guild_points + ? WHERE guild_id = ?", (points, guild_id))
    conn.commit()
    conn.close()


def delete_guild(guild_id: int):
    conn = get_conn()
    conn.execute("DELETE FROM guild_members WHERE guild_id = ?", (guild_id,))
    conn.execute("DELETE FROM guilds WHERE guild_id = ?", (guild_id,))
    conn.commit()
    conn.close()


# ===== TOURNAMENT OPERATIONS =====

def get_open_tournament() -> Optional[Dict]:
    conn = get_conn()
    row = conn.execute("SELECT * FROM tournaments WHERE status = 'Open' ORDER BY tournament_id DESC LIMIT 1").fetchone()
    conn.close()
    return dict(row) if row else None


def get_ongoing_tournament() -> Optional[Dict]:
    conn = get_conn()
    row = conn.execute("SELECT * FROM tournaments WHERE status IN ('Open','Ongoing') ORDER BY tournament_id DESC LIMIT 1").fetchone()
    conn.close()
    return dict(row) if row else None


def create_tournament(reward_coins=50000, reward_xp=5000) -> int:
    conn = get_conn()
    now = time.time()
    c = conn.execute("""
        INSERT INTO tournaments (status, start_time, reward_coins, reward_xp)
        VALUES ('Open', ?, ?, ?)
    """, (now, reward_coins, reward_xp))
    conn.commit()
    t_id = c.lastrowid
    conn.close()
    return t_id


def join_tournament(tournament_id: int, user_id: int, character_id: int):
    conn = get_conn()
    conn.execute("""
        INSERT OR REPLACE INTO tournament_participants (tournament_id, user_id, character_id)
        VALUES (?, ?, ?)
    """, (tournament_id, user_id, character_id))
    conn.commit()
    conn.close()


def get_tournament_participants(tournament_id: int) -> List[Dict]:
    conn = get_conn()
    rows = conn.execute("""
        SELECT tp.*, u.username, u.first_name, c.power, c.name as char_name
        FROM tournament_participants tp
        JOIN users u ON tp.user_id = u.user_id
        JOIN characters c ON tp.character_id = c.char_id
        WHERE tp.tournament_id = ?
    """, (tournament_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def count_tournament_participants(tournament_id: int) -> int:
    conn = get_conn()
    n = conn.execute("SELECT COUNT(*) FROM tournament_participants WHERE tournament_id = ?",
                     (tournament_id,)).fetchone()[0]
    conn.close()
    return n


def is_in_tournament(tournament_id: int, user_id: int) -> bool:
    conn = get_conn()
    row = conn.execute("SELECT 1 FROM tournament_participants WHERE tournament_id = ? AND user_id = ?",
                       (tournament_id, user_id)).fetchone()
    conn.close()
    return row is not None


def finish_tournament(tournament_id: int, winner_id: int):
    conn = get_conn()
    conn.execute("""
        UPDATE tournaments SET status = 'Finished', winner_id = ?, end_time = ?
        WHERE tournament_id = ?
    """, (winner_id, time.time(), tournament_id))
    conn.commit()
    conn.close()


def set_tournament_ongoing(tournament_id: int):
    conn = get_conn()
    conn.execute("UPDATE tournaments SET status = 'Ongoing' WHERE tournament_id = ?", (tournament_id,))
    conn.commit()
    conn.close()


# ===== ADS OPERATIONS =====

def get_active_ads() -> List[Dict]:
    conn = get_conn()
    rows = conn.execute("SELECT * FROM ads WHERE status = 'active'").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_all_ads() -> List[Dict]:
    conn = get_conn()
    rows = conn.execute("SELECT * FROM ads ORDER BY ad_id").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_ad(text: str, image_file_id: Optional[str], created_by: int) -> int:
    conn = get_conn()
    c = conn.execute("""
        INSERT INTO ads (text, image_file_id, created_by, status) VALUES (?, ?, ?, 'active')
    """, (text, image_file_id, created_by))
    conn.commit()
    ad_id = c.lastrowid
    conn.close()
    return ad_id


def toggle_ad(ad_id: int, status: str):
    conn = get_conn()
    conn.execute("UPDATE ads SET status = ? WHERE ad_id = ?", (status, ad_id))
    conn.commit()
    conn.close()


def delete_ad(ad_id: int):
    conn = get_conn()
    conn.execute("DELETE FROM ads WHERE ad_id = ?", (ad_id,))
    conn.commit()
    conn.close()


def count_ads() -> int:
    conn = get_conn()
    n = conn.execute("SELECT COUNT(*) FROM ads WHERE status='active'").fetchone()[0]
    conn.close()
    return n


# ===== GROUP OPERATIONS =====

def register_group(chat_id: int, chat_title: str):
    conn = get_conn()
    conn.execute("""
        INSERT OR IGNORE INTO groups (chat_id, chat_title) VALUES (?, ?)
    """, (chat_id, chat_title))
    conn.execute("UPDATE groups SET chat_title = ? WHERE chat_id = ?", (chat_title, chat_id))
    conn.commit()
    conn.close()


def get_all_groups() -> List[Dict]:
    conn = get_conn()
    rows = conn.execute("SELECT * FROM groups").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def count_groups() -> int:
    conn = get_conn()
    n = conn.execute("SELECT COUNT(*) FROM groups").fetchone()[0]
    conn.close()
    return n


def update_group_ad_time(chat_id: int):
    conn = get_conn()
    conn.execute("UPDATE groups SET last_ad_time = ? WHERE chat_id = ?", (time.time(), chat_id))
    conn.commit()
    conn.close()


# ===== MARKET OPERATIONS =====

def get_market_items() -> List[Dict]:
    conn = get_conn()
    rows = conn.execute("SELECT * FROM market ORDER BY type, id").fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ===== GUILD RAID OPERATIONS =====

def create_guild_raid(guild_id: int, boss_id: int) -> int:
    conn = get_conn()
    c = conn.execute("""
        INSERT INTO guild_raids (guild_id, boss_id, status, start_time) VALUES (?, ?, 'recruiting', ?)
    """, (guild_id, boss_id, time.time()))
    conn.commit()
    raid_id = c.lastrowid
    conn.close()
    return raid_id


def get_active_guild_raid(guild_id: int) -> Optional[Dict]:
    conn = get_conn()
    row = conn.execute("""
        SELECT gr.*, b.name as boss_name, b.power as boss_power, b.health as boss_health,
               b.rewards as boss_rewards
        FROM guild_raids gr
        JOIN bosses b ON gr.boss_id = b.boss_id
        WHERE gr.guild_id = ? AND gr.status IN ('recruiting', 'ongoing')
        ORDER BY gr.raid_id DESC LIMIT 1
    """, (guild_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def join_guild_raid(raid_id: int, user_id: int, char_id: int):
    conn = get_conn()
    conn.execute("""
        INSERT OR REPLACE INTO guild_raid_participants (raid_id, user_id, char_id)
        VALUES (?, ?, ?)
    """, (raid_id, user_id, char_id))
    conn.commit()
    conn.close()


def get_guild_raid_participants(raid_id: int) -> List[Dict]:
    conn = get_conn()
    rows = conn.execute("""
        SELECT grp.*, u.username, u.first_name, c.power, c.name as char_name
        FROM guild_raid_participants grp
        JOIN users u ON grp.user_id = u.user_id
        JOIN characters c ON grp.char_id = c.char_id
        WHERE grp.raid_id = ?
    """, (raid_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def set_guild_raid_status(raid_id: int, status: str):
    conn = get_conn()
    conn.execute("UPDATE guild_raids SET status = ? WHERE raid_id = ?", (status, raid_id))
    conn.commit()
    conn.close()


# ===== MEMORY OPERATIONS =====

def save_memory(user_id: int, key: str, value: str):
    conn = get_conn()
    conn.execute(
        "INSERT OR REPLACE INTO memory (user_id, key, value) VALUES (?, ?, ?)",
        (user_id, key.lower().strip(), value.strip())
    )
    conn.commit()
    conn.close()


def get_memory(user_id: int, key: str) -> Optional[str]:
    conn = get_conn()
    row = conn.execute(
        "SELECT value FROM memory WHERE user_id = ? AND key = ?",
        (user_id, key.lower().strip())
    ).fetchone()
    conn.close()
    return row[0] if row else None


def get_all_memories(user_id: int) -> dict:
    conn = get_conn()
    rows = conn.execute(
        "SELECT key, value FROM memory WHERE user_id = ?", (user_id,)
    ).fetchall()
    conn.close()
    return {r[0]: r[1] for r in rows}


def clear_memories(user_id: int):
    conn = get_conn()
    conn.execute("DELETE FROM memory WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()


# ===== LOVE / MOOD OPERATIONS =====

def get_user_love(user_id: int) -> int:
    conn = get_conn()
    row = conn.execute("SELECT love FROM users WHERE user_id = ?", (user_id,)).fetchone()
    conn.close()
    return int(row[0]) if row and row[0] is not None else 0


def increase_love(user_id: int, amount: int = 2):
    conn = get_conn()
    conn.execute(
        "UPDATE users SET love = COALESCE(love, 0) + ? WHERE user_id = ?",
        (amount, user_id)
    )
    conn.commit()
    conn.close()


def get_user_mood(user_id: int) -> str:
    conn = get_conn()
    row = conn.execute("SELECT mood FROM users WHERE user_id = ?", (user_id,)).fetchone()
    conn.close()
    return row[0] if row and row[0] else "normal"


def set_user_mood(user_id: int, mood: str):
    conn = get_conn()
    conn.execute(
        "UPDATE users SET mood = ? WHERE user_id = ?",
        (mood, user_id)
    )
    conn.commit()
    conn.close()


# ===== WARNINGS OPERATIONS =====

def get_warns(user_id: int, chat_id: int) -> int:
    conn = get_conn()
    row = conn.execute(
        "SELECT warns FROM warnings WHERE user_id = ? AND chat_id = ?",
        (user_id, chat_id)
    ).fetchone()
    conn.close()
    return int(row[0]) if row else 0


def set_warns(user_id: int, chat_id: int, warns: int):
    conn = get_conn()
    conn.execute(
        "INSERT OR REPLACE INTO warnings (user_id, chat_id, warns) VALUES (?, ?, ?)",
        (user_id, chat_id, warns)
    )
    conn.commit()
    conn.close()
