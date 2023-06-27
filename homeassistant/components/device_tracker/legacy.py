"""Legacy device tracker classes."""
from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine, Sequence
from datetime import datetime, timedelta
import hashlib
from types import ModuleType
from typing import Any, Final, Protocol, final

import attr
import voluptuous as vol

from homeassistant import util
from homeassistant.components import zone
from homeassistant.config import async_log_exception, load_yaml_config_file
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_GPS_ACCURACY,
    ATTR_ICON,
    ATTR_LATITUDE,
    ATTR_LONGITUDE,
    ATTR_NAME,
    CONF_ICON,
    CONF_MAC,
    CONF_NAME,
    DEVICE_DEFAULT_NAME,
    EVENT_HOMEASSISTANT_STOP,
    STATE_HOME,
    STATE_NOT_HOME,
)
from homeassistant.core import Event, HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import (
    config_per_platform,
    config_validation as cv,
    discovery,
    entity_registry as er,
)
from homeassistant.helpers.event import (
    async_track_time_interval,
    async_track_utc_time_change,
)
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import ConfigType, GPSType, StateType
from homeassistant.setup import async_prepare_setup_platform, async_start_setup
from homeassistant.util import dt as dt_util
from homeassistant.util.yaml import dump

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
    LOGGER,
    PLATFORM_TYPE_LEGACY,
    SCAN_INTERVAL,
    SourceType,
)

SERVICE_SEE: Final = "see"

SOURCE_TYPES = [cls.value for cls in SourceType]

NEW_DEVICE_DEFAULTS_SCHEMA = vol.Any(
    None,
    vol.Schema({vol.Optional(CONF_TRACK_NEW, default=DEFAULT_TRACK_NEW): cv.boolean}),
)
PLATFORM_SCHEMA: Final = cv.PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_SCAN_INTERVAL): cv.time_period,
        vol.Optional(CONF_TRACK_NEW): cv.boolean,
        vol.Optional(CONF_CONSIDER_HOME, default=DEFAULT_CONSIDER_HOME): vol.All(
            cv.time_period, cv.positive_timedelta
        ),
        vol.Optional(CONF_NEW_DEVICE_DEFAULTS, default={}): NEW_DEVICE_DEFAULTS_SCHEMA,
    }
)
PLATFORM_SCHEMA_BASE: Final[vol.Schema] = cv.PLATFORM_SCHEMA_BASE.extend(
    PLATFORM_SCHEMA.schema
)

SERVICE_SEE_PAYLOAD_SCHEMA: Final[vol.Schema] = vol.Schema(
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
            ATTR_SOURCE_TYPE: vol.Coerce(SourceType),
            ATTR_CONSIDER_HOME: cv.time_period,
            # Temp workaround for iOS app introduced in 0.65
            vol.Optional("battery_status"): str,
            vol.Optional("hostname"): str,
        },
    )
)

YAML_DEVICES: Final = "known_devices.yaml"
EVENT_NEW_DEVICE: Final = "device_tracker_new_device"


class SeeCallback(Protocol):
    """Protocol type for DeviceTracker.see callback."""

    def __call__(
        self,
        mac: str | None = None,
        dev_id: str | None = None,
        host_name: str | None = None,
        location_name: str | None = None,
        gps: GPSType | None = None,
        gps_accuracy: int | None = None,
        battery: int | None = None,
        attributes: dict[str, Any] | None = None,
        source_type: SourceType | str = SourceType.GPS,
        picture: str | None = None,
        icon: str | None = None,
        consider_home: timedelta | None = None,
    ) -> None:
        """Define see type."""


class AsyncSeeCallback(Protocol):
    """Protocol type for DeviceTracker.async_see callback."""

    async def __call__(
        self,
        mac: str | None = None,
        dev_id: str | None = None,
        host_name: str | None = None,
        location_name: str | None = None,
        gps: GPSType | None = None,
        gps_accuracy: int | None = None,
        battery: int | None = None,
        attributes: dict[str, Any] | None = None,
        source_type: SourceType | str = SourceType.GPS,
        picture: str | None = None,
        icon: str | None = None,
        consider_home: timedelta | None = None,
    ) -> None:
        """Define async_see type."""


