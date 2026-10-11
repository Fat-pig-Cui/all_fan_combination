#!/usr/bin/env python3
"""Independent four/three-player ranked riichi evaluator (standard library).

Input hand is BEFORE winning; the winning tile is supplied separately.
Reference: GrandDawn / Fat-pig-Cui's MIT calcFan.js, riichi branch only.
No runtime dependency on replay-editor, JavaScript, or its global state.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from dataclasses import asdict, dataclass, replace
from functools import lru_cache
from pathlib import Path
from typing import Iterable, Optional

from rules import get_rules


# Stable IDs match the ordinary riichi IDs in the reference calcFan.js.
# id, slug, Chinese name, closed han, open han
CATALOG = (
    (1, 'menzen_tsumo', '门前清自摸和', 1, 0),
    (2, 'riichi', '立直', 1, 0),
    (3, 'chankan', '抢杠', 1, 1),
    (4, 'rinshan', '岭上开花', 1, 1),
    (5, 'haitei', '海底摸月', 1, 1),
    (6, 'houtei', '河底捞鱼', 1, 1),
    (7, 'haku', '白', 1, 1),
    (8, 'hatsu', '发', 1, 1),
    (9, 'chun', '中', 1, 1),
    (10, 'seat_wind', '门风牌', 1, 1),
    (11, 'round_wind', '场风牌', 1, 1),
    (12, 'tanyao', '断幺九', 1, 1),
    (13, 'iipeikou', '一杯口', 1, 0),
    (14, 'pinfu', '平和', 1, 0),
    (15, 'chanta', '混全带幺九', 2, 1),
    (16, 'ittsuu', '一气通贯', 2, 1),
    (17, 'sanshoku_doujun', '三色同顺', 2, 1),
    (18, 'double_riichi', '双立直', 2, 0),
    (19, 'sanshoku_doukou', '三色同刻', 2, 2),
    (20, 'sankantsu', '三杠子', 2, 2),
    (21, 'toitoi', '对对和', 2, 2),
    (22, 'sanankou', '三暗刻', 2, 2),
    (23, 'shousangen', '小三元', 2, 2),
    (24, 'honroutou', '混老头', 2, 2),
    (25, 'chiitoitsu', '七对子', 2, 0),
    (26, 'junchan', '纯全带幺九', 3, 2),
    (27, 'honitsu', '混一色', 3, 2),
    (28, 'ryanpeikou', '二杯口', 3, 0),
    (29, 'chinitsu', '清一色', 6, 5),
    (30, 'ippatsu', '一发', 1, 0),
)
YAKU = {slug: (identifier, name, closed, opened)
        for identifier, slug, name, closed, opened in CATALOG}
ORDER = tuple(row[1] for row in CATALOG)
BIT = {slug: 1 << index for index, slug in enumerate(ORDER)}
DRAGONS = frozenset((31, 32, 33))
WINDS = frozenset(range(27, 31))
HONORS = frozenset(range(27, 34))
TERMINALS = frozenset((0, 8, 9, 17, 18, 26))
ORPHANS = TERMINALS | HONORS
GREEN = frozenset((19, 20, 21, 23, 25, 32))
YAKUMAN = {
    'tenhou': ('天和', 1), 'chiihou': ('地和', 1),
    'daisangen': ('大三元', 1), 'suuankou': ('四暗刻', 1),
    'suuankou_tanki': ('四暗刻单骑', 2), 'tsuuiisou': ('字一色', 1),
    'ryuuiisou': ('绿一色', 1), 'chinroutou': ('清老头', 1),
    'kokushi': ('国士无双', 1), 'kokushi_13': ('国士无双十三面', 2),
    'shousuushii': ('小四喜', 1), 'daisuushii': ('大四喜', 2),
    'suukantsu': ('四杠子', 1), 'chuuren': ('九莲宝灯', 1),
    'junsei_chuuren': ('纯正九莲宝灯', 2),
}


def parse_tiles(text: str) -> tuple[int, ...]:
    """Accept compact 123m notation; red fives share the five copy limit."""
    compact = re.sub(r'\s+', '', text)
    if not compact:
        return ()
    tokens = list(re.finditer(r'([0-9]+)([mpsz])', compact))
    if ''.join(match.group() for match in tokens) != compact:
        raise ValueError('Invalid tile notation: ' + text)
    result = []
    for match in tokens:
        digits, suit = match.groups()
        for digit in digits:
            number = int(digit)
            if suit == 'z':
                if number not in range(1, 8):
                    raise ValueError('Honors must be 1z..7z')
                result.append(26 + number)
            else:
                if number == 0:
                    number = 5
                if number not in range(1, 10):
                    raise ValueError('Numbered tiles must be 1..9')
                result.append('mps'.index(suit) * 9 + number - 1)
    return tuple(result)


def one_tile(value) -> int:
    if isinstance(value, int) and not isinstance(value, bool) and 0 <= value < 34:
        return value
    if not isinstance(value, str):
        raise ValueError('A tile must be an integer 0..33 or a tile string')
    parsed = parse_tiles(value)
    if len(parsed) != 1:
        raise ValueError('Expected exactly one tile')
    return parsed[0]


def tile_name(tile: int) -> str:
    return str(tile - 26) + 'z' if tile >= 27 else str(tile % 9 + 1) + 'mps'[tile // 9]


def compact_tiles(tiles: Iterable[int]) -> str:
    tiles = tuple(tiles)
    pieces = []
    for suit in range(4):
        part = sorted(tile for tile in tiles if (tile // 9 if tile < 27 else 3) == suit)
        if part:
            pieces.append(''.join(str(tile - 26 if suit == 3 else tile % 9 + 1) for tile in part) + 'mpsz'[suit])
    return ' '.join(pieces)


@dataclass(frozen=True, order=True)
class Group:
    tile: int
    sequence: bool = False
    open: bool = False
    kan: bool = False

    def __post_init__(self):
        if not isinstance(self.tile, int) or not 0 <= self.tile < 34:
            raise ValueError('Invalid group tile')
        if self.sequence and (self.tile >= 27 or self.tile % 9 > 6 or self.kan):
            raise ValueError('Invalid sequence/kan')

    @property
    def tiles(self) -> tuple[int, ...]:
        if self.sequence:
            return (self.tile, self.tile + 1, self.tile + 2)
        return (self.tile,) * (4 if self.kan else 3)

    @property
    def fixed(self) -> bool:
        return self.open or self.kan

    def to_dict(self) -> dict:
        kind = 'chi' if self.sequence and self.open else 'sequence' if self.sequence else 'minkan' if self.kan and self.open else 'ankan' if self.kan else 'pon' if self.open else 'triplet'
        return {'kind': kind, 'tiles': compact_tiles(self.tiles)}


def parse_meld(record: dict) -> Group:
    kind = record['kind']
    tiles = parse_tiles(record['tiles'])
    if kind not in {'chi', 'pon', 'minkan', 'kakan', 'ankan'}:
        raise ValueError('Fixed meld kind must be chi/pon/minkan/kakan/ankan')
    if kind == 'chi':
        if len(tiles) != 3 or tuple(sorted(tiles)) != tuple(range(min(tiles), min(tiles) + 3)):
            raise ValueError('Invalid chi')
        return Group(min(tiles), sequence=True, open=True)
    if len(set(tiles)) != 1 or len(tiles) != (3 if kind == 'pon' else 4):
        raise ValueError('Invalid triplet/kan')
    return Group(tiles[0], open=kind != 'ankan', kan=kind != 'pon')


@dataclass(frozen=True)
class Context:
    win: int
    tsumo: bool = False
    seat: int = 27
    round_wind: int = 27
    riichi: int = 0
    ippatsu: bool = False
    event: str = 'none'
    first_turn: bool = False
    dora: int = 0
    players: int = 4
    north_count: int = 0
    win_source: str = 'auto'
    live_tiles: Optional[int] = None

    @property
    def rules(self):
        return get_rules(self.players)

    def __post_init__(self):
        if self.win not in self.rules.available_tiles or self.seat not in self.rules.seats or self.round_wind not in self.rules.round_winds:
            raise ValueError('Invalid win/seat/round tile')
        if self.riichi not in (0, 1, 2) or self.event not in {'none', 'chankan', 'rinshan', 'haitei', 'houtei'}:
            raise ValueError('Invalid riichi/event')
        if self.ippatsu and not self.riichi:
            raise ValueError('Ippatsu requires riichi')
        if self.event in {'rinshan', 'haitei'} and not self.tsumo:
            raise ValueError('Rinshan/haitei require tsumo')
        if self.event in {'chankan', 'houtei'} and self.tsumo:
            raise ValueError('Chankan/houtei require ron')
        if self.ippatsu and self.event in {'rinshan', 'houtei'}:
            raise ValueError('This event cannot coexist with ippatsu in this ruleset')
        if self.riichi == 2 and self.ippatsu and self.event in {'chankan', 'haitei'}:
            raise ValueError('Double-riichi ippatsu cannot reach this event')
        if self.dora < 0:
            raise ValueError('Dora must be nonnegative')
        if isinstance(self.north_count, bool) or self.north_count not in range(5):
            raise ValueError('north_count must be 0..4')
        if self.north_count and not self.rules.north_extraction:
            raise ValueError('North extraction requires three-player rules')
        if self.win_source not in {'auto', 'kan_replacement', 'north_replacement', 'north_ron'}:
            raise ValueError('Invalid win_source')
        if self.win_source in {'kan_replacement', 'north_replacement'} and self.event != 'rinshan':
            raise ValueError('Replacement source requires rinshan')
        if self.win_source == 'north_replacement' and (self.players != 3 or not self.north_count):
            raise ValueError('North replacement requires an extracted north')
        if self.win_source == 'north_ron' and (self.players != 3 or self.tsumo or self.win != 30 or self.event != 'none'):
            raise ValueError('Robbing north is ron on 4z without chankan/last-tile yaku')
        if self.live_tiles is not None and (isinstance(self.live_tiles, bool) or not isinstance(self.live_tiles, int) or self.live_tiles < 0):
            raise ValueError('live_tiles must be nonnegative or omitted')


def han_for(yaku: Iterable[str], closed: bool) -> int:
    return sum(YAKU[name][2 if closed else 3] for name in yaku)


def validate_inventory(tiles, groups, context):
    """Physical tile resources, extraction area and the winning response."""
    if any(t not in context.rules.available_tiles for t in tiles):
        raise ValueError('Tile is unavailable in this ruleset')
    if not context.rules.allow_chi and any(g.sequence and g.open for g in groups):
        raise ValueError('Chi is forbidden in three-player rules')
    counts = Counter(tiles)
    counts[30] += context.north_count
    if max(counts.values()) > 4:
        raise ValueError('More than four physical copies, including extracted north')
    if sum(g.kan for g in groups) + context.north_count > context.rules.replacement_tiles:
        raise ValueError('Replacement tile capacity exceeded')
    if context.event == 'chankan' and counts[context.win] != 1:
        raise ValueError('An opponent needs the other three copies for kakan/ankan')
    if context.event == 'rinshan':
        if context.live_tiles is not None and context.live_tiles < 2:
            raise ValueError('Cannot kan/extract north with fewer than two live tiles')
        if context.win_source == 'north_replacement':
            pass
        elif not any(g.kan for g in groups):
            raise ValueError('Kan replacement requires a declared kan; specify north_replacement for nuki')
    if context.win_source == 'north_ron' and context.live_tiles is not None and context.live_tiles < 2:
        raise ValueError('Opponent cannot extract north at the last live tile')
    if context.first_turn and context.north_count:
        raise ValueError('Extraction interrupts first-turn yakuman')
    if context.riichi == 2 and context.ippatsu and context.north_count:
        raise ValueError('Extraction interrupts first-discard double-riichi ippatsu')


def base_points(fu: int, han: int, yakuman: int = 0) -> int:
    if yakuman:
        return 8000 * yakuman
    if han < 1:
        return 0
    for threshold, points in ((13, 8000), (11, 6000), (8, 4000), (6, 3000), (5, 2000)):
        if han >= threshold:
            return points
    return min(2000, fu * (1 << (han + 2)))


@dataclass(frozen=True)
class Score:
    yaku: tuple[str, ...]
    han: int
    fu: int
    closed: bool
    yakuman: tuple[str, ...] = ()
    groups: tuple[Group, ...] = ()
    pair: Optional[int] = None
    win_group: int = -1
    kind: str = 'standard'
    dora: int = 0

    @property
    def yakuman_multiple(self) -> int:
        return sum(YAKUMAN[name][1] for name in self.yakuman)

    @property
    def total_han(self) -> int:
        return self.han + self.dora if not self.yakuman else 0

    @property
    def points(self) -> int:
        return base_points(self.fu, self.total_han, self.yakuman_multiple)

    @property
    def comparison_key(self) -> tuple[int, int, int]:
        # calcSudian(x, 1) ranks payment first, then raw han and rounded fu.
        return (self.points, self.total_han, self.fu)

    @property
    def mask(self) -> int:
        return sum(BIT[name] for name in self.yaku)

    def to_dict(self) -> dict:
        return {
            'kind': self.kind, 'closed': self.closed,
            'yaku': [{'id': YAKU[name][0], 'slug': name, 'name': YAKU[name][1], 'han': YAKU[name][2 if self.closed else 3]} for name in self.yaku],
            'han': self.han, 'dora': self.dora, 'total_han': self.total_han,
            'fu': self.fu, 'base_points': self.points,
            'yakuman': [{'slug': name, 'name': YAKUMAN[name][0], 'multiple': YAKUMAN[name][1]} for name in self.yakuman],
            'groups': [group.to_dict() for group in self.groups],
            'pair': None if self.pair is None else tile_name(self.pair),
            'win_group': self.win_group,
        }


@lru_cache(maxsize=65536)
def meld_decompositions(counts: tuple[int, ...]) -> tuple[tuple[Group, ...], ...]:
    if not any(counts):
        return ((),)
    first = next(tile for tile, count in enumerate(counts) if count)
    results = []
    if counts[first] >= 3:
        rest = list(counts)
        rest[first] -= 3
        for groups in meld_decompositions(tuple(rest)):
            results.append((Group(first),) + groups)
    if first < 27 and first % 9 <= 6 and counts[first + 1] and counts[first + 2]:
        rest = list(counts)
        for tile in range(first, first + 3):
            rest[tile] -= 1
        for groups in meld_decompositions(tuple(rest)):
            results.append((Group(first, sequence=True),) + groups)
    return tuple(results)


@lru_cache(maxsize=65536)
def standard_decompositions(counts: tuple[int, ...], fixed: tuple[Group, ...]) -> tuple[tuple[int, tuple[Group, ...]], ...]:
    if sum(counts) != 14 - 3 * len(fixed):
        return ()
    result = []
    for pair, count in enumerate(counts):
        if count < 2:
            continue
        rest = list(counts)
        rest[pair] -= 2
        for groups in meld_decompositions(tuple(rest)):
            if len(groups) + len(fixed) == 4:
                result.append((pair, fixed + groups))
    return tuple(result)


def wait_type(group: Optional[Group], win: int) -> str:
    if group is None:
        return 'tanki'
    if not group.sequence:
        return 'shanpon'
    if win == group.tile + 1:
        return 'kanchan'
    if (group.tile % 9 == 0 and win == group.tile + 2) or (group.tile % 9 == 6 and win == group.tile):
        return 'penchan'
    return 'ryanmen'


def situational(context: Context, closed: bool) -> set[str]:
    result = set()
    if closed:
        if context.tsumo:
            result.add('menzen_tsumo')
        if context.riichi:
            result.add('riichi' if context.riichi == 1 else 'double_riichi')
        if context.ippatsu:
            result.add('ippatsu')
    if context.event != 'none':
        result.add(context.event)
    return result


def tile_yakuman(tiles: tuple[int, ...], context: Context) -> set[str]:
    result = set()
    present = set(tiles)
    if present <= HONORS:
        result.add('tsuuiisou')
    if present <= GREEN:
        result.add('ryuuiisou')
    if present <= TERMINALS:
        result.add('chinroutou')
    if context.first_turn and context.tsumo:
        result.add('tenhou' if context.seat == 27 else 'chiihou')
    return result


def flush_yaku(tiles: tuple[int, ...]) -> set[str]:
    suits = {tile // 9 for tile in tiles if tile < 27}
    return {'honitsu' if any(tile >= 27 for tile in tiles) else 'chinitsu'} if len(suits) == 1 else set()


def evaluate_shape(groups: tuple[Group, ...], pair: int, win_group: int, context: Context) -> Score:
    """Evaluate ONE decomposition; win_group=-1 means winning on the pair."""
    if len(groups) != 4:
        raise ValueError('A standard shape needs four groups')
    if win_group == -1:
        if context.win != pair:
            raise ValueError('Winning tile is not the pair')
    elif win_group not in range(4) or groups[win_group].fixed or context.win not in groups[win_group].tiles:
        raise ValueError('Winning tile must complete an unfixed group')
    closed = not any(group.open for group in groups)
    tiles = tuple(tile for group in groups for tile in group.tiles) + (pair, pair)
    counts = Counter(tiles)
    validate_inventory(tiles, groups, context)
    if max(counts.values()) > 4:
        raise ValueError('More than four copies of a tile')
    if context.riichi and not closed:
        raise ValueError('Open hands cannot riichi')
    if context.riichi == 2 and context.event == 'chankan':
        # Standard hands can only rob kakan.  Its pon cannot predate double
        # riichi, and passing the pon's winning discard causes permanent furiten.
        # Kokushi robbing ankan is handled separately by special_scores.
        raise ValueError('Double-riichi kakan ron is permanently furiten')
    if context.event == 'chankan' and counts[context.win] != 1:
        raise ValueError('An opponent needs the other three copies for kakan')
    if context.first_turn and (any(group.fixed for group in groups) or context.riichi):
        raise ValueError('First-turn yakuman cannot have calls/kans/riichi')

    triplets = [group.tile for group in groups if not group.sequence]
    seq_counts = Counter(group.tile for group in groups if group.sequence)
    kans = sum(group.kan for group in groups)
    concealed = sum(not group.sequence and not group.open and (context.tsumo or index != win_group) for index, group in enumerate(groups))
    natural = tile_yakuman(tiles, context)
    if DRAGONS <= set(triplets):
        natural.add('daisangen')
    if WINDS <= set(triplets):
        natural.add('daisuushii')
    elif len(WINDS & set(triplets)) == 3 and pair in WINDS:
        natural.add('shousuushii')
    if concealed == 4:
        natural.add('suuankou_tanki' if win_group == -1 else 'suuankou')
    if kans == 4:
        natural.add('suukantsu')
    suits = {tile // 9 for tile in tiles if tile < 27}
    if closed and not kans and len(suits) == 1 and all(tile < 27 for tile in tiles):
        offset = next(iter(suits)) * 9
        minimum = (3, 1, 1, 1, 1, 1, 1, 1, 3)
        if all(counts[offset + number] >= needed for number, needed in enumerate(minimum)):
            before = counts.copy()
            before[context.win] -= 1
            pure = all(before[offset + number] == needed for number, needed in enumerate(minimum))
            natural.add('junsei_chuuren' if pure else 'chuuren')
    if natural:
        return Score((), 0, 0, closed, tuple(sorted(natural)), groups, pair, win_group)

    result = situational(context, closed) | flush_yaku(tiles)
    if all(tile not in ORPHANS for tile in tiles):
        result.add('tanyao')
    if closed:
        duplicates = sum(count // 2 for count in seq_counts.values())
        if duplicates:
            result.add('ryanpeikou' if duplicates == 2 else 'iipeikou')
    value_pair = pair in DRAGONS or pair in (context.seat, context.round_wind)
    winning_group = None if win_group == -1 else groups[win_group]
    wait = wait_type(winning_group, context.win)
    pinfu = closed and sum(seq_counts.values()) == 4 and not value_pair and wait == 'ryanmen'
    if pinfu:
        result.add('pinfu')
    for tile, name in ((31, 'haku'), (32, 'hatsu'), (33, 'chun'), (context.seat, 'seat_wind'), (context.round_wind, 'round_wind')):
        if tile in triplets:
            result.add(name)
    if kans == 3:
        result.add('sankantsu')
    if len(triplets) == 4:
        result.add('toitoi')
    if concealed == 3:
        result.add('sanankou')
    if len(set(triplets) & DRAGONS) == 2 and pair in DRAGONS:
        result.add('shousangen')
    if all(tile in ORPHANS for tile in tiles):
        result.add('honroutou')
    if seq_counts and pair in ORPHANS and all((group.tile % 9 in (0, 6)) if group.sequence else group.tile in ORPHANS for group in groups):
        result.add('chanta' if any(tile in HONORS for tile in tiles) else 'junchan')
    for suit in range(3):
        if all(suit * 9 + rank in seq_counts for rank in (0, 3, 6)):
            result.add('ittsuu')
    for rank in range(7):
        if all(suit * 9 + rank in seq_counts for suit in range(3)):
            result.add('sanshoku_doujun')
    for rank in range(9):
        if all(suit * 9 + rank in triplets for suit in range(3)):
            result.add('sanshoku_doukou')

    if pinfu and context.tsumo:
        fu = 20
    else:
        fu = 20 + (2 if context.tsumo else 10 if closed else 0)
        fu += 2 * (int(pair in DRAGONS) + int(pair == context.seat) + int(pair == context.round_wind))
        if wait in {'tanki', 'kanchan', 'penchan'}:
            fu += 2
        for index, group in enumerate(groups):
            if group.sequence:
                continue
            hidden = not group.open and (context.tsumo or index != win_group)
            fu += (16 if hidden else 8) * (2 if group.tile in ORPHANS else 1) if group.kan else (4 if hidden else 2) * (2 if group.tile in ORPHANS else 1)
        fu = max(30, ((fu + 9) // 10) * 10)
    yaku = tuple(name for name in ORDER if name in result)
    return Score(yaku, han_for(yaku, closed), fu, closed, groups=groups, pair=pair, win_group=win_group, dora=context.dora)


def special_scores(completed: tuple[int, ...], context: Context) -> tuple[Score, ...]:
    validate_inventory(completed, (), context)
    counts = Counter(completed)
    natural = tile_yakuman(completed, context)
    if set(counts) == ORPHANS and sorted(counts.values()) == [1] * 12 + [2]:
        before = counts.copy()
        before[context.win] -= 1
        pure = all(before[tile] == 1 for tile in ORPHANS)
        names = natural | {'kokushi_13' if pure else 'kokushi'}
        return (Score((), 0, 0, True, tuple(sorted(names)), kind='kokushi'),)
    if len(counts) != 7 or set(counts.values()) != {2}:
        return ()
    if natural:
        return (Score((), 0, 0, True, tuple(sorted(natural)), kind='chiitoitsu'),)
    if context.event == 'chankan' or (context.event == 'rinshan' and context.win_source != 'north_replacement'):
        return ()
    result = {'chiitoitsu'} | situational(context, True) | flush_yaku(completed)
    if all(tile not in ORPHANS for tile in completed):
        result.add('tanyao')
    if all(tile in ORPHANS for tile in completed):
        result.add('honroutou')
    yaku = tuple(name for name in ORDER if name in result)
    return (Score(yaku, han_for(yaku, True), 25, True, kind='chiitoitsu', dora=context.dora),)


def score_hand(hand: Iterable[int], context: Context, melds: Iterable[Group] = ()) -> tuple[Score, ...]:
    """Return all highest-scoring interpretations, with deterministic ordering."""
    hand, melds = tuple(hand), tuple(melds)
    if any(not group.fixed for group in melds) or len(melds) > 4:
        raise ValueError('Only declared fixed melds belong in melds')
    if len(hand) != 13 - 3 * len(melds):
        raise ValueError('hand must be the concealed tiles BEFORE winning')
    if any(tile not in range(34) for tile in hand):
        raise ValueError('Invalid tile number')
    completed = hand + (context.win,)
    physical = completed + tuple(tile for group in melds for tile in group.tiles)
    validate_inventory(physical, melds, context)
    if max(Counter(physical).values()) > 4:
        raise ValueError('More than four physical copies, including fixed melds')
    if context.riichi and any(group.open for group in melds):
        raise ValueError('Open hand cannot declare riichi')
    if context.riichi == 2 and context.ippatsu and melds:
        raise ValueError('First-discard double-riichi ippatsu cannot include own kans/calls')
    if context.event == 'chankan' and Counter(physical)[context.win] != 1:
        raise ValueError('Opponent kakan/ankan requires the other three copies')
    if context.first_turn and (melds or context.riichi):
        raise ValueError('First-turn hand cannot already have melds or riichi')
    counts = tuple(Counter(completed)[tile] for tile in range(34))
    candidates = list(special_scores(completed, context)) if not melds else []
    for pair, groups in standard_decompositions(counts, melds):
        slots = [-1] if pair == context.win else []
        slots += [index for index, group in enumerate(groups) if not group.fixed and context.win in group.tiles]
        for slot in slots:
            try:
                candidate = evaluate_shape(groups, pair, slot, context)
            except ValueError:
                continue
            if candidate.yaku or candidate.yakuman:
                candidates.append(candidate)
    if not candidates:
        return ()
    # Natural yakuman suppress ordinary roles across ALL interpretations,
    # including the corner case where dora would make another decomposition
    # a counted yakuman with the same payment.
    if any(candidate.yakuman for candidate in candidates):
        candidates = [candidate for candidate in candidates if candidate.yakuman]
    key = max(candidate.comparison_key for candidate in candidates)
    # Equal (base points, raw han, fu) may still have different yaku lists.
    # Retain every tie rather than make the theory count depend on DFS order.
    seen = set()
    best = []
    for candidate in candidates:
        signature = (candidate.yaku, candidate.yakuman, candidate.fu)
        if candidate.comparison_key == key and signature not in seen:
            best.append(candidate)
            seen.add(signature)
    return tuple(best)


@lru_cache(maxsize=65536)
def waits(hand: tuple[int, ...], melds: tuple[Group, ...] = (), players: int = 4) -> frozenset[int]:
    """Structural waits, independent of yaku, payments and ron restrictions."""
    if len(hand) != 13 - 3 * len(melds):
        raise ValueError('Wait input must be a before-win hand')
    rules = get_rules(players)
    if any(t not in rules.available_tiles for t in hand + tuple(t for g in melds for t in g.tiles)):
        raise ValueError('Wait input contains an unavailable tile')
    if not rules.allow_chi and any(g.open and g.sequence for g in melds):
        raise ValueError('Chi is forbidden in three-player waits')
    full_counts = Counter(hand + tuple(tile for group in melds for tile in group.tiles))
    result = set()
    concealed = Counter(hand)
    for win in rules.available_tiles:
        if full_counts[win] >= 4:
            continue
        counts = tuple(concealed[tile] + int(tile == win) for tile in range(34))
        if standard_decompositions(counts, melds):
            result.add(win)
        if not melds:
            nonzero = [count for count in counts if count]
            if nonzero == [2] * 7 or (set(tile for tile, count in enumerate(counts) if count) == ORPHANS and sorted(nonzero) == [1] * 12 + [2]):
                result.add(win)
    return frozenset(result)


def context_from_dict(data: dict) -> Context:
    return Context(win=one_tile(data['win']), tsumo=data.get('tsumo', False),
                   seat=one_tile(data.get('seat', '1z')), round_wind=one_tile(data.get('round_wind', '1z')),
                   riichi=data.get('riichi', 0), ippatsu=data.get('ippatsu', False),
                   event=data.get('event', 'none'), first_turn=data.get('first_turn', False), dora=data.get('dora', 0),
                   players=data.get('players', 4), north_count=data.get('north_count', 0),
                   win_source=data.get('win_source', 'auto'), live_tiles=data.get('live_tiles'))


def score_request(data: dict) -> dict:
    hand = parse_tiles(data['hand'])
    context = context_from_dict(data)
    melds = tuple(parse_meld(record) for record in data.get('melds', []))
    best = score_hand(hand, context, melds)
    return {'legal_win': bool(best), 'selection': 'maximum(base_points, raw_han, fu); retain exact ties',
            'results': [candidate.to_dict() for candidate in best]}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', nargs='?', type=Path, help='JSON input; defaults to stdin')
    args = parser.parse_args()
    try:
        data = json.loads(args.input.read_text() if args.input else sys.stdin.read())
        result = score_request(data)
    except (ValueError, KeyError, TypeError) as error:
        parser.exit(2, str(error) + '\n')
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
