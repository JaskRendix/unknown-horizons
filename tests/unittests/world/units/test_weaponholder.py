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

from unittest.mock import MagicMock, patch

import pytest

from horizons.world.units.weapon import (
    SetStackableWeaponNumberError,
)
from horizons.world.units.weaponholder import (
    MovingWeaponHolder,
    StationaryWeaponHolder,
    WeaponHolder,
)


class DummyWeaponHolder(WeaponHolder):
    def __init__(self):
        self.session = MagicMock()

        self.position = MagicMock()
        self.position.center = MagicMock()

        self.owner = MagicMock()

        self.add_storage_modified_listener = MagicMock()
        self.remove_storage_modified_listener = MagicMock()

        self.on_storage_modified = MagicMock()
        self.on_user_attack_issued = MagicMock()

        self.try_attack_target = MagicMock()

        super().__init__()

    def remove(self):
        pass

    def get_status(self):
        return "idle"


class DummyMovingWeaponHolder(MovingWeaponHolder):
    def __init__(self):
        self.session = MagicMock()

        self.position = MagicMock()
        self.position.center = MagicMock()

        self.owner = MagicMock()

        self.add_storage_modified_listener = MagicMock()
        self.remove_storage_modified_listener = MagicMock()

        self.add_component = MagicMock()
        self.get_component = MagicMock()
        self.get_component_by_name = MagicMock()

        self.on_storage_modified = MagicMock()
        self.on_user_move_issued = MagicMock()
        self.on_user_attack_issued = MagicMock()

        self._move_tick = MagicMock()

        super().__init__()


@pytest.fixture
def holder():
    with patch(
        "horizons.world.units.weaponholder.Scheduler"
    ):
        return DummyWeaponHolder()


@pytest.fixture
def moving_holder():
    with (
        patch("horizons.world.units.weaponholder.Scheduler"),
        patch("horizons.world.units.weaponholder.HoldGroundStance"),
        patch("horizons.world.units.weaponholder.AggressiveStance"),
        patch("horizons.world.units.weaponholder.NoneStance"),
        patch("horizons.world.units.weaponholder.FleeStance"),
    ):
        return DummyMovingWeaponHolder()


def test_create_weapon_storage(holder):
    holder.create_weapon_storage()

    assert holder._weapon_storage == []
    assert holder._fireable == []
    assert holder.total_number_of_weapons == 30


def test_update_range_empty_storage(holder):
    holder._weapon_storage = []

    holder.update_range()

    assert holder._min_range == 0
    assert holder._max_range == 0


def test_update_range_populated(holder):
    w1 = MagicMock()
    w1.get_minimum_range.return_value = 5
    w1.get_maximum_range.return_value = 10

    w2 = MagicMock()
    w2.get_minimum_range.return_value = 1
    w2.get_maximum_range.return_value = 20

    holder._weapon_storage = [w1, w2]

    holder.update_range()

    assert holder._min_range == 1
    assert holder._max_range == 20


def test_add_to_fireable(holder):
    weapon = MagicMock()

    holder._fireable = []

    holder._add_to_fireable(weapon)

    assert holder._fireable == [weapon]


@patch("horizons.world.units.weaponholder.Callback")
@patch("horizons.world.units.weaponholder.Scheduler")
def test_remove_from_fireable(
    scheduler_cls,
    callback_cls,
    holder,
):
    holder._remove_from_fireable(MagicMock())

    scheduler_cls.return_value.add_new_object.assert_called_once()


def test_increase_fired_weapons_number(holder):
    holder._fired_weapons_number = 0

    holder._increase_fired_weapons_number()

    assert holder._fired_weapons_number == 1


def test_add_weapon_storage_full(holder):
    holder.equipped_weapon_number = holder.total_number_of_weapons

    assert holder.add_weapon_to_storage(1) is False


@patch("horizons.world.units.weaponholder.Weapon")
def test_add_non_stackable_weapon(
    weapon_cls,
    holder,
):
    holder.session.db.get_weapon_stackable.return_value = False

    weapon = MagicMock()
    weapon_cls.return_value = weapon

    assert holder.add_weapon_to_storage(1) is True

    assert weapon in holder._weapon_storage


def test_stackable_increases_existing_weapon(holder):
    holder.session.db.get_weapon_stackable.return_value = True

    stack = MagicMock()
    stack.weapon_id = 1

    holder._weapon_storage = [stack]

    holder.add_weapon_to_storage(1)

    stack.increase_number_of_weapons.assert_called_once_with(1)


@patch("horizons.world.units.weaponholder.StackableWeapon")
def test_stackable_creates_new_stack_when_full(
    stack_cls,
    holder,
):
    holder.session.db.get_weapon_stackable.return_value = True

    old_stack = MagicMock()
    old_stack.weapon_id = 1

    old_stack.increase_number_of_weapons.side_effect = (
        SetStackableWeaponNumberError
    )

    holder._weapon_storage = [old_stack]

    holder.add_weapon_to_storage(1)

    stack_cls.assert_called_once()


def test_remove_weapon_not_present(holder):
    assert holder.remove_weapon_from_storage(1) is False


def test_remove_non_stackable_weapon(holder):
    holder.session.db.get_weapon_stackable.return_value = False

    weapon = MagicMock()
    weapon.weapon_id = 1

    holder._weapon_storage = [weapon]
    holder._fireable = [weapon]
    holder.equipped_weapon_number = 1

    assert holder.remove_weapon_from_storage(1) is True

    assert weapon not in holder._weapon_storage


