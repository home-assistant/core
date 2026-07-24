"""Support for Aruba ClearPass Policy Manager."""

from typing import override

import voluptuous as vol

from homeassistant.components.device_tracker import (
    PLATFORM_SCHEMA as DEVICE_TRACKER_PLATFORM_SCHEMA,
    AsyncSeeCallback,
    ScannerEntity,
)
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import CONF_API_KEY, CONF_CLIENT_ID, CONF_HOST
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_validation as cv, issue_registry as ir
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import CppmConfigEntry, CppmDataUpdateCoordinator

PLATFORM_SCHEMA = DEVICE_TRACKER_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_CLIENT_ID): cv.string,
        vol.Required(CONF_API_KEY): cv.string,
    }
)


async def async_setup_scanner(
    hass: HomeAssistant,
    config: ConfigType,
    async_see: AsyncSeeCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> bool:
    """Import the legacy YAML device tracker into a config entry."""
    import_data = {
        CONF_HOST: config[CONF_HOST],
        CONF_CLIENT_ID: config[CONF_CLIENT_ID],
        CONF_API_KEY: config[CONF_API_KEY],
    }
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data=import_data
    )

    if result["type"] is FlowResultType.ABORT and result["reason"] == "cannot_connect":
        ir.async_create_issue(
            hass,
            DOMAIN,
            "yaml_import_cannot_connect",
            is_fixable=False,
            issue_domain=DOMAIN,
            severity=ir.IssueSeverity.ERROR,
            translation_key="yaml_import_cannot_connect",
            translation_placeholders={"host": config[CONF_HOST]},
        )
        return False

    ir.async_create_issue(
        hass,
        HOMEASSISTANT_DOMAIN,
        f"deprecated_yaml_{DOMAIN}",
        is_fixable=False,
        issue_domain=DOMAIN,
        severity=ir.IssueSeverity.WARNING,
        translation_key="deprecated_yaml",
        translation_placeholders={
            "domain": DOMAIN,
            "integration_title": "Aruba ClearPass",
        },
    )
    return True


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: CppmConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the device tracker for a ClearPass config entry."""
    coordinator = config_entry.runtime_data
    tracked: set[str] = set()

    @callback
    def _async_add_new_devices() -> None:
        new_macs = [mac for mac in coordinator.data if mac not in tracked]
        tracked.update(new_macs)
        if new_macs:
            async_add_entities(CppmScannerEntity(coordinator, mac) for mac in new_macs)

    config_entry.async_on_unload(coordinator.async_add_listener(_async_add_new_devices))
    _async_add_new_devices()


class CppmScannerEntity(CoordinatorEntity[CppmDataUpdateCoordinator], ScannerEntity):
    """Representation of an endpoint tracked by Aruba ClearPass."""

    def __init__(self, coordinator: CppmDataUpdateCoordinator, mac: str) -> None:
        """Initialize the tracked device."""
        super().__init__(coordinator)
        self._mac = mac
        self._attr_name = mac

    @property
    @override
    def mac_address(self) -> str:
        """Return the MAC address of the device."""
        return self._mac

    @property
    @override
    def is_connected(self) -> bool:
        """Return whether the device is online."""
        return self._mac in self.coordinator.data
