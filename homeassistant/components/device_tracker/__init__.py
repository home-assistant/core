"""Provide functionality to keep track of devices."""
import asyncio

import voluptuous as vol

from homeassistant.const import ATTR_GPS_ACCURACY, STATE_HOME
from homeassistant.helpers import discovery
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.event import async_track_utc_time_change
from homeassistant.helpers.typing import ConfigType, GPSType, HomeAssistantType
from homeassistant.loader import bind_hass

from . import legacy, setup
from .config_entry import (  # noqa: F401 pylint: disable=unused-import
    async_setup_entry,
    async_unload_entry,
)
from .const import (
    ATTR_ATTRIBUTES,
    ATTR_BATTERY,
    ATTR_CONSIDER_HOME,
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
    DEFAULT_CONSIDER_HOME,
    DEFAULT_TRACK_NEW,
    DOMAIN,
    PLATFORM_TYPE_LEGACY,
    SOURCE_TYPE_BLUETOOTH,
    SOURCE_TYPE_BLUETOOTH_LE,
    SOURCE_TYPE_GPS,
    SOURCE_TYPE_ROUTER,
)
from .legacy import DeviceScanner  # noqa: F401 pylint: disable=unused-import

SERVICE_SEE = "see"

SOURCE_TYPES = (
    SOURCE_TYPE_GPS,
    SOURCE_TYPE_ROUTER,
    SOURCE_TYPE_BLUETOOTH,
    SOURCE_TYPE_BLUETOOTH_LE,
)

NEW_DEVICE_DEFAULTS_SCHEMA = vol.Any(
    None,
    vol.Schema({vol.Optional(CONF_TRACK_NEW, default=DEFAULT_TRACK_NEW): cv.boolean}),
)
PLATFORM_SCHEMA = cv.PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_SCAN_INTERVAL): cv.time_period,
        vol.Optional(CONF_TRACK_NEW): cv.boolean,
        vol.Optional(CONF_CONSIDER_HOME, default=DEFAULT_CONSIDER_HOME): vol.All(
            cv.time_period, cv.positive_timedelta
        ),
        vol.Optional(CONF_NEW_DEVICE_DEFAULTS, default={}): NEW_DEVICE_DEFAULTS_SCHEMA,
    }
)
PLATFORM_SCHEMA_BASE = cv.PLATFORM_SCHEMA_BASE.extend(PLATFORM_SCHEMA.schema)
SERVICE_SEE_PAYLOAD_SCHEMA = vol.Schema(
    vol.All(
        cv.has_at_least_one_key(ATTR_MAC, ATTR_DEV_ID),
        {
            ATTR_MAC: cv.string,
            ATTR_DEV_ID: cv.string,
            ATTR_HOST_NAME: cv.string,
            ATTR_LOCATION_NAME: cv.string,
            ATTR_GPS: cv.gps,
            ATTR_GPS_ACCURACY: cv.positive_int,
            ATTR_BATTERY: cv.positive_int,
            ATTR_ATTRIBUTES: dict,
            ATTR_SOURCE_TYPE: vol.In(SOURCE_TYPES),
            ATTR_CONSIDER_HOME: cv.time_period,
            # Temp workaround for iOS app introduced in 0.65
            vol.Optional("battery_status"): str,
            vol.Optional("hostname"): str,
        },
    )
)


@bind_hass
def is_on(hass: HomeAssistantType, entity_id: str):
    """Return the state if any or a specified device is home."""
    return hass.states.is_state(entity_id, STATE_HOME)


def see(
    hass: HomeAssistantType,
    mac: str = None,
    dev_id: str = None,
    host_name: str = None,
    location_name: str = None,
    gps: GPSType = None,
    gps_accuracy=None,
    battery: int = None,
    attributes: dict = None,
):
    """Call service to notify you see device."""
    data = {
        key: value
        for key, value in (
            (ATTR_MAC, mac),
            (ATTR_DEV_ID, dev_id),
            (ATTR_HOST_NAME, host_name),
            (ATTR_LOCATION_NAME, location_name),
            (ATTR_GPS, gps),
            (ATTR_GPS_ACCURACY, gps_accuracy),
            (ATTR_BATTERY, battery),
        )
        if value is not None
    }
    if attributes:
        data[ATTR_ATTRIBUTES] = attributes
    hass.services.call(DOMAIN, SERVICE_SEE, data)


async def async_setup(hass: HomeAssistantType, config: ConfigType):
    """Set up the device tracker."""
    tracker = await legacy.get_tracker(hass, config)

    legacy_platforms = await setup.async_extract_config(hass, config)

    setup_tasks = [
        legacy_platform.async_setup_legacy(hass, tracker)
        for legacy_platform in legacy_platforms
    ]

    if setup_tasks:
        await asyncio.wait(setup_tasks)

    async def async_platform_discovered(p_type, info):
        """Load a platform."""
        platform = await setup.async_create_platform_type(hass, config, p_type, {})

        if platform is None or platform.type != PLATFORM_TYPE_LEGACY:
            return

        await platform.async_setup_legacy(hass, tracker, info)

    discovery.async_listen_platform(hass, DOMAIN, async_platform_discovered)

    # Clean up stale devices
    async_track_utc_time_change(
        hass, tracker.async_update_stale, second=range(0, 60, 5)
    )

    async def async_see_service(call):
        """Service to see a device."""
        # Temp workaround for iOS, introduced in 0.65
        data = dict(call.data)
        data.pop("hostname", None)
        data.pop("battery_status", None)
        await tracker.async_see(**data)

    hass.services.async_register(
        DOMAIN, SERVICE_SEE, async_see_service, SERVICE_SEE_PAYLOAD_SCHEMA
    )

    # restore
    await tracker.async_setup_tracked_device()
    return True
