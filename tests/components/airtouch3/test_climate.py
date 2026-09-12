"""Test AirTouch 3 climate entities."""

from unittest.mock import AsyncMock, Mock, call, patch

from pyairtouch3 import AirTouchError
from pyairtouch3.airtouch_aircon import Aircon
from pyairtouch3.airtouch_sensor import Sensor
from pyairtouch3.airtouch_zone import AirtouchZone
from pyairtouch3.enums import AcMode, ZoneStatus
import pytest

from homeassistant.components.airtouch3.climate import (
    PARALLEL_UPDATES,
    AirtouchAC,
    AirtouchGroup,
)
from homeassistant.components.airtouch3.const import DOMAIN
from homeassistant.components.airtouch3.coordinator import (
    AirTouch3Data,
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
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

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


def _entry_and_coordinator(
    hass: HomeAssistant,
) -> tuple[MockConfigEntry, Airtouch3DataUpdateCoordinator]:
    """Create a coordinator with data."""
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id=SYSTEM_ID, data={CONF_HOST: "1.1.1.1"}
    )
    entry.add_to_hass(hass)
    coordinator = Airtouch3DataUpdateCoordinator(hass, entry, "1.1.1.1")
    coordinator.data = AirTouch3Data.from_aircon(_aircon())
    entry.runtime_data = coordinator
    return entry, coordinator


def _coordinator(hass: HomeAssistant) -> Airtouch3DataUpdateCoordinator:
    """Create a coordinator with data."""
    return _entry_and_coordinator(hass)[1]


@pytest.mark.parametrize(
    "ignore_missing_translations",
    ["component.climate.services."],
)
async def test_async_setup_entry_adds_ac_and_zone_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the integration creates the AC and zone entities."""
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id=SYSTEM_ID, data={CONF_HOST: "1.1.1.1"}
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.airtouch3.coordinator.async_fetch_airtouch_data",
        AsyncMock(return_value=_aircon()),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    entries = er.async_entries_for_config_entry(entity_registry, entry.entry_id)
    assert {entry.unique_id for entry in entries} == {
        "35901813_ac_1",
        "35901813_1_group_1",
        "35901813_1_group_2",
    }
    assert len(hass.states.async_all("climate")) == 3
    assert PARALLEL_UPDATES == 1


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
    coordinator.data.aircon.status = False
    entity = AirtouchAC(coordinator, 1)

    assert entity.hvac_mode == HVACMode.OFF


async def test_ac_hvac_mode_commands(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test AC HVAC mode commands."""
    coordinator = _coordinator(hass)
    entity = AirtouchAC(coordinator, 1)
    set_mode = AsyncMock()
    toggle_ac_power = AsyncMock()
    write_state = Mock()
    monkeypatch.setattr(coordinator.client, "set_mode", set_mode)
    monkeypatch.setattr(coordinator.client, "toggle_ac_power", toggle_ac_power)
    monkeypatch.setattr(entity, "async_write_ha_state", write_state)

    await entity.async_set_hvac_mode(HVACMode.HEAT)
    await entity.async_set_hvac_mode(HVACMode.OFF)

    set_mode.assert_awaited_once_with(1, 2, AcMode.HEAT.value)
    toggle_ac_power.assert_awaited_once_with(1)
    assert coordinator.data.aircon.mode == AcMode.HEAT
    assert coordinator.data.aircon.status is False
    assert write_state.call_count == 2


