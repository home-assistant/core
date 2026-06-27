"""Linksys device tracker platform."""

from typing import override

from jnap import JNAPDevice
import voluptuous as vol

from homeassistant.components.device_tracker import (
    PLATFORM_SCHEMA as DEVICE_TRACKER_PLATFORM_SCHEMA,
    AsyncSeeCallback,
    ScannerEntity,
    SourceType,
)
from homeassistant.const import CONF_HOST
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, issue_registry as ir
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import LinksysConfigEntry
from .const import DOMAIN
from .coordinator import LinksysDataUpdateCoordinator

PLATFORM_SCHEMA = DEVICE_TRACKER_PLATFORM_SCHEMA.extend(
    {vol.Required(CONF_HOST): cv.string}
)

PARALLEL_UPDATES = 0


async def async_setup_scanner(
    hass: HomeAssistant,
    config: ConfigType,
    async_see: AsyncSeeCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> bool:
    """Inform users that the YAML configuration is no longer supported."""
    if hass.config_entries.async_entries(DOMAIN):
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
    else:
        ir.async_create_issue(
            hass,
            DOMAIN,
            "deprecated_yaml_import_issue_credentials_required",
            breaks_in_ha_version="2027.1.0",
            is_fixable=False,
            is_persistent=False,
            issue_domain=DOMAIN,
            severity=ir.IssueSeverity.WARNING,
            translation_key="deprecated_yaml_import_issue_credentials_required",
            translation_placeholders={
                "domain": DOMAIN,
                "integration_title": "Linksys Smart Wi-Fi",
                "host": config[CONF_HOST],
            },
        )
    return False


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LinksysConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Linksys device tracker from a config entry."""
    coordinator: LinksysDataUpdateCoordinator = entry.runtime_data
    tracked: set[str] = set()

    @callback
    def _async_update_router() -> None:
        new_entities = []
        for mac, device in coordinator.data.items():
            if mac not in tracked:
                tracked.add(mac)
                new_entities.append(LinksysScannerEntity(coordinator, device))
        async_add_entities(new_entities)

    entry.async_on_unload(coordinator.async_add_listener(_async_update_router))
    _async_update_router()


class LinksysScannerEntity(
    CoordinatorEntity[LinksysDataUpdateCoordinator], ScannerEntity
):
    """Represent a device tracked by the Linksys router."""

    _attr_has_entity_name = True
    _attr_source_type = SourceType.ROUTER

    def __init__(
        self, coordinator: LinksysDataUpdateCoordinator, device: JNAPDevice
    ) -> None:
        """Initialise the entity."""
        super().__init__(coordinator)
        self._mac = device.mac
        self._attr_mac_address = device.mac
        self._attr_unique_id = device.mac
        self._attr_name = device.name

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
