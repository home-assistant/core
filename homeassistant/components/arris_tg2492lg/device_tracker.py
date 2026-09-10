"""Support for Arris TG2492LG router."""

from typing import override

from arris_tg2492lg import Device
import voluptuous as vol

from homeassistant.components.device_tracker import (
    PLATFORM_SCHEMA as DEVICE_TRACKER_PLATFORM_SCHEMA,
    AsyncSeeCallback,
    ScannerEntity,
)
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import CONF_HOST, CONF_PASSWORD
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import issue_registry as ir
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DEFAULT_HOST, DOMAIN
from .coordinator import ArrisConfigEntry, ArrisCoordinator

PARALLEL_UPDATES = 0

PLATFORM_SCHEMA = DEVICE_TRACKER_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_HOST, default=DEFAULT_HOST): cv.string,
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
            CONF_PASSWORD: config[CONF_PASSWORD],
        },
    )

    if result["type"] is FlowResultType.ABORT:
        reason = result["reason"]
        if reason in ("invalid_auth", "cannot_connect"):
            ir.async_create_issue(
                hass,
                DOMAIN,
                f"yaml_import_{reason}",
                is_fixable=False,
                issue_domain=DOMAIN,
                severity=ir.IssueSeverity.ERROR,
                translation_key=f"yaml_import_{reason}",
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
            "integration_title": "Arris TG2492LG",
        },
    )

    return True


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ArrisConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up device tracker for the Arris TG2492LG component."""
    coordinator = entry.runtime_data

    tracked_devices: set[str] = set()

    def _async_add_new_entities() -> None:
        """Add entities for newly discovered devices."""
        entities = []
        for mac, device in coordinator.data.items():
            if mac not in tracked_devices:
                tracked_devices.add(mac)
                entities.append(ArrisScannerEntity(coordinator, mac, device))
        if entities:
            async_add_entities(entities)

    entry.async_on_unload(coordinator.async_add_listener(_async_add_new_entities))
    _async_add_new_entities()


class ArrisScannerEntity(CoordinatorEntity[ArrisCoordinator], ScannerEntity):
    """Representation of a device connected to an Arris TG2492LG router."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: ArrisCoordinator,
        mac: str,
        device: Device,
    ) -> None:
        """Initialize the scanner entity."""
        super().__init__(coordinator)
        self._mac = mac
        self._attr_mac_address = mac
        self._attr_hostname = device.hostname
        self._attr_ip_address = device.ip
        self._attr_name = device.hostname or mac

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
            self._attr_hostname = device.hostname
            self._attr_ip_address = device.ip
            self._attr_name = device.hostname or self._mac
        super()._handle_coordinator_update()
