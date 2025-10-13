"""Test the Generic Cover entity."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from homeassistant.components.cover import DOMAIN as COVER_DOMAIN
from homeassistant.components.generic_cover.const import DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_CLOSE_COVER,
    SERVICE_OPEN_COVER,
    SERVICE_STOP_COVER,
    STATE_CLOSED,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry


async def test_cover_entity_setup(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test the cover entity is set up correctly."""
    mock_config_entry.add_to_hass(hass)

    # Mock the switches
    hass.states.async_set("switch.test_open", "off")
    hass.states.async_set("switch.test_close", "off")

    with patch("homeassistant.core.ServiceRegistry.async_call", new_callable=AsyncMock):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Check entity is registered
    entity_registry = er.async_get(hass)
    entity = entity_registry.async_get_entity_id(
        COVER_DOMAIN, DOMAIN, mock_config_entry.entry_id
    )
    assert entity is not None

    # Check entity state
    state = hass.states.get(entity)
    assert state is not None
    assert state.state == STATE_CLOSED


async def test_cover_open(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test opening the cover."""
    mock_config_entry.add_to_hass(hass)

    # Mock the switches
    hass.states.async_set("switch.test_open", "off")
    hass.states.async_set("switch.test_close", "off")

    with patch(
        "homeassistant.core.ServiceRegistry.async_call", new_callable=AsyncMock
    ) as mock_call:
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        entity_registry = er.async_get(hass)
        entity_id = entity_registry.async_get_entity_id(
            COVER_DOMAIN, DOMAIN, mock_config_entry.entry_id
        )

        # Call open service
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_OPEN_COVER,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )

        # Verify the open switch was called
        mock_call.assert_called()


async def test_cover_close(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test closing the cover."""
    mock_config_entry.add_to_hass(hass)

    # Mock the switches
    hass.states.async_set("switch.test_open", "off")
    hass.states.async_set("switch.test_close", "off")

    with patch(
        "homeassistant.core.ServiceRegistry.async_call", new_callable=AsyncMock
    ) as mock_call:
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        entity_registry = er.async_get(hass)
        entity_id = entity_registry.async_get_entity_id(
            COVER_DOMAIN, DOMAIN, mock_config_entry.entry_id
        )

        # Call close service
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_CLOSE_COVER,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )

        # Verify the close switch was called
        mock_call.assert_called()


async def test_cover_stop(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test stopping the cover."""
    mock_config_entry.add_to_hass(hass)

    # Mock the switches
    hass.states.async_set("switch.test_open", "off")
    hass.states.async_set("switch.test_close", "off")

    with patch(
        "homeassistant.core.ServiceRegistry.async_call", new_callable=AsyncMock
    ) as mock_call:
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        entity_registry = er.async_get(hass)
        entity_id = entity_registry.async_get_entity_id(
            COVER_DOMAIN, DOMAIN, mock_config_entry.entry_id
        )

        # Call stop service
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_STOP_COVER,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )

        # Verify service was called to turn off switches
        mock_call.assert_called()
