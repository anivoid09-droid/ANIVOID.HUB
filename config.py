import os

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
ADMIN_ID = 7036768966

# Game constants
GUILD_CREATE_COST = 200000
GUILD_MAX_MEMBERS = 50
TOURNAMENT_MAX_PLAYERS = 16
TOURNAMENT_DURATION_HOURS = 24
CHARACTER_DEAD_HOURS = 3
AD_INTERVAL_HOURS = 7

LOOTBOX_PRICES = {
    "basic": 3000,
    "silver": 6000,
    "gold": 12000,
    "diamond": 24000
}

BATTLEPASS_PRICES = {
    "1": (1, 2000),    # days, cost
    "2": (3, 6000),
    "3": (6, 12000)
}

SKILL_POWER = {
    "fire punch": 100,
    "heal": 50,
    "healing": 50,
    "boost": 75,
    "infinity": 200,
    "sharingan": 150,
    "rinnegan": 200,
    "thunder": 120,
    "wind": 90,
    "water": 80,
    "earth": 70,
    "ice": 110,
    "dark": 130,
    "light": 140,
}

RANK_THRESHOLDS = [
    (0, "Bronze"),
    (5, "Silver"),
    (10, "Gold"),
    (20, "Platinum"),
    (30, "Diamond"),
    (50, "Master"),
    (75, "Grandmaster"),
    (100, "Legend"),
]


def get_rank(level: int) -> str:
    rank = "Bronze"
    for threshold, name in RANK_THRESHOLDS:
        if level >= threshold:
            rank = name
    return rank
