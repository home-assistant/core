"""Track devices connected to a Hitron CODA router."""

from typing import override

import probatio

from homeassistant.components.device_tracker import (
    CONF_SCAN_INTERVAL as CONF_INTERVAL_SECONDS,
    PLATFORM_SCHEMA as DEVICE_TRACKER_PLATFORM_SCHEMA,
    AsyncSeeCallback,
    ScannerEntity,
)
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_TYPE,
    CONF_USERNAME,
)
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_validation as cv, issue_registry as ir
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DEFAULT_TYPE, DOMAIN
from .coordinator import HitronCodaConfigEntry, HitronCodaDataUpdateCoordinator

PLATFORM_SCHEMA = DEVICE_TRACKER_PLATFORM_SCHEMA.extend(
    {
        probatio.Required(CONF_HOST): cv.string,
        probatio.Required(CONF_USERNAME): cv.string,
        probatio.Required(probatio.Secret(CONF_PASSWORD)): cv.string,
        probatio.Optional(CONF_TYPE, default=DEFAULT_TYPE): cv.string,
    }
)


async def async_setup_scanner(
    hass: HomeAssistant,
    config: ConfigType,
    _async_see: AsyncSeeCallback,
    _discovery_info: DiscoveryInfoType | None = None,
) -> bool:
    """Import legacy YAML configuration into a config entry."""
    data = {
        key: config[key] for key in (CONF_HOST, CONF_USERNAME, CONF_PASSWORD, CONF_TYPE)
    }
    if CONF_INTERVAL_SECONDS in config:
        data[CONF_SCAN_INTERVAL] = config[CONF_INTERVAL_SECONDS].total_seconds()
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data=data
    )
    if (
        result["type"] is FlowResultType.ABORT
        and result["reason"] != "already_configured"
    ):
        ir.async_create_issue(
            hass,
            DOMAIN,
            "yaml_import_failed",
            is_fixable=False,
            severity=ir.IssueSeverity.ERROR,
            translation_key="yaml_import_failed",
            translation_placeholders={CONF_HOST: config[CONF_HOST]},
        )
        return False

    ir.async_delete_issue(hass, DOMAIN, "yaml_import_failed")
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
            "integration_title": "Rogers Hitron CODA",
        },
    )
    return True


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HitronCodaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up device trackers for the router."""
    coordinator = entry.runtime_data
    tracked: set[str] = set()

    @callback
    def async_add_devices() -> None:
        """Add devices first seen in a successful update."""
        new_macs = coordinator.data.keys() - tracked
        tracked.update(new_macs)
        async_add_entities(
            HitronCodaScannerEntity(coordinator, mac) for mac in sorted(new_macs)
        )

    entry.async_on_unload(coordinator.async_add_listener(async_add_devices))
    async_add_devices()


class HitronCodaScannerEntity(
    CoordinatorEntity[HitronCodaDataUpdateCoordinator], ScannerEntity
):
    """Represent a client seen on the router's network."""

    def __init__(self, coordinator: HitronCodaDataUpdateCoordinator, mac: str) -> None:
        """Initialize a client using its stable MAC address."""
        super().__init__(coordinator)
        self._mac = mac
        self._attr_mac_address = format_mac(mac)
        self._attr_hostname = coordinator.data[mac]
        self._attr_name = self._attr_hostname or self._attr_mac_address

    @property
    @override
    def is_connected(self) -> bool:
        """Return whether the client was seen in the latest successful scan."""
        return self._mac in self.coordinator.data

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        """Update client names, retaining them while a client is disconnected."""
        if self._mac in self.coordinator.data:
            self._attr_hostname = self.coordinator.data[self._mac]
            self._attr_name = self._attr_hostname or self._attr_mac_address
        super()._handle_coordinator_update()
