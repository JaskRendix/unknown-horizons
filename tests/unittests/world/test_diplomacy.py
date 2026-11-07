#!/usr/bin/env python3

# ###################################################
# Copyright (C) 2008-2017 The Unknown Horizons Team
# team@unknown-horizons.org
# This file is part of Unknown Horizons.
#
# Unknown Horizons is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the
# Free Software Foundation, Inc.,
# 51 Franklin St, Fifth Floor, Boston, MA 02110-1301 USA
# ###################################################

from unittest.mock import Mock

import pytest

from horizons.world.diplomacy import Diplomacy, make_tup


class DummyPlayer:
    def __init__(self, worldid):
        self.worldid = worldid

    def __repr__(self):
        return f"Player({self.worldid})"


@pytest.fixture
def diplomacy():
    return Diplomacy()


@pytest.fixture
def players():
    return DummyPlayer(1), DummyPlayer(2), DummyPlayer(3)


@pytest.fixture
def pair(players):
    return players[0], players[1]


@pytest.fixture
def diplomacy_with_spy(monkeypatch):
    diplomacy = Diplomacy()
    diplomacy.on_diplomacy_status_changed = Mock()
    return diplomacy


def test_make_tup_orders_players(players):
    a, b, _ = players

    assert make_tup(b, a) == (a, b)
    assert make_tup(a, b) == (a, b)


def test_make_tup_same_player_returns_none(players):
    a = players[0]

    assert make_tup(a, a) is None


@pytest.mark.parametrize(
    "method,expected",
    [
        ("are_allies", False),
        ("are_enemies", False),
        ("are_neutral", True),
    ],
)
def test_default_relationship_state(diplomacy, pair, method, expected):
    a, b = pair

    result = getattr(diplomacy, method)(a, b)

    assert result is expected


def test_add_allies(diplomacy, pair):
    a, b = pair

    diplomacy.add_ally_pair(a, b)

    assert diplomacy.are_allies(a, b)
    assert not diplomacy.are_enemies(a, b)
    assert not diplomacy.are_neutral(a, b)


def test_add_ally_is_idempotent(diplomacy, pair):
    a, b = pair

    diplomacy.add_ally_pair(a, b)
    diplomacy.add_ally_pair(a, b)

    assert len(diplomacy.allies) == 1


def test_add_enemies(diplomacy, pair):
    a, b = pair

    diplomacy.add_enemy_pair(a, b)

    assert diplomacy.are_enemies(a, b)
    assert not diplomacy.are_allies(a, b)
    assert not diplomacy.are_neutral(a, b)


def test_add_enemy_is_idempotent(diplomacy, pair):
    a, b = pair

    diplomacy.add_enemy_pair(a, b)
    diplomacy.add_enemy_pair(a, b)

    assert len(diplomacy.enemies) == 1


def test_enemy_replaces_ally(diplomacy, pair):
    a, b = pair

    diplomacy.add_ally_pair(a, b)
    diplomacy.add_enemy_pair(a, b)

    assert diplomacy.are_enemies(a, b)
    assert not diplomacy.are_allies(a, b)


def test_ally_replaces_enemy(diplomacy, pair):
    a, b = pair

    diplomacy.add_enemy_pair(a, b)
    diplomacy.add_ally_pair(a, b)

    assert diplomacy.are_allies(a, b)
    assert not diplomacy.are_enemies(a, b)


def test_neutral_removes_enemy_relationship(diplomacy, pair):
    a, b = pair

    diplomacy.add_enemy_pair(a, b)
    diplomacy.add_neutral_pair(a, b)

    assert diplomacy.are_neutral(a, b)


def test_neutral_removes_ally_relationship(diplomacy, pair):
    a, b = pair

    diplomacy.add_ally_pair(a, b)
    diplomacy.add_neutral_pair(a, b)

    assert diplomacy.are_neutral(a, b)


@pytest.mark.parametrize(
    "setup,action,old_state,new_state",
    [
        (None, "add_ally_pair", "neutral", "ally"),
        (None, "add_enemy_pair", "neutral", "enemy"),
        ("ally", "add_neutral_pair", "ally", "neutral"),
        ("enemy", "add_neutral_pair", "enemy", "neutral"),
        ("ally", "add_enemy_pair", "ally", "enemy"),
        ("enemy", "add_ally_pair", "enemy", "ally"),
    ],
)
def test_event_notification(
    diplomacy_with_spy,
    pair,
    setup,
    action,
    old_state,
    new_state,
):
    a, b = pair

    if setup == "ally":
        diplomacy_with_spy.add_ally_pair(a, b)
        diplomacy_with_spy.on_diplomacy_status_changed.reset_mock()

    elif setup == "enemy":
        diplomacy_with_spy.add_enemy_pair(a, b)
        diplomacy_with_spy.on_diplomacy_status_changed.reset_mock()

    getattr(diplomacy_with_spy, action)(a, b)

    diplomacy_with_spy.on_diplomacy_status_changed.assert_called_once_with(
        old_state=old_state,
        new_state=new_state,
        a=a,
        b=b,
    )


def test_self_is_always_ally(players, diplomacy):
    a = players[0]

    assert diplomacy.are_allies(a, a)


def test_self_is_never_enemy(players, diplomacy):
    a = players[0]

    assert not diplomacy.are_enemies(a, a)


def test_self_is_never_neutral(players, diplomacy):
    a = players[0]

    assert not diplomacy.are_neutral(a, a)


