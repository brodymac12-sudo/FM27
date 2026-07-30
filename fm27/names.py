"""Name pools used to generate fictional players.

Names are grouped by broad naming style; each style covers a set of
nationalities so generated squads feel internationally varied while the
domestic league stays majority home-grown.
"""

from __future__ import annotations

import random

NAME_STYLES = {
    "anglo": {
        "nations": ["England", "England", "England", "Scotland", "Wales", "Ireland", "USA", "Australia"],
        "first": ["Jack", "Harry", "Oliver", "George", "Callum", "Lewis", "Mason", "Reece",
                  "Kieran", "Tyler", "Aaron", "Declan", "Finlay", "Owen", "Josh", "Liam",
                  "Ethan", "Charlie", "Sam", "Connor"],
        "last": ["Walker", "Hughes", "Turner", "Brooks", "Mercer", "Whitfield", "Dawson",
                 "Kendall", "Barrow", "Ashford", "Redfern", "Colton", "Hale", "Ferris",
                 "Ogden", "Pryce", "Stanton", "Wren", "Maddox", "Ellery"],
    },
    "latin": {
        "nations": ["Spain", "Argentina", "Uruguay", "Colombia", "Mexico", "Chile"],
        "first": ["Mateo", "Santiago", "Nicolás", "Diego", "Álvaro", "Sergio", "Iker",
                  "Joaquín", "Emiliano", "Rodrigo", "Facundo", "Tomás", "Lucas", "Bruno"],
        "last": ["Fernández", "Aguirre", "Sosa", "Valverde", "Cabrera", "Herrera",
                 "Montoya", "Quintero", "Salazar", "Ibáñez", "Roldán", "Peralta", "Vidal"],
    },
    "luso": {
        "nations": ["Portugal", "Brazil", "Brazil"],
        "first": ["João", "Thiago", "Rafael", "Gustavo", "Vinícius", "Caio", "Éder",
                  "Matheus", "Renato", "Bernardo", "Nuno", "Rúben"],
        "last": ["Silva", "Moreira", "Cardoso", "Barbosa", "Teixeira", "Fonseca",
                 "Amaral", "Rocha", "Sales", "Peixoto", "Varela", "Coutinho"],
    },
    "gallic": {
        "nations": ["France", "Belgium"],
        "first": ["Antoine", "Théo", "Maxime", "Lucas", "Hugo", "Baptiste", "Rémy",
                  "Adrien", "Yanis", "Corentin", "Mathis"],
        "last": ["Moreau", "Lefèvre", "Garnier", "Perrin", "Chevalier", "Marchand",
                 "Dubois", "Renard", "Lambert", "Fontaine", "Bertrand"],
    },
    "germanic": {
        "nations": ["Germany", "Netherlands", "Austria", "Denmark", "Norway", "Sweden"],
        "first": ["Lukas", "Jonas", "Finn", "Niklas", "Sven", "Daan", "Lars", "Emil",
                  "Mikkel", "Timo", "Jesper", "Florian"],
        "last": ["Bauer", "Keller", "Vogel", "Brandt", "Van Dijk", "De Vries", "Hansen",
                 "Lindgren", "Fischer", "Kramer", "Sørensen", "Weiss"],
    },
    "italic": {
        "nations": ["Italy"],
        "first": ["Matteo", "Lorenzo", "Alessandro", "Davide", "Federico", "Marco",
                  "Nicolò", "Gianluca", "Riccardo", "Simone"],
        "last": ["Ricci", "Moretti", "Colombo", "Greco", "Marino", "Bruno", "Gallo",
                 "Conti", "De Luca", "Ferraro"],
    },
    "african": {
        "nations": ["Nigeria", "Ghana", "Senegal", "Ivory Coast", "Cameroon"],
        "first": ["Kwame", "Emeka", "Sadio", "Ibrahima", "Chidi", "Yaw", "Moussa",
                  "Abdoulaye", "Kofi", "Oumar", "Tunde"],
        "last": ["Okafor", "Mensah", "Diallo", "Ndiaye", "Traoré", "Adeyemi", "Boateng",
                 "Kouassi", "Sarr", "Eze", "Camara"],
    },
    "slavic": {
        "nations": ["Poland", "Croatia", "Serbia", "Czechia", "Ukraine"],
        "first": ["Jakub", "Mateusz", "Luka", "Nikola", "Marko", "Petr", "Andriy",
                  "Tomasz", "Ivan", "Filip"],
        "last": ["Kowalski", "Nowak", "Kovačić", "Petrović", "Horváth", "Novotný",
                 "Shevchuk", "Zielinski", "Jurić", "Marek"],
    },
    "asian": {
        "nations": ["Japan", "South Korea"],
        "first": ["Takumi", "Kaoru", "Ritsu", "Daichi", "Min-jae", "Ji-sung", "Hyun-woo",
                  "Sota", "Kenta"],
        "last": ["Tanaka", "Ito", "Kubo", "Nakamura", "Kim", "Lee", "Park", "Sato",
                 "Endo"],
    },
}

# Domestic league flavour: most players come from anglo-style nations.
_STYLE_WEIGHTS = [
    ("anglo", 55), ("latin", 8), ("luso", 8), ("gallic", 6), ("germanic", 7),
    ("italic", 4), ("african", 6), ("slavic", 4), ("asian", 2),
]


def random_identity(rng: random.Random) -> tuple[str, str]:
    """Return a random (full name, nationality) pair."""
    styles = [s for s, w in _STYLE_WEIGHTS for _ in range(w)]
    style = NAME_STYLES[rng.choice(styles)]
    name = f"{rng.choice(style['first'])} {rng.choice(style['last'])}"
    nation = rng.choice(style["nations"])
    return name, nation
