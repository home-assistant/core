"""Support for Xiaomi Gateways."""

import asyncio
import logging

import voluptuous as vol
from xiaomi_gateway import AsyncXiaomiGatewayMulticast, XiaomiGateway

from homeassistant.components import persistent_notification
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_DEVICE_ID,
    CONF_HOST,
    CONF_PORT,
    CONF_PROTOCOL,
    EVENT_HOMEASSISTANT_STOP,
    Platform,
)
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_INTERFACE,
    CONF_KEY,
    CONF_SID,
    DEFAULT_DISCOVERY_RETRY,
    DOMAIN,
    GATEWAYS_KEY,
    KEY_SETUP_LOCK,
    KEY_UNSUB_STOP,
    LISTENER_KEY,
)

_LOGGER = logging.getLogger(__name__)

GATEWAY_PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.COVER,
    Platform.LIGHT,
    Platform.LOCK,
    Platform.SENSOR,
    Platform.SWITCH,
]
GATEWAY_PLATFORMS_NO_KEY = [Platform.BINARY_SENSOR, Platform.SENSOR]

ATTR_GW_MAC = "gw_mac"
ATTR_RINGTONE_ID = "ringtone_id"
ATTR_RINGTONE_VOL = "ringtone_vol"

SERVICE_PLAY_RINGTONE = "play_ringtone"
SERVICE_STOP_RINGTONE = "stop_ringtone"
SERVICE_ADD_DEVICE = "add_device"
SERVICE_REMOVE_DEVICE = "remove_device"

SERVICE_SCHEMA_PLAY_RINGTONE = vol.Schema(
    {
        vol.Required(ATTR_RINGTONE_ID): vol.All(
            vol.Coerce(int), vol.NotIn([9, 14, 15, 16, 17, 18, 19])
        ),
        vol.Optional(ATTR_RINGTONE_VOL): vol.All(
            vol.Coerce(int), vol.Clamp(min=0, max=100)
        ),
    }
)

SERVICE_SCHEMA_REMOVE_DEVICE = vol.Schema(
    {vol.Required(ATTR_DEVICE_ID): vol.All(cv.string, vol.Length(min=14, max=14))}
)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


def setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Xiaomi component."""

    def play_ringtone_service(call: ServiceCall) -> None:
        """Service to play ringtone through Gateway."""
        ring_id = call.data.get(ATTR_RINGTONE_ID)
        gateway: XiaomiGateway = call.data[ATTR_GW_MAC]

        kwargs = {"mid": ring_id}

        if (ring_vol := call.data.get(ATTR_RINGTONE_VOL)) is not None:
            kwargs["vol"] = ring_vol

        gateway.write_to_hub(gateway.sid, **kwargs)

    def stop_ringtone_service(call: ServiceCall) -> None:
        """Service to stop playing ringtone on Gateway."""
        gateway: XiaomiGateway = call.data[ATTR_GW_MAC]
        gateway.write_to_hub(gateway.sid, mid=10000)

    def add_device_service(call: ServiceCall) -> None:
        """Service to add a new sub-device within the next 30 seconds."""
        gateway: XiaomiGateway = call.data[ATTR_GW_MAC]
        gateway.write_to_hub(gateway.sid, join_permission="yes")
        persistent_notification.async_create(
            hass,
            (
                "Join permission enabled for 30 seconds! "
                "Please press the pairing button of the new device once."
            ),
            title="Xiaomi Aqara Gateway",
        )

    def remove_device_service(call: ServiceCall) -> None:
        """Service to remove a sub-device from the gateway."""
        device_id = call.data.get(ATTR_DEVICE_ID)
        gateway: XiaomiGateway = call.data[ATTR_GW_MAC]
        gateway.write_to_hub(gateway.sid, remove_device=device_id)

    gateway_only_schema = _add_gateway_to_schema(hass, vol.Schema({}))

    hass.services.register(
        DOMAIN,
        SERVICE_PLAY_RINGTONE,
        play_ringtone_service,
        schema=_add_gateway_to_schema(hass, SERVICE_SCHEMA_PLAY_RINGTONE),
    )

    hass.services.register(
        DOMAIN, SERVICE_STOP_RINGTONE, stop_ringtone_service, schema=gateway_only_schema
    )

    hass.services.register(
        DOMAIN, SERVICE_ADD_DEVICE, add_device_service, schema=gateway_only_schema
    )

    hass.services.register(
        DOMAIN,
        SERVICE_REMOVE_DEVICE,
        remove_device_service,
        schema=_add_gateway_to_schema(hass, SERVICE_SCHEMA_REMOVE_DEVICE),
    )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the xiaomi aqara components from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    setup_lock = hass.data[DOMAIN].setdefault(KEY_SETUP_LOCK, asyncio.Lock())
    hass.data[DOMAIN].setdefault(GATEWAYS_KEY, {})

    # Connect to Xiaomi Aqara Gateway
    xiaomi_gateway = await hass.async_add_executor_job(
        XiaomiGateway,
        entry.data[CONF_HOST],
        entry.data[CONF_SID],
        entry.data[CONF_KEY],
        DEFAULT_DISCOVERY_RETRY,
        entry.data[CONF_INTERFACE],
        entry.data[CONF_PORT],
        entry.data[CONF_PROTOCOL],
    )
    hass.data[DOMAIN][GATEWAYS_KEY][entry.entry_id] = xiaomi_gateway

    async with setup_lock:
        if LISTENER_KEY not in hass.data[DOMAIN]:
            multicast = AsyncXiaomiGatewayMulticast(
                interface=entry.data[CONF_INTERFACE]
            )
            hass.data[DOMAIN][LISTENER_KEY] = multicast

            # start listining for local pushes (only once)
            await multicast.start_listen()

            # register stop callback to shutdown listining for local pushes
            @callback
            def stop_xiaomi(event):
                """Stop Xiaomi Socket."""
                _LOGGER.debug("Shutting down Xiaomi Gateway Listener")
                multicast.stop_listen()

            unsub = hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, stop_xiaomi)
            hass.data[DOMAIN][KEY_UNSUB_STOP] = unsub

    multicast = hass.data[DOMAIN][LISTENER_KEY]
    multicast.register_gateway(entry.data[CONF_HOST], xiaomi_gateway.multicast_callback)
    _LOGGER.debug(
        "Gateway with host '%s' connected, listening for broadcasts",
        entry.data[CONF_HOST],
    )

    assert entry.unique_id
    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.unique_id)},
        manufacturer="Xiaomi Aqara",
        name=entry.title,
        sw_version=entry.data[CONF_PROTOCOL],
    )

    if entry.data[CONF_KEY] is not None:
        platforms = GATEWAY_PLATFORMS
    else:
        platforms = GATEWAY_PLATFORMS_NO_KEY

    await hass.config_entries.async_forward_entry_setups(entry, platforms)

    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if config_entry.data[CONF_KEY] is not None:
        platforms = GATEWAY_PLATFORMS
    else:
        platforms = GATEWAY_PLATFORMS_NO_KEY

    unload_ok = await hass.config_entries.async_unload_platforms(
        config_entry, platforms
    )
    if unload_ok:
        hass.data[DOMAIN][GATEWAYS_KEY].pop(config_entry.entry_id)

    if not hass.config_entries.async_loaded_entries(DOMAIN):
        # No gateways left, stop Xiaomi socket
        unsub_stop = hass.data[DOMAIN].pop(KEY_UNSUB_STOP)
        unsub_stop()
        hass.data[DOMAIN].pop(GATEWAYS_KEY)
        _LOGGER.debug("Shutting down Xiaomi Gateway Listener")
        multicast = hass.data[DOMAIN].pop(LISTENER_KEY)
        multicast.stop_listen()

    return unload_ok


def _add_gateway_to_schema(hass, schema):
    """Extend a voluptuous schema with a gateway validator."""

    def gateway(sid):
        """Convert sid to a gateway."""
        sid = str(sid).replace(":", "").lower()

        for gateway in hass.data[DOMAIN][GATEWAYS_KEY].values():
            if gateway.sid == sid:
                return gateway

        raise vol.Invalid(f"Unknown gateway sid {sid}")

    kwargs = {}
    if (xiaomi_data := hass.data.get(DOMAIN)) is not None:
        gateways = list(xiaomi_data[GATEWAYS_KEY].values())

        # If the user has only 1 gateway, make it the default for services.
        if len(gateways) == 1:
            kwargs["default"] = gateways[0].sid

    return schema.extend({vol.Required(ATTR_GW_MAC, **kwargs): gateway})
