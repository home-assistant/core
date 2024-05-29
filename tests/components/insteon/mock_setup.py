"""Utility to setup the Insteon integration."""

from homeassistant.components.insteon.api import async_load_api
from homeassistant.components.insteon.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .const import MOCK_USER_INPUT_PLM
from .mock_devices import MockDevices

from tests.common import MockConfigEntry
from tests.typing import WebSocketGenerator


async def async_mock_setup(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    config_data: dict | None = None,
    config_options: dict | None = None,
):
    """Set up for tests."""
    config_data = MOCK_USER_INPUT_PLM if config_data is None else config_data
    config_options = {} if config_options is None else config_options
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        entry_id="abcde12345",
        data=config_data,
        options=config_options,
    )
    config_entry.add_to_hass(hass)
    async_load_api(hass)

    ws_client = await hass_ws_client(hass)
    devices = MockDevices()
    await devices.async_load()

    dev_reg = dr.async_get(hass)
    # Create device registry entry for mock node
    ha_device = dev_reg.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, "11.11.11")},
        name="Device 11.11.11",
    )
    return ws_client, devices, ha_device, dev_reg
