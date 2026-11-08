"""Support for Sony projectors via SDCP network control."""

from typing import Any, override

import probatio

from homeassistant.components.switch import (
    PLATFORM_SCHEMA as SWITCH_PLATFORM_SCHEMA,
    SwitchEntity,
)
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_validation as cv, issue_registry as ir
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    AddEntitiesCallback,
)
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DEFAULT_NAME, DOMAIN
from .coordinator import SonyProjectorConfigEntry, SonyProjectorCoordinator

PARALLEL_UPDATES = 1

BREAKS_IN_HA_VERSION = "2027.7.0"

PLATFORM_SCHEMA = SWITCH_PLATFORM_SCHEMA.extend(
    {
        probatio.Required(CONF_HOST): cv.string,
        probatio.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Import the YAML platform into a config entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={CONF_HOST: config[CONF_HOST], CONF_NAME: config[CONF_NAME]},
    )

    translation_placeholders = {"domain": DOMAIN, "integration_title": DEFAULT_NAME}

    if (
        result["type"] is FlowResultType.ABORT
        and result["reason"] != "already_configured"
    ):
        ir.async_create_issue(
            hass,
            DOMAIN,
            f"deprecated_yaml_import_issue_{result['reason']}",
            breaks_in_ha_version=BREAKS_IN_HA_VERSION,
            is_fixable=False,
            issue_domain=DOMAIN,
            severity=ir.IssueSeverity.ERROR,
            translation_key=f"deprecated_yaml_import_issue_{result['reason']}",
            translation_placeholders=translation_placeholders,
        )
        return

    ir.async_create_issue(
        hass,
        HOMEASSISTANT_DOMAIN,
        f"deprecated_yaml_{DOMAIN}",
        breaks_in_ha_version=BREAKS_IN_HA_VERSION,
        is_fixable=False,
        issue_domain=DOMAIN,
        severity=ir.IssueSeverity.WARNING,
        translation_key="deprecated_yaml",
        translation_placeholders=translation_placeholders,
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SonyProjectorConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the projector switch from a config entry."""
    async_add_entities([SonyProjectorSwitch(entry.runtime_data)])


class SonyProjectorSwitch(CoordinatorEntity[SonyProjectorCoordinator], SwitchEntity):
    """Represents a Sony projector as a switch."""

    _attr_has_entity_name = True
    _attr_name = None

    def __init__(self, coordinator: SonyProjectorCoordinator) -> None:
        """Initialize the switch."""
        super().__init__(coordinator)
        entry = coordinator.config_entry
        self._attr_unique_id = entry.entry_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            manufacturer="Sony",
            name=entry.title,
        )

    @property
    @override
    def is_on(self) -> bool:
        """Return whether the projector is on."""
        return self.coordinator.data

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the projector on."""
        await self.coordinator.async_set_power(True)

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the projector off."""
        await self.coordinator.async_set_power(False)