def see(
    hass: HomeAssistant,
    mac: str | None = None,
    dev_id: str | None = None,
    host_name: str | None = None,
    location_name: str | None = None,
    gps: GPSType | None = None,
    gps_accuracy: int | None = None,
    battery: int | None = None,
    attributes: dict[str, Any] | None = None,
) -> None:
    """Call service to notify you see device."""
    data: dict[str, Any] = {
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
    if attributes is not None:
        data[ATTR_ATTRIBUTES] = attributes
    hass.services.call(DOMAIN, SERVICE_SEE, data)


async def async_setup_integration(hass: HomeAssistant, config: ConfigType) -> None:
    """Set up the legacy integration."""
    tracker = await get_tracker(hass, config)

    legacy_platforms = await async_extract_config(hass, config)

    setup_tasks = [
        asyncio.create_task(legacy_platform.async_setup_legacy(hass, tracker))
        for legacy_platform in legacy_platforms
    ]

    if setup_tasks:
        await asyncio.wait(setup_tasks)

    async def async_platform_discovered(
        p_type: str, info: dict[str, Any] | None
    ) -> None:
        """Load a platform."""
        platform = await async_create_platform_type(hass, config, p_type, {})

        if platform is None or platform.type != PLATFORM_TYPE_LEGACY:
            return

        await platform.async_setup_legacy(hass, tracker, info)

    discovery.async_listen_platform(hass, DOMAIN, async_platform_discovered)

    # Clean up stale devices
    cancel_update_stale = async_track_utc_time_change(
        hass, tracker.async_update_stale, second=range(0, 60, 5)
    )

    async def async_see_service(call: ServiceCall) -> None:
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

    @callback
    def _on_hass_stop(_: Event) -> None:
        """Cleanup when Home Assistant stops.

        Cancel the async_update_stale schedule.
        """
        cancel_update_stale()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _on_hass_stop)


@attr.s
class DeviceTrackerPlatform:
    """Class to hold platform information."""

    LEGACY_SETUP: Final[tuple[str, ...]] = (
        "async_get_scanner",
        "get_scanner",
        "async_setup_scanner",
        "setup_scanner",
    )

    name: str = attr.ib()
    platform: ModuleType = attr.ib()
    config: dict = attr.ib()

    @property
    def type(self) -> str | None:
        """Return platform type."""
        methods, platform_type = self.LEGACY_SETUP, PLATFORM_TYPE_LEGACY
        for method in methods:
            if hasattr(self.platform, method):
                return platform_type
        return None

    async def async_setup_legacy(
        self,
        hass: HomeAssistant,
        tracker: DeviceTracker,
        discovery_info: dict[str, Any] | None = None,
    ) -> None:
        """Set up a legacy platform."""
        assert self.type == PLATFORM_TYPE_LEGACY
        full_name = f"{DOMAIN}.{self.name}"
        LOGGER.info("Setting up %s", full_name)
        with async_start_setup(hass, [full_name]):
            try:
                scanner = None
                setup: bool | None = None
                if hasattr(self.platform, "async_get_scanner"):
                    scanner = await self.platform.async_get_scanner(
                        hass, {DOMAIN: self.config}
                    )
                elif hasattr(self.platform, "get_scanner"):
                    scanner = await hass.async_add_executor_job(
                        self.platform.get_scanner,
                        hass,
                        {DOMAIN: self.config},
                    )
                elif hasattr(self.platform, "async_setup_scanner"):
                    setup = await self.platform.async_setup_scanner(
                        hass, self.config, tracker.async_see, discovery_info
                    )
                elif hasattr(self.platform, "setup_scanner"):
                    setup = await hass.async_add_executor_job(
                        self.platform.setup_scanner,
                        hass,
                        self.config,
                        tracker.see,
                        discovery_info,
                    )
                else:
                    raise HomeAssistantError("Invalid legacy device_tracker platform.")

                if scanner is not None:
                    async_setup_scanner_platform(
                        hass, self.config, scanner, tracker.async_see, self.type
                    )

                if not setup and scanner is None:
                    LOGGER.error(
                        "Error setting up platform %s %s", self.type, self.name
                    )
                    return

                hass.config.components.add(full_name)

            except Exception:  # pylint: disable=broad-except
                LOGGER.exception(
                    "Error setting up platform %s %s", self.type, self.name
                )


async def async_extract_config(
    hass: HomeAssistant, config: ConfigType
) -> list[DeviceTrackerPlatform]:
    """Extract device tracker config and split between legacy and modern."""
    legacy: list[DeviceTrackerPlatform] = []

    for platform in await asyncio.gather(
        *(
            async_create_platform_type(hass, config, p_type, p_config)
            for p_type, p_config in config_per_platform(config, DOMAIN)
            if p_type is not None
        )
    ):
        if platform is None:
            continue

        if platform.type == PLATFORM_TYPE_LEGACY:
            legacy.append(platform)
        else:
            raise ValueError(
                f"Unable to determine type for {platform.name}: {platform.type}"
            )

    return legacy


async def async_create_platform_type(
    hass: HomeAssistant, config: ConfigType, p_type: str, p_config: dict
) -> DeviceTrackerPlatform | None:
    """Determine type of platform."""
    platform = await async_prepare_setup_platform(hass, config, DOMAIN, p_type)

    if platform is None:
        return None

    return DeviceTrackerPlatform(p_type, platform, p_config)


def _load_device_names_and_attributes(
    scanner: DeviceScanner,
    device_name_uses_executor: bool,
    extra_attributes_uses_executor: bool,
    seen: set[str],
    found_devices: list[str],
) -> tuple[dict[str, str | None], dict[str, dict[str, Any]]]:
    """Load device names and attributes in a single executor job."""
    host_name_by_mac: dict[str, str | None] = {}
    extra_attributes_by_mac: dict[str, dict[str, Any]] = {}
    for mac in found_devices:
        if device_name_uses_executor and mac not in seen:
            host_name_by_mac[mac] = scanner.get_device_name(mac)
        if extra_attributes_uses_executor:
            try:
                extra_attributes_by_mac[mac] = scanner.get_extra_attributes(mac)
            except NotImplementedError:
                extra_attributes_by_mac[mac] = {}
    return host_name_by_mac, extra_attributes_by_mac


@callback
def async_setup_scanner_platform(
    hass: HomeAssistant,
    config: ConfigType,
    scanner: DeviceScanner,
    async_see_device: Callable[..., Coroutine[None, None, None]],
    platform: str,
) -> None:
    """Set up the connect scanner-based platform to device tracker.

    This method must be run in the event loop.
    """
    interval = config.get(CONF_SCAN_INTERVAL, SCAN_INTERVAL)
    update_lock = asyncio.Lock()
    scanner.hass = hass

    # Initial scan of each mac we also tell about host name for config
    seen: set[str] = set()

    async def async_device_tracker_scan(now: datetime | None) -> None:
        """Handle interval matches."""
        if update_lock.locked():
            LOGGER.warning(
                (
                    "Updating device list from %s took longer than the scheduled "
                    "scan interval %s"
                ),
                platform,
                interval,
            )
            return

        async with update_lock:
            found_devices = await scanner.async_scan_devices()

        device_name_uses_executor = (
            scanner.async_get_device_name.__func__  # type: ignore[attr-defined]
            is DeviceScanner.async_get_device_name
        )
        extra_attributes_uses_executor = (
            scanner.async_get_extra_attributes.__func__  # type: ignore[attr-defined]
            is DeviceScanner.async_get_extra_attributes
        )
        host_name_by_mac: dict[str, str | None] = {}
        extra_attributes_by_mac: dict[str, dict[str, Any]] = {}
        if device_name_uses_executor or extra_attributes_uses_executor:
            (
                host_name_by_mac,
                extra_attributes_by_mac,
            ) = await hass.async_add_executor_job(
                _load_device_names_and_attributes,
                scanner,
                device_name_uses_executor,
                extra_attributes_uses_executor,
                seen,
                found_devices,
            )

        for mac in found_devices:
            if mac in seen:
                host_name = None
            else:
                host_name = host_name_by_mac.get(
                    mac, await scanner.async_get_device_name(mac)
                )
                seen.add(mac)

            try:
                extra_attributes = extra_attributes_by_mac.get(
                    mac, await scanner.async_get_extra_attributes(mac)
                )
            except NotImplementedError:
                extra_attributes = {}

            kwargs: dict[str, Any] = {
                "mac": mac,
                "host_name": host_name,
                "source_type": SourceType.ROUTER,
                "attributes": {
                    "scanner": scanner.__class__.__name__,
                    **extra_attributes,
                },
            }

            zone_home = hass.states.get(hass.components.zone.ENTITY_ID_HOME)
            if zone_home is not None:
                kwargs["gps"] = [
                    zone_home.attributes[ATTR_LATITUDE],
                    zone_home.attributes[ATTR_LONGITUDE],
                ]
                kwargs["gps_accuracy"] = 0

            hass.async_create_task(async_see_device(**kwargs))

    cancel_legacy_scan = async_track_time_interval(
        hass,
        async_device_tracker_scan,
        interval,
        name=f"device_tracker {platform} legacy scan",
    )
    hass.async_create_task(async_device_tracker_scan(None))

    @callback
    def _on_hass_stop(_: Event) -> None:
        """Cleanup when Home Assistant stops.

        Cancel the legacy scan.
        """
        cancel_legacy_scan()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _on_hass_stop)


