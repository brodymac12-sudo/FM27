"""Transfer market: AI window activity and user-driven bids.

The AI window runs once per season (pre-season). Clubs shore up their
weakest positions with affordable signings; selling clubs only let players
go for a premium, or when they have surplus depth or money trouble.
"""

from __future__ import annotations

import random

from .club import Club
from .player import Player

# Minimum bodies a club wants per position before it will sell one.
MIN_DEPTH = {"GK": 2, "DF": 6, "MF": 5, "FW": 4}
IDEAL_DEPTH = {"GK": 3, "DF": 8, "MF": 7, "FW": 5}
MAX_BUYS_PER_WINDOW = 3


class Transfer:
    def __init__(self, player_name: str, position: str, from_club: str,
                 to_club: str, fee: float):
        self.player_name = player_name
        self.position = position
        self.from_club = from_club
        self.to_club = to_club
        self.fee = fee

    def __str__(self) -> str:
        return (f"{self.player_name} ({self.position}) — {self.from_club} → "
                f"{self.to_club} for £{self.fee:.1f}M")


def _positional_need(club: Club) -> list[str]:
    """Positions ranked by how badly the club needs reinforcement."""
    scores = []
    for pos, ideal in IDEAL_DEPTH.items():
        group = club.players_at(pos)
        shortage = ideal - len(group)
        best = max((p.ability for p in group), default=0)
        weakness = max(0.0, club.squad_strength - best)
        scores.append((pos, shortage * 8 + weakness))
    scores.sort(key=lambda t: t[1], reverse=True)
    return [pos for pos, score in scores if score > 0] or ["MF"]


def will_sell(seller: Club, player: Player, fee: float) -> bool:
    """Whether the selling club accepts a bid at this fee."""
    if fee < player.value * 0.9:
        return False
    depth = len(seller.players_at(player.position))
    is_surplus = depth > MIN_DEPTH[player.position] and player.ability < seller.squad_strength - 4
    money_trouble = seller.balance < 0
    big_premium = fee >= player.value * 1.45
    fair_premium = fee >= player.value * 1.1
    if is_surplus and fair_premium:
        return True
    if money_trouble and fair_premium and depth > MIN_DEPTH[player.position]:
        return True
    return big_premium and depth > MIN_DEPTH[player.position]


def execute_transfer(buyer: Club, seller: Club, player: Player, fee: float) -> Transfer:
    seller.remove_player(player)
    buyer.add_player(player)
    seller.balance = round(seller.balance + fee, 2)
    seller.transfer_budget = round(seller.transfer_budget + fee * 0.6, 2)
    buyer.balance = round(buyer.balance - fee, 2)
    buyer.transfer_budget = round(buyer.transfer_budget - fee, 2)
    player.morale = min(100.0, player.morale + 8)
    return Transfer(player.name, player.position, seller.name, buyer.name, round(fee, 2))


def _candidates(buyer: Club, clubs: list[Club], pos: str,
                user_club_id: int | None) -> list[tuple[Club, Player]]:
    out = []
    for seller in clubs:
        if seller.id == buyer.id or seller.id == user_club_id:
            continue  # the AI never raids the user's squad silently
        if len(seller.players_at(pos)) <= MIN_DEPTH[pos]:
            continue
        for p in seller.players_at(pos):
            if p.value <= buyer.transfer_budget and p.ability > 40:
                out.append((seller, p))
    return out


def run_ai_window(rng: random.Random, clubs: list[Club],
                  user_club_id: int | None = None) -> list[Transfer]:
    """One pre-season window of AI transfer activity. Returns completed deals."""
    completed: list[Transfer] = []
    # Richer clubs move first, like real life.
    order = sorted(clubs, key=lambda c: c.reputation, reverse=True)
    for buyer in order:
        if buyer.id == user_club_id:
            continue  # the user runs their own transfers
        buys = 0
        for pos in _positional_need(buyer):
            if buys >= MAX_BUYS_PER_WINDOW or buyer.transfer_budget < 1.0:
                break
            candidates = _candidates(buyer, clubs, pos, user_club_id)
            if not candidates:
                continue
            # Chase the best player the budget can stretch to, mostly.
            candidates.sort(key=lambda t: t[1].ability, reverse=True)
            pool = candidates[: max(3, len(candidates) // 10)]
            seller, target = rng.choice(pool)
            if target.ability < buyer.squad_strength - 10:
                continue  # not an upgrade worth the fee
            fee = target.value * rng.uniform(1.05, 1.4)
            if fee > buyer.transfer_budget:
                continue
            if will_sell(seller, target, fee):
                completed.append(execute_transfer(buyer, seller, target, fee))
                buys += 1
    return completed


# ------------------------------------------------------------------ user side

def scout_targets(clubs: list[Club], buyer: Club, position: str | None = None,
                  max_value: float | None = None, limit: int = 25) -> list[Player]:
    """Players at other clubs the user could realistically bid for."""
    pool = []
    for c in clubs:
        if c.id == buyer.id:
            continue
        for p in c.squad:
            if position and p.position != position:
                continue
            if max_value is not None and p.value > max_value:
                continue
            pool.append(p)
    pool.sort(key=lambda p: p.ability, reverse=True)
    return pool[:limit]


def user_bid(buyer: Club, seller: Club, player: Player, fee: float) -> tuple[bool, str]:
    """Attempt a user bid. Returns (success, message)."""
    if fee > buyer.transfer_budget:
        return False, (f"Bid of £{fee:.1f}M exceeds your transfer budget "
                       f"(£{buyer.transfer_budget:.1f}M).")
    if buyer.wage_bill + player.wage > buyer.wage_budget:
        return False, "Signing would blow the wage budget."
    if not will_sell(seller, player, fee):
        ask = player.value * 1.45
        return False, (f"{seller.name} reject the bid. They'd want around "
                       f"£{ask:.1f}M for {player.name}.")
    t = execute_transfer(buyer, seller, player, fee)
    return True, f"Deal done! {t}"


def ai_offer_for(rng: random.Random, clubs: list[Club], seller: Club,
                 player: Player) -> tuple[Club, float] | None:
    """When the user lists a player, find an AI club willing to buy."""
    suitors = [c for c in clubs
               if c.id != seller.id
               and c.transfer_budget >= player.value * 0.85
               and player.ability >= c.squad_strength - 12]
    if not suitors or rng.random() < 0.25:      # sometimes nobody calls
        return None
    buyer = max(suitors, key=lambda c: c.reputation * rng.uniform(0.8, 1.2))
    offer = player.value * rng.uniform(0.85, 1.25)
    return buyer, round(min(offer, buyer.transfer_budget), 2)