async def test_ac_hvac_mode_off_skips_when_already_off(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test turning off an already off AC does not send a toggle command."""
    coordinator = _coordinator(hass)
    coordinator.data.aircon.status = False
    entity = AirtouchAC(coordinator, 1)
    toggle_ac_power = AsyncMock()
    write_state = Mock()
    monkeypatch.setattr(coordinator.client, "toggle_ac_power", toggle_ac_power)
    monkeypatch.setattr(entity, "async_write_ha_state", write_state)

    await entity.async_set_hvac_mode(HVACMode.OFF)

    toggle_ac_power.assert_not_called()
    assert coordinator.data.aircon.status is False
    write_state.assert_called_once()


async def test_ac_hvac_mode_turns_on_when_needed(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test setting an active HVAC mode powers on an off AC."""
    coordinator = _coordinator(hass)
    coordinator.data.aircon.status = False
    entity = AirtouchAC(coordinator, 1)
    set_mode = AsyncMock()
    toggle_ac_power = AsyncMock()
    write_state = Mock()
    monkeypatch.setattr(coordinator.client, "set_mode", set_mode)
    monkeypatch.setattr(coordinator.client, "toggle_ac_power", toggle_ac_power)
    monkeypatch.setattr(entity, "async_write_ha_state", write_state)

    await entity.async_set_hvac_mode(HVACMode.HEAT)

    set_mode.assert_awaited_once_with(1, 2, AcMode.HEAT.value)
    toggle_ac_power.assert_awaited_once_with(1)
    assert coordinator.data.aircon.mode == AcMode.HEAT
    assert coordinator.data.aircon.status is True
    write_state.assert_called_once()


async def test_ac_fan_mode_commands(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test AC fan mode commands."""
    coordinator = _coordinator(hass)
    entity = AirtouchAC(coordinator, 1)
    set_fan_speed = AsyncMock()
    write_state = Mock()
    monkeypatch.setattr(coordinator.client, "set_fan_speed", set_fan_speed)
    monkeypatch.setattr(entity, "async_write_ha_state", write_state)

    await entity.async_set_fan_mode(FAN_HIGH)

    set_fan_speed.assert_awaited_once_with(1, 2, 3)
    assert coordinator.data.aircon.fan_speed == 3
    write_state.assert_called_once()


async def test_ac_command_error_raises_home_assistant_error(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test pyairtouch3 write errors are surfaced as action errors."""
    coordinator = _coordinator(hass)
    entity = AirtouchAC(coordinator, 1)
    set_fan_speed = AsyncMock(side_effect=AirTouchError("closed"))
    write_state = Mock()
    monkeypatch.setattr(coordinator.client, "set_fan_speed", set_fan_speed)
    monkeypatch.setattr(entity, "async_write_ha_state", write_state)

    with pytest.raises(HomeAssistantError):
        await entity.async_set_fan_mode(FAN_HIGH)

    set_fan_speed.assert_awaited_once_with(1, 2, 3)
    write_state.assert_not_called()


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
    assert missing.available is False
    assert missing.target_temperature is None


async def test_group_set_temperature_steps_to_target(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test zone temperature changes are sent one step at a time."""
    coordinator = _coordinator(hass)
    entity = AirtouchGroup(coordinator, 1, 1, "Living")
    adjust_zone_temperature = AsyncMock()
    write_state = Mock()
    monkeypatch.setattr(
        coordinator.client, "adjust_zone_temperature", adjust_zone_temperature
    )
    monkeypatch.setattr(entity, "async_write_ha_state", write_state)

    await entity.async_set_temperature(**{ATTR_TEMPERATURE: 22})

    assert adjust_zone_temperature.mock_calls == [call(1, 1), call(1, 1)]
    assert coordinator.data.zones[1].desired_temperature == 22
    write_state.assert_called_once()


async def test_group_set_temperature_ignores_noop_and_missing_zone(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test zone temperature changes are skipped when no command is needed."""
    coordinator = _coordinator(hass)
    living = AirtouchGroup(coordinator, 1, 1, "Living")
    missing = AirtouchGroup(coordinator, 99, 1, "Missing")
    adjust_zone_temperature = AsyncMock()
    monkeypatch.setattr(
        coordinator.client, "adjust_zone_temperature", adjust_zone_temperature
    )

    await living.async_set_temperature(**{ATTR_TEMPERATURE: 20})
    await living.async_set_temperature()
    await missing.async_set_temperature(**{ATTR_TEMPERATURE: 20})

    adjust_zone_temperature.assert_not_called()


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
    toggle_zone = AsyncMock()
    write_state = Mock()
    monkeypatch.setattr(coordinator.client, "toggle_zone", toggle_zone)
    monkeypatch.setattr(entity, "async_write_ha_state", write_state)

    await entity.async_set_hvac_mode(hvac_mode)

    toggle_zone.assert_awaited_once_with(group_id)
    assert entity.hvac_mode == hvac_mode
    write_state.assert_called_once()


async def test_group_hvac_mode_ignores_missing_zone(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test zone HVAC mode change is skipped when the zone is missing."""
    coordinator = _coordinator(hass)
    entity = AirtouchGroup(coordinator, 99, 1, "Missing")
    toggle_zone = AsyncMock()
    monkeypatch.setattr(coordinator.client, "toggle_zone", toggle_zone)

    await entity.async_set_hvac_mode(HVACMode.FAN_ONLY)

    toggle_zone.assert_not_called()


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
