"""Seed data for the FM27 game world.

Real English club names across the 2026 Premier League (20 clubs) and EFL
Championship (24 clubs) — an unofficial fan project; club names are used
descriptively. Each entry is (name, short code, reputation 0-100, stadium
capacity). Reputation drives squad quality, finances, and transfer pull.
Players are entirely fictional.
"""

PREMIER_CLUBS = [
    ("Liverpool", "LIV", 94, 61276),
    ("Manchester City", "MCI", 94, 53400),
    ("Arsenal", "ARS", 93, 60704),
    ("Chelsea", "CHE", 90, 40341),
    ("Manchester United", "MUN", 88, 74310),
    ("Tottenham Hotspur", "TOT", 87, 62850),
    ("Newcastle United", "NEW", 87, 52305),
    ("Aston Villa", "AVL", 85, 42918),
    ("Brighton & Hove Albion", "BHA", 82, 31800),
    ("Crystal Palace", "CRY", 81, 25486),
    ("Nottingham Forest", "NFO", 81, 30445),
    ("Bournemouth", "BOU", 79, 11307),
    ("Fulham", "FUL", 78, 29600),
    ("Brentford", "BRE", 78, 17250),
    ("West Ham United", "WHU", 78, 62500),
    ("Everton", "EVE", 77, 52888),
    ("Wolverhampton Wanderers", "WOL", 75, 31750),
    ("Leeds United", "LEE", 74, 37792),
    ("Sunderland", "SUN", 71, 48707),
    ("Burnley", "BUR", 71, 21944),
]

CHAMPIONSHIP_CLUBS = [
    ("Leicester City", "LEI", 70, 32261),
    ("Southampton", "SOU", 69, 32384),
    ("Ipswich Town", "IPS", 68, 29813),
    ("Sheffield United", "SHU", 66, 32050),
    ("West Bromwich Albion", "WBA", 65, 26850),
    ("Middlesbrough", "MID", 65, 34742),
    ("Coventry City", "COV", 65, 32609),
    ("Norwich City", "NOR", 64, 27359),
    ("Watford", "WAT", 63, 22200),
    ("Birmingham City", "BIR", 63, 29409),
    ("Bristol City", "BRC", 62, 27000),
    ("Stoke City", "STK", 62, 30089),
    ("Swansea City", "SWA", 62, 21088),
    ("Hull City", "HUL", 61, 25400),
    ("Blackburn Rovers", "BLB", 61, 31367),
    ("Millwall", "MIL", 61, 20146),
    ("Preston North End", "PNE", 60, 23408),
    ("Queens Park Rangers", "QPR", 60, 18439),
    ("Derby County", "DER", 60, 32956),
    ("Portsmouth", "POR", 60, 20899),
    ("Wrexham", "WRX", 60, 13341),
    ("Charlton Athletic", "CHA", 59, 27111),
    ("Sheffield Wednesday", "SHW", 58, 39732),
    ("Oxford United", "OXF", 58, 12500),
]

DIVISION_NAMES = ["Premier League", "Championship"]
CUP_NAME = "FA Cup"
START_YEAR = 2026
