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
    StackableWeapon,
    Weapon,
)


@pytest.fixture
def weapon_db_row():
    return [
        (
            1,          # id
            "cannon",   # type
            10,         # damage
            2,          # min_range
            8,          # max_range
            5,          # cooldown_time
            20,         # attack_speed
            1,          # attack_radius
        )
    ]


@pytest.fixture
def session(weapon_db_row):
    session = MagicMock()
    session.db.return_value = weapon_db_row
    return session


@pytest.fixture
def weapon(session):
    return Weapon(session, 1)


@pytest.fixture
def stackable_weapon(session):
    return StackableWeapon(session, 1)


def test_weapon_initialization(weapon):
    assert weapon.weapon_id == 1
    assert weapon.weapon_type == "cannon"
    assert weapon.damage == 10
    assert weapon.weapon_range == (2, 8)
    assert weapon.cooldown_time == 5
    assert weapon.attack_speed == 20
    assert weapon.attack_radius == 1
    assert weapon.attack_ready is True


def test_damage_modifier_returns_base_damage(weapon):
    assert weapon.get_damage_modifier() == 10


def test_get_minimum_range(weapon):
    assert weapon.get_minimum_range() == 2


def test_get_maximum_range(weapon):
    assert weapon.get_maximum_range() == 8


@pytest.mark.parametrize(
    "distance,expected",
    [
        (1, False),
        (2, True),
        (5, True),
        (8, True),
        (9, False),
    ],
)
def test_check_target_in_range(weapon, distance, expected):
    assert weapon.check_target_in_range(distance) is expected


def test_fire_exactly_at_min_range(weapon):
    assert weapon.check_target_in_range(
        weapon.get_minimum_range()
    )


def test_fire_exactly_at_max_range(weapon):
    assert weapon.check_target_in_range(
        weapon.get_maximum_range()
    )


def test_make_attack_ready_sets_flag_and_calls_hook(weapon):
    weapon.attack_ready = False
    weapon.on_attack_ready = MagicMock()

    weapon.make_attack_ready()

    assert weapon.attack_ready is True
    weapon.on_attack_ready.assert_called_once_with()


@patch("horizons.world.units.weapon.Scheduler")
def test_fire_does_nothing_if_not_ready(mock_scheduler, weapon):
    weapon.attack_ready = False

    destination = MagicMock()
    position = MagicMock()

    weapon.fire(destination, position)

    mock_scheduler.return_value.add_new_object.assert_not_called()


@patch("horizons.world.units.weapon.Scheduler")
def test_fire_target_out_of_range(mock_scheduler, weapon):
    destination = MagicMock()
    destination.center = MagicMock()

    position = MagicMock()
    position.distance.return_value = 999

    weapon.fire(destination, position)

    mock_scheduler.return_value.add_new_object.assert_not_called()


def test_fire_rounds_distance_before_range_check(weapon):
    destination = MagicMock()
    destination.center = MagicMock()

    position = MagicMock()
    position.distance.return_value = 2.6

    with (
        patch.object(
            weapon,
            "check_target_in_range",
            return_value=True,
        ) as check_target,
        patch("horizons.world.units.weapon.Scheduler"),
        patch("horizons.world.units.weapon.Callback"),
    ):
        weapon.fire(destination, position)

    check_target.assert_called_once_with(3)


@patch("horizons.world.units.weapon.Callback")
@patch("horizons.world.units.weapon.Scheduler")
def test_fire_schedules_impact_and_cooldown(
    mock_scheduler,
    mock_callback,
    weapon,
):
    scheduler = mock_scheduler.return_value

    destination = MagicMock()
    destination.center = MagicMock()

    position = MagicMock()
    position.distance.return_value = 4

    weapon.on_weapon_fired = MagicMock()

    weapon.fire(destination, position)

    assert scheduler.add_new_object.call_count == 2
    weapon.on_weapon_fired.assert_called_once_with()
    assert weapon.attack_ready is False


@patch("horizons.world.units.weapon.Callback")
@patch("horizons.world.units.weapon.Scheduler")
def test_fire_creates_impact_callback(
    scheduler_cls,
    callback_cls,
    weapon,
):
    destination = MagicMock()
    destination.center = MagicMock()

    position = MagicMock()
    position.distance.return_value = 5

    weapon.fire(destination, position)

    callback_cls.assert_called_once_with(
        Weapon.on_impact,
        weapon.session,
        weapon.weapon_id,
        weapon.get_damage_modifier(),
        destination,
    )


@patch("horizons.world.units.weapon.Callback")
@patch("horizons.world.units.weapon.Scheduler")
def test_fire_uses_damage_modifier(
    scheduler_cls,
    callback_cls,
    weapon,
):
    destination = MagicMock()
    destination.center = MagicMock()

    position = MagicMock()
    position.distance.return_value = 5

    with patch.object(
        weapon,
        "get_damage_modifier",
        return_value=123,
    ):
        weapon.fire(destination, position)

    callback_cls.assert_called_once_with(
        Weapon.on_impact,
        weapon.session,
        weapon.weapon_id,
        123,
        destination,
    )


@patch("horizons.world.units.weapon.Callback")
@patch("horizons.world.units.weapon.Scheduler")
def test_fire_calculates_correct_impact_time(
    mock_scheduler,
    mock_callback,
    weapon,
):
    destination = MagicMock()
    destination.center = MagicMock()

    position = MagicMock()
    position.distance.return_value = 4

    with patch(
        "horizons.world.units.weapon.GAME_SPEED.TICKS_PER_SECOND",
        10,
    ):
        weapon.fire(destination, position)

    impact_ticks = int(10 * 4 / 20)

    first_call = (
        mock_scheduler.return_value
        .add_new_object
        .call_args_list[0]
    )

    assert first_call.args[2] == impact_ticks


@patch("horizons.world.units.weapon.Callback")
@patch("horizons.world.units.weapon.Scheduler")
def test_fire_calculates_correct_cooldown(
    mock_scheduler,
    mock_callback,
    weapon,
):
    destination = MagicMock()
    destination.center = MagicMock()

    position = MagicMock()
    position.distance.return_value = 3

    with patch(
        "horizons.world.units.weapon.GAME_SPEED.TICKS_PER_SECOND",
        10,
    ):
        weapon.fire(destination, position)

    cooldown_ticks = 50

    second_call = (
        mock_scheduler.return_value
        .add_new_object
        .call_args_list[1]
    )

    assert second_call.args[2] == cooldown_ticks


def test_on_impact_deals_damage_to_all_units():
    session = MagicMock()

    session.db.get_weapon_attack_radius.return_value = 2

    health1 = MagicMock()
    health2 = MagicMock()

    unit1 = MagicMock()
    unit2 = MagicMock()

    unit1.get_component.return_value = health1
    unit2.get_component.return_value = health2

    session.world.get_health_instances.return_value = [
        unit1,
        unit2,
    ]

    position = MagicMock()

    Weapon.on_impact(
        session=session,
        weapon_id=1,
        damage=15,
        position=position,
    )

    health1.deal_damage.assert_called_once_with(1, 15)
    health2.deal_damage.assert_called_once_with(1, 15)


def test_impact_with_no_units():
    session = MagicMock()

    session.db.get_weapon_attack_radius.return_value = 1
    session.world.get_health_instances.return_value = []

    Weapon.on_impact(
        session=session,
        weapon_id=1,
        damage=10,
        position=MagicMock(),
    )

    session.world.get_health_instances.assert_called_once()


def test_on_impact_uses_weapon_attack_radius():
    session = MagicMock()

    session.db.get_weapon_attack_radius.return_value = 17
    session.world.get_health_instances.return_value = []

    position = MagicMock()

    Weapon.on_impact(
        session,
        weapon_id=5,
        damage=10,
        position=position,
    )

    session.db.get_weapon_attack_radius.assert_called_once_with(5)

    session.world.get_health_instances.assert_called_once_with(
        position,
        17,
    )


def test_get_ticks_until_ready_when_ready(weapon):
    weapon.attack_ready = True

    assert weapon.get_ticks_until_ready() == 0


@patch("horizons.world.units.weapon.Scheduler")
def test_get_ticks_until_ready_when_not_ready(
    mock_scheduler,
    weapon,
):
    weapon.attack_ready = False

    mock_scheduler.return_value.get_remaining_ticks.return_value = 77

    assert weapon.get_ticks_until_ready() == 77


@patch("horizons.world.units.weapon.Point")
@patch("horizons.world.units.weapon.Callback")
@patch("horizons.world.units.weapon.Scheduler")
def test_load_attacks(
    mock_scheduler,
    mock_callback,
    mock_point,
):
    session = MagicMock()

    db = MagicMock()
    db.return_value = [
        (12, 1, 20, 30, 40),
        (25, 2, 50, 60, 70),
    ]

    Weapon.load_attacks(session, db)

    assert (
        mock_scheduler.return_value.add_new_object.call_count
        == 2
    )


@patch("horizons.world.units.weapon.Scheduler")
def test_load_attacks_empty_db(mock_scheduler):
    session = MagicMock()

    db = MagicMock()
    db.return_value = []

    Weapon.load_attacks(session, db)

    mock_scheduler.return_value.add_new_object.assert_not_called()


@patch("horizons.world.units.weapon.Scheduler")
def test_save_attacks(mock_scheduler):
    db = MagicMock()

    callback = MagicMock()
    callback.args = (
        None,
        9,
        33,
        MagicMock(x=100, y=200),
    )

    scheduled_call = MagicMock()
    scheduled_call.callback = callback

    mock_scheduler.return_value.get_classinst_calls.return_value = {
        scheduled_call: 55
    }

    Weapon.save_attacks(db)

    db.assert_called_once_with(
        "INSERT INTO attacks(remaining_ticks, weapon_id, damage, dest_x, dest_y) VALUES (?, ?, ?, ?, ?)",
        55,
        9,
        33,
        100,
        200,
    )


@patch("horizons.world.units.weapon.Scheduler")
def test_save_attacks_no_calls(mock_scheduler):
    db = MagicMock()

    mock_scheduler.return_value.get_classinst_calls.return_value = {}

    Weapon.save_attacks(db)

    db.assert_not_called()


def test_str_representation(weapon):
    result = str(weapon)

    assert "Weapon" in result
    assert "id:1" in result
    assert "cannon" in result


def test_stackable_weapon_defaults(stackable_weapon):
    assert stackable_weapon.number_of_weapons == 1
    assert stackable_weapon.max_number_of_weapons == 1


def test_set_number_of_weapons_success(stackable_weapon):
    stackable_weapon.max_number_of_weapons = 5

    stackable_weapon.set_number_of_weapons(3)

    assert stackable_weapon.number_of_weapons == 3


def test_set_number_of_weapons_too_many(stackable_weapon):
    stackable_weapon.max_number_of_weapons = 2

    with pytest.raises(SetStackableWeaponNumberError):
        stackable_weapon.set_number_of_weapons(3)


def test_set_number_of_weapons_zero_allowed(stackable_weapon):
    stackable_weapon.max_number_of_weapons = 5

    stackable_weapon.set_number_of_weapons(0)

    assert stackable_weapon.number_of_weapons == 0


def test_increase_number_of_weapons_success(stackable_weapon):
    stackable_weapon.max_number_of_weapons = 5

    stackable_weapon.increase_number_of_weapons(2)

    assert stackable_weapon.number_of_weapons == 3


def test_increase_number_of_weapons_above_limit(stackable_weapon):
    stackable_weapon.max_number_of_weapons = 2

    with pytest.raises(SetStackableWeaponNumberError):
        stackable_weapon.increase_number_of_weapons(2)


def test_decrease_number_of_weapons_success(stackable_weapon):
    stackable_weapon.max_number_of_weapons = 10
    stackable_weapon.number_of_weapons = 5

    stackable_weapon.decrease_number_of_weapons(2)

    assert stackable_weapon.number_of_weapons == 3


@pytest.mark.parametrize(
    "number",
    [1, 5, 10],
)
def test_decrease_number_of_weapons_not_allowed(
    stackable_weapon,
    number,
):
    stackable_weapon.number_of_weapons = number

    with pytest.raises(SetStackableWeaponNumberError):
        stackable_weapon.decrease_number_of_weapons(number)


@pytest.mark.parametrize(
    "method,args",
    [
        ("set_number_of_weapons", (2,)),
        ("increase_number_of_weapons", (2,)),
    ],
)
def test_stackable_methods_raise_expected_exception(
    stackable_weapon,
    method,
    args,
):
    stackable_weapon.max_number_of_weapons = 1

    with pytest.raises(SetStackableWeaponNumberError):
        getattr(stackable_weapon, method)(*args)


@pytest.mark.parametrize(
    "count,base_damage,expected",
    [
        (1, 10, 10),
        (2, 10, 20),
        (5, 10, 50),
        (10, 10, 100),
    ],
)
def test_stackable_damage_modifier(
    count,
    base_damage,
    expected,
    session,
):
    session.db.return_value = [
        (
            1,
            "cannon",
            base_damage,
            2,
            8,
            5,
            20,
            1,
        )
    ]

    weapon = StackableWeapon(session, 1)

    weapon.max_number_of_weapons = count
    weapon.number_of_weapons = count

    assert weapon.get_damage_modifier() == expected


def test_stackable_weapon_damage_changes_after_increment(
    stackable_weapon,
):
    stackable_weapon.max_number_of_weapons = 5

    stackable_weapon.increase_number_of_weapons(2)

    assert stackable_weapon.get_damage_modifier() == 30


def test_fire_uses_rounded_distance_for_range_check(weapon):
    destination = MagicMock()
    destination.center = MagicMock()

    position = MagicMock()
    position.distance.return_value = 1.6

    with patch.object(
        weapon,
        "check_target_in_range",
        return_value=True,
    ) as mock_check, patch("horizons.world.units.weapon.Scheduler"):
        with patch("horizons.world.units.weapon.Callback"):
            weapon.fire(destination, position)

    mock_check.assert_called_once_with(2)
