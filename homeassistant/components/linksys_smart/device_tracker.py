"""Linksys Smart Wi-Fi device tracker platform."""

from typing import override

import probatio

from homeassistant.components.device_tracker import (
    DOMAIN as DEVICE_TRACKER_DOMAIN,
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
    entity_registry as er,
    issue_registry as ir,
)
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import LinksysConfigEntry, LinksysDataUpdateCoordinator

PLATFORM_SCHEMA = DEVICE_TRACKER_PLATFORM_SCHEMA.extend(
    {probatio.Required(CONF_HOST): cv.string}
)

PARALLEL_UPDATES = 0


async def async_setup_scanner(
    hass: HomeAssistant,
    config: ConfigType,
    async_see: AsyncSeeCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> bool:
    """Migrate the YAML configuration to a config entry."""
    host = config[CONF_HOST]

    def _create_deprecated_yaml_issue() -> None:
        ir.async_create_issue(
            hass,
            HOMEASSISTANT_DOMAIN,
            f"deprecated_yaml_{DOMAIN}",
            is_fixable=False,
            issue_domain=DOMAIN,
            breaks_in_ha_version="2027.1.0",
            severity=ir.IssueSeverity.WARNING,
            translation_key="deprecated_yaml",
            translation_placeholders={
                "domain": DOMAIN,
                "integration_title": "Linksys Smart Wi-Fi",
            },
        )

    if any(
        entry.data[CONF_HOST] == host
        for entry in hass.config_entries.async_entries(DOMAIN)
    ):
        _create_deprecated_yaml_issue()
        return True

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={CONF_HOST: host},
    )
    if (
        result["type"] is not FlowResultType.ABORT
        or result["reason"] == "already_configured"
    ):
        _create_deprecated_yaml_issue()
        return True
    return False


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LinksysConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Linksys device tracker from a config entry."""
    coordinator = entry.runtime_data
    tracked: set[str] = set()

    @callback
    def _async_update_router() -> None:
        new_entities = []
        for mac, device in coordinator.data.items():
            if mac not in tracked:
                tracked.add(mac)
                new_entities.append(LinksysScannerEntity(coordinator, mac, device.name))
        async_add_entities(new_entities)

    entry.async_on_unload(coordinator.async_add_listener(_async_update_router))
    _async_update_router()

    registry = er.async_get(hass)
    restored_entities = []
    for reg_entry in er.async_entries_for_config_entry(registry, entry.entry_id):
        if reg_entry.domain != DEVICE_TRACKER_DOMAIN:
            continue
        mac = reg_entry.unique_id.removeprefix(f"{entry.entry_id}_")
        if mac in tracked:
            continue
        tracked.add(mac)
        restored_entities.append(
            LinksysScannerEntity(coordinator, mac, reg_entry.original_name or mac)
        )
    async_add_entities(restored_entities)


class LinksysScannerEntity(
    CoordinatorEntity[LinksysDataUpdateCoordinator], ScannerEntity
):
    """Represent a device tracked by the Linksys router."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: LinksysDataUpdateCoordinator, mac: str, name: str
    ) -> None:
        """Initialise the entity."""
        super().__init__(coordinator)
        self._mac = mac
        self._attr_mac_address = mac
        self._fallback_name = name

    @property
    @override
    def name(self) -> str | None:
        """Return the device's current name, falling back when disconnected."""
        if device := self.coordinator.data.get(self._mac):
            self._fallback_name = device.name
        return self._fallback_name

    @property
    @override
    def unique_id(self) -> str:
        """Return a unique ID scoped to this router's config entry."""
        return f"{self.coordinator.config_entry.entry_id}_{self._mac}"

    @property
    @override
    def entity_registry_enabled_default(self) -> bool:
        """Enable by default for routers migrated from YAML to preserve prior behavior."""
        if self.coordinator.config_entry.source == SOURCE_IMPORT:
            return True
        return super().entity_registry_enabled_default

    @property
    @override
    def is_connected(self) -> bool:
        """Return true if the device is currently connected to the router."""
        return self._mac in self.coordinator.data

    @property
    @override
    def ip_address(self) -> str | None:
        """Return the IP address of the device if connected."""
        if device := self.coordinator.data.get(self._mac):
            return device.ip_address
        return None

    @property
    @override
    def hostname(self) -> str | None:
        """Return the hostname of the device if connected."""
        if device := self.coordinator.data.get(self._mac):
            return device.hostname
        return None
