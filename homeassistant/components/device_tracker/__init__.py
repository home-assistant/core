"""Provide functionality to keep track of devices."""

from __future__ import annotations

from homeassistant.config import config_per_platform
from homeassistant.const import ATTR_GPS_ACCURACY, STATE_HOME  # noqa: F401
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import bind_hass
from homeassistant.setup import async_prepare_setup_platform

from .config_entry import (  # noqa: F401
    DATA_COMPONENT,
    BaseTrackerEntity,
    ScannerEntity,
    ScannerEntityDescription,
    TrackerEntity,
    TrackerEntityDescription,
    async_setup_entry,
    async_unload_entry,
)
from .const import (  # noqa: F401
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
    LOGGER,
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

LEGACY_SETUP_METHODS = (
    "async_get_scanner",
    "get_scanner",
    "async_setup_scanner",
    "setup_scanner",
)


@bind_hass
def is_on(hass: HomeAssistant, entity_id: str) -> bool:
    """Return the state if any or a specified device is home."""
    return hass.states.is_state(entity_id, STATE_HOME)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the device tracker."""
    # Ensure entity component exists for entity-based platforms
    if DATA_COMPONENT not in hass.data:
        component = hass.data[DATA_COMPONENT] = EntityComponent[BaseTrackerEntity](
            LOGGER, DOMAIN, hass
        )
        component.register_shutdown()
    component: EntityComponent[BaseTrackerEntity] = hass.data[DATA_COMPONENT]
    component.config = config

    # Discover and load entity-based YAML platforms
    for p_type, p_config in config_per_platform(config, DOMAIN):
        if p_type is None:
            continue
        platform = await async_prepare_setup_platform(hass, config, DOMAIN, p_type)
        if platform is None:
            continue
        # Skip legacy platforms - they're handled by async_setup_legacy_integration
        if any(hasattr(platform, method) for method in LEGACY_SETUP_METHODS):
            continue
        # Entity-based platform - set up via EntityComponent
        hass.async_create_task(
            component.async_setup_platform(p_type, p_config),
            eager_start=True,
        )

    # Set up legacy platforms
    async_setup_legacy_integration(hass, config)
    return True
