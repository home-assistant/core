"""Support for OpenWRT (luci) routers."""

import logging
from typing import Any

import voluptuous as vol

from homeassistant.components.device_tracker import (
    PLATFORM_SCHEMA as DEVICE_TRACKER_PLATFORM_SCHEMA,
    AsyncSeeCallback,
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
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import issue_registry as ir
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
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
            CONF_SSL: config.get(CONF_SSL, DEFAULT_SSL),
            CONF_VERIFY_SSL: config.get(CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL),
        },
    )

    if result["type"] == FlowResultType.ABORT:
        if result["reason"] == "invalid_auth":
            ir.async_create_issue(
                hass,
                DOMAIN,
                "yaml_import_invalid_auth",
                is_fixable=False,
                issue_domain=DOMAIN,
                severity=ir.IssueSeverity.ERROR,
                translation_key="yaml_import_invalid_auth",
                translation_placeholders={"host": config[CONF_HOST]},
            )
            return True
        if result["reason"] == "cannot_connect":
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
            return True

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
            "integration_title": "OpenWrt (luci)",
        },
    )

    return True


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LuciConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up device tracker for OpenWrt (luci) component."""
    coordinator = entry.runtime_data

    async_add_entities(
        LuciScannerEntity(coordinator, mac, device)
        for mac, device in coordinator.data.items()
    )


class LuciScannerEntity(CoordinatorEntity[LuciCoordinator], ScannerEntity):
    """Representation of a device connected to an OpenWrt router."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: LuciCoordinator,
        mac: str,
        device: Any,
    ) -> None:
        """Initialize the scanner entity."""
        super().__init__(coordinator)
        self._mac = mac
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{mac}"
        self._attr_mac_address = mac
        self._attr_hostname = device.hostname
        self._attr_ip_address = device.ip
        self._attr_name = device.hostname or mac

    @property
    def unique_id(self) -> str | None:
        """Return the unique ID of the entity."""
        return self._attr_unique_id

    @property
    def is_connected(self) -> bool:
        """Return true if the device is connected to the router."""
        return self._mac in self.coordinator.data

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if self._mac in self.coordinator.data:
            device = self.coordinator.data[self._mac]
            self._attr_hostname = device.hostname
            self._attr_ip_address = device.ip
            self._attr_name = device.hostname or self._mac
        super()._handle_coordinator_update()
