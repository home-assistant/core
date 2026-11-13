"""Support for French FAI Bouygues Bbox routers."""

from datetime import datetime
import logging
from typing import override

from aiohttp import CookieJar
from bbox_api import BboxApiError, BboxClient, Host
import probatio

from homeassistant.components.device_tracker import (
    PLATFORM_SCHEMA as DEVICE_TRACKER_PLATFORM_SCHEMA,
    AsyncSeeCallback,
    ScannerEntity,
    SourceType,
)
from homeassistant.components.device_tracker.const import (
    ATTR_IP,
    CONF_CONSIDER_HOME,
    CONF_NEW_DEVICE_DEFAULTS,
    CONF_SCAN_INTERVAL,
    CONF_TRACK_NEW,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_VERIFY_SSL,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, issue_registry as ir
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util.dt import utcnow

from .const import DEFAULT_HOST, DOMAIN, INTEGRATION_TITLE, SCAN_INTERVAL
from .coordinator import BboxConfigEntry, BboxCoordinator

_LOGGER = logging.getLogger(__name__)

# The legacy YAML scanner keeps working until 2027.5 (see the
# migrate_device_tracker repair): it is deliberately not imported into a
# config entry, because the known_devices.yaml trackers still claim their
# entity ids while the platform is configured. host/password/verify_ssl
# stay accepted so an existing YAML keeps validating.
PLATFORM_SCHEMA = DEVICE_TRACKER_PLATFORM_SCHEMA.extend(
    {
        probatio.Optional(CONF_HOST, default=DEFAULT_HOST): cv.string,
        probatio.Optional(CONF_PASSWORD, default=""): cv.string,
        probatio.Optional(CONF_VERIFY_SSL, default=True): cv.boolean,
    }
)

# All entities consume coordinator data, so they never poll independently.
PARALLEL_UPDATES = 0


async def async_setup_scanner(
    hass: HomeAssistant,
    config: ConfigType,
    async_see: AsyncSeeCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> bool:
    """Run the legacy YAML scanner until 2027.5.

    The configuration is not imported into a config entry: while the YAML
    platform is configured, the known_devices.yaml trackers keep claiming
    their entity ids, so automatically created replacement entities could
    get suffixed ids. The migrate_device_tracker repair explains the manual
    migration instead.
    """
    dropped = [
        key
        for key in (
            CONF_SCAN_INTERVAL,
            CONF_TRACK_NEW,
            CONF_CONSIDER_HOME,
            CONF_NEW_DEVICE_DEFAULTS,
        )
        if key in config
    ]
    if dropped:
        _LOGGER.warning(
            "The bbox device_tracker YAML options %s are no longer supported"
            " and were not imported; remove them from the YAML configuration",
            ", ".join(dropped),
        )
    ir.async_create_issue(
        hass,
        DOMAIN,
        f"migrate_device_tracker_{DOMAIN}",
        breaks_in_ha_version="2027.5.0",
        is_fixable=False,
        issue_domain=DOMAIN,
        severity=ir.IssueSeverity.WARNING,
        translation_key="migrate_device_tracker",
        translation_placeholders={
            "domain": DOMAIN,
            "integration_title": INTEGRATION_TITLE,
        },
    )
    password = config[CONF_PASSWORD]
    if not password:
        _LOGGER.error(
            "The bbox device_tracker YAML platform needs the admin password"
            " (`password`); set it in the platform configuration or migrate"
            " to the UI integration"
        )
        return False
    verify_ssl = config[CONF_VERIFY_SSL]
    session = async_create_clientsession(
        hass, verify_ssl=verify_ssl, cookie_jar=CookieJar(unsafe=True)
    )
    client = BboxClient(
        password,
        config[CONF_HOST],
        use_tls=True,
        verify_ssl=verify_ssl,
        session=session,
    )

    async def _async_scan(_now: datetime) -> None:
        """Report the hosts currently active on the box."""
        try:
            hosts = await client.get_hosts()
        except BboxApiError as err:
            _LOGGER.warning("Error fetching the Bbox device list: %s", err)
            return
        for device in hosts:
            if device.active and device.macaddress:
                await async_see(
                    mac=device.macaddress,
                    host_name=device.hostname,
                    source_type=SourceType.ROUTER,
                    attributes={ATTR_IP: device.ipaddress},
                )

    cancel_scan = async_track_time_interval(
        hass, _async_scan, SCAN_INTERVAL, cancel_on_shutdown=True
    )

    @callback
    def _async_close(_event: Event) -> None:
        cancel_scan()
        # Detach the client; the HA-managed session is closed at shutdown.
        hass.async_create_task(client.close())

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _async_close)
    await _async_scan(utcnow())
    return True


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BboxConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Bbox device trackers from a config entry."""
    coordinator = entry.runtime_data
    tracked: set[str] = set()

    @callback
    def _async_add_new_trackers() -> None:
        """Add a tracker entity for each newly seen MAC address."""
        new_entities = [
            BboxDeviceTracker(coordinator, host.macaddress)
            for host in coordinator.data.hosts
            if host.macaddress and host.macaddress not in tracked
        ]
        for entity in new_entities:
            tracked.add(entity.mac_address)
        if new_entities:
            async_add_entities(new_entities)

    entry.async_on_unload(coordinator.async_add_listener(_async_add_new_trackers))
    _async_add_new_trackers()


class BboxDeviceTracker(CoordinatorEntity[BboxCoordinator], ScannerEntity):
    """A device connected to the Bbox."""

    _attr_source_type = SourceType.ROUTER
    # Keep the legacy entity ids (device_tracker.<hostname>, not prefixed
    # with the router name).
    _attr_has_entity_name = False
    # New trackers stay disabled by default (ScannerEntity default): users
    # enable per device, e.g. after migrating from known_devices.yaml.

    def __init__(self, coordinator: BboxCoordinator, mac: str) -> None:
        """Initialize the tracker."""
        super().__init__(coordinator)
        self._mac = mac
        self._attr_unique_id = mac
        # Empty device info on purpose: linking a device would prefix the
        # entity id with the device name and break the legacy entity ids
        # (device_tracker.<hostname>) of YAML-imported configurations.
        self._attr_device_info = DeviceInfo()

    @property
    def _host(self) -> Host | None:
        """Return the current data of the tracked host."""
        for host in self.coordinator.data.hosts:
            if host.macaddress == self._mac:
                return host
        return None

    @property
    @override
    def mac_address(self) -> str:
        """Return the MAC address of the tracked device."""
        return self._mac

    @property
    @override
    def hostname(self) -> str | None:
        """Return the hostname of the tracked device."""
        host = self._host
        return host.hostname if host else None

    @property
    @override
    def ip_address(self) -> str | None:
        """Return the IP address of the tracked device."""
        host = self._host
        return host.ipaddress if host else None

    @property
    @override
    def is_connected(self) -> bool:
        """Return True if the device is currently active on the network."""
        host = self._host
        return host is not None and host.active

    @property
    @override
    def name(self) -> str:
        """Return the name of the tracked device."""
        return self.hostname or self._mac
