"""Tests for the Honeywell Lyric climate platform."""

from collections.abc import Generator
from datetime import timedelta
from typing import Any
from unittest.mock import ANY, MagicMock, call, patch

from aiolyric.exceptions import LyricException
from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.climate import (
    ATTR_FAN_MODE,
    ATTR_HVAC_ACTION,
    ATTR_HVAC_MODE,
    ATTR_PRESET_MODE,
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    DOMAIN as CLIMATE_DOMAIN,
    FAN_DIFFUSE,
    SERVICE_SET_FAN_MODE,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_PRESET_MODE,
    SERVICE_SET_TEMPERATURE,
    HVACAction,
    HVACMode,
)
from homeassistant.components.lyric.const import DOMAIN
from homeassistant.components.lyric.services import SERVICE_HOLD_TIME
from homeassistant.const import ATTR_ENTITY_ID, ATTR_TEMPERATURE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform

LCC_ENTITY_ID = "climate.hallway_thermostat"
LCC_MAC_ID = "AABBCC000011"
TCC_ENTITY_ID = "climate.landing_thermostat"
TCC_MAC_ID = "AABBCC000012"


@pytest.fixture(autouse=True)
def platforms() -> Generator[None]:
    """Only set up the climate platform."""
    with patch("homeassistant.components.lyric.PLATFORMS", [Platform.CLIMATE]):
        yield


@pytest.fixture
async def mock_lyric(
    hass: HomeAssistant,
    setup_credentials: None,
    mock_config_entry: MockConfigEntry,
    mock_lyric_thermostats: MagicMock,
) -> MagicMock:
    """Set up the integration and return the mocked Lyric client."""
    await setup_integration(hass, mock_config_entry)
    return mock_lyric_thermostats


def set_changeable_values(lyric: MagicMock, mac_id: str, **values: Any) -> None:
    """Change a thermostat's changeable values in the mocked API data."""
    device = lyric.locations[0].devices_dict[mac_id]
    device.attributes["changeableValues"].update(values)


@pytest.mark.usefixtures("mock_lyric")
async def test_climate(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the climate entities."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_hvac_action_idle(
    hass: HomeAssistant, mock_lyric: MagicMock, freezer: FrozenDateTimeFactory
) -> None:
    """Test the action is idle when the equipment is off but the mode is not."""
    lyric_device = mock_lyric.locations[0].devices_dict[LCC_MAC_ID]
    lyric_device.attributes["operationStatus"]["mode"] = "EquipmentOff"
    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get(LCC_ENTITY_ID).attributes[ATTR_HVAC_ACTION] == (
        HVACAction.IDLE
    )


@pytest.mark.parametrize(
    ("mode", "expected"),
    [
        pytest.param("Heat", {"heat_setpoint": 21}, id="heat"),
        pytest.param("Cool", {"cool_setpoint": 21}, id="cool"),
    ],
)
async def test_set_temperature(
    hass: HomeAssistant,
    mock_lyric: MagicMock,
    mode: str,
    expected: dict[str, Any],
) -> None:
    """Test setting the target temperature."""
    set_changeable_values(mock_lyric, LCC_MAC_ID, mode=mode)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: LCC_ENTITY_ID, ATTR_TEMPERATURE: 21},
        blocking=True,
    )

    mock_lyric.update_thermostat.assert_awaited_once_with(ANY, ANY, **expected)


@pytest.mark.parametrize(
    ("entity_id", "mac_id", "expected"),
    [
        pytest.param(
            LCC_ENTITY_ID,
            LCC_MAC_ID,
            {"heat_setpoint": 20, "cool_setpoint": 25, "mode": None},
            id="lcc",
        ),
        pytest.param(
            TCC_ENTITY_ID,
            TCC_MAC_ID,
            {"heat_setpoint": 68, "cool_setpoint": 77, "mode": "Heat"},
            id="tcc",
        ),
    ],
)
async def test_set_temperature_range(
    hass: HomeAssistant,
    mock_lyric: MagicMock,
    entity_id: str,
    mac_id: str,
    expected: dict[str, Any],
) -> None:
    """Test setting the target temperature range in auto mode."""
    set_changeable_values(mock_lyric, mac_id, mode="Auto", autoChangeoverActive=True)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {
            ATTR_ENTITY_ID: entity_id,
            ATTR_TARGET_TEMP_LOW: 20,
            ATTR_TARGET_TEMP_HIGH: 25,
        },
        blocking=True,
    )

    mock_lyric.update_thermostat.assert_awaited_once_with(ANY, ANY, **expected)


async def test_set_temperature_range_missing(
    hass: HomeAssistant, mock_lyric: MagicMock
) -> None:
    """Test auto mode needs both ends of the temperature range."""
    set_changeable_values(mock_lyric, LCC_MAC_ID, mode="Auto")

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {ATTR_ENTITY_ID: LCC_ENTITY_ID, ATTR_TEMPERATURE: 21},
            blocking=True,
        )

    mock_lyric.update_thermostat.assert_not_awaited()


async def test_set_temperature_off(hass: HomeAssistant, mock_lyric: MagicMock) -> None:
    """Test setting the temperature does nothing while the thermostat is off."""
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: TCC_ENTITY_ID, ATTR_TEMPERATURE: 21},
        blocking=True,
    )

    mock_lyric.update_thermostat.assert_not_awaited()


@pytest.mark.parametrize(
    ("hvac_mode", "expected"),
    [
        pytest.param(
            HVACMode.COOL,
            {"mode": "Cool", "auto_changeover_active": None},
            id="cool",
        ),
        pytest.param(
            HVACMode.HEAT_COOL,
            {"mode": "Auto", "auto_changeover_active": True},
            id="heat_cool",
        ),
    ],
)
async def test_set_hvac_mode_lcc(
    hass: HomeAssistant,
    mock_lyric: MagicMock,
    hvac_mode: HVACMode,
    expected: dict[str, Any],
) -> None:
    """Test setting the HVAC mode on an LCC thermostat."""
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: LCC_ENTITY_ID, ATTR_HVAC_MODE: hvac_mode},
        blocking=True,
    )

    mock_lyric.update_thermostat.assert_awaited_once_with(ANY, ANY, **expected)


async def test_set_hvac_mode_tcc(hass: HomeAssistant, mock_lyric: MagicMock) -> None:
    """Test setting the HVAC mode on a TCC thermostat."""
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: TCC_ENTITY_ID, ATTR_HVAC_MODE: HVACMode.COOL},
        blocking=True,
    )

    mock_lyric.update_thermostat.assert_awaited_once_with(
        ANY, ANY, mode="Cool", auto_changeover_active=False
    )


async def test_set_hvac_mode_tcc_heat_cool(
    hass: HomeAssistant, mock_lyric: MagicMock
) -> None:
    """Test switching a TCC thermostat to auto while it is already running."""
    set_changeable_values(mock_lyric, TCC_MAC_ID, mode="Heat")

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: TCC_ENTITY_ID, ATTR_HVAC_MODE: HVACMode.HEAT_COOL},
        blocking=True,
    )

    mock_lyric.update_thermostat.assert_awaited_once_with(
        ANY, ANY, auto_changeover_active=True
    )


async def test_set_hvac_mode_tcc_heat_cool_from_off(
    hass: HomeAssistant, mock_lyric: MagicMock
) -> None:
    """Test a TCC thermostat that is off is switched to heat before auto."""
    with patch("homeassistant.components.lyric.climate.asyncio.sleep") as mock_sleep:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_HVAC_MODE,
            {ATTR_ENTITY_ID: TCC_ENTITY_ID, ATTR_HVAC_MODE: HVACMode.HEAT_COOL},
            blocking=True,
        )

    mock_sleep.assert_awaited_once_with(3)
    assert mock_lyric.update_thermostat.await_args_list == [
        call(ANY, ANY, mode="Heat", auto_changeover_active=False),
        call(ANY, ANY, mode="Heat", auto_changeover_active=True),
    ]


async def test_set_preset_mode(hass: HomeAssistant, mock_lyric: MagicMock) -> None:
    """Test setting the preset mode."""
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: LCC_ENTITY_ID, ATTR_PRESET_MODE: "PermanentHold"},
        blocking=True,
    )

    mock_lyric.update_thermostat.assert_awaited_once_with(
        ANY, ANY, thermostat_setpoint_status="PermanentHold"
    )


async def test_set_fan_mode(hass: HomeAssistant, mock_lyric: MagicMock) -> None:
    """Test setting the fan mode."""
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_FAN_MODE,
        {ATTR_ENTITY_ID: LCC_ENTITY_ID, ATTR_FAN_MODE: FAN_DIFFUSE},
        blocking=True,
    )

    mock_lyric.update_fan.assert_awaited_once_with(ANY, ANY, mode="Circulate")


async def test_set_hold_time(hass: HomeAssistant, mock_lyric: MagicMock) -> None:
    """Test the set hold time action."""
    await hass.services.async_call(
        DOMAIN,
        SERVICE_HOLD_TIME,
        {ATTR_ENTITY_ID: LCC_ENTITY_ID, "time_period": "01:00:00"},
        blocking=True,
    )

    mock_lyric.update_thermostat.assert_awaited_once_with(
        ANY, ANY, thermostat_setpoint_status="HoldUntil", next_period_time=ANY
    )


@pytest.mark.parametrize(
    ("domain", "service", "data", "translation_key"),
    [
        pytest.param(
            CLIMATE_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {ATTR_TEMPERATURE: 21},
            "failed_to_set_temperature",
            id="temperature",
        ),
        pytest.param(
            CLIMATE_DOMAIN,
            SERVICE_SET_HVAC_MODE,
            {ATTR_HVAC_MODE: HVACMode.COOL},
            "failed_to_set_hvac_mode",
            id="hvac_mode",
        ),
        pytest.param(
            CLIMATE_DOMAIN,
            SERVICE_SET_PRESET_MODE,
            {ATTR_PRESET_MODE: "PermanentHold"},
            "failed_to_set_preset_mode",
            id="preset_mode",
        ),
        pytest.param(
            CLIMATE_DOMAIN,
            SERVICE_SET_FAN_MODE,
            {ATTR_FAN_MODE: FAN_DIFFUSE},
            "failed_to_set_fan_mode",
            id="fan_mode",
        ),
        pytest.param(
            DOMAIN,
            SERVICE_HOLD_TIME,
            {"time_period": "01:00:00"},
            "failed_to_set_hold_time",
            id="hold_time",
        ),
    ],
)
async def test_action_error(
    hass: HomeAssistant,
    mock_lyric: MagicMock,
    domain: str,
    service: str,
    data: dict[str, Any],
    translation_key: str,
) -> None:
    """Test API errors are raised as translated errors and data is still refreshed."""
    mock_lyric.update_thermostat.side_effect = LyricException("error")
    mock_lyric.update_fan.side_effect = LyricException("error")
    mock_lyric.get_locations.reset_mock()

    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            domain,
            service,
            {ATTR_ENTITY_ID: LCC_ENTITY_ID, **data},
            blocking=True,
        )

    assert err.value.translation_key == translation_key
    mock_lyric.get_locations.assert_awaited_once()
