"""Support for French FAI Bouygues Bbox routers."""

import logging
from typing import override

from bbox_api import Host
import probatio

from homeassistant.components.device_tracker import (
    PLATFORM_SCHEMA as DEVICE_TRACKER_PLATFORM_SCHEMA,
    AsyncSeeCallback,
    ScannerEntity,
    SourceType,
)
from homeassistant.components.device_tracker.const import (
    CONF_CONSIDER_HOME,
    CONF_NEW_DEVICE_DEFAULTS,
    CONF_SCAN_INTERVAL,
    CONF_TRACK_NEW,
)
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_VERIFY_SSL
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, issue_registry as ir
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DEFAULT_HOST, DOMAIN, INTEGRATION_TITLE
from .coordinator import BboxConfigEntry, BboxCoordinator

_LOGGER = logging.getLogger(__name__)

# The legacy YAML structure is kept as-is: it is imported into a config
# entry by async_setup_scanner below, new options live in the config flow.
# host/password/verify_ssl stay accepted so a YAML written for them still
# imports into the entry instead of failing schema validation.
PLATFORM_SCHEMA = DEVICE_TRACKER_PLATFORM_SCHEMA.extend(
    {
        probatio.Optional(CONF_HOST, default=DEFAULT_HOST): cv.string,
        probatio.Optional(CONF_PASSWORD, default=""): cv.string,
        probatio.Optional(CONF_VERIFY_SSL, default=True): cv.boolean,
    }
)

# The coordinator polls the Bbox.
PARALLEL_UPDATES = 0


async def async_setup_scanner(
    hass: HomeAssistant,
    config: ConfigType,
    async_see: AsyncSeeCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> bool:
    """Import the legacy YAML device tracker configuration."""
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
    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=config
        )
    )
    ir.async_create_issue(
        hass,
        HOMEASSISTANT_DOMAIN,
        f"deprecated_yaml_{DOMAIN}",
        breaks_in_ha_version="2027.2.0",
        is_fixable=False,
        issue_domain=DOMAIN,
        severity=ir.IssueSeverity.WARNING,
        translation_key="deprecated_yaml",
        translation_placeholders={
            "domain": DOMAIN,
            "integration_title": INTEGRATION_TITLE,
        },
    )
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
    # The legacy scanner entities were enabled by default; keep that so an
    # imported YAML configuration keeps tracking without manual enabling.
    _attr_entity_registry_enabled_default = True

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
