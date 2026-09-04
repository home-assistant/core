"""Tests for the Openhome media player platform."""

from unittest.mock import AsyncMock, MagicMock, patch

from openhomedevice.exceptions import OpenhomeConnectionError
import pytest

from homeassistant.components.media_player import DOMAIN as MEDIA_PLAYER_DOMAIN
from homeassistant.components.openhome.const import DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, CONF_HOST, SERVICE_TURN_OFF, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from tests.common import MockConfigEntry

ENTITY_ID = "media_player.friendly_name"


async def test_action_error_is_raised(hass: HomeAssistant) -> None:
    """Test a failing action raises rather than being swallowed."""
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: "http://localhost"}, unique_id="uuid"
    )
    entry.add_to_hass(hass)

    set_standby = AsyncMock(side_effect=OpenhomeConnectionError("no route to host"))

    with (
        patch("homeassistant.components.openhome.PLATFORMS", [Platform.MEDIA_PLAYER]),
        patch("homeassistant.components.openhome.Device", MagicMock()) as mock_device,
    ):
        device = mock_device.return_value
        device.init = AsyncMock()
        device.uuid = MagicMock(return_value="uuid")
        device.manufacturer = MagicMock(return_value="manufacturer")
        device.model_name = MagicMock(return_value="model_name")
        device.friendly_name = MagicMock(return_value="friendly_name")
        device.set_standby = set_standby

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        with pytest.raises(HomeAssistantError):
            await hass.services.async_call(
                MEDIA_PLAYER_DOMAIN,
                SERVICE_TURN_OFF,
                {ATTR_ENTITY_ID: ENTITY_ID},
                blocking=True,
            )

    set_standby.assert_awaited_once_with(True)
