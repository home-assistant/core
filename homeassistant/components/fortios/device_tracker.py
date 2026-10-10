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
from homeassistant.helpers import config_validation as cv, issue_registry as ir
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
    if (
        result["type"] is FlowResultType.ABORT
        and result["reason"] != "already_configured"
    ):
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
    ir.async_create_issue(
        hass,
        HOMEASSISTANT_DOMAIN,
        f"deprecated_yaml_{DOMAIN}",
        is_fixable=False,
        issue_domain=DOMAIN,
        severity=ir.IssueSeverity.WARNING,
        translation_key="deprecated_yaml",
        translation_placeholders={"domain": DOMAIN, "integration_title": "FortiOS"},
    )
    return True


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FortiOSConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create one entity per online client using the shared coordinator."""
    coordinator = entry.runtime_data
    known: set[str] = set()

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

    def __init__(self, coordinator: FortiOSCoordinator, mac: str) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._mac = mac
        self._attr_unique_id = f"{coordinator.client.serial}_{mac}"
        self._attr_name = coordinator.data[mac].hostname or mac.replace(":", "_")

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
        last_seen = self.coordinator.last_seen[self._mac]
        return (
            dt_util.utcnow() - last_seen
        ).total_seconds() < self.coordinator.consider_home or bool(
            (device := self.coordinator.data.get(self._mac)) and device.online
        )
