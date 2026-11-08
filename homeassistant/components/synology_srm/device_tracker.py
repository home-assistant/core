"""Device tracker for Synology SRM routers."""

import logging
from typing import override

import probatio
import synology_srm

from homeassistant.components.device_tracker import (
    DOMAIN as DEVICE_TRACKER_DOMAIN,
    PLATFORM_SCHEMA as DEVICE_TRACKER_PLATFORM_SCHEMA,
    DeviceScanner,
    ScannerEntity,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    entity_registry as er,
    issue_registry as ir,
)
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_TRACKED_DEVICES,
    DEFAULT_PORT,
    DEFAULT_SSL,
    DEFAULT_USERNAME,
    DEFAULT_VERIFY_SSL,
    DOMAIN,
)
from .coordinator import SynologySrmConfigEntry, SynologySrmCoordinator

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0

PLATFORM_SCHEMA = DEVICE_TRACKER_PLATFORM_SCHEMA.extend(
    {
        probatio.Required(CONF_HOST): cv.string,
        probatio.Required(CONF_USERNAME, default=DEFAULT_USERNAME): cv.string,
        probatio.Required(probatio.Secret(CONF_PASSWORD)): cv.string,
        probatio.Optional(CONF_PORT, default=DEFAULT_PORT): probatio.Port(),
        probatio.Optional(CONF_SSL, default=DEFAULT_SSL): cv.boolean,
        probatio.Optional(CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL): cv.boolean,
    }
)

ATTRIBUTE_ALIAS = {
    "band": None,
    "connection": None,
    "current_rate": None,
    "dev_type": None,
    "hostname": None,
    "ip6_addr": None,
    "ip_addr": None,
    "is_baned": "is_banned",
    "is_beamforming_on": None,
    "is_guest": None,
    "is_high_qos": None,
    "is_low_qos": None,
    "is_manual_dev_type": None,
    "is_manual_hostname": None,
    "is_online": None,
    "is_parental_controled": "is_parental_controlled",
    "is_qos": None,
    "is_wireless": None,
    "mac": None,
    "max_rate": None,
    "mesh_node_id": None,
    "rate_quality": None,
    "signalstrength": "signal_strength",
    "transferRXRate": "transfer_rx_rate",
    "transferTXRate": "transfer_tx_rate",
}


def get_scanner(
    hass: HomeAssistant, config: ConfigType
) -> SynologySrmDeviceScanner | None:
    """Validate the configuration and return Synology SRM scanner."""

    @callback
    def async_create_issue() -> None:
        host = config[DEVICE_TRACKER_DOMAIN][CONF_HOST]
        ir.async_create_issue(
            hass,
            DOMAIN,
            f"deprecated_yaml_{host}",
            breaks_in_ha_version="2027.5.0",
            is_fixable=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key="deprecated_yaml",
            translation_placeholders={"host": host},
        )

    hass.add_job(async_create_issue)
    scanner = SynologySrmDeviceScanner(config[DEVICE_TRACKER_DOMAIN])

    return scanner if scanner.success_init else None


