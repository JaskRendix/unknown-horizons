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


from unittest.mock import MagicMock

import pytest

from horizons.world.disaster.disastermanager import DisasterManager


class DummySettlement:
    pass


class DummyDisaster:
    TYPE = "dummy"
    SEED_CHANCE = 1.0

    def __init__(self, settlement, manager):
        self.settlement = settlement
        self.manager = manager
        self.breakout = MagicMock()
        self.end = MagicMock()
        self.save = MagicMock()
        self.load = MagicMock()

    @classmethod
    def can_breakout(cls, settlement):
        return True


class DummyDisasterNoBreakout(DummyDisaster):
    TYPE = "no_breakout"

    @classmethod
    def can_breakout(cls, settlement):
        return False


class FakeDB:
    def __init__(self, results=None):
        self.results = results or {}
        self.calls = []

    def __call__(self, query, *args):
        self.calls.append((query, args))

        for key, value in self.results.items():
            if key in query:
                return value
        return []


@pytest.fixture
def settlement():
    return DummySettlement()


@pytest.fixture
def session(settlement):
    session = MagicMock()

    session.world.settlements = [settlement]

    session.random.random.return_value = 0.0

    return session


@pytest.fixture
def scheduler_mock(monkeypatch):
    scheduler = MagicMock()

    import horizons.world.disaster.disastermanager as dm

    monkeypatch.setattr(dm, "Scheduler", lambda: scheduler)

    return scheduler


@pytest.fixture
def manager(session, scheduler_mock):
    mgr = DisasterManager(session)
    mgr.disasters = [DummyDisaster]
    return mgr


def test_registers_periodic_scheduler(session, scheduler_mock):
    DisasterManager(session)

    scheduler_mock.add_new_object.assert_called_once()

    args, kwargs = scheduler_mock.add_new_object.call_args

    assert kwargs["run_in"] == DisasterManager.CALL_EVERY
    assert kwargs["loops"] == -1


def test_initial_state(manager):
    assert manager._active_disaster == {}


def test_run_seeds_disaster(manager, settlement):
    manager.run()

    assert settlement in manager._active_disaster

    disaster = manager._active_disaster[settlement]
    disaster.breakout.assert_called_once()


def test_run_does_nothing_when_disabled(session, scheduler_mock):
    mgr = DisasterManager(session, disabled=True)
    mgr.disasters = [DummyDisaster]

    mgr.run()

    assert mgr._active_disaster == {}


def test_run_skips_if_disaster_cannot_breakout(session, scheduler_mock,
                                               settlement):
    mgr = DisasterManager(session)
    mgr.disasters = [DummyDisasterNoBreakout]

    mgr.run()

    assert settlement not in mgr._active_disaster


def test_run_does_not_seed_when_probability_fails(
    session,
    scheduler_mock,
    settlement
):
    session.random.random.return_value = 1.0

    class RareDisaster(DummyDisaster):
        SEED_CHANCE = 0.5

    mgr = DisasterManager(session)
    mgr.disasters = [RareDisaster]

    mgr.run()

    assert settlement not in mgr._active_disaster


def test_run_does_not_create_second_disaster(manager, settlement):
    manager.run()

    first = manager._active_disaster[settlement]

    manager.run()

    assert manager._active_disaster[settlement] is first


def test_save_persists_remaining_ticks(manager, scheduler_mock, settlement):
    manager.run()

    scheduler_mock.get_remaining_ticks.return_value = 123

    db = FakeDB()

    manager.save(db)

    insert_calls = [
        c for c in db.calls
        if "INSERT INTO disaster_manager" in c[0]
    ]

    assert len(insert_calls) == 1

    manager._active_disaster[settlement].save.assert_called_once_with(db)


def test_load_restores_scheduler(session, scheduler_mock):
    mgr = DisasterManager(session)

    db = FakeDB({
        "SELECT remaining_ticks FROM disaster_manager": [(42,)],
        "SELECT rowid, type, settlement FROM disaster": [],
    })

    mgr.load(db)

    scheduler_mock.rem_all_classinst_calls.assert_called_once_with(mgr)

    scheduler_mock.add_new_object.assert_called_with(
        mgr.run,
        mgr,
        run_in=42,
        loop_interval=DisasterManager.CALL_EVERY,
        loops=-1,
    )


def test_load_restores_disasters(monkeypatch, session, scheduler_mock):
    settlement = DummySettlement()

    import horizons.world.disaster.disastermanager as dm

    worldobj = MagicMock()
    worldobj.get_object_by_id.return_value = settlement

    monkeypatch.setattr(dm, "WorldObject", worldobj)

    mgr = DisasterManager(session)
    mgr.disasters = [DummyDisaster]

    db = FakeDB({
        "SELECT remaining_ticks FROM disaster_manager": [],
        "SELECT rowid, type, settlement FROM disaster": [
            (5, "dummy", 99),
        ],
    })

    mgr.load(db)

    assert settlement in mgr._active_disaster

    restored = mgr._active_disaster[settlement]

    restored.load.assert_called_once_with(db, 5)


def test_end_disaster(manager, settlement):
    manager.run()

    disaster = manager._active_disaster[settlement]

    manager.end_disaster(settlement)

    disaster.end.assert_called_once()

    assert settlement not in manager._active_disaster