async def get_tracker(hass: HomeAssistant, config: ConfigType) -> DeviceTracker:
    """Create a tracker."""
    yaml_path = hass.config.path(YAML_DEVICES)

    conf = config.get(DOMAIN, [])
    conf = conf[0] if conf else {}
    consider_home = conf.get(CONF_CONSIDER_HOME, DEFAULT_CONSIDER_HOME)

    defaults = conf.get(CONF_NEW_DEVICE_DEFAULTS, {})
    if (track_new := conf.get(CONF_TRACK_NEW)) is None:
        track_new = defaults.get(CONF_TRACK_NEW, DEFAULT_TRACK_NEW)

    devices = await async_load_config(yaml_path, hass, consider_home)
    tracker = DeviceTracker(hass, consider_home, track_new, defaults, devices)
    return tracker


class DeviceTracker:
    """Representation of a device tracker."""

    def __init__(
        self,
        hass: HomeAssistant,
        consider_home: timedelta,
        track_new: bool,
        defaults: dict[str, Any],
        devices: Sequence[Device],
    ) -> None:
        """Initialize a device tracker."""
        self.hass = hass
        self.devices: dict[str, Device] = {dev.dev_id: dev for dev in devices}
        self.mac_to_dev = {dev.mac: dev for dev in devices if dev.mac}
        self.consider_home = consider_home
        self.track_new = (
            track_new
            if track_new is not None
            else defaults.get(CONF_TRACK_NEW, DEFAULT_TRACK_NEW)
        )
        self.defaults = defaults
        self._is_updating = asyncio.Lock()

        for dev in devices:
            if self.devices[dev.dev_id] is not dev:
                LOGGER.warning("Duplicate device IDs detected %s", dev.dev_id)
            if dev.mac and self.mac_to_dev[dev.mac] is not dev:
                LOGGER.warning("Duplicate device MAC addresses detected %s", dev.mac)

    def see(
        self,
        mac: str | None = None,
        dev_id: str | None = None,
        host_name: str | None = None,
        location_name: str | None = None,
        gps: GPSType | None = None,
        gps_accuracy: int | None = None,
        battery: int | None = None,
        attributes: dict[str, Any] | None = None,
        source_type: SourceType | str = SourceType.GPS,
        picture: str | None = None,
        icon: str | None = None,
        consider_home: timedelta | None = None,
    ) -> None:
        """Notify the device tracker that you see a device."""
        self.hass.create_task(
            self.async_see(
                mac,
                dev_id,
                host_name,
                location_name,
                gps,
                gps_accuracy,
                battery,
                attributes,
                source_type,
                picture,
                icon,
                consider_home,
            )
        )

    async def async_see(
        self,
        mac: str | None = None,
        dev_id: str | None = None,
        host_name: str | None = None,
        location_name: str | None = None,
        gps: GPSType | None = None,
        gps_accuracy: int | None = None,
        battery: int | None = None,
        attributes: dict[str, Any] | None = None,
        source_type: SourceType | str = SourceType.GPS,
        picture: str | None = None,
        icon: str | None = None,
        consider_home: timedelta | None = None,
    ) -> None:
        """Notify the device tracker that you see a device.

        This method is a coroutine.
        """
        registry = er.async_get(self.hass)
        if mac is None and dev_id is None:
            raise HomeAssistantError("Neither mac or device id passed in")
        if mac is not None:
            mac = str(mac).upper()
            if (device := self.mac_to_dev.get(mac)) is None:
                dev_id = util.slugify(host_name or "") or util.slugify(mac)
        else:
            dev_id = cv.slug(str(dev_id).lower())
            device = self.devices.get(dev_id)

        if device is not None:
            await device.async_seen(
                host_name,
                location_name,
                gps,
                gps_accuracy,
                battery,
                attributes,
                source_type,
                consider_home,
            )
            if device.track:
                device.async_write_ha_state()
            return

        # If it's None then device is not None and we can't get here.
        assert dev_id is not None

        # Guard from calling see on entity registry entities.
        entity_id = f"{DOMAIN}.{dev_id}"
        if registry.async_is_registered(entity_id):
            LOGGER.error(
                "The see service is not supported for this entity %s", entity_id
            )
            return

        # If no device can be found, create it
        dev_id = util.ensure_unique_string(dev_id, self.devices.keys())
        device = Device(
            self.hass,
            consider_home or self.consider_home,
            self.track_new,
            dev_id,
            mac,
            picture=picture,
            icon=icon,
        )
        self.devices[dev_id] = device
        if mac is not None:
            self.mac_to_dev[mac] = device

        await device.async_seen(
            host_name,
            location_name,
            gps,
            gps_accuracy,
            battery,
            attributes,
            source_type,
        )

        if device.track:
            device.async_write_ha_state()

        self.hass.bus.async_fire(
            EVENT_NEW_DEVICE,
            {
                ATTR_ENTITY_ID: device.entity_id,
                ATTR_HOST_NAME: device.host_name,
                ATTR_MAC: device.mac,
            },
        )

        # update known_devices.yaml
        self.hass.async_create_task(
            self.async_update_config(
                self.hass.config.path(YAML_DEVICES), dev_id, device
            )
        )

    async def async_update_config(self, path: str, dev_id: str, device: Device) -> None:
        """Add device to YAML configuration file.

        This method is a coroutine.
        """
        async with self._is_updating:
            await self.hass.async_add_executor_job(
                update_config, self.hass.config.path(YAML_DEVICES), dev_id, device
            )

    @callback
    def async_update_stale(self, now: datetime) -> None:
        """Update stale devices.

        This method must be run in the event loop.
        """
        for device in self.devices.values():
            if (device.track and device.last_update_home) and device.stale(now):
                self.hass.async_create_task(device.async_update_ha_state(True))

    async def async_setup_tracked_device(self) -> None:
        """Set up all not exists tracked devices.

        This method is a coroutine.
        """

        async def async_init_single_device(dev: Device) -> None:
            """Init a single device_tracker entity."""
            await dev.async_added_to_hass()
            dev.async_write_ha_state()

        tasks: list[asyncio.Task] = []
        for device in self.devices.values():
            if device.track and not device.last_seen:
                tasks.append(
                    self.hass.async_create_task(async_init_single_device(device))
                )

        if tasks:
            await asyncio.wait(tasks)


