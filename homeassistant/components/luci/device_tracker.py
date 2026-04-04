"""Support for OpenWRT (luci) routers."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.components.device_tracker import (
    PLATFORM_SCHEMA as DEVICE_TRACKER_PLATFORM_SCHEMA,
    ScannerEntity,
)
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DEFAULT_SSL, DEFAULT_VERIFY_SSL, DOMAIN
from .coordinator import LuciConfigEntry, LuciCoordinator

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0

PLATFORM_SCHEMA = DEVICE_TRACKER_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_SSL, default=DEFAULT_SSL): cv.boolean,
        vol.Optional(CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL): cv.boolean,
    }
)


async def async_get_scanner(
    hass: HomeAssistant,
    config: ConfigType,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Import legacy YAML configuration."""
    scanner_config = config["device_tracker"]

    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data={
                CONF_HOST: scanner_config[CONF_HOST],
                CONF_USERNAME: scanner_config[CONF_USERNAME],
                CONF_PASSWORD: scanner_config[CONF_PASSWORD],
                CONF_SSL: scanner_config.get(CONF_SSL, DEFAULT_SSL),
                CONF_VERIFY_SSL: scanner_config.get(
                    CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL
                ),
            },
        )
    )

    async_create_issue(
        hass,
        HOMEASSISTANT_DOMAIN,
        f"deprecated_yaml_{DOMAIN}",
        is_fixable=False,
        issue_domain=DOMAIN,
        severity=IssueSeverity.WARNING,
        translation_key="deprecated_yaml",
        translation_placeholders={
            "domain": DOMAIN,
            "integration_title": "OpenWrt (luci)",
        },
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LuciConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up device tracker for OpenWrt (luci) component."""
    coordinator = entry.runtime_data
    tracked: set[str] = set()

    @callback
    def _async_add_new_entities() -> None:
        """Add new tracker entities from the router."""
        new_entities: list[LuciScannerEntity] = []
        for mac, device in coordinator.data.items():
            if mac not in tracked:
                tracked.add(mac)
                new_entities.append(LuciScannerEntity(coordinator, mac, device))
        if new_entities:
            async_add_entities(new_entities)

    _async_add_new_entities()
    entry.async_on_unload(coordinator.async_add_listener(_async_add_new_entities))


class LuciScannerEntity(CoordinatorEntity[LuciCoordinator], ScannerEntity):
    """Representation of a device connected to an OpenWrt router."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: LuciCoordinator,
        mac: str,
        device: dict[str, Any],
    ) -> None:
        """Initialize the scanner entity."""
        super().__init__(coordinator)
        self._mac = mac
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{mac}"
        self._attr_mac_address = mac
        self._attr_hostname = device.get("hostname")
        self._attr_ip_address = device.get("ip")
        self._attr_name = device.get("hostname") or mac

    @property
    def is_connected(self) -> bool:
        """Return true if the device is connected to the router."""
        return self._mac in self.coordinator.data

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if self._mac in self.coordinator.data:
            device = self.coordinator.data[self._mac]
            self._attr_hostname = device.get("hostname")
            self._attr_ip_address = device.get("ip")
            self._attr_name = device.get("hostname") or self._mac
        super()._handle_coordinator_update()
