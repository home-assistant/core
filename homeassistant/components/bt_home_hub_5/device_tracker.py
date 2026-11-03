"""Support for BT Home Hub 5."""

from typing import override

import probatio

from homeassistant.components.device_tracker import (
    PLATFORM_SCHEMA as DEVICE_TRACKER_PLATFORM_SCHEMA,
    AsyncSeeCallback,
    ScannerEntity,
    SourceType,
)
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import CONF_HOST
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.issue_registry import (
    IssueSeverity,
    async_create_issue,
    async_delete_issue,
)
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DEFAULT_HOST, DOMAIN
from .coordinator import BTHomeHub5ConfigEntry, BTHomeHub5DataUpdateCoordinator

PLATFORM_SCHEMA = DEVICE_TRACKER_PLATFORM_SCHEMA.extend(
    {probatio.Optional(CONF_HOST, default=DEFAULT_HOST): cv.string}
)


async def async_setup_scanner(
    hass: HomeAssistant,
    config: ConfigType,
    see: AsyncSeeCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> bool:
    """Import legacy YAML device tracker configuration."""
    host = config[CONF_HOST]
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={CONF_HOST: host},
    )

    issue_id = f"yaml_import_cannot_connect_{host}"

    if result["type"] is FlowResultType.ABORT and result["reason"] in (
        "cannot_connect",
        "unknown",
    ):
        async_create_issue(
            hass,
            DOMAIN,
            issue_id,
            breaks_in_ha_version="2027.6.0",
            is_fixable=False,
            issue_domain=DOMAIN,
            severity=IssueSeverity.ERROR,
            translation_key="yaml_import_cannot_connect",
            translation_placeholders={"host": host},
        )
        return True

    async_delete_issue(hass, DOMAIN, issue_id)
    async_create_issue(
        hass,
        HOMEASSISTANT_DOMAIN,
        f"deprecated_yaml_{DOMAIN}",
        breaks_in_ha_version="2027.6.0",
        is_fixable=False,
        issue_domain=DOMAIN,
        severity=IssueSeverity.WARNING,
        translation_key="deprecated_yaml",
        translation_placeholders={
            "domain": DOMAIN,
            "integration_title": "BT Home Hub 5",
        },
    )
    return True


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BTHomeHub5ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up device tracker entities from a config entry."""
    coordinator = entry.runtime_data
    known_macs: set[str] = set()

    def _update_entities() -> None:
        """Add newly discovered devices as scanner entities."""
        new_entities: list[BTHomeHub5ScannerEntity] = []
        for mac, name in coordinator.data.items():
            if mac not in known_macs:
                known_macs.add(mac)
                new_entities.append(BTHomeHub5ScannerEntity(coordinator, mac, name))
        if new_entities:
            async_add_entities(new_entities)

    _update_entities()
    entry.async_on_unload(coordinator.async_add_listener(_update_entities))


class BTHomeHub5ScannerEntity(
    CoordinatorEntity[BTHomeHub5DataUpdateCoordinator], ScannerEntity
):
    """Representation of a BT Home Hub 5 tracked device."""

    _attr_source_type = SourceType.ROUTER
    _attr_has_entity_name = True
    _attr_name = None

    def __init__(
        self,
        coordinator: BTHomeHub5DataUpdateCoordinator,
        mac: str,
        name: str,
    ) -> None:
        """Initialize the device tracker entity."""
        super().__init__(coordinator)
        self._mac = mac
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{mac}"
        self._attr_hostname = name or None
        self._attr_device_info = DeviceInfo(
            connections={(CONNECTION_NETWORK_MAC, mac)},
            name=name or mac,
        )

    @property
    @override
    def unique_id(self) -> str | None:
        """Return the unique ID of the entity."""
        return self._attr_unique_id

    @property
    @override
    def mac_address(self) -> str:
        """Return the MAC address of the device."""
        return self._mac

    @property
    @override
    def is_connected(self) -> bool:
        """Return True if the device is currently connected to the router."""
        return self._mac in self.coordinator.data
