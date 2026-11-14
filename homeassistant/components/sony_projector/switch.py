"""Support for Sony projectors via SDCP network control."""

import logging
from typing import Any, override

import probatio
import pysdcp

from homeassistant.components.switch import (
    PLATFORM_SCHEMA as SWITCH_PLATFORM_SCHEMA,
    SwitchEntity,
)
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_ENTITY_NAMESPACE, CONF_HOST, CONF_NAME
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_validation as cv, issue_registry as ir
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    AddEntitiesCallback,
)
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import DEFAULT_NAME, DOMAIN

_LOGGER = logging.getLogger(__name__)

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
    # The entity ID comes from the entry title, so the namespace keeps its prefix.
    name = " ".join(
        filter(None, [config.get(CONF_ENTITY_NAMESPACE), config[CONF_NAME]])
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={CONF_HOST: config[CONF_HOST], CONF_NAME: name},
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
        # The shared warning says to remove all YAML, which would drop this one.
        ir.async_delete_issue(hass, HOMEASSISTANT_DOMAIN, f"deprecated_yaml_{DOMAIN}")
        return

    # Each YAML block imports on its own, so another one may already have failed.
    if any(
        issue.active
        and issue.domain == DOMAIN
        and issue.issue_id.startswith("deprecated_yaml_import_issue_")
        for issue in ir.async_get(hass).issues.values()
    ):
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
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the projector switch from a config entry."""
    async_add_entities(
        [SonyProjector(pysdcp.Projector(entry.data[CONF_HOST]), entry)], True
    )


class SonyProjector(SwitchEntity):
    """Represents a Sony Projector as a switch."""

    _attr_has_entity_name = True
    _attr_name = None

    def __init__(self, sdcp_connection: pysdcp.Projector, entry: ConfigEntry) -> None:
        """Init of the Sony projector."""
        self._sdcp = sdcp_connection
        self._attr_available = False
        self._attr_unique_id = entry.entry_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            manufacturer="Sony",
            name=entry.title,
        )

    def update(self) -> None:
        """Get the latest state from the projector."""
        try:
            self._attr_is_on = self._sdcp.get_power()
            self._attr_available = True
        except ConnectionRefusedError:
            _LOGGER.error("Projector connection refused")
            self._attr_available = False

    @override
    def turn_on(self, **kwargs: Any) -> None:
        """Turn the projector on."""
        _LOGGER.debug("Powering on projector '%s'", self.name)
        if self._sdcp.set_power(True):
            _LOGGER.debug("Powered on successfully")
            self._attr_is_on = True
        else:
            _LOGGER.error("Power on command was not successful")

    @override
    def turn_off(self, **kwargs: Any) -> None:
        """Turn the projector off."""
        _LOGGER.debug("Powering off projector '%s'", self.name)
        if self._sdcp.set_power(False):
            _LOGGER.debug("Powered off successfully")
            self._attr_is_on = False
        else:
            _LOGGER.error("Power off command was not successful")
