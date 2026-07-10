"""Support for DD-WRT routers as a device tracker."""

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
from homeassistant.helpers import config_validation as cv, issue_registry as ir
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_WIRELESS_ONLY,
    DEFAULT_NAME,
    DEFAULT_SSL,
    DEFAULT_VERIFY_SSL,
    DEFAULT_WIRELESS_ONLY,
    DOMAIN,
)
from .coordinator import DdWrtConfigEntry, DdWrtDataUpdateCoordinator

PLATFORM_SCHEMA = DEVICE_TRACKER_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Optional(CONF_SSL, default=DEFAULT_SSL): cv.boolean,
        vol.Optional(CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL): cv.boolean,
        vol.Optional(CONF_WIRELESS_ONLY, default=DEFAULT_WIRELESS_ONLY): cv.boolean,
    }
)


async def async_setup_scanner(
    hass: HomeAssistant,
    config: ConfigType,
    _async_see: AsyncSeeCallback,
    _discovery_info: DiscoveryInfoType | None = None,
) -> bool:
    """Set up the legacy DD-WRT device tracker by importing YAML config."""
    import_data = {
        CONF_HOST: config[CONF_HOST],
        CONF_USERNAME: config[CONF_USERNAME],
        CONF_PASSWORD: config[CONF_PASSWORD],
        CONF_SSL: config[CONF_SSL],
        CONF_VERIFY_SSL: config[CONF_VERIFY_SSL],
        CONF_WIRELESS_ONLY: config[CONF_WIRELESS_ONLY],
    }
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data=import_data,
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
            "integration_title": DEFAULT_NAME,
        },
    )

    return True


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: DdWrtConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up device tracker entities for a DD-WRT config entry."""
    coordinator = config_entry.runtime_data
    tracked: set[str] = set()

    @callback
    def _async_update_devices() -> None:
        """Add entities for newly discovered devices."""
        new_entities = [
            DdWrtScannerEntity(coordinator, mac)
            for mac in coordinator.data
            if mac not in tracked
        ]
        if new_entities:
            tracked.update(entity.mac_address for entity in new_entities)
            async_add_entities(new_entities)

    config_entry.async_on_unload(coordinator.async_add_listener(_async_update_devices))
    _async_update_devices()


class DdWrtScannerEntity(CoordinatorEntity[DdWrtDataUpdateCoordinator], ScannerEntity):
    """Representation of a device connected to a DD-WRT router."""

    def __init__(self, coordinator: DdWrtDataUpdateCoordinator, mac: str) -> None:
        """Initialize the tracked device."""
        super().__init__(coordinator)
        self._mac = mac
        device = coordinator.data.get(mac) or {}
        self._attr_name = device.get("hostname") or mac

    @property
    def is_connected(self) -> bool:
        """Return true if the device is currently connected to the router."""
        return self._mac in self.coordinator.data

    @property
    def mac_address(self) -> str:
        """Return the MAC address of the device."""
        return self._mac

    @property
    def ip_address(self) -> str | None:
        """Return the IP address of the device."""
        if device := self.coordinator.data.get(self._mac):
            return device.get("ip")
        return None

    @property
    def hostname(self) -> str | None:
        """Return the hostname of the device."""
        if device := self.coordinator.data.get(self._mac):
            return device.get("hostname")
        return None
