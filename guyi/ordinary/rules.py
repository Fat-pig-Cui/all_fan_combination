"""Explicit ranked rules; tile and yaku IDs stay stable between player counts."""
from dataclasses import asdict, dataclass
import hashlib
import json


@dataclass(frozen=True)
class Rules:
    players: int
    riichi_min_live_tiles: int
    replacement_tiles: int
    allow_chi: bool
    north_extraction: bool
    version: str = 'ranked-v1'

    @property
    def available_tiles(self):
        return tuple(t for t in range(34) if self.players == 4 or t not in range(1, 8))

    @property
    def seats(self):
        return tuple(range(27, 27 + self.players))

    @property
    def round_winds(self):
        return (27, 28, 29)

    @property
    def ippatsu_haitei_possible(self):
        return self.riichi_min_live_tiles <= self.players

    def to_dict(self):
        return dict(asdict(self), available_tiles=list(self.available_tiles),
                    seats=list(self.seats), round_winds=list(self.round_winds))

    @property
    def fingerprint(self):
        return hashlib.sha256(json.dumps(self.to_dict(), sort_keys=True).encode()).hexdigest()


FOUR_PLAYER = Rules(4, 4, 4, True, False)
# Three-live-tile riichi threshold confirmed by the user on 2026-10-11.
THREE_PLAYER = Rules(3, 3, 8, False, True)


def get_rules(players=4):
    if isinstance(players, bool) or players not in (3, 4):
        raise ValueError('players must be 3 or 4')
    return THREE_PLAYER if players == 3 else FOUR_PLAYER
