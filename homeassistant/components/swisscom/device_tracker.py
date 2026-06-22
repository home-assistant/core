"""Device tracker for the Swisscom Internet-Box."""

import voluptuous as vol

from homeassistant.components.device_tracker import (
    PLATFORM_SCHEMA as DEVICE_TRACKER_PLATFORM_SCHEMA,
    AsyncSeeCallback,
    ScannerEntity,
)
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, issue_registry as ir
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DEFAULT_HOST, DOMAIN
from .coordinator import SwisscomConfigEntry, SwisscomDataUpdateCoordinator

PLATFORM_SCHEMA = DEVICE_TRACKER_PLATFORM_SCHEMA.extend(
    {vol.Optional(CONF_HOST, default=DEFAULT_HOST): cv.string}
)


async def async_setup_scanner(
    hass: HomeAssistant,
    config: ConfigType,
    async_see: AsyncSeeCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> bool:
    """Inform users that the YAML configuration is no longer supported."""
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
            "integration_title": "Swisscom Internet-Box",
            "host": config[CONF_HOST],
        },
    )
    return False


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SwisscomConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up device tracker entities for the Swisscom Internet-Box."""
    coordinator = entry.runtime_data
    tracked: set[str] = set()

    @callback
    def _add_new_entities() -> None:
        new_keys = [key for key in coordinator.data if key not in tracked]
        if new_keys:
            tracked.update(new_keys)
            async_add_entities(
                SwisscomScannerEntity(coordinator, key) for key in new_keys
            )

    _add_new_entities()
    entry.async_on_unload(coordinator.async_add_listener(_add_new_entities))


class SwisscomScannerEntity(
    CoordinatorEntity[SwisscomDataUpdateCoordinator], ScannerEntity
):
    """A device tracked by the Swisscom Internet-Box."""

    def __init__(self, coordinator: SwisscomDataUpdateCoordinator, key: str) -> None:
        """Initialize the scanner entity."""
        super().__init__(coordinator)
        self._key = key
        self._attr_unique_id = key

    @property
    def _device(self):
        return self.coordinator.data.get(self._key)

    @property
    def is_connected(self) -> bool:
        """Return whether the device is currently connected to the LAN."""
        device = self._device
        return bool(device and device.active)

    @property
    def mac_address(self) -> str:
        """Return the MAC address of the device."""
        device = self._device
        return device.phys_address if device else self._key

    @property
    def hostname(self) -> str | None:
        """Return the hostname of the device."""
        device = self._device
        return device.name if device else None

    @property
    def ip_address(self) -> str | None:
        """Return the IP address of the device."""
        device = self._device
        return device.ip_address if device else None

    @property
    def name(self) -> str | None:
        """Return the friendly name of the device."""
        return self.hostname
