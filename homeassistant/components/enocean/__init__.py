"""Support for EnOcean devices."""

from enocean_async import Gateway
import voluptuous as vol

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

from .const import (
    DOMAIN,
    SIGNAL_OBSERVATION,
    SIGNAL_RECEIVE_MESSAGE,
    SIGNAL_SEND_MESSAGE,
)

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

    # immediately store the gateway in the hass.data to make it available for platform setup
    hass.data.setdefault(DOMAIN, gateway)

    # this is the Gateway's low level callback; it is used for the legacy code
    # once all code is migrated to use the high-level observation callback, this can be removed
    gateway.add_erp1_received_callback(
        lambda packet: async_dispatcher_send(hass, SIGNAL_RECEIVE_MESSAGE, packet)
    )

    # this is the Gateway's high-level callback; it is used for all new code
    gateway.add_observation_callback(
        lambda obs: async_dispatcher_send(hass, SIGNAL_OBSERVATION, obs)
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
