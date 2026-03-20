import time
from typing import Optional


def get_display_name(user) -> str:
    username = getattr(user, 'username', None)
    first_name = getattr(user, 'first_name', None)
    if username:
        return f"@{username}"
    if first_name:
        return first_name
    return f"User_{user.id}"


def get_display_name_from_db(user_dict: dict) -> str:
    if user_dict.get('username'):
        return f"@{user_dict['username']}"
    if user_dict.get('first_name'):
        return user_dict['first_name']
    return f"User_{user_dict['user_id']}"


def format_time_remaining(timestamp: float) -> str:
    remaining = timestamp - time.time()
    if remaining <= 0:
        return "Ready"
    hours = int(remaining // 3600)
    minutes = int((remaining % 3600) // 60)
    seconds = int(remaining % 60)
    parts = []
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    if seconds or not parts:
        parts.append(f"{seconds}s")
    return " ".join(parts)


def format_coins(amount: int) -> str:
    return f"{amount:,}"


def is_character_dead(char: dict) -> bool:
    if char.get('status') == 'Dead':
        if char.get('dead_until', 0) > time.time():
            return True
    return False


def get_skill_power(skill: str) -> int:
    from config import SKILL_POWER
    if not skill:
        return 0
    return SKILL_POWER.get(skill.lower().strip(), 50)


def calculate_raid_duration(char_power: int, boss_power: int) -> int:
    diff = char_power - boss_power
    if diff <= 0:
        diff = 0
    base_seconds = 20 * 60
    reductions = diff // 10000
    reduction = reductions * 10
    total = max(30, base_seconds - reduction)
    return total


def parse_caption_fields(caption: str) -> dict:
    result = {}
    if not caption:
        return result
    for line in caption.strip().split("\n"):
        if ":" in line:
            key, _, val = line.partition(":")
            result[key.strip().lower()] = val.strip()
    return result


def medal(position: int) -> str:
    medals = {1: "🥇", 2: "🥈", 3: "🥉"}
    return medals.get(position, f"{position}.")


def rarity_emoji(rarity: str) -> str:
    emojis = {
        "Common": "⚪",
        "Rare": "🔵",
        "Epic": "🟣",
        "Legendary": "🟡",
        "SSR": "🌟",
    }
    return emojis.get(rarity, "⚪")


def battlepass_active(user: dict) -> bool:
    return user.get('battlepass_expiry', 0) > time.time()
