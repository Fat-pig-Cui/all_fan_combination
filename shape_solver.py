"""Finite structural constraint model; enumerate projected yaku sets with Z3.

The model produces four-meld/pair or seven-pair witnesses, not subsets of
the old project's conflict chart.  Python calc_fan independently validates
the witness and all competing decompositions before a projection is kept.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import z3

from calc_fan import Context, Group, ORDER, DRAGONS, WINDS, HONORS, TERMINALS, GREEN, ORPHANS


EVENTS = ('none', 'chankan', 'rinshan', 'haitei', 'houtei')


def either(items):
    return z3.Or(list(items))


def every(items):
    return z3.And(list(items))


def isum(items):
    return z3.Sum(list(items))


def member(tile, values):
    return either(tile == value for value in values)


def count_true(items):
    return isum(z3.If(item, 1, 0) for item in items)


@dataclass(frozen=True)
class Witness:
    hand: tuple[int, ...]
    melds: tuple[Group, ...]
    context: Context
    closed: bool
    mask: int
    groups: tuple[Group, ...] = ()
    pair: Optional[int] = None
    win_group: int = -1
    kind: str = 'standard'


class ShapeSolver:
    def __init__(self, *, timeout_ms=0, closed=None, kind=None, context=None, seed=0):
        self.solver = z3.Solver()
        self.solver.set(random_seed=seed)
        if timeout_ms:
            self.solver.set(timeout=timeout_ms)
        add = self.solver.add
        self.kind = z3.Int('kind')  # 0 standard, 1 seven pairs
        self.pair = z3.Int('pair')
        self.tile = [z3.Int('tile_' + str(i)) for i in range(4)]
        self.seq = [z3.Bool('seq_' + str(i)) for i in range(4)]
        self.open = [z3.Bool('open_' + str(i)) for i in range(4)]
        self.kan = [z3.Bool('kan_' + str(i)) for i in range(4)]
        self.pairs = [z3.Int('seven_pair_' + str(i)) for i in range(7)]
        self.win = z3.Int('win')
        self.win_group = z3.Int('win_group')
        self.delta = z3.Int('win_offset')
        self.tsumo = z3.Bool('tsumo')
        self.seat = z3.Int('seat')
        self.round = z3.Int('round_wind')
        self.riichi = z3.Int('riichi')
        self.ippatsu = z3.Bool('ippatsu')
        self.event = z3.Int('event')
        self.closed = z3.Bool('closed')
        standard, seven = self.kind == 0, self.kind == 1
        add(member(self.kind, (0, 1)), self.pair >= 0, self.pair < 34,
            self.win >= 0, self.win < 34, self.delta >= 0, self.delta <= 2,
            self.seat >= 27, self.seat <= 30, self.round >= 27, self.round <= 29,
            self.riichi >= 0, self.riichi <= 2, self.event >= 0, self.event <= 4)
        if closed is not None:
            add(self.closed == closed)
        if kind is not None:
            add(self.kind == (0 if kind == 'standard' else 1))
        if context is not None:
            for name in ('tsumo', 'riichi', 'ippatsu'):
                add(getattr(self, name) == getattr(context, name))
            add(self.event == EVENTS.index(context.event))

        keys = []
        for i in range(4):
            add(self.tile[i] >= 0, self.tile[i] < 34)
            add(z3.Implies(self.seq[i], z3.And(self.tile[i] < 27, self.tile[i] % 9 <= 6, z3.Not(self.kan[i]))))
            add(z3.Implies(seven, z3.And(self.tile[i] == 0, z3.Not(self.seq[i]), z3.Not(self.open[i]), z3.Not(self.kan[i]))))
            keys.append(self.tile[i] * 8 + z3.If(self.seq[i], 4, 0) + z3.If(self.open[i], 2, 0) + z3.If(self.kan[i], 1, 0))
        add(z3.Implies(standard, every(keys[i] <= keys[i + 1] for i in range(3))))
        add(self.closed == z3.Or(seven, every(z3.Not(flag) for flag in self.open)))
        for i in range(7):
            add(self.pairs[i] >= 0, self.pairs[i] < 34)
            add(z3.Implies(standard, self.pairs[i] == 0))
        add(z3.Implies(seven, every(self.pairs[i] < self.pairs[i + 1] for i in range(6))))
        add(z3.Implies(seven, z3.And(member(self.win, self.pairs), self.pair == self.pairs[0], self.win_group == -1, self.delta == 0)))
        slots = [z3.And(self.win_group == -1, self.win == self.pair, self.delta == 0)]
        for i in range(4):
            slots.append(z3.And(self.win_group == i, z3.Not(self.open[i]), z3.Not(self.kan[i]),
                                self.win == self.tile[i] + z3.If(self.seq[i], self.delta, 0),
                                z3.Implies(z3.Not(self.seq[i]), self.delta == 0)))
        add(z3.Implies(standard, either(slots)))

        def physical_count(tile):
            return z3.If(standard,
                         2 * z3.If(self.pair == tile, 1, 0) + isum(
                             z3.If(self.seq[i], z3.If(z3.And(tile >= self.tile[i], tile <= self.tile[i] + 2), 1, 0),
                                   z3.If(self.tile[i] == tile, z3.If(self.kan[i], 4, 3), 0)) for i in range(4)),
                         2 * count_true(self.pairs[i] == tile for i in range(7)))
        self.counts = [physical_count(tile) for tile in range(34)]
        add(every(count <= 4 for count in self.counts))
        win_copies = physical_count(self.win)
        kans = count_true(self.kan)
        nseq = count_true(self.seq)
        concealed = count_true(z3.And(z3.Not(self.seq[i]), z3.Not(self.open[i]), z3.Or(self.tsumo, self.win_group != i)) for i in range(4))
        add(z3.Implies(self.riichi > 0, self.closed), z3.Implies(self.ippatsu, self.riichi > 0),
            z3.Implies(member(self.event, (1, 4)), z3.Not(self.tsumo)),
            z3.Implies(member(self.event, (2, 3)), self.tsumo),
            z3.Implies(self.event == 1, z3.And(standard, win_copies == 1)),
            z3.Implies(self.event == 2, z3.And(standard, kans > 0, z3.Not(self.ippatsu))),
            z3.Implies(self.event == 4, z3.Not(self.ippatsu)),
            z3.Implies(z3.And(self.riichi == 2, self.ippatsu), z3.And(kans == 0, z3.Not(member(self.event, (1, 3))))))

        def has_triplet(tile):
            return z3.And(standard, either(z3.And(z3.Not(self.seq[i]), self.tile[i] == tile) for i in range(4)))

        def has_sequence(tile):
            return z3.And(standard, either(z3.And(self.seq[i], self.tile[i] == tile) for i in range(4)))

        def only(values):
            return every(self.counts[tile] == 0 for tile in range(34) if tile not in values)

        # Every natural yakuman is excluded using the actual tile inventory,
        # winning-group assignment and hidden/open status.
        add(z3.Not(only(HONORS)), z3.Not(only(GREEN)), z3.Not(only(TERMINALS)))
        add(z3.Implies(standard, z3.And(
            concealed < 4, kans < 4,
            z3.Not(every(has_triplet(tile) for tile in DRAGONS)),
            z3.Not(every(has_triplet(tile) for tile in WINDS)),
            z3.Not(z3.And(member(self.pair, WINDS), count_true(has_triplet(tile) for tile in WINDS) == 3)))))
        nine_gates = []
        for suit in range(3):
            offset = 9 * suit
            nine_gates.append(z3.And(self.closed, standard, kans == 0,
                                    self.counts[offset] >= 3, self.counts[offset + 8] >= 3,
                                    every(self.counts[offset + rank] >= 1 for rank in range(1, 8))))
        add(z3.Not(either(nine_gates)))

        role = {}
        role['menzen_tsumo'] = z3.And(self.closed, self.tsumo)
        role['riichi'] = self.riichi == 1
        role['double_riichi'] = self.riichi == 2
        role['ippatsu'] = self.ippatsu
        for number, event in enumerate(EVENTS[1:], 1):
            role[event] = self.event == number
        for tile, name in ((31, 'haku'), (32, 'hatsu'), (33, 'chun'), (self.seat, 'seat_wind'), (self.round, 'round_wind')):
            role[name] = has_triplet(tile)
        role['tanyao'] = only(set(range(34)) - ORPHANS)
        role['chiitoitsu'] = seven
        matches = [[z3.And(self.seq[i], self.seq[j], self.tile[i] == self.tile[j]) for j in range(4)] for i in range(4)]
        dup_pairings = either(z3.And(matches[a][b], matches[c][d]) for a, b, c, d in ((0, 1, 2, 3), (0, 2, 1, 3), (0, 3, 1, 2)))
        one_dup = either(matches[i][j] for i in range(4) for j in range(i + 1, 4))
        role['ryanpeikou'] = z3.And(standard, self.closed, dup_pairings)
        role['iipeikou'] = z3.And(standard, self.closed, one_dup, z3.Not(dup_pairings))
        ryanmen = either(z3.And(self.win_group == i, self.seq[i],
                               z3.Or(z3.And(self.delta == 0, self.tile[i] % 9 < 6),
                                     z3.And(self.delta == 2, self.tile[i] % 9 > 0))) for i in range(4))
        value_pair = z3.Or(member(self.pair, DRAGONS), self.pair == self.seat, self.pair == self.round)
        role['pinfu'] = z3.And(standard, self.closed, nseq == 4, z3.Not(value_pair), ryanmen)
        role['sankantsu'] = z3.And(standard, kans == 3)
        role['toitoi'] = z3.And(standard, nseq == 0)
        role['sanankou'] = z3.And(standard, concealed == 3)
        role['shousangen'] = z3.And(standard, member(self.pair, DRAGONS), count_true(has_triplet(tile) for tile in DRAGONS) == 2)
        role['honroutou'] = only(ORPHANS)
        all_terminal_groups = every(z3.If(self.seq[i], member(self.tile[i] % 9, (0, 6)), member(self.tile[i], ORPHANS)) for i in range(4))
        has_honor = either(self.counts[tile] > 0 for tile in HONORS)
        outside = z3.And(standard, nseq > 0, member(self.pair, ORPHANS), all_terminal_groups)
        role['chanta'] = z3.And(outside, has_honor)
        role['junchan'] = z3.And(outside, z3.Not(has_honor))
        one_suit = count_true(either(self.counts[suit * 9 + rank] > 0 for rank in range(9)) for suit in range(3)) == 1
        role['honitsu'] = z3.And(one_suit, has_honor)
        role['chinitsu'] = z3.And(one_suit, z3.Not(has_honor))
        role['ittsuu'] = either(every(has_sequence(suit * 9 + rank) for rank in (0, 3, 6)) for suit in range(3))
        role['sanshoku_doujun'] = either(every(has_sequence(suit * 9 + rank) for suit in range(3)) for rank in range(7))
        role['sanshoku_doukou'] = either(every(has_triplet(suit * 9 + rank) for suit in range(3)) for rank in range(9))
        self.yaku = [z3.Bool('yaku_' + name) for name in ORDER]
        add(*(flag == role[name] for flag, name in zip(self.yaku, ORDER)))
        add(either(self.yaku))
        self.decision_vars = [self.kind, self.pair, self.win, self.win_group, self.delta,
                              self.tsumo, self.seat, self.round, self.riichi, self.ippatsu, self.event]
        self.decision_vars += self.tile + self.seq + self.open + self.kan + self.pairs

    def check(self):
        return self.solver.check()

    def decode(self, model=None) -> Witness:
        model = model if model is not None else self.solver.model()
        integer = lambda expr: model.eval(expr, model_completion=True).as_long()
        boolean = lambda expr: z3.is_true(model.eval(expr, model_completion=True))
        context = Context(win=integer(self.win), tsumo=boolean(self.tsumo), seat=integer(self.seat),
                          round_wind=integer(self.round), riichi=integer(self.riichi),
                          ippatsu=boolean(self.ippatsu), event=EVENTS[integer(self.event)])
        mask = sum((1 << i) for i, flag in enumerate(self.yaku) if boolean(flag))
        closed = boolean(self.closed)
        if integer(self.kind) == 1:
            completed = tuple(tile for expr in self.pairs for tile in (integer(expr), integer(expr)))
            hand = list(completed)
            hand.remove(context.win)
            return Witness(tuple(hand), (), context, True, mask, kind='chiitoitsu')
        groups = tuple(Group(integer(self.tile[i]), boolean(self.seq[i]), boolean(self.open[i]), boolean(self.kan[i])) for i in range(4))
        pair = integer(self.pair)
        melds = tuple(group for group in groups if group.fixed)
        completed = tuple(tile for group in groups if not group.fixed for tile in group.tiles) + (pair, pair)
        hand = list(completed)
        hand.remove(context.win)
        return Witness(tuple(hand), melds, context, closed, mask, groups, pair, integer(self.win_group))

    def block_projection(self, closed: bool, mask: int):
        self.solver.add(z3.Or(self.closed != closed, *(flag != bool(mask & (1 << i)) for i, flag in enumerate(self.yaku))))

    def block_model(self, model=None):
        model = model if model is not None else self.solver.model()
        self.solver.add(z3.Or(*(variable != model.eval(variable, model_completion=True) for variable in self.decision_vars)))

    def block_rejected_hand(self, witness: Witness):
        """Reject only this projection for this hand/context, not other sets.

        The Python evaluator checks ALL decompositions.  A rejected target
        cannot be recovered merely by assigning its winning tile to another
        group of the same physical hand and declared melds.
        """
        from collections import Counter
        physical = Counter(witness.hand + (witness.context.win,) + tuple(tile for group in witness.melds for tile in group.tiles))
        different = [self.closed != witness.closed]
        different += [flag != bool(witness.mask & (1 << i)) for i, flag in enumerate(self.yaku)]
        different += [count != physical[tile] for tile, count in enumerate(self.counts)]
        context = witness.context
        different += [self.win != context.win, self.tsumo != context.tsumo, self.seat != context.seat,
                      self.round != context.round_wind, self.riichi != context.riichi,
                      self.ippatsu != context.ippatsu, self.event != EVENTS.index(context.event)]
        fixed_count = count_true(z3.Or(self.open[i], self.kan[i]) for i in range(4))
        different.append(fixed_count != len(witness.melds))
        for group, multiplicity in Counter(witness.melds).items():
            matching = count_true(z3.And(self.tile[i] == group.tile, self.seq[i] == group.sequence,
                                         self.open[i] == group.open, self.kan[i] == group.kan) for i in range(4))
            different.append(matching != multiplicity)
        self.solver.add(z3.Or(different))

    def require_yaku(self, names, *, exact=False):
        names = set(names)
        for name, flag in zip(ORDER, self.yaku):
            if name in names or exact:
                self.solver.add(flag == (name in names))

    def forbid(self, names):
        for name, flag in zip(ORDER, self.yaku):
            if name in names:
                self.solver.add(z3.Not(flag))
