"""Test the Reolink services."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from reolink_aio.api import Chime
from reolink_aio.exceptions import InvalidParameterError, ReolinkError

from homeassistant.components.reolink.const import DOMAIN as REOLINK_DOMAIN
from homeassistant.components.reolink.services import ATTR_RINGTONE
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_DEVICE_ID, ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er

from .conftest import TEST_NVR_NAME

from tests.common import MockConfigEntry


async def test_play_chime_service_entity(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    reolink_connect: MagicMock,
    test_chime: Chime,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test chime play service."""
    with patch("homeassistant.components.reolink.PLATFORMS", [Platform.SELECT]):
        assert await hass.config_entries.async_setup(config_entry.entry_id) is True
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    entity_id = f"{Platform.SELECT}.test_chime_visitor_ringtone"
    entity = entity_registry.async_get(entity_id)
    assert entity is not None
    device_id = entity.device_id

    # Test chime play service with entity
    test_chime.play = AsyncMock()
    await hass.services.async_call(
        REOLINK_DOMAIN,
        "play_chime",
        {ATTR_ENTITY_ID: [entity_id], ATTR_RINGTONE: "attraction"},
        blocking=True,
    )
    test_chime.play.assert_called_once()

    # Test chime play service with device
    test_chime.play = AsyncMock()
    await hass.services.async_call(
        REOLINK_DOMAIN,
        "play_chime",
        {ATTR_DEVICE_ID: [device_id], ATTR_RINGTONE: "attraction"},
        blocking=True,
    )
    test_chime.play.assert_called_once()

    # Test errors
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            REOLINK_DOMAIN,
            "play_chime",
            {ATTR_DEVICE_ID: ["invalid_id"], ATTR_RINGTONE: "attraction"},
            blocking=True,
        )

    entity_id_non_chime = f"{Platform.SELECT}.{TEST_NVR_NAME}_floodlight_mode"
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            REOLINK_DOMAIN,
            "play_chime",
            {ATTR_ENTITY_ID: [entity_id_non_chime], ATTR_RINGTONE: "attraction"},
            blocking=True,
        )

    test_chime.play = AsyncMock(side_effect=ReolinkError("Test error"))
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            REOLINK_DOMAIN,
            "play_chime",
            {ATTR_ENTITY_ID: [entity_id], ATTR_RINGTONE: "attraction"},
            blocking=True,
        )

    test_chime.play = AsyncMock(side_effect=InvalidParameterError("Test error"))
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            REOLINK_DOMAIN,
            "play_chime",
            {ATTR_ENTITY_ID: [entity_id], ATTR_RINGTONE: "attraction"},
            blocking=True,
        )