def test_is_affected_false(manager, settlement):
    assert manager.is_affected(settlement) is False


def test_is_affected_true(manager, settlement):
    manager.run()

    assert manager.is_affected(settlement) is True


def test_get_disaster_returns_none_when_not_active(manager, settlement):
    assert manager.get_disaster(settlement) is None


def test_get_disaster_returns_disaster(manager, settlement):
    manager.run()

    disaster = manager.get_disaster(settlement)

    assert disaster is manager._active_disaster[settlement]


@pytest.mark.parametrize(
    "chance,random_value,expected",
    [
        (1.0, 0.0, True),
        (0.5, 0.5, True),
        (0.5, 0.9, False),
        (0.0, 0.0, True),
        (0.0, 0.1, False),
    ],
)
def test_seed_probability(
    session,
    scheduler_mock,
    settlement,
    chance,
    random_value,
    expected,
):
    class ProbDisaster(DummyDisaster):
        SEED_CHANCE = chance

    session.random.random.return_value = random_value

    mgr = DisasterManager(session)
    mgr.disasters = [ProbDisaster]

    mgr.run()

    assert (settlement in mgr._active_disaster) is expected


def test_load_without_scheduler_state(session, scheduler_mock):
    mgr = DisasterManager(session)

    db = FakeDB({
        "SELECT remaining_ticks FROM disaster_manager": [],
        "SELECT rowid, type, settlement FROM disaster": [],
    })

    mgr.load(db)

    scheduler_mock.rem_all_classinst_calls.assert_not_called()

    add_calls = [
        call for call in scheduler_mock.add_new_object.call_args_list
        if call.kwargs.get("loop_interval") == DisasterManager.CALL_EVERY
    ]

    assert not add_calls


def test_save_without_active_disasters(manager, scheduler_mock):
    scheduler_mock.get_remaining_ticks.return_value = 88

    db = FakeDB()

    manager.save(db)

    insert_calls = [
        c for c in db.calls
        if "INSERT INTO disaster_manager" in c[0]
    ]

    assert len(insert_calls) == 1


def test_load_unknown_disaster_type_raises(
    monkeypatch,
    session,
    scheduler_mock,
):
    settlement = DummySettlement()

    import horizons.world.disaster.disastermanager as dm

    worldobj = MagicMock()
    worldobj.get_object_by_id.return_value = settlement

    monkeypatch.setattr(dm, "WorldObject", worldobj)

    mgr = DisasterManager(session)
    mgr.disasters = [DummyDisaster]

    db = FakeDB({
        "SELECT remaining_ticks FROM disaster_manager": [],
        "SELECT rowid, type, settlement FROM disaster": [
            (1, "totally_unknown", 5),
        ],
    })

    with pytest.raises(StopIteration):
        mgr.load(db)


def test_run_handles_multiple_settlements(session, scheduler_mock):
    s1 = DummySettlement()
    s2 = DummySettlement()

    session.world.settlements = [s1, s2]

    mgr = DisasterManager(session)
    mgr.disasters = [DummyDisaster]

    mgr.run()

    assert s1 in mgr._active_disaster
    assert s2 in mgr._active_disaster


def test_run_only_seeds_unaffected_settlements(session, scheduler_mock):
    s1 = DummySettlement()
    s2 = DummySettlement()

    session.world.settlements = [s1, s2]

    mgr = DisasterManager(session)
    mgr.disasters = [DummyDisaster]

    existing = DummyDisaster(s1, mgr)
    mgr._active_disaster[s1] = existing

    mgr.run()

    assert mgr._active_disaster[s1] is existing
    assert s2 in mgr._active_disaster


def test_run_uses_second_disaster_when_first_cannot_breakout(
    session,
    scheduler_mock,
    settlement,
):
    class FirstDisaster(DummyDisaster):
        TYPE = "first"

        @classmethod
        def can_breakout(cls, settlement):
            return False

    class SecondDisaster(DummyDisaster):
        TYPE = "second"

    mgr = DisasterManager(session)
    mgr.disasters = [FirstDisaster, SecondDisaster]

    mgr.run()

    disaster = mgr._active_disaster[settlement]

    assert isinstance(disaster, SecondDisaster)


def test_load_restores_multiple_disasters(
    monkeypatch,
    session,
    scheduler_mock,
):
    s1 = DummySettlement()
    s2 = DummySettlement()

    import horizons.world.disaster.disastermanager as dm

    worldobj = MagicMock()
    worldobj.get_object_by_id.side_effect = lambda obj_id: {
        10: s1,
        20: s2,
    }[obj_id]

    monkeypatch.setattr(dm, "WorldObject", worldobj)

    mgr = DisasterManager(session)
    mgr.disasters = [DummyDisaster]

    db = FakeDB({
        "SELECT remaining_ticks FROM disaster_manager": [],
        "SELECT rowid, type, settlement FROM disaster": [
            (1, "dummy", 10),
            (2, "dummy", 20),
        ],
    })

    mgr.load(db)

    assert s1 in mgr._active_disaster
    assert s2 in mgr._active_disaster
