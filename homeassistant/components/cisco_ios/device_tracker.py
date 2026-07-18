"""Support for Cisco IOS Routers."""

from typing import override

import voluptuous as vol

from homeassistant.components.device_tracker import (
    CONF_CONSIDER_HOME,
    DOMAIN as DEVICE_TRACKER_DOMAIN,
    PLATFORM_SCHEMA as DEVICE_TRACKER_PLATFORM_SCHEMA,
    AsyncSeeCallback,
    ScannerEntity,
)
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import (
    config_validation as cv,
    entity_registry as er,
    issue_registry as ir,
)
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DEFAULT_NAME, DOMAIN
from .coordinator import CiscoIOSConfigEntry, CiscoIOSDataUpdateCoordinator

PLATFORM_SCHEMA = vol.All(
    DEVICE_TRACKER_PLATFORM_SCHEMA.extend(
        {
            vol.Required(CONF_HOST): cv.string,
            vol.Required(CONF_USERNAME): cv.string,
            vol.Optional(CONF_PASSWORD, default=""): cv.string,
            vol.Optional(CONF_PORT): cv.port,
        }
    )
)


async def async_setup_scanner(
    hass: HomeAssistant,
    config: ConfigType,
    _async_see: AsyncSeeCallback,
    _discovery_info: DiscoveryInfoType | None = None,
) -> bool:
    """Set up the legacy Cisco IOS device tracker."""
    import_data = {
        CONF_HOST: config[CONF_HOST],
        CONF_USERNAME: config[CONF_USERNAME],
        CONF_PASSWORD: config[CONF_PASSWORD],
        CONF_CONSIDER_HOME: int(config[CONF_CONSIDER_HOME].total_seconds()),
    }
    if CONF_PORT in config:
        import_data[CONF_PORT] = config[CONF_PORT]

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
    config_entry: CiscoIOSConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up device tracker for Cisco IOS."""
    coordinator = config_entry.runtime_data
    tracked: set[str] = set()

    @callback
    def _async_update_devices() -> None:
        """Add new devices from the coordinator."""
        new_entities: list[CiscoIOSScannerEntity] = []
        for mac in coordinator.data:
            if mac not in tracked:
                tracked.add(mac)
                new_entities.append(CiscoIOSScannerEntity(coordinator, mac))
        if new_entities:
            async_add_entities(new_entities)

    # Restore previously registered devices, so a device that is away
    # during a restart is reported as not_home instead of disappearing.
    entity_registry = er.async_get(hass)
    unique_id_prefix = f"{config_entry.entry_id}_"
    restored_entities = [
        CiscoIOSScannerEntity(
            coordinator, registry_entry.unique_id.removeprefix(unique_id_prefix)
        )
        for registry_entry in er.async_entries_for_config_entry(
            entity_registry, config_entry.entry_id
        )
        if registry_entry.domain == DEVICE_TRACKER_DOMAIN
    ]
    tracked.update(entity.mac_address for entity in restored_entities)
    if restored_entities:
        async_add_entities(restored_entities)

    config_entry.async_on_unload(coordinator.async_add_listener(_async_update_devices))
    _async_update_devices()


class CiscoIOSScannerEntity(
    CoordinatorEntity[CiscoIOSDataUpdateCoordinator], ScannerEntity
):
    """Representation of a device connected to the Cisco IOS router."""

    def __init__(self, coordinator: CiscoIOSDataUpdateCoordinator, mac: str) -> None:
        """Initialize the tracked device."""
        super().__init__(coordinator)
        self._mac = mac
        self._attr_name = mac

    @property
    @override
    def unique_id(self) -> str:
        """Return the unique ID of the entity, scoped to the config entry.

        The same client can be seen by multiple routers, so the default
        MAC address based unique ID would collide between config entries.
        """
        return f"{self.coordinator.config_entry.entry_id}_{self._mac}"

    @property
    @override
    def is_connected(self) -> bool:
        """Return true if the device was recently seen by the router."""
        if (device := self.coordinator.data.get(self._mac)) is None:
            return False
        return device.connected

    @property
    @override
    def mac_address(self) -> str:
        """Return the MAC address of the device."""
        return self._mac

    @property
    @override
    def ip_address(self) -> str | None:
        """Return the IP address of the device."""
        if (device := self.coordinator.data.get(self._mac)) is None:
            return None
        return device.ip_address
