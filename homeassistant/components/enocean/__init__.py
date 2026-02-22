"""Support for EnOcean devices."""

from serial import SerialException
import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_DEVICE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN
from .dongle import EnOceanDongle

type EnOceanConfigEntry = ConfigEntry[EnOceanDongle]

CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: vol.Schema({vol.Required(CONF_DEVICE): cv.string})}, extra=vol.ALLOW_EXTRA
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the EnOcean component."""
    # support for text-based configuration (legacy)
    if DOMAIN not in config:
        return True

    if hass.config_entries.async_entries(DOMAIN):
        # We can only have one dongle. If there is already one in the config,
        # there is no need to import the yaml based config.
        return True

    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=config[DOMAIN]
        )
    )

    return True


async def async_setup_entry(
    hass: HomeAssistant, config_entry: EnOceanConfigEntry
) -> bool:
    """Set up an EnOcean dongle for the given entry."""
    try:
        usb_dongle = EnOceanDongle(hass, config_entry.data[CONF_DEVICE])
    except SerialException as err:
        raise ConfigEntryNotReady(f"Failed to set up EnOcean dongle: {err}") from err
    await usb_dongle.async_setup()
    config_entry.runtime_data = usb_dongle

    return True


async def async_unload_entry(
    hass: HomeAssistant, config_entry: EnOceanConfigEntry
) -> bool:
    """Unload EnOcean config entry."""

    enocean_dongle = config_entry.runtime_data
    enocean_dongle.unload()

    return True
