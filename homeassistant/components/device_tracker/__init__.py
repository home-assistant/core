"""Provide functionality to keep track of devices."""

from __future__ import annotations

from homeassistant.const import STATE_HOME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import bind_hass

from .config_entry import (
    ScannerEntity,
    ScannerEntityDescription,
    TrackerEntity,
    TrackerEntityDescription,
    async_setup_entry,
    async_unload_entry,
)
from .const import (
    ATTR_ATTRIBUTES,
    ATTR_BATTERY,
    ATTR_DEV_ID,
    ATTR_GPS,
    ATTR_HOST_NAME,
    ATTR_IP,
    ATTR_LOCATION_NAME,
    ATTR_MAC,
    ATTR_SOURCE_TYPE,
    CONF_CONSIDER_HOME,
    CONF_NEW_DEVICE_DEFAULTS,
    CONF_SCAN_INTERVAL,
    CONF_TRACK_NEW,
    CONNECTED_DEVICE_REGISTERED,
    DEFAULT_CONSIDER_HOME,
    DEFAULT_TRACK_NEW,
    DOMAIN,
    ENTITY_ID_FORMAT,
    SCAN_INTERVAL,
    SourceType,
)
from .legacy import (
    PLATFORM_SCHEMA,
    SERVICE_SEE,
    SERVICE_SEE_PAYLOAD_SCHEMA,
    AsyncSeeCallback,
    DeviceScanner,
    SeeCallback,
    async_setup_integration as async_setup_legacy_integration,
)


@bind_hass
def is_on(hass: HomeAssistant, entity_id: str) -> bool:
    """Return the state if any or a specified device is home."""
    return hass.states.is_state(entity_id, STATE_HOME)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the device tracker."""
    async_setup_legacy_integration(hass, config)
    return True


__all__ = (
    "ATTR_ATTRIBUTES",
    "ATTR_BATTERY",
    "ATTR_DEV_ID",
    "ATTR_GPS",
    "ATTR_HOST_NAME",
    "ATTR_IP",
    "ATTR_LOCATION_NAME",
    "ATTR_MAC",
    "ATTR_SOURCE_TYPE",
    "CONF_CONSIDER_HOME",
    "CONF_NEW_DEVICE_DEFAULTS",
    "CONF_SCAN_INTERVAL",
    "CONF_TRACK_NEW",
    "CONNECTED_DEVICE_REGISTERED",
    "DEFAULT_CONSIDER_HOME",
    "DEFAULT_TRACK_NEW",
    "DOMAIN",
    "ENTITY_ID_FORMAT",
    "PLATFORM_SCHEMA",
    "SCAN_INTERVAL",
    "SERVICE_SEE",
    "SERVICE_SEE_PAYLOAD_SCHEMA",
    "AsyncSeeCallback",
    "DeviceScanner",
    "ScannerEntity",
    "ScannerEntityDescription",
    "SeeCallback",
    "SourceType",
    "TrackerEntity",
    "TrackerEntityDescription",
    "async_setup_entry",
    "async_unload_entry",
)
