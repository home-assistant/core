"""Tests for the MadVR remote entity."""

from __future__ import annotations

from unittest.mock import AsyncMock

from homeassistant.components.remote import DOMAIN as REMOTE_DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_TURN_OFF, SERVICE_TURN_ON
from homeassistant.core import HomeAssistant
import homeassistant.helpers.entity_registry as er

from . import setup_integration
from .const import MOCK_MAC

from tests.common import MockConfigEntry


async def test_remote_setup(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setup of the remote entity."""
    await setup_integration(hass, mock_config_entry)

    entity_registry = er.async_get(hass)
    remote_entity = entity_registry.async_get(f"{REMOTE_DOMAIN}.madvr_envy")

    assert remote_entity is not None
    assert remote_entity.unique_id == MOCK_MAC


async def test_remote_power(
    hass: HomeAssistant,
    mock_madvr_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test turning on the remote entity."""

    await setup_integration(hass, mock_config_entry)
    await hass.async_block_till_done()

    entity_id = f"{REMOTE_DOMAIN}.madvr_envy"
    remote = hass.states.get(entity_id)
    assert remote.state == "on"

    await hass.services.async_call(
        REMOTE_DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    await hass.async_block_till_done()

    mock_madvr_client.power_off.assert_called_once()

    await hass.services.async_call(
        REMOTE_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    await hass.async_block_till_done()

    mock_madvr_client.power_on.assert_called_once()


async def test_send_command(
    hass: HomeAssistant,
    mock_madvr_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test sending command to the remote entity."""

    await setup_integration(hass, mock_config_entry)
    await hass.async_block_till_done()

    entity_id = f"{REMOTE_DOMAIN}.madvr_envy"
    remote = hass.states.get(entity_id)
    assert remote.state == "on"

    await hass.services.async_call(
        REMOTE_DOMAIN,
        "send_command",
        {ATTR_ENTITY_ID: entity_id, "command": "test"},
        blocking=True,
    )
    await hass.async_block_till_done()

    mock_madvr_client.add_command_to_queue.assert_called_once_with(["test"])
