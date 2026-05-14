"""The russound_rio component."""

import logging

from aiorussound import RussoundTcpConnectionHandler
from aiorussound.connection import (
    RussoundConnectionHandler,
    RussoundSerialConnectionHandler,
)
from aiorussound.rio import RussoundRIOClient
from aiorussound.rio.models import CallbackType

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_DEVICE, CONF_HOST, CONF_PORT, CONF_TYPE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC

from .const import CONF_BAUDRATE, DOMAIN, RUSSOUND_RIO_EXCEPTIONS, TYPE_TCP

PLATFORMS = [Platform.MEDIA_PLAYER, Platform.NUMBER, Platform.SELECT, Platform.SWITCH]

_LOGGER = logging.getLogger(__name__)

type RussoundConfigEntry = ConfigEntry[RussoundRIOClient]


async def async_setup_entry(hass: HomeAssistant, entry: RussoundConfigEntry) -> bool:
    """Set up a config entry."""
    handler: RussoundConnectionHandler
    if entry.data[CONF_TYPE] == TYPE_TCP:
        host = entry.data[CONF_HOST]
        port = entry.data[CONF_PORT]
        handler = RussoundTcpConnectionHandler(host, port)
    else:
        device = entry.data[CONF_DEVICE]
        baudrate = entry.data[CONF_BAUDRATE]
        handler = RussoundSerialConnectionHandler(device, baudrate)
    client = RussoundRIOClient(handler)

    async def _connection_update_callback(
        _client: RussoundRIOClient, _callback_type: CallbackType
    ) -> None:
        """Call when the device is notified of changes."""
        if _callback_type == CallbackType.CONNECTION:
            if _client.is_connected():
                _LOGGER.warning("Reconnected to device at %s", entry.data[CONF_HOST])
            else:
                _LOGGER.warning("Disconnected from device at %s", entry.data[CONF_HOST])

    await client.register_state_update_callbacks(_connection_update_callback)

    try:
        await client.connect()
        await client.load_zone_source_metadata()
    except RUSSOUND_RIO_EXCEPTIONS as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="entry_cannot_connect",
            translation_placeholders={
                "host": host or device,
                "port": port or baudrate,
            },
        ) from err
    entry.runtime_data = client

    device_registry = dr.async_get(hass)

    for controller_id, controller in client.controllers.items():
        _device_identifier = (
            controller.mac_address
            or f"{client.controllers[1].mac_address}-{controller_id}"
        )
        connections = None
        via_device = None
        configuration_url = None
        if controller_id != 1:
            assert client.controllers[1].mac_address
            via_device = (
                DOMAIN,
                client.controllers[1].mac_address,
            )
        else:
            assert controller.mac_address
            connections = {(CONNECTION_NETWORK_MAC, controller.mac_address)}
        if isinstance(client.connection_handler, RussoundTcpConnectionHandler):
            configuration_url = f"http://{client.connection_handler.host}"
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, _device_identifier)},
            manufacturer="Russound",
            name=controller.controller_type,
            model=controller.controller_type,
            sw_version=controller.firmware_version,
            connections=connections,
            via_device=via_device,
            configuration_url=configuration_url,
        )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: RussoundConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        await entry.runtime_data.disconnect()

    return unload_ok


async def async_migrate_entry(
    hass: HomeAssistant, config_entry: RussoundConfigEntry
) -> bool:
    """Migrate old entry."""
    if config_entry.version > 2:
        # This means the user has downgraded from a future version
        return False

    if config_entry.version == 1:
        (
            hass.config_entries.async_update_entry(
                config_entry,
                data={
                    CONF_TYPE: TYPE_TCP,
                    **config_entry.data,
                },
                version=2,
            ),
        )

    _LOGGER.debug(
        "Migration to configuration version %s successful", config_entry.version
    )

    return True
