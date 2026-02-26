"""Support for EnOcean devices."""

from collections.abc import Callable
from dataclasses import dataclass

from enocean_async import EnOceanGateway
import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_DEVICE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_connect, dispatcher_send
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN, SIGNAL_RECEIVE_MESSAGE, SIGNAL_SEND_MESSAGE

type EnOceanConfigEntry = ConfigEntry[EnOceanGateway]


@dataclass
class EnOceanHassData:
    """Store gateway and dispatcher in hass.data (TEMPORARY until legacy code is removed)."""

    gateway: EnOceanGateway
    disconnect_handle: Callable | None


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
    gateway = EnOceanGateway(port=config_entry.data[CONF_DEVICE])

    gateway.add_erp1_received_callback(
        lambda packet: dispatcher_send(hass, SIGNAL_RECEIVE_MESSAGE, packet)
    )

    try:
        await gateway.start()
    except ConnectionError as err:
        raise ConfigEntryNotReady(f"Failed to start EnOcean gateway: {err}") from err

    config_entry.runtime_data = gateway

    hass.data.setdefault(
        DOMAIN,
        EnOceanHassData(
            gateway=gateway,
            disconnect_handle=async_dispatcher_connect(
                hass, SIGNAL_SEND_MESSAGE, gateway.send_esp3_packet
            ),
        ),
    )
    return True


async def async_unload_entry(
    hass: HomeAssistant, config_entry: EnOceanConfigEntry
) -> bool:
    """Unload EnOcean config entry."""

    gateway = config_entry.runtime_data
    await gateway.stop()

    hass_data: EnOceanHassData | None = hass.data.get(DOMAIN)
    if hass_data is not None and hass_data.disconnect_handle is not None:
        hass_data.disconnect_handle()
        hass_data.disconnect_handle = None

    return True