def test_self_can_trade(players, diplomacy):
    a = players[0]

    assert diplomacy.can_trade(a, a)


def test_add_ally_with_same_player_does_nothing(players, diplomacy):
    a = players[0]

    diplomacy.add_ally_pair(a, a)

    assert len(diplomacy.allies) == 0


def test_add_enemy_with_same_player_does_nothing(players, diplomacy):
    a = players[0]

    diplomacy.add_enemy_pair(a, a)

    assert len(diplomacy.enemies) == 0


@pytest.mark.parametrize(
    "relationship,can_trade",
    [
        ("neutral", True),
        ("ally", True),
        ("enemy", False),
    ],
)
def test_can_trade_depends_on_enemy_status(
    diplomacy,
    pair,
    relationship,
    can_trade,
):
    a, b = pair

    if relationship == "ally":
        diplomacy.add_ally_pair(a, b)
    elif relationship == "enemy":
        diplomacy.add_enemy_pair(a, b)

    assert diplomacy.can_trade(a, b) is can_trade


def test_remove_enemy_pair(diplomacy, pair):
    a, b = pair

    diplomacy.add_enemy_pair(a, b)
    diplomacy.remove_enemy_pair(a, b)

    assert diplomacy.are_neutral(a, b)


def test_remove_ally_pair(diplomacy, pair):
    a, b = pair

    diplomacy.add_ally_pair(a, b)
    diplomacy.remove_ally_pair(a, b)

    assert diplomacy.are_neutral(a, b)


def test_removing_missing_relationship_is_safe(diplomacy, pair):
    a, b = pair

    diplomacy.remove_enemy_pair(a, b)
    diplomacy.remove_ally_pair(a, b)

    assert diplomacy.are_neutral(a, b)


@pytest.mark.parametrize(
    "setup,action",
    [
        ("ally", "add_ally_pair"),
        ("enemy", "add_enemy_pair"),
    ],
)
def test_no_event_for_duplicate_state(setup, action, pair):
    a, b = pair

    diplomacy = Diplomacy()
    diplomacy.on_diplomacy_status_changed = Mock()

    if setup == "ally":
        diplomacy.add_ally_pair(a, b)
    else:
        diplomacy.add_enemy_pair(a, b)

    diplomacy.on_diplomacy_status_changed.reset_mock()

    getattr(diplomacy, action)(a, b)

    diplomacy.on_diplomacy_status_changed.assert_not_called()


@pytest.mark.parametrize(
    "setter,checker",
    [
        ("add_ally_pair", "are_allies"),
        ("add_enemy_pair", "are_enemies"),
    ],
)
def test_relationships_are_symmetric(
    diplomacy, pair, setter, checker
):
    a, b = pair

    getattr(diplomacy, setter)(a, b)

    assert getattr(diplomacy, checker)(a, b)
    assert getattr(diplomacy, checker)(b, a)


@pytest.mark.parametrize(
    "setup",
    ["ally", "enemy"],
)
def test_neutral_clears_only_existing_relation(
    diplomacy,
    pair,
    setup,
):
    a, b = pair

    if setup == "ally":
        diplomacy.add_ally_pair(a, b)
    else:
        diplomacy.add_enemy_pair(a, b)

    diplomacy.add_neutral_pair(a, b)

    assert len(diplomacy.allies) == 0
    assert len(diplomacy.enemies) == 0


@pytest.mark.parametrize(
    "initial,target,expected_ally,expected_enemy",
    [
        ("neutral", "ally", True, False),
        ("neutral", "enemy", False, True),
        ("ally", "enemy", False, True),
        ("enemy", "ally", True, False),
        ("ally", "neutral", False, False),
        ("enemy", "neutral", False, False),
    ],
)
def test_state_transitions(
    diplomacy,
    pair,
    initial,
    target,
    expected_ally,
    expected_enemy,
):
    a, b = pair

    if initial == "ally":
        diplomacy.add_ally_pair(a, b)
    elif initial == "enemy":
        diplomacy.add_enemy_pair(a, b)

    {
        "ally": diplomacy.add_ally_pair,
        "enemy": diplomacy.add_enemy_pair,
        "neutral": diplomacy.add_neutral_pair,
    }[target](a, b)

    assert diplomacy.are_allies(a, b) is expected_ally
    assert diplomacy.are_enemies(a, b) is expected_enemy


class FakeDB:
    def __init__(self):
        self.allies = []
        self.enemies = []

    def __call__(self, query, *args):
        if query.startswith("INSERT INTO diplomacy_allies"):
            self.allies.append(args)

        elif query.startswith("INSERT INTO diplomacy_enemies"):
            self.enemies.append(args)

        elif query.startswith("SELECT player1, player2 FROM diplomacy_allies"):
            return self.allies

        elif query.startswith("SELECT player1, player2 FROM diplomacy_enemies"):
            return self.enemies

        return []


def test_save_load_roundtrip(players):
    a, b, c = players

    original = Diplomacy()
    original.add_ally_pair(a, b)
    original.add_enemy_pair(a, c)

    db = FakeDB()
    original.save(db)

    world = Mock()
    world.get_object_by_id.side_effect = {
        1: a,
        2: b,
        3: c,
    }.__getitem__

    loaded = Diplomacy()
    loaded.load(world, db)

    assert loaded.are_allies(a, b)
    assert loaded.are_enemies(a, c)
