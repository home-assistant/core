"""Tests for the Hot Spring water heater platform."""

from unittest.mock import MagicMock

from hotspring import HotSpringConnectionError, HotSpringError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.water_heater import (
    ATTR_TEMPERATURE,
    DOMAIN as WATER_HEATER_DOMAIN,
    SERVICE_SET_TEMPERATURE,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import setup_with_selected_platforms

from tests.common import MockConfigEntry

ENTITY_ID = "water_heater.connectedspa_c59c9c"


async def test_water_heater_state(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the water heater entity state."""
    state = hass.states.get(ENTITY_ID)
    assert state == snapshot

    entry = entity_registry.async_get(ENTITY_ID)
    assert entry == snapshot


async def test_set_temperature(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hotspring: MagicMock,
) -> None:
    """Test setting target temperature."""
    await setup_with_selected_platforms(
        hass, mock_config_entry, [Platform.WATER_HEATER]
    )

    await hass.services.async_call(
        WATER_HEATER_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {
            ATTR_ENTITY_ID: ENTITY_ID,
            ATTR_TEMPERATURE: 103,
        },
        blocking=True,
    )

    mock_hotspring.set_temperature.assert_called_once_with(217.4)


async def test_set_temperature_connection_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hotspring: MagicMock,
) -> None:
    """Test connection error when setting target temperature."""
    await setup_with_selected_platforms(
        hass, mock_config_entry, [Platform.WATER_HEATER]
    )

    mock_hotspring.set_temperature.side_effect = HotSpringConnectionError

    with pytest.raises(
        HomeAssistantError, match="Error communicating with Hot Spring API"
    ):
        await hass.services.async_call(
            WATER_HEATER_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {
                ATTR_ENTITY_ID: ENTITY_ID,
                ATTR_TEMPERATURE: 103,
            },
            blocking=True,
        )


async def test_set_temperature_api_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hotspring: MagicMock,
) -> None:
    """Test API error when setting target temperature."""
    await setup_with_selected_platforms(
        hass, mock_config_entry, [Platform.WATER_HEATER]
    )

    mock_hotspring.set_temperature.side_effect = HotSpringError

    with pytest.raises(
        HomeAssistantError, match="Invalid response from Hot Spring API"
    ):
        await hass.services.async_call(
            WATER_HEATER_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {
                ATTR_ENTITY_ID: ENTITY_ID,
                ATTR_TEMPERATURE: 103,
            },
            blocking=True,
        )
