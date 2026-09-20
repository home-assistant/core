"""Tests for the Honeywell Lyric select platform."""

from unittest.mock import patch

import pytest

from homeassistant.components.lyric.const import DOMAIN
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("setup_credentials", "mock_lyric_mixed_devices")
async def test_room_priority_select_created_regardless_of_device_id_prefix(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """The room priority select is created regardless of device ID prefix."""
    with patch("homeassistant.components.lyric.PLATFORMS", [Platform.SELECT]):
        await setup_integration(hass, mock_config_entry)

    lcc_select = hass.states.get(
        entity_registry.async_get_entity_id(
            Platform.SELECT, DOMAIN, "AABBCC000001_room_priority"
        )
    )
    assert lcc_select.attributes["options"] == ["follow_me", "Living Room"]

    non_lcc_select = hass.states.get(
        entity_registry.async_get_entity_id(
            Platform.SELECT, DOMAIN, "AABBCC000002_room_priority"
        )
    )
    assert non_lcc_select.attributes["options"] == ["follow_me", "Office"]

    assert (
        entity_registry.async_get_entity_id(
            Platform.SELECT, DOMAIN, "AABBCC000003_room_priority"
        )
        is None
    )
