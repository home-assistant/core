"""The orvibo component."""

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
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_SWITCHES
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

from .const import DOMAIN
from .util import S20ConfigEntry

_LOGGER = logging.getLogger(__name__)


PARALLEL_UPDATES = 1

PLATFORM_SCHEMA = SWITCH_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_SWITCHES, default=[]): vol.All(
            cv.ensure_list,
            [
                {
                    vol.Required(CONF_HOST): cv.string,
                    vol.Optional(CONF_MAC): cv.string,
                }
            ],
        )
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities_callback: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the integration from configuration.yaml."""
    for switch in config.get("switches", []):
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
                f"yaml_deprecation_import_issue_{switch.get('mac').replace(':', '').lower()}",
                breaks_in_ha_version="2026.5.0",
                is_fixable=False,
                issue_domain=DOMAIN,
                severity=ir.IssueSeverity.WARNING,
                translation_key="yaml_deprecation_import_issue",
                translation_placeholders={
                    "host": switch.get("host"),
                    "mac": switch.get("mac"),
                },
            )
            return

        ir.async_create_issue(
            hass,
            DOMAIN,
            f"eyaml_deprecation_{switch.get('mac').replace(':', '').lower()}",
            breaks_in_ha_version="2026.5.0",
            is_fixable=False,
            is_persistent=True,
            severity=ir.IssueSeverity.WARNING,
            translation_key="yaml_deprecation",
            translation_placeholders={
                "host": switch.get("host"),
                "mac": switch.get("mac"),
            },
        )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: S20ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Setup Entry."""
    async_add_entities(
        [
            S20Switch(
                entry.title,
                entry.data[CONF_HOST],
                entry.data[CONF_MAC],
                entry.runtime_data.s20,
            )
        ]
    )


class S20Switch(SwitchEntity):
    """Representation of an S20 switch."""

    _attr_has_entity_name = True

    def __init__(self, name: str, host: str, mac: str, s20: S20) -> None:
        """Initialize the S20 device."""

        self._attr_name = name
        self._attr_is_on = False
        self._host = host
        self._mac = mac
        self._s20 = s20
        self._attr_unique_id = self._mac
        self._attr_device_info = DeviceInfo(
            identifiers={
                # Serial numbers are unique identifiers within a specific domain
                (DOMAIN, self._attr_unique_id)
            },
            name=self._attr_name,
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
                translation_placeholders={"name": str(self._attr_name)},
            ) from err

    def turn_off(self, **kwargs: Any) -> None:
        """Turn the device off."""
        try:
            self._s20.on = False
        except S20Exception as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="turn_off_error",
                translation_placeholders={"name": str(self._attr_name)},
            ) from err

    def update(self) -> None:
        """Update device state."""
        try:
            self._attr_is_on = self._s20.on
        except S20Exception as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="update_error",
                translation_placeholders={"name": str(self._attr_name)},
            ) from err
