"""Support for EnOcean devices."""

from enocean_async import Gateway
import voluptuous as vol

from homeassistant.components.usb import (
    get_serial_by_id,
    usb_device_from_path,
    usb_service_info_from_device,
    usb_unique_id_from_service_info,
)
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_DEVICE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN, LOGGER, SIGNAL_RECEIVE_MESSAGE, SIGNAL_SEND_MESSAGE

type EnOceanConfigEntry = ConfigEntry[Gateway]

CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: vol.Schema({vol.Required(CONF_DEVICE): cv.string})}, extra=vol.ALLOW_EXTRA
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the EnOcean component."""
    # support for text-based configuration (legacy)
    if DOMAIN not in config:
        return True

    if hass.config_entries.async_entries(DOMAIN):
        # We can only have one gateway. If there is already one in the config,
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
    """Set up an EnOcean gateway for the given entry."""
    gateway = Gateway(port=config_entry.data[CONF_DEVICE])

    gateway.add_erp1_received_callback(
        lambda packet: async_dispatcher_send(hass, SIGNAL_RECEIVE_MESSAGE, packet)
    )

    try:
        await gateway.start()
    except ConnectionError as err:
        gateway.stop()
        raise ConfigEntryNotReady(f"Failed to start EnOcean gateway: {err}") from err

    config_entry.runtime_data = gateway

    config_entry.async_on_unload(
        async_dispatcher_connect(hass, SIGNAL_SEND_MESSAGE, gateway.send_esp3_packet)
    )
    return True


async def async_unload_entry(
    hass: HomeAssistant, config_entry: EnOceanConfigEntry
) -> bool:
    """Unload EnOcean config entry: stop the gateway."""

    config_entry.runtime_data.stop()
    return True


async def async_migrate_entry(
    hass: HomeAssistant, config_entry: EnOceanConfigEntry
) -> bool:
    """Migrate config entry."""
    if config_entry.version != 1:
        LOGGER.error(
            "Cannot migrate config entry %s: unsupported version %s",
            config_entry.entry_id,
            config_entry.version,
        )
        return False

    if config_entry.minor_version < 2:
        new_unique_id = config_entry.unique_id
        new_device_path = config_entry.data[CONF_DEVICE]
        LOGGER.debug(
            "Migrating config entry %s to version %s.%s",
            config_entry.entry_id,
            1,
            2,
        )

        # normalize device path
        new_device_path = await hass.async_add_executor_job(
            get_serial_by_id, config_entry.data[CONF_DEVICE]
        )

        if config_entry.unique_id is None:
            LOGGER.debug(
                "Config entry %s has no unique_id, attempting to set it based on the usb device path",
                config_entry.entry_id,
            )

            usb_device = await hass.async_add_executor_job(
                usb_device_from_path, new_device_path
            )
            if usb_device is None:
                LOGGER.warning(
                    "Cannot fully migrate config entry %s: USB device at path %s not found; "
                    "proceeding without setting a unique_id",
                    config_entry.entry_id,
                    new_device_path,
                )
            else:
                # set unique id
                new_unique_id = usb_unique_id_from_service_info(
                    usb_service_info_from_device(usb_device)
                )

        hass.config_entries.async_update_entry(
            config_entry,
            data={**config_entry.data, CONF_DEVICE: new_device_path},
            unique_id=new_unique_id,
            version=1,
            minor_version=2,
        )
        LOGGER.debug(
            "Migrated config entry %s to version %s.%s",
            config_entry.entry_id,
            1,
            2,
        )
    return True
