"""Provide functionality to keep track of devices."""
from __future__ import annotations

from homeassistant.const import ATTR_GPS_ACCURACY, STATE_HOME  # noqa: F401
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import bind_hass

from .config_entry import async_setup_entry, async_unload_entry  # noqa: F401
from .const import (  # noqa: F401
    ATTR_ATTRIBUTES,
    ATTR_BATTERY,
    ATTR_DEV_ID,
    ATTR_GPS,
    ATTR_HOST_NAME,
    ATTR_LOCATION_NAME,
    ATTR_MAC,
    ATTR_SOURCE_TYPE,
    CONF_CONSIDER_HOME,
    CONF_NEW_DEVICE_DEFAULTS,
    CONF_SCAN_INTERVAL,
    CONF_TRACK_NEW,
    DOMAIN,
    ENTITY_ID_FORMAT,
    SOURCE_TYPE_BLUETOOTH,
    SOURCE_TYPE_BLUETOOTH_LE,
    SOURCE_TYPE_GPS,
    SOURCE_TYPE_ROUTER,
)
from .legacy import (  # noqa: F401
    PLATFORM_SCHEMA,
    PLATFORM_SCHEMA_BASE,
    SERVICE_SEE,
    SERVICE_SEE_PAYLOAD_SCHEMA,
    SOURCE_TYPES,
    DeviceScanner,
    async_setup_integration as async_setup_legacy_integration,
    see,
)


@bind_hass
def is_on(hass: HomeAssistant, entity_id: str) -> bool:
    """Return the state if any or a specified device is home."""
    return hass.states.is_state(entity_id, STATE_HOME)


@callback
def async_register_mac(
    hass: HomeAssistant, domain: str, mac: str, unique_id: str | None = None
) -> None:
    """Register a mac address with a unique ID.

    If no unique ID given, it is assumed to be the mac.
    """
    data_key = "device_tracker_mac"
    if data_key in hass.data:
        hass.data[data_key][mac] = (domain, unique_id or mac)
        return

    # Setup listening.

    # dict mapping mac -> partial unique ID
    data = hass.data[data_key] = {mac: (domain, unique_id or mac)}

    @callback
    def handle_device_event(ev: Event) -> None:
        """Enable the online status entity for the mac of a newly created device."""
        # Only for new devices
        if ev.data["action"] != "create":
            return

        dev_reg = dr.async_get(hass)
        device_entry = dev_reg.async_get(ev.data["device_id"])

        if device_entry is None:
            return

        # Check if device has a mac
        mac = None
        for conn in device_entry.connections:
            if conn[0] == dr.CONNECTION_NETWORK_MAC:
                mac = conn[1]
                break

        if mac is None:
            return

        # Check if we have an entity for this mac
        if (unique_id := data.get(mac)) is None:
            return

        ent_reg = er.async_get(hass)
        entity_id = ent_reg.async_get_entity_id(DOMAIN, *unique_id)

        if entity_id is None:
            return

        entity_entry = ent_reg.async_get(entity_id)

        if entity_entry is None:
            return

        # Make sure entity has a config entry and was disabled by the
        # default disable logic in the integration.
        if (
            entity_entry.config_entry_id is None
            or entity_entry.disabled_by != er.DISABLED_INTEGRATION
        ):
            return

        # Enable entity
        ent_reg.async_update_entity(entity_id, disabled_by=None)

    hass.bus.async_listen(dr.EVENT_DEVICE_REGISTRY_UPDATED, handle_device_event)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the device tracker."""
    await async_setup_legacy_integration(hass, config)
    return True