class Device(RestoreEntity):
    """Base class for a tracked device."""

    host_name: str | None = None
    location_name: str | None = None
    gps: GPSType | None = None
    gps_accuracy: int = 0
    last_seen: datetime | None = None
    battery: int | None = None
    attributes: dict | None = None

    # Track if the last update of this device was HOME.
    last_update_home: bool = False
    _state: str = STATE_NOT_HOME

    def __init__(
        self,
        hass: HomeAssistant,
        consider_home: timedelta,
        track: bool,
        dev_id: str,
        mac: str | None,
        name: str | None = None,
        picture: str | None = None,
        gravatar: str | None = None,
        icon: str | None = None,
    ) -> None:
        """Initialize a device."""
        self.hass = hass
        self.entity_id = f"{DOMAIN}.{dev_id}"

        # Timedelta object how long we consider a device home if it is not
        # detected anymore.
        self.consider_home = consider_home

        # Device ID
        self.dev_id = dev_id
        self.mac = mac

        # If we should track this device
        self.track = track

        # Configured name
        self.config_name = name

        # Configured picture
        self.config_picture: str | None
        if gravatar is not None:
            self.config_picture = get_gravatar_for_email(gravatar)
        else:
            self.config_picture = picture

        self._icon = icon

        self.source_type: SourceType | str | None = None

        self._attributes: dict[str, Any] = {}

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        return self.config_name or self.host_name or self.dev_id or DEVICE_DEFAULT_NAME

    @property
    def state(self) -> str:
        """Return the state of the device."""
        return self._state

    @property
    def entity_picture(self) -> str | None:
        """Return the picture of the device."""
        return self.config_picture

    @final
    @property
    def state_attributes(self) -> dict[str, StateType]:
        """Return the device state attributes."""
        attributes: dict[str, StateType] = {ATTR_SOURCE_TYPE: self.source_type}

        if self.gps is not None:
            attributes[ATTR_LATITUDE] = self.gps[0]
            attributes[ATTR_LONGITUDE] = self.gps[1]
            attributes[ATTR_GPS_ACCURACY] = self.gps_accuracy

        if self.battery is not None:
            attributes[ATTR_BATTERY] = self.battery

        return attributes

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return device state attributes."""
        return self._attributes

    @property
    def icon(self) -> str | None:
        """Return device icon."""
        return self._icon

    async def async_seen(
        self,
        host_name: str | None = None,
        location_name: str | None = None,
        gps: GPSType | None = None,
        gps_accuracy: int | None = None,
        battery: int | None = None,
        attributes: dict[str, Any] | None = None,
        source_type: SourceType | str = SourceType.GPS,
        consider_home: timedelta | None = None,
    ) -> None:
        """Mark the device as seen."""
        self.source_type = source_type
        self.last_seen = dt_util.utcnow()
        self.host_name = host_name or self.host_name
        self.location_name = location_name
        self.consider_home = consider_home or self.consider_home

        if battery is not None:
            self.battery = battery
        if attributes is not None:
            self._attributes.update(attributes)

        self.gps = None

        if gps is not None:
            try:
                self.gps = float(gps[0]), float(gps[1])
                self.gps_accuracy = gps_accuracy or 0
            except (ValueError, TypeError, IndexError):
                self.gps = None
                self.gps_accuracy = 0
                LOGGER.warning("Could not parse gps value for %s: %s", self.dev_id, gps)

        await self.async_update()

    def stale(self, now: datetime | None = None) -> bool:
        """Return if device state is stale.

        Async friendly.
        """
        return (
            self.last_seen is None
            or (now or dt_util.utcnow()) - self.last_seen > self.consider_home
        )

    def mark_stale(self) -> None:
        """Mark the device state as stale."""
        self._state = STATE_NOT_HOME
        self.gps = None
        self.last_update_home = False

    async def async_update(self) -> None:
        """Update state of entity.

        This method is a coroutine.
        """
        if not self.last_seen:
            return
        if self.location_name:
            self._state = self.location_name
        elif self.gps is not None and self.source_type == SourceType.GPS:
            zone_state = zone.async_active_zone(
                self.hass, self.gps[0], self.gps[1], self.gps_accuracy
            )
            if zone_state is None:
                self._state = STATE_NOT_HOME
            elif zone_state.entity_id == zone.ENTITY_ID_HOME:
                self._state = STATE_HOME
            else:
                self._state = zone_state.name
        elif self.stale():
            self.mark_stale()
        else:
            self._state = STATE_HOME
            self.last_update_home = True

    async def async_added_to_hass(self) -> None:
        """Add an entity."""
        await super().async_added_to_hass()
        if not (state := await self.async_get_last_state()):
            return
        self._state = state.state
        self.last_update_home = state.state == STATE_HOME
        self.last_seen = dt_util.utcnow()

        for attribute, var in (
            (ATTR_SOURCE_TYPE, "source_type"),
            (ATTR_GPS_ACCURACY, "gps_accuracy"),
            (ATTR_BATTERY, "battery"),
        ):
            if attribute in state.attributes:
                setattr(self, var, state.attributes[attribute])

        if ATTR_LONGITUDE in state.attributes:
            self.gps = (
                state.attributes[ATTR_LATITUDE],
                state.attributes[ATTR_LONGITUDE],
            )


class DeviceScanner:
    """Device scanner object."""

    hass: HomeAssistant | None = None

    def scan_devices(self) -> list[str]:
        """Scan for devices."""
        raise NotImplementedError()

    async def async_scan_devices(self) -> list[str]:
        """Scan for devices."""
        assert (
            self.hass is not None
        ), "hass should be set by async_setup_scanner_platform"
        return await self.hass.async_add_executor_job(self.scan_devices)

    def get_device_name(self, device: str) -> str | None:
        """Get the name of a device."""
        raise NotImplementedError()

    async def async_get_device_name(self, device: str) -> str | None:
        """Get the name of a device."""
        assert (
            self.hass is not None
        ), "hass should be set by async_setup_scanner_platform"
        return await self.hass.async_add_executor_job(self.get_device_name, device)

    def get_extra_attributes(self, device: str) -> dict:
        """Get the extra attributes of a device."""
        raise NotImplementedError()

    async def async_get_extra_attributes(self, device: str) -> dict:
        """Get the extra attributes of a device."""
        assert (
            self.hass is not None
        ), "hass should be set by async_setup_scanner_platform"
        return await self.hass.async_add_executor_job(self.get_extra_attributes, device)


async def async_load_config(
    path: str, hass: HomeAssistant, consider_home: timedelta
) -> list[Device]:
    """Load devices from YAML configuration file.

    This method is a coroutine.
    """
    dev_schema = vol.Schema(
        {
            vol.Required(CONF_NAME): cv.string,
            vol.Optional(CONF_ICON, default=None): vol.Any(None, cv.icon),
            vol.Optional("track", default=False): cv.boolean,
            vol.Optional(CONF_MAC, default=None): vol.Any(
                None, vol.All(cv.string, vol.Upper)
            ),
            vol.Optional("gravatar", default=None): vol.Any(None, cv.string),
            vol.Optional("picture", default=None): vol.Any(None, cv.string),
            vol.Optional(CONF_CONSIDER_HOME, default=consider_home): vol.All(
                cv.time_period, cv.positive_timedelta
            ),
        }
    )
    result: list[Device] = []
    try:
        devices = await hass.async_add_executor_job(load_yaml_config_file, path)
    except HomeAssistantError as err:
        LOGGER.error("Unable to load %s: %s", path, str(err))
        return []
    except FileNotFoundError:
        return []

    for dev_id, device in devices.items():
        # Deprecated option. We just ignore it to avoid breaking change
        device.pop("vendor", None)
        device.pop("hide_if_away", None)
        try:
            device = dev_schema(device)
            device["dev_id"] = cv.slugify(dev_id)
        except vol.Invalid as exp:
            async_log_exception(exp, dev_id, devices, hass)
        else:
            result.append(Device(hass, **device))
    return result


def update_config(path: str, dev_id: str, device: Device) -> None:
    """Add device to YAML configuration file."""
    with open(path, "a", encoding="utf8") as out:
        device_config = {
            device.dev_id: {
                ATTR_NAME: device.name,
                ATTR_MAC: device.mac,
                ATTR_ICON: device.icon,
                "picture": device.config_picture,
                "track": device.track,
            }
        }
        out.write("\n")
        out.write(dump(device_config))


def get_gravatar_for_email(email: str) -> str:
    """Return an 80px Gravatar for the given email address.

    Async friendly.
    """

    return (
        "https://www.gravatar.com/avatar/"
        f"{hashlib.md5(email.encode('utf-8').lower()).hexdigest()}.jpg?s=80&d=wavatar"
    )