class SynologySrmDeviceScanner(DeviceScanner):
    """Scanner for devices connected to a Synology SRM router."""

    def __init__(self, config):
        """Initialize the scanner."""

        self.client = synology_srm.Client(
            host=config[CONF_HOST],
            port=config[CONF_PORT],
            username=config[CONF_USERNAME],
            password=config[CONF_PASSWORD],
            https=config[CONF_SSL],
        )

        if not config[CONF_VERIFY_SSL]:
            self.client.http.disable_https_verify()

        self.devices = []
        self.success_init = self._update_info()

    @override
    def scan_devices(self):
        """Scan for new devices and return a list with found device IDs."""
        self._update_info()

        return [device["mac"] for device in self.devices]

    @override
    def get_extra_attributes(self, device) -> dict:
        """Get the extra attributes of a device."""
        device = next(
            (result for result in self.devices if result["mac"] == device), None
        )
        filtered_attributes: dict[str, str] = {}
        if not device:
            return filtered_attributes
        for attribute, alias in ATTRIBUTE_ALIAS.items():
            if (value := device.get(attribute)) is None:
                continue
            attr = alias or attribute
            filtered_attributes[attr] = value
        return filtered_attributes

    @override
    def get_device_name(self, device):
        """Return the name of the given device or None if we don't know."""
        filter_named = [
            result["hostname"] for result in self.devices if result["mac"] == device
        ]

        if filter_named:
            return filter_named[0]

        return None

    def _update_info(self):
        """Check the router for connected devices."""
        _LOGGER.debug("Scanning for connected devices")

        try:
            self.devices = self.client.core.get_network_nsm_device({"is_online": True})
        except synology_srm.http.SynologyException as ex:
            _LOGGER.error("Error with the Synology SRM: %s", ex)
            return False

        _LOGGER.debug("Found %d device(s) connected to the router", len(self.devices))

        return True


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SynologySrmConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up config entry based trackers."""
    coordinator = entry.runtime_data
    tracked: set[str] = set()
    device_registry = dr.async_get(hass)
    entity_registry = er.async_get(hass)
    registered = {
        entity.unique_id
        for entity in er.async_entries_for_config_entry(
            er.async_get(hass), entry.entry_id
        )
    }

    @callback
    def async_update_devices() -> None:
        """Discover clients and update names even for disabled trackers."""
        for mac, client in coordinator.data.items():
            if (
                (name := client.get("hostname"))
                and (
                    registered_device := device_registry.async_get_device_by_connection(
                        (dr.CONNECTION_NETWORK_MAC, mac), entry.entry_id
                    )
                )
                and registered_device.name != name
            ):
                device_registry.async_update_device(registered_device.id, name=name)
        new_macs = (coordinator.data.keys() | registered) - tracked
        new_macs = {
            mac
            for mac in new_macs
            if (
                entity_id := entity_registry.async_get_entity_id(
                    "device_tracker", DOMAIN, mac
                )
            )
            is None
            or entity_registry.entities[entity_id].config_entry_id == entry.entry_id
        }
        tracked.update(new_macs)
        for mac in new_macs:
            connection = (dr.CONNECTION_NETWORK_MAC, mac)
            existing_device = device_registry.async_get_device_by_connection(
                connection, entry.entry_id
            )
            device = device_registry.async_get_or_create(
                config_entry_id=entry.entry_id,
                connections={connection},
                name=coordinator.data.get(mac, {}).get("hostname")
                or (existing_device.name if existing_device else mac),
                disabled_by=(
                    dr.DeviceEntryDisabler.INTEGRATION
                    if CONF_TRACKED_DEVICES in entry.data
                    and mac not in entry.data[CONF_TRACKED_DEVICES]
                    else None
                ),
            )
            if CONF_TRACKED_DEVICES not in entry.data:
                continue
            device_disabled = device.disabled
            if existing_device is None:
                device_disabled = mac not in entry.data[CONF_TRACKED_DEVICES]
                device_registry.async_update_device(
                    device.id,
                    disabled_by=None
                    if mac in entry.data[CONF_TRACKED_DEVICES]
                    else dr.DeviceEntryDisabler.INTEGRATION,
                )
            existing_entity_id = entity_registry.async_get_entity_id(
                "device_tracker", DOMAIN, mac
            )
            entity = entity_registry.async_get_or_create(
                "device_tracker",
                DOMAIN,
                mac,
                config_entry=entry,
                device_id=device.id,
                suggested_object_id=device.name or mac,
                has_entity_name=True,
            )
            if existing_entity_id is None:
                # An explicit selection also applies when restoring a deleted entry.
                entity_registry.async_update_entity(
                    entity.entity_id,
                    disabled_by=er.RegistryEntryDisabler.DEVICE
                    if device_disabled
                    else None,
                )
        async_add_entities(SynologySrmTracker(coordinator, mac) for mac in new_macs)

    entry.async_on_unload(coordinator.async_add_listener(async_update_devices))
    async_update_devices()


class SynologySrmTracker(CoordinatorEntity[SynologySrmCoordinator], ScannerEntity):
    """A client of a Synology SRM router."""

    _attr_has_entity_name = True
    _attr_name = None

    def __init__(self, coordinator: SynologySrmCoordinator, mac: str) -> None:
        """Initialize the tracker."""
        super().__init__(coordinator)
        self._mac = self._attr_mac_address = mac
        self._attr_entity_registry_enabled_default = (
            CONF_TRACKED_DEVICES in coordinator.config_entry.data
        )
        connection = (dr.CONNECTION_NETWORK_MAC, mac)
        self._attr_device_info = dr.DeviceInfo(connections={connection})
        if name := coordinator.data.get(mac, {}).get("hostname"):
            self._attr_device_info["name"] = name
        elif not dr.async_get(coordinator.hass).async_get_device_by_connection(
            connection, coordinator.config_entry.entry_id
        ):
            self._attr_device_info["name"] = mac

    @property
    @override
    def is_connected(self) -> bool:
        """Return whether this client is online."""
        return self.coordinator.data.get(self._mac, {}).get("is_online", False)

    @property
    @override
    def hostname(self) -> str | None:
        """Return the hostname."""
        return self.coordinator.data.get(self._mac, {}).get("hostname")

    @property
    @override
    def ip_address(self) -> str | None:
        """Return the IP address."""
        return self.coordinator.data.get(self._mac, {}).get("ip_addr")

    @property
    @override
    def extra_state_attributes(self) -> dict[str, object]:
        """Return the same client attributes as the legacy tracker."""
        device = self.coordinator.data.get(self._mac, {})
        return {
            alias or attribute: value
            for attribute, alias in ATTRIBUTE_ALIAS.items()
            if (value := device.get(attribute)) is not None
        }
