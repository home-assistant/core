"""Provide functionality to keep track of devices."""
from homeassistant.const import ATTR_GPS_ACCURACY, STATE_HOME  # noqa: F401
from homeassistant.core import HomeAssistant
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


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the device tracker."""
    await async_setup_legacy_integration(hass, config)

    return True
