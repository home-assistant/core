"""Support for Verizon FiOS Quantum Gateway as device tracker using Coordinator."""

import logging
from typing import override

from propcache.api import cached_property
import voluptuous as vol

from homeassistant.components.device_tracker import (
    PLATFORM_SCHEMA as DEVICE_TRACKER_PLATFORM_SCHEMA,
    AsyncSeeCallback,
    ScannerEntity,
)
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_SSL
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_validation as cv, issue_registry as ir
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DEFAULT_HOST, DOMAIN
from .coordinator import QuantumGatewayConfigEntry, QuantumGatewayDataUpdateCoordinator

PLATFORM_SCHEMA = DEVICE_TRACKER_PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_HOST, default=DEFAULT_HOST): cv.string,
        vol.Optional(CONF_SSL, default=True): cv.boolean,
        vol.Required(CONF_PASSWORD): cv.string,
    }
)

LOGGER = logging.getLogger(__name__)


async def async_setup_scanner(
    hass: HomeAssistant,
    config: ConfigType,
    _async_see: AsyncSeeCallback,
    _discovery_info: DiscoveryInfoType | None,
) -> bool:
    """Set up the legacy Quantum Gateway device tracker."""
    import_data = {
        CONF_HOST: config[CONF_HOST],
        CONF_SSL: config[CONF_SSL],
        CONF_PASSWORD: config[CONF_PASSWORD],
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
            translation_placeholders={"host": import_data[CONF_HOST]},
        )

        return False

    if result["type"] is FlowResultType.ABORT and result["reason"] == "invalid_auth":
        ir.async_create_issue(
            hass,
            DOMAIN,
            "yaml_import_invalid_auth",
            is_fixable=False,
            issue_domain=DOMAIN,
            severity=ir.IssueSeverity.ERROR,
            translation_key="yaml_import_invalid_auth",
            translation_placeholders={"host": import_data[CONF_HOST]},
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
            "integration_title": "Quantum Gateway",
        },
    )

    return True


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: QuantumGatewayConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up device tracker for Quantum Gateway."""
    coordinator = config_entry.runtime_data
    tracked: set[str] = set()

    @callback
    def _async_update_devices() -> None:
        """Add new devices from the coordinator."""
        new_entities = []
        for mac in coordinator.data:
            if mac not in tracked:
                tracked.add(mac)
                new_entities.append(QuantumGatewayScannerEntity(coordinator, mac))

        if new_entities:
            async_add_entities(new_entities)

    config_entry.async_on_unload(coordinator.async_add_listener(_async_update_devices))
    _async_update_devices()


class QuantumGatewayScannerEntity(
    CoordinatorEntity[QuantumGatewayDataUpdateCoordinator], ScannerEntity
):
    """Representation of a device connected to a Quantum Gateway."""

    _attr_mac_address: str

    def __init__(
        self, coordinator: QuantumGatewayDataUpdateCoordinator, mac: str
    ) -> None:
        """Initialize the tracked device."""
        super().__init__(coordinator)
        self._attr_mac_address = mac
        self._attr_name = self.hostname

    @override
    @property
    def is_connected(self) -> bool:
        """Return true if the device is connected to the Quantum Gateway."""
        return self._attr_mac_address in self.coordinator.data

    @override
    @cached_property
    def hostname(self) -> str | None:
        """Return hostname of the device."""
        return self.coordinator.data.get(self._attr_mac_address)
