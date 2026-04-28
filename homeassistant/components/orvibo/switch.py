"""Switch platform for the Orvibo integration."""

from __future__ import annotations

import logging
from typing import Any

from orvibo.s20 import S20, S20Exception
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.switch import (
    PLATFORM_SCHEMA as SWITCH_PLATFORM_SCHEMA,
    SwitchEntity,
)
from homeassistant.const import (
    CONF_DISCOVERY,
    CONF_HOST,
    CONF_MAC,
    CONF_NAME,
    CONF_SWITCHES,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, issue_registry as ir
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    AddEntitiesCallback,
)
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import DEFAULT_NAME, DOMAIN
from .models import S20ConfigEntry

_LOGGER = logging.getLogger(__name__)

DEFAULT_DISCOVERY = False

# Library is not thread safe and uses global variables, so we limit to 1 update at a time
PARALLEL_UPDATES = 1

PLATFORM_SCHEMA = SWITCH_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_SWITCHES, default=[]): vol.All(
            cv.ensure_list,
            [
                {
                    vol.Required(CONF_HOST): cv.string,
                    vol.Optional(CONF_MAC): cv.string,
                    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
                }
            ],
        ),
        vol.Optional(CONF_DISCOVERY, default=DEFAULT_DISCOVERY): cv.boolean,
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities_callback: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the integration from configuration.yaml."""
    for switch in config.get(CONF_SWITCHES, []):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data=switch,
        )

        if (
            result.get("type") is FlowResultType.ABORT
            and result.get("reason") != "already_configured"
        ):
            ir.async_create_issue(
                hass,
                DOMAIN,
                f"yaml_deprecation_import_issue_{switch.get('host')}_{(switch.get('mac') or 'unknown_mac').replace(':', '').lower()}",
                breaks_in_ha_version="2026.9.0",
                is_fixable=False,
                is_persistent=False,
                issue_domain=DOMAIN,
                severity=ir.IssueSeverity.WARNING,
                translation_key="yaml_deprecation_import_issue",
                translation_placeholders={
                    "reason": str(result.get("reason")),
                    "host": switch.get("host"),
                    "mac": switch.get("mac", ""),
                },
            )
            continue

        ir.async_create_issue(
            hass,
            DOMAIN,
            f"yaml_deprecation_{switch.get('host')}_{(switch.get('mac') or 'unknown_mac').replace(':', '').lower()}",
            breaks_in_ha_version="2026.9.0",
            is_fixable=False,
            is_persistent=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key="yaml_deprecation",
            translation_placeholders={
                "host": switch.get("host"),
                "mac": switch.get("mac") or "Unknown MAC",
            },
        )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: S20ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up orvibo from a config entry."""
    async_add_entities(
        [
            S20Switch(
                entry.title,
                entry.data[CONF_HOST],
                entry.data[CONF_MAC],
                entry.runtime_data,
            )
        ]
    )


class S20Switch(SwitchEntity):
    """Representation of an S20 switch."""

    _attr_has_entity_name = True

    def __init__(self, name: str, host: str, mac: str, s20: S20) -> None:
        """Initialize the S20 device."""

        self._attr_is_on = False
        self._host = host
        self._mac = mac
        self._s20 = s20
        self._attr_unique_id = self._mac
        self._name = name
        self._attr_name = None
        self._attr_device_info = DeviceInfo(
            identifiers={
                # MAC addresses are used as unique identifiers within this domain
                (DOMAIN, self._attr_unique_id)
            },
            name=name,
            manufacturer="Orvibo",
            model="S20",
            connections={(CONNECTION_NETWORK_MAC, self._mac)},
        )

    def turn_on(self, **kwargs: Any) -> None:
        """Turn the device on."""
        try:
            self._s20.on = True
        except S20Exception as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="turn_on_error",
                translation_placeholders={"name": self._name},
            ) from err

    def turn_off(self, **kwargs: Any) -> None:
        """Turn the device off."""
        try:
            self._s20.on = False
        except S20Exception as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="turn_off_error",
                translation_placeholders={"name": self._name},
            ) from err

    def update(self) -> None:
        """Update device state."""
        try:
            self._attr_is_on = self._s20.on

            # If the device was previously offline, let the user know it's back!
            if not self._attr_available:
                _LOGGER.info("Orvibo switch %s reconnected", self._name)
                self._attr_available = True

        except S20Exception as err:
            # Only log the error if this is the FIRST time it failed
            if self._attr_available:
                _LOGGER.info(
                    "Error communicating with Orvibo switch %s: %s", self._name, err
                )
                self._attr_available = False
