"""FortiOS device tracking and legacy YAML import."""

from typing import override

import probatio

from homeassistant.components.device_tracker import (
    CONF_CONSIDER_HOME,
    PLATFORM_SCHEMA as DEVICE_TRACKER_PLATFORM_SCHEMA,
    AsyncSeeCallback,
    ScannerEntity,
)
from homeassistant.components.homeassistant import DOMAIN as HOMEASSISTANT_DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import CONF_HOST, CONF_TOKEN, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import (
    config_validation as cv,
    entity_registry as er,
    issue_registry as ir,
)
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .coordinator import FortiOSConfigEntry, FortiOSCoordinator

PARALLEL_UPDATES = 0
PLATFORM_SCHEMA = DEVICE_TRACKER_PLATFORM_SCHEMA.extend(
    {
        probatio.Required(CONF_HOST): cv.string,
        probatio.Required(probatio.Secret(CONF_TOKEN)): cv.string,
        probatio.Optional(CONF_VERIFY_SSL, default=False): cv.boolean,
    }
)


async def async_setup_scanner(
    hass: HomeAssistant,
    config: ConfigType,
    async_see: AsyncSeeCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> bool:
    """Import an existing YAML configuration into a config entry."""
    data = {key: config[key] for key in (CONF_HOST, CONF_TOKEN, CONF_VERIFY_SSL)}
    data[CONF_CONSIDER_HOME] = config[CONF_CONSIDER_HOME].total_seconds()
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data=data
    )
    ir.async_delete_issue(hass, HOMEASSISTANT_DOMAIN, f"deprecated_yaml_{DOMAIN}")
    if (
        result["type"] is FlowResultType.ABORT
        and result["reason"] != "already_configured"
    ):
        ir.async_delete_issue(hass, DOMAIN, f"yaml_imported_{config[CONF_HOST]}")
        ir.async_create_issue(
            hass,
            DOMAIN,
            f"yaml_import_{config[CONF_HOST]}",
            is_fixable=False,
            severity=ir.IssueSeverity.ERROR,
            translation_key="yaml_import_failed",
            translation_placeholders={"host": config[CONF_HOST]},
        )
        return True
    ir.async_delete_issue(hass, DOMAIN, f"yaml_import_{config[CONF_HOST]}")
    ir.async_create_issue(
        hass,
        DOMAIN,
        f"yaml_imported_{config[CONF_HOST]}",
        is_fixable=False,
        severity=ir.IssueSeverity.WARNING,
        translation_key="yaml_imported",
        translation_placeholders={"host": config[CONF_HOST]},
    )
    return True


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FortiOSConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Restore registered clients and discover online clients."""
    coordinator = entry.runtime_data
    known: set[str] = set()
    registry = er.async_get(hass)
    prefix = f"{coordinator.client.serial}_"
    restored = []
    for entity in registry.entities.get_entries_for_config_entry_id(entry.entry_id):
        if (
            entity.domain != "device_tracker"
            or entity.platform != DOMAIN
            or not entity.unique_id.startswith(prefix)
        ):
            continue
        mac = entity.unique_id.removeprefix(prefix)
        known.add(mac)
        restored.append(FortiOSTracker(coordinator, mac, entity.original_name))
    async_add_entities(restored)

    @callback
    def async_discover_devices() -> None:
        """Discover clients when they first come online."""
        entities = []
        for mac, device in coordinator.data.items():
            if mac in known or not device.online:
                continue
            known.add(mac)
            entities.append(FortiOSTracker(coordinator, mac))
        async_add_entities(entities)

    async_discover_devices()
    entry.async_on_unload(coordinator.async_add_listener(async_discover_devices))


class FortiOSTracker(CoordinatorEntity[FortiOSCoordinator], ScannerEntity):
    """A FortiOS client whose state comes from one shared scan."""

    def __init__(
        self, coordinator: FortiOSCoordinator, mac: str, name: str | None = None
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._mac = mac
        self._attr_unique_id = f"{coordinator.client.serial}_{mac}"
        device = coordinator.data.get(mac)
        self._attr_name = (
            (device.hostname if device else None) or name or mac.replace(":", "_")
        )

    @property
    @override
    def unique_id(self) -> str | None:
        """Identify this client within its FortiGate device."""
        return self._attr_unique_id

    @property
    @override
    def mac_address(self) -> str:
        """Return the MAC address."""
        return self._mac

    @property
    @override
    def hostname(self) -> str | None:
        """Return the most recently reported hostname."""
        if device := self.coordinator.data.get(self._mac):
            return device.hostname
        return None

    @property
    @override
    def is_connected(self) -> bool:
        """Preserve the configured consider-home grace period."""
        last_seen = self.coordinator.last_seen.get(self._mac)
        return bool(
            last_seen is not None
            and (dt_util.utcnow() - last_seen).total_seconds()
            < self.coordinator.consider_home
        ) or bool((device := self.coordinator.data.get(self._mac)) and device.online)
