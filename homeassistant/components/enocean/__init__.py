"""Support for EnOcean devices."""

from dataclasses import dataclass
from typing import Any

from homeassistant_enocean.gateway import EnOceanHomeAssistantGateway
import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_DEVICE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.dispatcher import async_dispatcher_connect, dispatcher_send
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN, PLATFORMS, SIGNAL_RECEIVE_MESSAGE, SIGNAL_SEND_MESSAGE

type EnOceanConfigEntry = ConfigEntry[EnOceanHomeAssistantGateway]

CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: vol.Schema({vol.Required(CONF_DEVICE): cv.string})}, extra=vol.ALLOW_EXTRA
)


@dataclass
class EnOceanHassData:
    """Data stored in hass.data for EnOcean integration."""

    gateway: EnOceanHomeAssistantGateway
    dispatcher_disconnect_handle: Any


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
    """Set up an EnOcean gateway for the given config entry."""

    gateway: EnOceanHomeAssistantGateway

    try:
        gateway = EnOceanHomeAssistantGateway(
            config_entry.data[CONF_DEVICE], create_task=hass.create_task
        )
        await gateway.start()
        gateway.legacy_handle_packet_callback = lambda packet: dispatcher_send(
            hass, SIGNAL_RECEIVE_MESSAGE, packet
        )
    except Exception as ex:
        raise ConfigEntryError from ex

    config_entry.runtime_data = gateway

    # storage in hass.data is needed for (later) transfer of device setup from yaml to UI
    # it will be removed once this transfer is done and yaml support is removed
    hass.data.setdefault(
        DOMAIN,
        EnOceanHassData(gateway=None, dispatcher_disconnect_handle=None),
    )
    hass.data[DOMAIN].gateway = gateway
    hass.data[DOMAIN].dispatcher_disconnect_handle = async_dispatcher_connect(
        hass, SIGNAL_SEND_MESSAGE, gateway.legacy_send_packet
    )

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

    if not await hass.config_entries.async_unload_platforms(config_entry, PLATFORMS):
        return False

    config_entry.runtime_data.stop()

    hass_data: EnOceanHassData | None = hass.data.get(DOMAIN)
    if hass_data and hass_data.dispatcher_disconnect_handle:
        hass_data.dispatcher_disconnect_handle()
        hass_data.dispatcher_disconnect_handle = None

    return True
