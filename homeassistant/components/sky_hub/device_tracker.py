"""Support for Sky Hub."""

from typing import override

import probatio

from homeassistant.components.device_tracker import (
    PLATFORM_SCHEMA as DEVICE_TRACKER_PLATFORM_SCHEMA,
    AsyncSeeCallback,
    ScannerEntity,
)
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import CONF_HOST
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    issue_registry as ir,
)
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DEFAULT_HOST, DOMAIN
from .coordinator import SkyHubConfigEntry, SkyHubCoordinator

PARALLEL_UPDATES = 0

PLATFORM_SCHEMA = DEVICE_TRACKER_PLATFORM_SCHEMA.extend(
    {probatio.Optional(CONF_HOST, default=DEFAULT_HOST): cv.string}
)


async def async_setup_scanner(
    hass: HomeAssistant,
    config: ConfigType,
    async_see: AsyncSeeCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> bool:
    """Import legacy YAML configuration."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={CONF_HOST: config[CONF_HOST]},
    )

    issue_id = f"yaml_import_cannot_connect_{config[CONF_HOST]}"

    if result["type"] is FlowResultType.ABORT and result["reason"] == "cannot_connect":
        ir.async_create_issue(
            hass,
            DOMAIN,
            issue_id,
            breaks_in_ha_version="2027.5.0",
            is_fixable=False,
            issue_domain=DOMAIN,
            severity=ir.IssueSeverity.ERROR,
            translation_key="yaml_import_cannot_connect",
            translation_placeholders={"host": config[CONF_HOST]},
        )
        return True

    ir.async_delete_issue(hass, DOMAIN, issue_id)
    ir.async_create_issue(
        hass,
        HOMEASSISTANT_DOMAIN,
        f"deprecated_yaml_{DOMAIN}",
        breaks_in_ha_version="2027.5.0",
        is_fixable=False,
        issue_domain=DOMAIN,
        severity=ir.IssueSeverity.WARNING,
        translation_key="deprecated_yaml",
        translation_placeholders={
            "domain": DOMAIN,
            "integration_title": "Sky Hub",
        },
    )
    return True


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SkyHubConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Sky Hub device tracker entities."""
    coordinator = entry.runtime_data

    @callback
    def async_add_new_devices() -> None:
        """Rename the devices of renamed clients and add new clients."""
        # Done here because disabled trackers do not listen to the coordinator
        device_registry = dr.async_get(hass)
        for mac, name in coordinator.data.items():
            if (
                name
                and (
                    device := device_registry.async_get_device_by_connection(
                        (dr.CONNECTION_NETWORK_MAC, mac), entry.entry_id
                    )
                )
                and device.name != name
            ):
                device_registry.async_update_device(device.id, name=name)
        if new_macs := coordinator.data.keys() - coordinator.tracked_macs:
            coordinator.tracked_macs.update(new_macs)
            async_add_entities(
                SkyHubScannerEntity(coordinator, mac, coordinator.data[mac])
                for mac in new_macs
            )

    async_add_new_devices()
    entry.async_on_unload(coordinator.async_add_listener(async_add_new_devices))


class SkyHubScannerEntity(CoordinatorEntity[SkyHubCoordinator], ScannerEntity):
    """Representation of a device connected to a Sky Hub."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: SkyHubCoordinator,
        mac: str,
        name: str,
    ) -> None:
        """Initialize the scanner entity."""
        super().__init__(coordinator)
        self._mac = mac
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{mac}"
        self._attr_mac_address = mac
        self._attr_hostname = name or None
        connection = (dr.CONNECTION_NETWORK_MAC, mac)
        self._attr_device_info = DeviceInfo(connections={connection})
        if name:
            self._attr_device_info["name"] = name
        elif not dr.async_get(coordinator.hass).async_get_device_by_connection(
            connection, coordinator.config_entry.entry_id
        ):
            # Only name a new device by MAC, an existing device keeps its name
            self._attr_device_info["name"] = mac

    @property
    @override
    def unique_id(self) -> str | None:
        """Return the unique ID of the entity."""
        return self._attr_unique_id

    @property
    @override
    def is_connected(self) -> bool:
        """Return true if the device is connected to the router."""
        return self._mac in self.coordinator.data

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if self._mac in self.coordinator.data:
            self._attr_hostname = self.coordinator.data[self._mac] or None
        super()._handle_coordinator_update()
