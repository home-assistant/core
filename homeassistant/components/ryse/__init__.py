import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from custom_components.ryse.bluetooth import RyseBLEDevice

_LOGGER = logging.getLogger(__name__)

DOMAIN = "ryse"


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the RYSE component."""
    _LOGGER.debug("Setting up RYSE Device integration")
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up RYSE from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = entry

    device = RyseBLEDevice(
        address=entry.data["address"],
        rx_uuid=entry.data["rx_uuid"],
        tx_uuid=entry.data["tx_uuid"],
    )

    async def handle_pair(call):
        """Handle the pair_device service call."""
        paired = await device.pair()
        if paired:
            device_info = await device.get_device_info()
            _LOGGER.debug("Getting Device Info")

    async def handle_unpair(call):
        """Handle the unpair_device service call."""
        await device.unpair()

    async def handle_read(call):
        """Handle the read_info service call."""
        data = await device.read_data()
        if data:
            _LOGGER.debug("Reading Data")

    async def handle_write(call):
        """Handle the send_raw_data service call."""
        data = bytes.fromhex(call.data["data"])
        await device.write_data(data)

    hass.services.async_register(DOMAIN, "pair_device", handle_pair)
    hass.services.async_register(DOMAIN, "unpair_device", handle_unpair)
    hass.services.async_register(DOMAIN, "read_info", handle_read)
    hass.services.async_register(DOMAIN, "send_raw_data", handle_write)

    await hass.config_entries.async_forward_entry_setups(entry, ["cover"])

    return True
