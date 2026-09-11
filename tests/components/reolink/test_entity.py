"""Test the Reolink entity file."""

from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory

from homeassistant.components.reolink.coordinator import DEVICE_UPDATE_INTERVAL_MIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant

from .conftest import TEST_CAM_NAME

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_battery_available(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    config_entry: MockConfigEntry,
    reolink_host: MagicMock,
) -> None:
    """Test available property of a entity from a Reolink battery camera."""
    reolink_host.volume.return_value = 80
    reolink_host.is_battery = True

    with patch("homeassistant.components.reolink.PLATFORMS", [Platform.NUMBER]):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.LOADED

    entity_id = f"{Platform.NUMBER}.{TEST_CAM_NAME}_volume"

    assert hass.states.get(entity_id).state == "80"

    reolink_host.baichuan.login_sucess = False
    freezer.tick(2 * DEVICE_UPDATE_INTERVAL_MIN)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE
