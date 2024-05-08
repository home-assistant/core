"""Provide functionality to keep track of devices."""
from __future__ import annotations

from functools import partial

from homeassistant.const import ATTR_GPS_ACCURACY, STATE_HOME  # noqa: F401
from homeassistant.core import HomeAssistant
from homeassistant.helpers.deprecation import (
    all_with_deprecated_constants,
    check_if_deprecated_constant,
    dir_with_deprecated_constants,
)
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import bind_hass

from .config_entry import (  # noqa: F401
    ScannerEntity,
    TrackerEntity,
    async_setup_entry,
    async_unload_entry,
)
from .const import (  # noqa: F401
    _DEPRECATED_SOURCE_TYPE_BLUETOOTH,
    _DEPRECATED_SOURCE_TYPE_BLUETOOTH_LE,
    _DEPRECATED_SOURCE_TYPE_GPS,
    _DEPRECATED_SOURCE_TYPE_ROUTER,
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
from .legacy import (  # noqa: F401
    PLATFORM_SCHEMA,
    PLATFORM_SCHEMA_BASE,
    SERVICE_SEE,
    SERVICE_SEE_PAYLOAD_SCHEMA,
    SOURCE_TYPES,
    AsyncSeeCallback,
    DeviceScanner,
    SeeCallback,
    async_setup_integration as async_setup_legacy_integration,
    see,
)


@bind_hass
def is_on(hass: HomeAssistant, entity_id: str) -> bool:
    """Return the state if any or a specified device is home."""
    return hass.states.is_state(entity_id, STATE_HOME)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the device tracker."""

    # We need to add the component here break the deadlock
    # when setting up integrations from config entries as
    # they would otherwise wait for the device tracker to be
    # setup and thus the config entries would not be able to
    # setup their platforms.
    hass.config.components.add(DOMAIN)

    await async_setup_legacy_integration(hass, config)

    return True


# As we import deprecated constants from the const module, we need to add these two functions
# otherwise this module will be logged for using deprecated constants and not the custom component
# These can be removed if no deprecated constant are in this module anymore
__getattr__ = partial(check_if_deprecated_constant, module_globals=globals())
__dir__ = partial(
    dir_with_deprecated_constants, module_globals_keys=[*globals().keys()]
)
__all__ = all_with_deprecated_constants(globals())
