"""ESPHome set up tests."""
from unittest.mock import AsyncMock

from aioesphomeapi import DeviceInfo

from homeassistant.components.esphome import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_unique_id_updated_to_mac(
    hass: HomeAssistant, mock_client, mock_zeroconf: None
) -> None:
    """Test we update config entry unique ID to MAC address."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "test.local", CONF_PORT: 6053, CONF_PASSWORD: ""},
        unique_id="mock-config-name",
    )
    entry.add_to_hass(hass)

    mock_client.device_info = AsyncMock(
        return_value=DeviceInfo(
            mac_address="1122334455aa",
        )
    )

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.unique_id == "11:22:33:44:55:aa"
