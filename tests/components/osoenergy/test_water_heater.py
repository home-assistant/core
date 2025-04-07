"""The water heater tests for the OSO Energy platform."""

from unittest.mock import ANY, MagicMock, patch

import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.osoenergy.const import DOMAIN
from homeassistant.components.osoenergy.water_heater import (
    ATTR_UNTIL_TEMP_LIMIT,
    ATTR_V40MIN,
    SERVICE_GET_PROFILE,
    SERVICE_SET_PROFILE,
    SERVICE_SET_V40MIN,
)
from homeassistant.components.water_heater import (
    DOMAIN as WATER_HEATER_DOMAIN,
    SERVICE_SET_TEMPERATURE,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_TEMPERATURE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import snapshot_platform


@patch("homeassistant.components.osoenergy.PLATFORMS", [Platform.WATER_HEATER])
async def test_water_heater(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_osoenergy_client: MagicMock,
    snapshot: SnapshotAssertion,
    mock_config_entry: ConfigEntry,
) -> None:
    """Test states of the water heater."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.freeze_time("2024-10-10 00:00:00")
async def test_get_profile(
    hass: HomeAssistant,
    mock_osoenergy_client: MagicMock,
    mock_config_entry: ConfigEntry,
) -> None:
    """Test getting the heater profile."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    profile = await hass.services.async_call(
        DOMAIN,
        SERVICE_GET_PROFILE,
        {ATTR_ENTITY_ID: "water_heater.test_device"},
        blocking=True,
        return_response=True,
    )

    # The profile is returned in UTC format from the server
    # Each index represents an hour from the current day (0-23). For example index 2 - 02:00 UTC
    # Depending on the time zone and the DST the UTC hour is converted to local time and the value is placed in the correct index
    # Example: time zone 'US/Pacific' and DST (-7 hours difference) - index 9 (09:00 UTC) will be converted to index 2 (02:00 Local)
    assert profile == {
        "water_heater.test_device": {
            "profile": [
                60,
                60,
                60,
                60,
                60,
                60,
                60,
                60,
                60,
                60,
                60,
                60,
                60,
                60,
                60,
                60,
                60,
                10,
                60,
                60,
                60,
                60,
                60,
                60,
            ],
        },
    }


@pytest.mark.freeze_time("2024-10-10 00:00:00")
async def test_set_profile(
    hass: HomeAssistant,
    mock_osoenergy_client: MagicMock,
    mock_config_entry: ConfigEntry,
) -> None:
    """Test getting the heater profile."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_PROFILE,
        {ATTR_ENTITY_ID: "water_heater.test_device", "hour_01": 45},
        blocking=True,
    )

    # The server expects to receive the profile in UTC format
    # Each field represents an hour from the current day (0-23). For example field hour_01 - 01:00 Local time
    # Depending on the time zone and the DST the Local hour is converted to UTC time and the value is placed in the correct index
    # Example: time zone 'US/Pacific' and DST (-7 hours difference) - index 1 (01:00 Local) will be converted to index 8 (08:00 Utc)
    mock_osoenergy_client().hotwater.set_profile.assert_called_once_with(
        ANY,
        [
            10,
            60,
            60,
            60,
            60,
            60,
            60,
            60,
            45,
            60,
            60,
            60,
            60,
            60,
            60,
            60,
            60,
            60,
            60,
            60,
            60,
            60,
            60,
            60,
        ],
    )


async def test_set_v40_min(
    hass: HomeAssistant,
    mock_osoenergy_client: MagicMock,
    mock_config_entry: ConfigEntry,
) -> None:
    """Test getting the heater profile."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_V40MIN,
        {ATTR_ENTITY_ID: "water_heater.test_device", ATTR_V40MIN: 300},
        blocking=True,
    )

    mock_osoenergy_client().hotwater.set_v40_min.assert_called_once_with(ANY, 300)


async def test_set_temperature(
    hass: HomeAssistant,
    mock_osoenergy_client: MagicMock,
    mock_config_entry: ConfigEntry,
) -> None:
    """Test getting the heater profile."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.services.async_call(
        WATER_HEATER_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: "water_heater.test_device", ATTR_TEMPERATURE: 45},
        blocking=True,
    )

    mock_osoenergy_client().hotwater.set_profile.assert_called_once_with(
        ANY,
        [
            45,
            45,
            45,
            45,
            45,
            45,
            45,
            45,
            45,
            45,
            45,
            45,
            45,
            45,
            45,
            45,
            45,
            45,
            45,
            45,
            45,
            45,
            45,
            45,
        ],
    )


async def test_turn_on(
    hass: HomeAssistant,
    mock_osoenergy_client: MagicMock,
    mock_config_entry: ConfigEntry,
) -> None:
    """Test turning the heater on."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.services.async_call(
        WATER_HEATER_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "water_heater.test_device"},
        blocking=True,
    )

    mock_osoenergy_client().hotwater.turn_on.assert_called_once_with(ANY, True)


async def test_turn_off(
    hass: HomeAssistant,
    mock_osoenergy_client: MagicMock,
    mock_config_entry: ConfigEntry,
) -> None:
    """Test getting the heater profile."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.services.async_call(
        WATER_HEATER_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "water_heater.test_device"},
        blocking=True,
    )

    mock_osoenergy_client().hotwater.turn_off.assert_called_once_with(ANY, True)


async def test_oso_turn_on(
    hass: HomeAssistant,
    mock_osoenergy_client: MagicMock,
    mock_config_entry: ConfigEntry,
) -> None:
    """Test turning the heater on."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.services.async_call(
        DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "water_heater.test_device", ATTR_UNTIL_TEMP_LIMIT: False},
        blocking=True,
    )

    mock_osoenergy_client().hotwater.turn_on.assert_called_once_with(ANY, False)


async def test_oso_turn_off(
    hass: HomeAssistant,
    mock_osoenergy_client: MagicMock,
    mock_config_entry: ConfigEntry,
) -> None:
    """Test getting the heater profile."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.services.async_call(
        DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "water_heater.test_device", ATTR_UNTIL_TEMP_LIMIT: False},
        blocking=True,
    )

    mock_osoenergy_client().hotwater.turn_off.assert_called_once_with(ANY, False)
