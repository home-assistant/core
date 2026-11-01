"""Support for BT Home Hub 5."""

from typing import override

from homeassistant.components.device_tracker import (
    DOMAIN as DEVICE_TRACKER_DOMAIN,
    AsyncSeeCallback,
    ScannerEntity,
    SourceType,
)
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import BTHomeHub5ConfigEntry, BTHomeHub5DataUpdateCoordinator


async def async_setup_scanner(
    hass: HomeAssistant,
    config: ConfigType,
    see: AsyncSeeCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> bool:
    """Import legacy YAML device tracker configuration."""
    async_create_issue(
        hass,
        DOMAIN,
        "deprecated_yaml_device_tracker",
        breaks_in_ha_version="2026.12.0",
        is_fixable=False,
        severity=IssueSeverity.WARNING,
        translation_key="deprecated_yaml",
        translation_placeholders={
            "domain": DOMAIN,
            "platform": DEVICE_TRACKER_DOMAIN,
        },
    )

    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "import"},
            data={CONF_HOST: config[CONF_HOST]},
        )
    )
    return True


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BTHomeHub5ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up device tracker entities from a config entry."""
    coordinator = entry.runtime_data
    known_macs: set[str] = set()

    def _update_entities() -> None:
        """Add newly discovered devices as scanner entities."""
        new_entities: list[BTHomeHub5ScannerEntity] = []
        for mac, name in coordinator.data.items():
            if mac not in known_macs:
                known_macs.add(mac)
                new_entities.append(BTHomeHub5ScannerEntity(coordinator, mac, name))
        if new_entities:
            async_add_entities(new_entities)

    _update_entities()
    entry.async_on_unload(coordinator.async_add_listener(_update_entities))


class BTHomeHub5ScannerEntity(
    CoordinatorEntity[BTHomeHub5DataUpdateCoordinator], ScannerEntity
):
    """Representation of a BT Home Hub 5 tracked device."""

    _attr_source_type = SourceType.ROUTER
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: BTHomeHub5DataUpdateCoordinator,
        mac: str,
        name: str,
    ) -> None:
        """Initialize the device tracker entity."""
        super().__init__(coordinator)
        self._mac = mac
        self._attr_unique_id = mac
        self._attr_name = name

    @property
    @override
    def mac_address(self) -> str:
        """Return the MAC address of the device."""
        return self._mac

    @property
    @override
    def hostname(self) -> str | None:
        """Return the hostname of the device."""
        return self._attr_name

    @property
    @override
    def is_connected(self) -> bool:
        """Return True if the device is currently connected to the router."""
        return self._mac in self.coordinator.data
