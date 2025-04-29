"""Define tests for the Airzone init."""

from unittest.mock import patch

from homeassistant.components.airzone_mqtt.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from .util import CONFIG

from tests.common import MockConfigEntry
from tests.typing import MqttMockHAClient


async def test_unload_entry(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
) -> None:
    """Test unload."""

    config_entry = MockConfigEntry(
        data=CONFIG,
        domain=DOMAIN,
    )
    config_entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.airzone_mqtt.AirzoneMqttApi.update",
            return_value=None,
        ),
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        assert config_entry.state is ConfigEntryState.LOADED

        await hass.config_entries.async_unload(config_entry.entry_id)
        await hass.async_block_till_done()
        assert config_entry.state is ConfigEntryState.NOT_LOADED
