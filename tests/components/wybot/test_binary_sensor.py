"""Tests for the WyBot binary sensor platform."""

from wybot.dp_models import Battery, DockConnectionStatus, SolarStatus

from homeassistant.components.wybot.binary_sensor import (
    WyBotDockChargingBinarySensor,
    WyBotRobotChargingBinarySensor,
    format_mac,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .wybot_platform_helpers import (
    add_entity,
    dp,
    make_coordinator,
    make_group,
    setup_integration,
)

IDX = "grp1"


def _robot_dps(battery="0132"):
    """Robot dps."""
    return {"50": dp(Battery, id=50, type=0, len=2, data=battery)}


def _dock_dps(solar="01"):
    """Dock dps."""
    return {
        "222": dp(SolarStatus, id=222, type=0, len=1, data=solar),
        "213": dp(DockConnectionStatus, id=213, type=4, len=1, data="01"),
    }


def _coord(hass: HomeAssistant, battery="0132", solar="01", **kwargs):
    """Coord."""
    group = make_group(
        device_dps=_robot_dps(battery), docker_dps=_dock_dps(solar), **kwargs
    )
    coord, entry = make_coordinator(hass, {IDX: group})
    return coord, entry, group


def test_format_mac() -> None:
    """Test format mac."""
    assert format_mac("CCBA97932A96") == "CC:BA:97:93:2A:96"


def _binary_count(hass: HomeAssistant, entry) -> int:
    """Return the number of binary_sensor entities registered for the entry."""
    ent_reg = er.async_get(hass)
    return sum(
        e.domain == "binary_sensor"
        for e in er.async_entries_for_config_entry(ent_reg, entry.entry_id)
    )


async def test_async_setup_entry(hass: HomeAssistant) -> None:
    """A docked device registers the robot and dock charging sensors."""
    group = make_group(device_dps=_robot_dps(), docker_dps=_dock_dps())
    entry = await setup_integration(hass, {IDX: group})
    assert _binary_count(hass, entry) == 2


async def test_async_setup_entry_dockless_only_robot_charging(
    hass: HomeAssistant,
) -> None:
    """A group without a dock registers only the robot charging sensor."""
    group = make_group(device_dps=_robot_dps(), with_docker=False)
    entry = await setup_integration(hass, {IDX: group})
    assert _binary_count(hass, entry) == 1


async def test_dock_charging_unavailable_when_dock_removed(
    hass: HomeAssistant,
) -> None:
    """The dock charging sensor goes unavailable if the group loses its dock."""
    coord, _, _ = _coord(hass)
    ent = WyBotDockChargingBinarySensor(idx=IDX, coordinator=coord)
    assert ent.available is True
    ent._data.docker = None
    assert ent.available is False


async def test_dock_added_after_setup_creates_dock_charging(
    hass: HomeAssistant,
) -> None:
    """A dock appearing after setup adds the dock charging sensor, no duplicates."""
    group = make_group(device_dps=_robot_dps(), with_docker=False)
    entry = await setup_integration(hass, {IDX: group})
    assert _binary_count(hass, entry) == 1  # robot charging only

    docked = make_group(device_dps=_robot_dps(), docker_dps=_dock_dps(solar="01"))
    coord = entry.runtime_data
    coord.data = {IDX: docked}
    coord.async_set_updated_data(coord.data)
    await hass.async_block_till_done()

    assert _binary_count(hass, entry) == 2


async def test_robot_charging_on(hass: HomeAssistant) -> None:
    """Test robot charging on."""
    coord, _, _ = _coord(hass, battery="0132")  # 01 -> CHARGING
    ent = WyBotRobotChargingBinarySensor(idx=IDX, coordinator=coord)
    assert ent.is_on is True
    assert ent.unique_id == "grp1_robot_charging"
    assert ent.translation_key == "robot_charging"
    assert ent.available is True
    attrs = ent.extra_state_attributes
    assert attrs["charge_state"] == "CHARGING"
    assert attrs["is_fully_charged"] is False
    info = ent.device_info
    assert info["identifiers"] == {("wybot", "grp1")}
    assert info["via_device"] == ("wybot", "grp1_dock")


async def test_robot_charging_off_and_fully_charged(hass: HomeAssistant) -> None:
    """Test robot charging off and fully charged."""
    coord, _, _ = _coord(hass, battery="0264")  # 02 -> CHARGED
    ent = WyBotRobotChargingBinarySensor(idx=IDX, coordinator=coord)
    assert ent.is_on is False
    attrs = ent.extra_state_attributes
    assert attrs["charge_state"] == "CHARGED"
    assert attrs["is_fully_charged"] is True


async def test_robot_charging_no_data(hass: HomeAssistant) -> None:
    """Test robot charging no data."""
    coord, _, _ = _coord(hass)
    ent = WyBotRobotChargingBinarySensor(idx=IDX, coordinator=coord)
    ent._data = None
    assert ent.is_on is None
    assert ent.extra_state_attributes == {}
    assert ent.available is False


async def test_robot_charging_dp_missing(hass: HomeAssistant) -> None:
    """Test robot charging dp missing."""
    group = make_group(device_dps={}, docker_dps={})
    coord, _ = make_coordinator(hass, {IDX: group})
    ent = WyBotRobotChargingBinarySensor(idx=IDX, coordinator=coord)
    assert ent.is_on is None
    assert ent.extra_state_attributes == {}


async def test_robot_charging_unavailable_coordinator(hass: HomeAssistant) -> None:
    """Test robot charging unavailable coordinator."""
    coord, _, _ = _coord(hass)
    ent = WyBotRobotChargingBinarySensor(idx=IDX, coordinator=coord)
    coord._connection_available = False
    assert ent.available is False


async def test_robot_charging_idx_missing(hass: HomeAssistant) -> None:
    """Test robot charging idx missing."""
    coord, _, group = _coord(hass)
    ent = WyBotRobotChargingBinarySensor(idx=IDX, coordinator=coord)
    coord.data = {"other": group}
    assert ent.available is False


async def test_dock_charging_on(hass: HomeAssistant) -> None:
    """Test dock charging on."""
    coord, _, _ = _coord(hass, solar="01")
    ent = WyBotDockChargingBinarySensor(idx=IDX, coordinator=coord)
    assert ent.is_on is True
    assert ent.unique_id == "grp1_dock_charging"
    assert ent.translation_key == "dock_charging"
    attrs = ent.extra_state_attributes
    assert attrs["is_docked"] is True
    assert attrs["raw_value"] == "01"
    info = ent.device_info
    assert info["identifiers"] == {("wybot", "grp1_dock")}
    assert info["name"] == "DS20 Solar Dock"
    assert ("bluetooth", "3C:84:27:56:5A:1A") in info["connections"]


async def test_dock_charging_off(hass: HomeAssistant) -> None:
    """Test dock charging off."""
    coord, _, _ = _coord(hass, solar="00")
    ent = WyBotDockChargingBinarySensor(idx=IDX, coordinator=coord)
    assert ent.is_on is False


async def test_dock_charging_no_data(hass: HomeAssistant) -> None:
    """Test dock charging no data."""
    coord, _, _ = _coord(hass)
    ent = WyBotDockChargingBinarySensor(idx=IDX, coordinator=coord)
    ent._data = None
    assert ent.is_on is None
    assert ent.extra_state_attributes == {}
    # device_info default branch.
    info = ent.device_info
    assert info["name"] == "Solar Dock"
    assert info["model"] == "Unknown"
    assert info["connections"] is None


async def test_dock_charging_dp_missing(hass: HomeAssistant) -> None:
    """Test dock charging dp missing."""
    group = make_group(device_dps={}, docker_dps={})
    coord, _ = make_coordinator(hass, {IDX: group})
    ent = WyBotDockChargingBinarySensor(idx=IDX, coordinator=coord)
    assert ent.is_on is None
    assert ent.extra_state_attributes == {}


async def test_robot_name_fallbacks(hass: HomeAssistant) -> None:
    """Test robot name fallbacks."""
    group = make_group(device_dps=_robot_dps(), name="")
    coord, _ = make_coordinator(hass, {IDX: group})
    ent = WyBotRobotChargingBinarySensor(idx=IDX, coordinator=coord)
    assert ent._get_robot_name() == "Robot"
    group.device.device_name = ""
    assert ent._get_robot_name() == "S2 Pro"
    ent._data = None
    assert ent._get_robot_name() == "Unknown"
    assert ent._get_robot_model() == "Unknown"


async def test_device_info_no_ble_no_docker(hass: HomeAssistant) -> None:
    """Test device info no ble no docker."""
    group = make_group(device_dps=_robot_dps(), with_docker=False)
    group.device.ble_name = ""
    coord, _ = make_coordinator(hass, {IDX: group})
    ent = WyBotRobotChargingBinarySensor(idx=IDX, coordinator=coord)
    info = ent.device_info
    assert info["connections"] is None
    assert info["via_device"] is None


async def test_handle_coordinator_update(hass: HomeAssistant) -> None:
    """Test handle coordinator update."""
    coord, _, group = _coord(hass)
    ent = WyBotRobotChargingBinarySensor(idx=IDX, coordinator=coord)
    await add_entity(hass, ent, domain="binary_sensor")
    ent._handle_coordinator_update()
    assert ent._data is group
    state = hass.states.get(ent.entity_id)
    assert state is not None
    assert state.state == "on"


async def test_handle_coordinator_update_idx_missing(hass: HomeAssistant) -> None:
    """Test handle coordinator update idx missing."""
    coord, _, group = _coord(hass)
    ent = WyBotRobotChargingBinarySensor(idx=IDX, coordinator=coord)
    await add_entity(hass, ent, domain="binary_sensor")
    coord.data = {}
    ent._handle_coordinator_update()
    assert ent._data is group
