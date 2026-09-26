"""Support for Xiaomi Mi routers."""

from typing import override

import probatio

from homeassistant.components.device_tracker import (
    PLATFORM_SCHEMA as DEVICE_TRACKER_PLATFORM_SCHEMA,
    AsyncSeeCallback,
    ScannerEntity,
)
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import issue_registry as ir
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DEFAULT_USERNAME, DOMAIN
from .coordinator import XiaomiConfigEntry, XiaomiCoordinator, XiaomiDeviceInfo

PARALLEL_UPDATES = 0

PLATFORM_SCHEMA = DEVICE_TRACKER_PLATFORM_SCHEMA.extend(
    {
        probatio.Required(CONF_HOST): cv.string,
        probatio.Required(CONF_USERNAME, default=DEFAULT_USERNAME): cv.string,
        probatio.Required(CONF_PASSWORD): cv.string,
    }
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
        data={
            CONF_HOST: config[CONF_HOST],
            CONF_USERNAME: config[CONF_USERNAME],
            CONF_PASSWORD: config[CONF_PASSWORD],
        },
    )

    if result["type"] is FlowResultType.ABORT:
        reason = result["reason"]
        if reason in ("invalid_auth", "cannot_connect"):
            ir.async_create_issue(
                hass,
                DOMAIN,
                f"yaml_import_{reason}_{config[CONF_HOST]}",
                is_fixable=False,
                issue_domain=DOMAIN,
                severity=ir.IssueSeverity.ERROR,
                translation_key=f"yaml_import_{reason}",
                translation_placeholders={"host": config[CONF_HOST]},
            )
            return True

    ir.async_create_issue(
        hass,
        DOMAIN,
        f"deprecated_device_tracker_yaml_{config[CONF_HOST]}",
        is_fixable=False,
        issue_domain=DOMAIN,
        severity=ir.IssueSeverity.WARNING,
        translation_key="deprecated_device_tracker_yaml",
        translation_placeholders={"host": config[CONF_HOST]},
    )

    return True


async def async_setup_entry(
    hass: HomeAssistant,
    entry: XiaomiConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up device tracker for the Xiaomi component."""
    coordinator = entry.runtime_data
    tracked: set[str] = set()

    @callback
    def _async_add_new_devices() -> None:
        """Add entities for devices seen for the first time."""
        if new_macs := coordinator.data.keys() - tracked:
            tracked.update(new_macs)
            async_add_entities(
                XiaomiScannerEntity(coordinator, mac, coordinator.data[mac])
                for mac in new_macs
            )

    _async_add_new_devices()
    entry.async_on_unload(coordinator.async_add_listener(_async_add_new_devices))


class XiaomiScannerEntity(CoordinatorEntity[XiaomiCoordinator], ScannerEntity):
    """Representation of a device connected to a Xiaomi Mi router."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: XiaomiCoordinator,
        mac: str,
        device: XiaomiDeviceInfo,
    ) -> None:
        """Initialize the scanner entity."""
        super().__init__(coordinator)
        self._mac = mac
        # Scoped to the config entry: the same client can be connected to
        # multiple configured routers.
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{mac}"
        self._attr_mac_address = mac
        self._attr_hostname = device.get("name")
        self._attr_ip_address = device.get("ip")
        self._attr_name = device.get("name") or mac

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
            device = self.coordinator.data[self._mac]
            self._attr_hostname = device.get("name")
            self._attr_ip_address = device.get("ip")
            self._attr_name = device.get("name") or self._mac
        super()._handle_coordinator_update()
