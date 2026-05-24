"""Provide functionality to keep track of devices."""

import asyncio
from typing import Any

from homeassistant.const import ATTR_GPS_ACCURACY, STATE_HOME  # noqa: F401
from homeassistant.core import HomeAssistant
from homeassistant.helpers import discovery
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.typing import ConfigType

from .config_entry import (  # noqa: F401
    DATA_COMPONENT,
    BaseScannerEntity,
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
    ATTR_IN_ZONES,
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
    PLATFORM_TYPE_LEGACY,
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
    DeviceTracker,
    SeeCallback,
    async_create_platform_type,
    async_setup_integration as async_setup_legacy_integration,
    see,
)


def is_on(hass: HomeAssistant, entity_id: str) -> bool:
    """Return the state if any or a specified device is home."""
    return hass.states.is_state(entity_id, STATE_HOME)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the device tracker."""
    component = hass.data[DATA_COMPONENT] = EntityComponent[BaseTrackerEntity](
        LOGGER, DOMAIN, hass, SCAN_INTERVAL
    )
    component.config = {}
    component.register_shutdown()

    # The tracker is loaded in the async_setup_legacy_integration task so
    # we create a future to avoid waiting on it here so that only
    # async_platform_discovered will have to wait in the rare event
    # a custom component still uses the legacy device tracker discovery.
    tracker_future: asyncio.Future[DeviceTracker] = hass.loop.create_future()

    async def async_platform_discovered(
        p_type: str, info: dict[str, Any] | None
    ) -> None:
        """Load a platform."""
        platform = await async_create_platform_type(hass, config, p_type, {})

        if platform is None:
            return

        if platform.type != PLATFORM_TYPE_LEGACY:
            await component.async_setup_platform(p_type, {}, info)
            return

        tracker = await tracker_future
        await platform.async_setup_legacy(hass, tracker, info)

    discovery.async_listen_platform(hass, DOMAIN, async_platform_discovered)
    #
    # Legacy and platforms load in a non-awaited tracked task
    # to ensure device tracker setup can continue and config
    # entry integrations are not waiting for legacy device
    # tracker platforms to be set up.
    #
    hass.async_create_task(
        async_setup_legacy_integration(hass, config, tracker_future),
        eager_start=True,
    )
    return True
