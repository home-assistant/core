"""Test AirTouch 3 climate entities."""

from typing import cast
from unittest.mock import AsyncMock, Mock, call

from pyairtouch3.airtouch_aircon import Aircon
from pyairtouch3.airtouch_sensor import Sensor
from pyairtouch3.airtouch_zone import AirtouchZone
from pyairtouch3.enums import AcMode, ZoneStatus
import pytest

from homeassistant.components.airtouch3.climate import (
    PARALLEL_UPDATES,
    AirtouchAC,
    AirtouchGroup,
    async_setup_entry,
)
from homeassistant.components.airtouch3.const import DOMAIN
from homeassistant.components.airtouch3.coordinator import (
    Airtouch3DataUpdateCoordinator,
)
from homeassistant.components.climate import (
    FAN_AUTO,
    FAN_HIGH,
    FAN_LOW,
    FAN_MEDIUM,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, CONF_HOST
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

SYSTEM_ID = "35901813"


def _sensor(temperature: int) -> Sensor:
    """Create an available sensor."""
    sensor = Sensor()
    sensor.current_temperature = temperature
    sensor.is_available = True
    return sensor


def _zone(
    zone_id: int,
    name: str,
    desired_temperature: int,
    status: ZoneStatus,
    sensor: Sensor | None = None,
) -> AirtouchZone:
    """Create a zone fixture."""
    zone = AirtouchZone(20)
    zone.id = zone_id
    zone.name = name
    zone.desired_temperature = desired_temperature
    zone.status = status
    if sensor:
        zone.sensor = sensor
    return zone


def _aircon() -> Aircon:
    """Create AirTouch data for climate tests."""
    aircon = Aircon(1)
    aircon.system_id = SYSTEM_ID
    aircon.brand_id = 2
    aircon.fan_speed = 2
    aircon.mode = AcMode.COOL
    aircon.room_temperature = 19
    aircon.status = True
    aircon.zones = [
        _zone(1, "Living", 20, ZoneStatus.ZONE_ON, _sensor(23)),
        _zone(2, "Bedroom", 21, ZoneStatus.ZONE_OFF),
    ]
    return aircon


def _coordinator(hass: HomeAssistant) -> Airtouch3DataUpdateCoordinator:
    """Create a coordinator with data."""
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id=SYSTEM_ID, data={CONF_HOST: "1.1.1.1"}
    )
    entry.add_to_hass(hass)
    coordinator = Airtouch3DataUpdateCoordinator(hass, entry, "1.1.1.1")
    coordinator.data = _aircon()
    return coordinator


async def test_async_setup_entry_adds_ac_and_zone_entities(
    hass: HomeAssistant,
) -> None:
    """Test climate setup creates the AC and zone entities."""
    coordinator = _coordinator(hass)
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_HOST: "1.1.1.1"})
    entry.runtime_data = coordinator
    async_add_entities = Mock()

    await async_setup_entry(hass, entry, async_add_entities)

    entities = async_add_entities.call_args.args[0]
    assert [entity.unique_id for entity in entities] == [
        "35901813_airtouch_ac_1",
        "35901813_airtouch_1_group_1",
        "35901813_airtouch_1_group_2",
    ]
    assert PARALLEL_UPDATES == 1
    assert entities[0].translation_key == "air_conditioner"
    assert entities[1].translation_key == "zone"
    assert entities[0].device_info["manufacturer"] == "Polyaire"


async def test_async_setup_entry_skips_missing_data(hass: HomeAssistant) -> None:
    """Test climate setup does not add entities without coordinator data."""
    coordinator = _coordinator(hass)
    coordinator.data = cast(Aircon, None)
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_HOST: "1.1.1.1"})
    entry.runtime_data = coordinator
    async_add_entities = Mock()

    await async_setup_entry(hass, entry, async_add_entities)

    async_add_entities.assert_not_called()


async def test_ac_properties(hass: HomeAssistant) -> None:
    """Test AC entity properties map AirTouch data to Home Assistant values."""
    coordinator = _coordinator(hass)
    entity = AirtouchAC(coordinator, 1)

    assert entity.fan_modes == [FAN_AUTO, FAN_LOW, FAN_MEDIUM, FAN_HIGH]
    assert entity.fan_mode == FAN_MEDIUM
    assert entity.current_temperature == 19
    assert entity.hvac_mode == HVACMode.COOL


def test_ac_hvac_mode_off(hass: HomeAssistant) -> None:
    """Test AC entity is off when AirTouch reports power off."""
    coordinator = _coordinator(hass)
    coordinator.data.status = False
    entity = AirtouchAC(coordinator, 1)

    assert entity.hvac_mode == HVACMode.OFF