def test_remove_stackable_weapon_decrements(holder):
    holder.session.db.get_weapon_stackable.return_value = True

    weapon = MagicMock()
    weapon.weapon_id = 1

    holder._weapon_storage = [weapon]
    holder.equipped_weapon_number = 1

    holder.remove_weapon_from_storage(1)

    weapon.decrease_number_of_weapons.assert_called_once_with(1)


def test_attack_in_range_no_target(holder):
    holder._target = None

    assert holder.attack_in_range() is False


@pytest.mark.parametrize(
    "distance,expected",
    [
        (1, False),
        (5, True),
        (10, True),
        (11, False),
    ],
)
def test_attack_in_range(
    holder,
    distance,
    expected,
):
    holder._min_range = 5
    holder._max_range = 10

    target = MagicMock()
    target.position.center = MagicMock()

    holder.position.distance.return_value = distance

    holder._target = target

    assert holder.attack_in_range() is expected


def test_can_attack_position_no_fireable(holder):
    holder._fireable = []

    assert holder.can_attack_position(MagicMock()) is False


@pytest.mark.parametrize(
    "distance,expected",
    [
        (0, False),
        (5, True),
        (10, True),
        (11, False),
    ],
)
def test_can_attack_position(
    holder,
    distance,
    expected,
):
    holder._fireable = [MagicMock()]
    holder._min_range = 5
    holder._max_range = 10

    holder.position.distance.return_value = distance

    pos = MagicMock()
    pos.center = MagicMock()

    assert holder.can_attack_position(pos) is expected


def test_remove_target(holder):
    holder._target = MagicMock()

    holder.remove_target()

    assert holder._target is None


@pytest.mark.parametrize(
    "target,expected",
    [
        (None, False),
        (object(), True),
    ]
)
def test_is_attacking(holder, target, expected):
    holder._target = target

    assert holder.is_attacking() is expected


def test_stop_attack(holder):
    target = MagicMock()

    holder._target = target

    holder.stop_attack()

    target.discard_remove_listener.assert_called_once()
    assert holder._target is None


def test_attack_new_target(holder):
    holder.try_attack_target = MagicMock()

    target = MagicMock()
    target.has_remove_listener.return_value = False

    holder.attack(target)

    assert holder._target is target
    target.add_remove_listener.assert_called_once_with(
        holder.remove_target
    )


def test_attack_same_target_returns(holder):
    target = MagicMock()
    target.has_remove_listener.return_value = True

    holder.try_attack_target = MagicMock()
    holder._target = target

    holder.attack(target)

    holder.try_attack_target.assert_not_called()


@patch(
    "horizons.world.units.weaponholder.WorldObject.get_object_by_id"
)
def test_user_attack(
    get_object_by_id,
    holder,
):
    target = MagicMock()

    get_object_by_id.return_value = target

    holder.attack = MagicMock()

    holder.user_attack(77)

    holder.attack.assert_called_once_with(target)
    holder.on_user_attack_issued.assert_called_once()


def test_fire_all_weapons_position_not_attackable(holder):
    holder.can_attack_position = MagicMock(
        return_value=False
    )

    holder.fire_all_weapons(MagicMock())

    assert holder._fired_weapons_number == 0


def test_fire_all_weapons(holder):
    holder.can_attack_position = MagicMock(
        return_value=True
    )

    dest = MagicMock()

    weapon1 = MagicMock()
    weapon2 = MagicMock()

    holder.position.center = MagicMock()

    holder._fireable = [weapon1, weapon2]

    holder.fire_all_weapons(dest)

    weapon1.fire.assert_called_once()
    weapon2.fire.assert_called_once()


def test_fire_all_weapons_calls_act_attack(holder):
    holder.can_attack_position = MagicMock(return_value=True)

    holder.act_attack = MagicMock()

    weapon = MagicMock()

    def fire_side_effect(*args, **kwargs):
        holder._fired_weapons_number += 1

    weapon.fire.side_effect = fire_side_effect

    holder._fireable = [weapon]

    dest = MagicMock()

    holder.fire_all_weapons(dest)

    holder.act_attack.assert_called_once_with(dest)


@patch("horizons.world.units.weaponholder.Scheduler")
def test_try_attack_target_no_target(
    scheduler_cls,
    holder,
):
    holder._target = None

    holder.try_attack_target()

    scheduler_cls.return_value.add_new_object.assert_not_called()


@patch("horizons.world.units.weaponholder.Scheduler")
def test_stop_for(
    scheduler_cls,
    moving_holder,
):
    scheduler_cls.return_value.rem_call.return_value = True

    moving_holder.stop_for(10)

    scheduler_cls.return_value.add_new_object.assert_called_once()


def test_set_stance(moving_holder):
    old_component = MagicMock()
    old_component.get_state.return_value = "state"

    new_component = MagicMock()

    moving_holder.stance = object()

    moving_holder.get_component.side_effect = [
        old_component,
        new_component,
    ]

    new_stance = object()

    moving_holder.set_stance(new_stance)

    assert moving_holder.stance is new_stance

    new_component.set_state.assert_called_once_with(
        "state"
    )


def test_stationary_holder_instantiation():
    with patch(
        "horizons.world.units.weaponholder.HoldGroundStance"
    ):
        holder = StationaryWeaponHolder.__new__(
            StationaryWeaponHolder
        )

        holder.add_component = MagicMock()

        holder._StationaryWeaponHolder__init()

        holder.add_component.assert_called_once()
