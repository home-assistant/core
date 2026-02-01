"""Support for EnOcean devices."""

from homeassistant_enocean.address import EnOceanDeviceAddress
from homeassistant_enocean.gateway import EnOceanHomeAssistantGateway
from homeassistant_enocean.legacy import combine_hex
import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_DEVICE, Platform
from homeassistant.core import _LOGGER, HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN, PLATFORMS

CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: vol.Schema({vol.Required(CONF_DEVICE): cv.string})}, extra=vol.ALLOW_EXTRA
)

type EnOceanConfigEntry = ConfigEntry[EnOceanHomeAssistantGateway]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the EnOcean component."""
    store_enocean_yaml_platform_config_in_hass_data(hass, config)

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


def store_enocean_yaml_platform_config_in_hass_data(
    hass: HomeAssistant, config: ConfigType
) -> None:
    """Store yaml configuration to hass.data for later retrieval during config entry setup."""
    hass.data.setdefault(DOMAIN, {})

    enocean_devices: dict[str, list[dict]] = hass.data[DOMAIN]

    for platform in PLATFORMS:
        if platform.value not in config:
            continue

        platform_config = config[platform.value]

        for entry in platform_config:
            if "platform" not in entry or entry["platform"] != DOMAIN:
                continue

            try:
                dev_id = entry["id"]
                eurid = EnOceanDeviceAddress.from_number(combine_hex(dev_id))
                device_name = (
                    "EnOcean " + platform.value.capitalize() + " " + eurid.to_string()
                )
                if "name" in entry:
                    device_name = entry["name"]

                if enocean_devices.get(eurid.to_string()) is None:
                    enocean_devices[eurid.to_string()] = []

                device_data = {
                    "platform": platform.value,
                    "name": device_name,
                }

                for key in (
                    "channel",
                    "sender_id",
                    "device_class",
                    "range_from",
                    "range_to",
                ):
                    if key in entry:
                        device_data[key] = entry[key]

                enocean_devices[eurid.to_string()].append(device_data)

            except ValueError:
                continue

    _LOGGER.warning(
        "Completed storing EnOcean yaml configuration to hass.data: %s", enocean_devices
    )


async def add_devices_from_config(
    gateway: EnOceanHomeAssistantGateway, config: ConfigType
) -> None:
    """Add devices from configuration."""
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


async def async_setup_entry(
    hass: HomeAssistant, config_entry: EnOceanConfigEntry
) -> bool:
    """Set up an EnOcean gateway for the given config entry."""

    gateway: EnOceanHomeAssistantGateway | None = None

    try:
        gateway = EnOceanHomeAssistantGateway(
            config_entry.data[CONF_DEVICE], create_task=hass.create_task
        )
        _LOGGER.info("Starting EnOcean gateway")
        await gateway.start()
        # gateway.legacy_callback()
        _LOGGER.info("EnOcean gateway started")
    except Exception as ex:
        raise ConfigEntryError from ex

    config_entry.runtime_data = gateway

    config_entry.async_on_unload(config_entry.add_update_listener(async_reload_entry))

    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, gateway.chip_id.to_string())},
        manufacturer="EnOcean",
        name="EnOcean Gateway",
        model="TCM300/310 Transmitter",
        serial_number=gateway.chip_id.to_string(),
        sw_version=gateway.sw_version,
        hw_version=gateway.chip_version,
    )

    return True


async def async_reload_entry(hass: HomeAssistant, entry: EnOceanConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(
    hass: HomeAssistant, config_entry: EnOceanConfigEntry
) -> bool:
    """Unload EnOcean config entry."""

    if unload_platforms := await hass.config_entries.async_unload_platforms(
        config_entry, PLATFORMS
    ):
        config_entry.runtime_data.stop()

    return unload_platforms
