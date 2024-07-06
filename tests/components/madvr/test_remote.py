"""Tests for the MadVR remote entity."""

from __future__ import annotations

from homeassistant.components.remote import DOMAIN as REMOTE_DOMAIN
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