async def test_ac_hvac_mode_commands(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test AC HVAC mode commands."""
    coordinator = _coordinator(hass)
    entity = AirtouchAC(coordinator, 1)
    send_command = AsyncMock()
    write_state = Mock()
    monkeypatch.setattr(coordinator, "send_command", send_command)
    monkeypatch.setattr(entity, "async_write_ha_state", write_state)

    await entity.async_set_hvac_mode(HVACMode.HEAT)
    await entity.async_set_hvac_mode(HVACMode.OFF)

    assert send_command.mock_calls == [
        call("set_mode", 1, AcMode.HEAT.value),
        call("turn_on", 1),
        call("turn_off", 1),
    ]
    assert coordinator.data.mode == AcMode.HEAT
    assert write_state.call_count == 2


async def test_ac_unsupported_hvac_mode_does_not_write_state(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test unsupported AC HVAC mode is ignored."""
    coordinator = _coordinator(hass)
    entity = AirtouchAC(coordinator, 1)
    send_command = AsyncMock()
    write_state = Mock()
    monkeypatch.setattr(coordinator, "send_command", send_command)
    monkeypatch.setattr(entity, "async_write_ha_state", write_state)

    await entity.async_set_hvac_mode(cast(HVACMode, "unsupported"))

    send_command.assert_not_called()
    write_state.assert_not_called()


async def test_ac_fan_mode_commands(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test AC fan mode commands."""
    coordinator = _coordinator(hass)
    entity = AirtouchAC(coordinator, 1)
    send_command = AsyncMock()
    write_state = Mock()
    monkeypatch.setattr(coordinator, "send_command", send_command)
    monkeypatch.setattr(entity, "async_write_ha_state", write_state)

    await entity.async_set_fan_mode(FAN_HIGH)
    await entity.async_set_fan_mode("turbo")

    send_command.assert_awaited_once_with("set_fan_speed", 1, 3)
    assert coordinator.data.fan_speed == 3
    write_state.assert_called_once()


def test_group_properties(hass: HomeAssistant) -> None:
    """Test zone entity properties."""
    coordinator = _coordinator(hass)
    living = AirtouchGroup(coordinator, 1, 1, "Living")
    bedroom = AirtouchGroup(coordinator, 2, 1, "Bedroom")
    missing = AirtouchGroup(coordinator, 99, 1, "Missing")

    assert living.current_temperature == 23
    assert living.target_temperature == 20
    assert living.hvac_mode == HVACMode.FAN_ONLY
    assert bedroom.current_temperature == 19
    assert bedroom.hvac_mode == HVACMode.OFF
    assert missing.target_temperature is None


async def test_group_set_temperature_steps_to_target(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test zone temperature changes are sent one step at a time."""
    coordinator = _coordinator(hass)
    entity = AirtouchGroup(coordinator, 1, 1, "Living")
    send_command = AsyncMock()
    write_state = Mock()
    monkeypatch.setattr(coordinator, "send_command", send_command)
    monkeypatch.setattr(entity, "async_write_ha_state", write_state)

    await entity.async_set_temperature(**{ATTR_TEMPERATURE: 22})

    assert send_command.mock_calls == [
        call("set_group_temperature", 1, 1),
        call("set_group_temperature", 1, 1),
    ]
    assert coordinator.data.zones[0].desired_temperature == 22
    write_state.assert_called_once()


async def test_group_set_temperature_ignores_noop_and_missing_zone(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test zone temperature changes are skipped when no command is needed."""
    coordinator = _coordinator(hass)
    living = AirtouchGroup(coordinator, 1, 1, "Living")
    missing = AirtouchGroup(coordinator, 99, 1, "Missing")
    send_command = AsyncMock()
    monkeypatch.setattr(coordinator, "send_command", send_command)

    await living.async_set_temperature(**{ATTR_TEMPERATURE: 20})
    await living.async_set_temperature()
    await missing.async_set_temperature(**{ATTR_TEMPERATURE: 20})

    send_command.assert_not_called()


@pytest.mark.parametrize(
    ("group_id", "hvac_mode"),
    [
        (1, HVACMode.OFF),
        (2, HVACMode.FAN_ONLY),
    ],
)
async def test_group_hvac_mode_toggles_zone(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
    group_id: int,
    hvac_mode: HVACMode,
) -> None:
    """Test zone HVAC mode toggles zone power when needed."""
    coordinator = _coordinator(hass)
    entity = AirtouchGroup(coordinator, group_id, 1, "Zone")
    send_command = AsyncMock()
    write_state = Mock()
    monkeypatch.setattr(coordinator, "send_command", send_command)
    monkeypatch.setattr(entity, "async_write_ha_state", write_state)

    await entity.async_set_hvac_mode(hvac_mode)

    send_command.assert_awaited_once_with("toggle_zone", group_id)
    assert entity.hvac_mode == hvac_mode
    write_state.assert_called_once()


async def test_group_hvac_mode_ignores_missing_zone(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test zone HVAC mode change is skipped when the zone is missing."""
    coordinator = _coordinator(hass)
    entity = AirtouchGroup(coordinator, 99, 1, "Missing")
    send_command = AsyncMock()
    monkeypatch.setattr(coordinator, "send_command", send_command)

    await entity.async_set_hvac_mode(HVACMode.FAN_ONLY)

    send_command.assert_not_called()


async def test_group_update_refreshes_hvac_mode(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test zone update requests a coordinator refresh."""
    coordinator = _coordinator(hass)
    entity = AirtouchGroup(coordinator, 1, 1, "Living")
    refresh = AsyncMock()
    monkeypatch.setattr(coordinator, "async_request_refresh", refresh)

    await entity.async_update()

    refresh.assert_awaited_once()
    assert entity.hvac_mode == HVACMode.FAN_ONLY
