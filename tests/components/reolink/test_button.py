"""Test the Reolink button platform."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from reolink_aio.exceptions import ReolinkError

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN
from homeassistant.components.reolink import const
from homeassistant.components.reolink.button import ATTR_SPEED
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from .conftest import TEST_NVR_NAME, TEST_UID

from tests.common import MockConfigEntry


async def test_button(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    reolink_connect: MagicMock,
) -> None:
    """Test button entity with ptz up."""
    with patch("homeassistant.components.reolink.PLATFORMS", [Platform.BUTTON]):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.LOADED

    entity_id = f"{Platform.BUTTON}.{TEST_NVR_NAME}_ptz_up"

    reolink_connect.set_ptz_command = AsyncMock()
    await hass.services.async_call(
        BUTTON_DOMAIN,
        "press",
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    reolink_connect.set_ptz_command.assert_called_once()

    reolink_connect.set_ptz_command = AsyncMock(side_effect=ReolinkError("Test error"))
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            BUTTON_DOMAIN,
            "press",
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )

    reolink_connect.set_ptz_command = AsyncMock()
    await hass.services.async_call(
        const.DOMAIN,
        "ptz_move",
        {ATTR_ENTITY_ID: entity_id, ATTR_SPEED: 5},
        blocking=True,
    )
    reolink_connect.set_ptz_command.assert_called_with(0, command="Up", speed=5)

    reolink_connect.set_ptz_command = AsyncMock(side_effect=ReolinkError("Test error"))
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            const.DOMAIN,
            "ptz_move",
            {ATTR_ENTITY_ID: entity_id, ATTR_SPEED: 5},
            blocking=True,
        )


async def test_host_button(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    reolink_connect: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test host button entity with reboot."""
    unique_id = f"{TEST_UID}_reboot"
    entity_id = f"{Platform.BUTTON}.{TEST_NVR_NAME}_reboot"

    # enable the reboot button entity
    entity_registry.async_get_or_create(
        domain=Platform.BUTTON,
        platform=const.DOMAIN,
        unique_id=unique_id,
        config_entry=config_entry,
        suggested_object_id=f"{TEST_NVR_NAME}_reboot",
        disabled_by=None,
    )

    with patch("homeassistant.components.reolink.PLATFORMS", [Platform.BUTTON]):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.LOADED

    reolink_connect.reboot = AsyncMock()
    await hass.services.async_call(
        BUTTON_DOMAIN,
        "press",
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    reolink_connect.reboot.assert_called_once()

    reolink_connect.reboot = AsyncMock(side_effect=ReolinkError("Test error"))
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            BUTTON_DOMAIN,
            "press",
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )
