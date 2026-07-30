"""Seed data for the FM27 game world: 28 fictional clubs across two divisions.

Each entry is (name, short name, reputation 0-100, stadium capacity).
Reputation drives squad quality, finances, and transfer pull.
"""

PREMIER_CLUBS = [
    ("Ashworth Rovers", "ASH", 90, 61000),
    ("Blackmere City", "BLM", 88, 55000),
    ("Caldervale United", "CAL", 86, 52000),
    ("Duncastle Athletic", "DUN", 84, 48000),
    ("Eastgate Albion", "EAS", 82, 42000),
    ("Farrowdon FC", "FAR", 80, 38000),
    ("Gravenport Town", "GRA", 79, 34000),
    ("Hartcliffe Wanderers", "HAR", 78, 33000),
    ("Ironbridge United", "IRO", 77, 31000),
    ("Kingsmoor FC", "KIN", 76, 30000),
    ("Larkhall Orient", "LRK", 75, 27000),
    ("Mersebrook FC", "MER", 74, 26000),
    ("Northfleet Rangers", "NOR", 73, 25000),
    ("Oakhampton City", "OAK", 72, 24000),
]

CHAMPIONSHIP_CLUBS = [
    ("Pembrook Argyle", "PEM", 68, 23000),
    ("Quarrington FC", "QUA", 67, 22000),
    ("Redwell County", "RED", 66, 21000),
    ("Silverton Vale", "SIL", 65, 20000),
    ("Thornbury Athletic", "THO", 64, 19000),
    ("Umberside FC", "UMB", 63, 18500),
    ("Valemont Rovers", "VAL", 62, 18000),
    ("Westmarch Town", "WES", 61, 17000),
    ("Yarrowfield United", "YAR", 60, 16500),
    ("Aldenbrook FC", "ALD", 59, 16000),
    ("Brightstone City", "BRI", 58, 15500),
    ("Cindermoor Colliers", "CIN", 57, 15000),
    ("Dovemere Wanderers", "DOV", 56, 14500),
    ("Elmswick Rangers", "ELM", 55, 14000),
]

DIVISION_NAMES = ["Premier Division", "Championship"]
CUP_NAME = "FA National Cup"
START_YEAR = 2026
