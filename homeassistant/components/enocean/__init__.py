"""Support for EnOcean devices."""

from homeassistant_enocean.address import EnOceanDeviceAddress
from homeassistant_enocean.legacy import combine_hex
import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_DEVICE, Platform
from homeassistant.core import _LOGGER, HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import DATA_ENOCEAN, DOMAIN, ENOCEAN_DONGLE
from .dongle import EnOceanDongle

CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: vol.Schema({vol.Required(CONF_DEVICE): cv.string})}, extra=vol.ALLOW_EXTRA
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the EnOcean component."""

    # gateway = EnOceanHomeAssistantGateway()

    if Platform.BINARY_SENSOR in config:
        for entry in config[Platform.BINARY_SENSOR]:
            if "platform" not in entry or entry["platform"] != DOMAIN:
                continue

            if "id" not in entry:
                continue

            dev_id = entry["id"]
            try:
                eurid = EnOceanDeviceAddress.from_number(combine_hex(dev_id))
                device_name = "EnOcean Binary Sensor " + eurid.to_string()
                if "name" in entry:
                    device_name = entry["name"]

                _LOGGER.warning("Adding EnOcean binary sensor %s", device_name)

                # gateway.add_device(eurid, device_type=BINARY_SENSOR_DEVICE_TYPE, device_name = device_name, sender_id=None)

            except ValueError:
                continue

    # _LOGGER.warning("EnOcean platform %s found in config entries", config[platform.value])

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


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up an EnOcean dongle for the given entry."""
    enocean_data = hass.data.setdefault(DATA_ENOCEAN, {})
    usb_dongle = EnOceanDongle(hass, config_entry.data[CONF_DEVICE])
    await usb_dongle.async_setup()
    enocean_data[ENOCEAN_DONGLE] = usb_dongle

    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload EnOcean config entry."""

    enocean_dongle = hass.data[DATA_ENOCEAN][ENOCEAN_DONGLE]
    enocean_dongle.unload()
    hass.data.pop(DATA_ENOCEAN)

    return True
