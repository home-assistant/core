"""Device tracker for the Swisscom Internet-Box."""

import logging

import voluptuous as vol

from homeassistant.components.device_tracker import (
    PLATFORM_SCHEMA as DEVICE_TRACKER_PLATFORM_SCHEMA,
    AsyncSeeCallback,
    ScannerEntity,
)
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_validation as cv, issue_registry as ir
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DEFAULT_HOST, DEFAULT_USERNAME, DOMAIN
from .coordinator import SwisscomConfigEntry, SwisscomDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = DEVICE_TRACKER_PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_HOST, default=DEFAULT_HOST): cv.string,
        vol.Optional(CONF_USERNAME, default=DEFAULT_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
    }
)


async def async_setup_scanner(
    hass: HomeAssistant,
    config: ConfigType,
    async_see: AsyncSeeCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> bool:
    """Import YAML configuration into a config entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={
            CONF_HOST: config[CONF_HOST],
            CONF_USERNAME: config[CONF_USERNAME],
            CONF_PASSWORD: config[CONF_PASSWORD],
        },
    )
    if (
        result.get("type") is FlowResultType.ABORT
        and result.get("reason") != "already_configured"
    ):
        _LOGGER.warning(
            "Could not import Swisscom Internet-Box YAML configuration: %s",
            result.get("reason"),
        )
        return False

    ir.async_create_issue(
        hass,
        HOMEASSISTANT_DOMAIN,
        f"deprecated_yaml_{DOMAIN}",
        breaks_in_ha_version="2027.5.0",
        is_fixable=False,
        is_persistent=False,
        issue_domain=DOMAIN,
        severity=ir.IssueSeverity.WARNING,
        translation_key="deprecated_yaml",
        translation_placeholders={
            "domain": DOMAIN,
            "integration_title": "Swisscom Internet-Box",
        },
    )
    return True


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
