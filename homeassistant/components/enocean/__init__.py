"""Support for EnOcean devices."""

from homeassistant import config_entries, core
from homeassistant.const import CONF_DEVICE

from .const import DATA_ENOCEAN, ENOCEAN_DONGLE
from .dongle import EnOceanDongle


async def async_setup_entry(
    hass: core.HomeAssistant, config_entry: config_entries.ConfigEntry
):
    """Set up an EnOcean dongle for the given entry."""
    enocean_data = hass.data.setdefault(DATA_ENOCEAN, {})
    usb_dongle = EnOceanDongle(hass, config_entry.data[CONF_DEVICE])
    await usb_dongle.async_setup()
    enocean_data[ENOCEAN_DONGLE] = usb_dongle

    return True


async def async_unload_entry(hass, config_entry):
    """Unload ENOcean config entry."""

    enocean_dongle = hass.data[DATA_ENOCEAN][ENOCEAN_DONGLE]
    enocean_dongle.unload()
    hass.data.pop(DATA_ENOCEAN)

    return True
