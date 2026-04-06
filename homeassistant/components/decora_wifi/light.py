"""Interfaces with the myLeviton API for Decora Smart WiFi products."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

import voluptuous as vol

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_TRANSITION,
    PLATFORM_SCHEMA as LIGHT_PLATFORM_SCHEMA,
    ColorMode,
    LightEntity,
    LightEntityFeature,
)
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_validation as cv, issue_registry as ir
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    AddEntitiesCallback,
)
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import Throttle

from . import DecoraWifiConfigEntry
from .const import DOMAIN, INTEGRATION_TITLE

_LOGGER = logging.getLogger(__name__)

# Validation of the user's configuration
PLATFORM_SCHEMA = LIGHT_PLATFORM_SCHEMA.extend(
    {vol.Required(CONF_USERNAME): cv.string, vol.Required(CONF_PASSWORD): cv.string}
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Decora WiFi platform from YAML (deprecated)."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data=config,
    )

    if (
        result.get("type") is FlowResultType.ABORT
        and (reason := result.get("reason")) != "already_configured"
    ):
        ir.async_create_issue(
            hass,
            DOMAIN,
            f"deprecated_yaml_import_issue_{reason}",
            breaks_in_ha_version="2026.10.0",
            is_fixable=False,
            issue_domain=DOMAIN,
            severity=ir.IssueSeverity.WARNING,
            translation_key=f"deprecated_yaml_import_issue_{reason}",
            translation_placeholders={
                "domain": DOMAIN,
                "integration_title": INTEGRATION_TITLE,
            },
        )
        return

    ir.async_create_issue(
        hass,
        HOMEASSISTANT_DOMAIN,
        f"deprecated_yaml_{DOMAIN}",
        breaks_in_ha_version="2026.10.0",
        is_fixable=False,
        issue_domain=DOMAIN,
        severity=ir.IssueSeverity.WARNING,
        translation_key="deprecated_yaml",
        translation_placeholders={
            "domain": DOMAIN,
            "integration_title": INTEGRATION_TITLE,
        },
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DecoraWifiConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Decora WiFi lights from a config entry."""
    async_add_entities(
        DecoraWifiLight(switch) for switch in entry.runtime_data.switches
    )


class DecoraWifiLight(LightEntity):
    """Representation of a Decora WiFi switch."""

    def __init__(self, switch):
        """Initialize the switch."""
        self._switch = switch
        self._attr_unique_id = switch.serial

    @property
    def color_mode(self) -> ColorMode:
        """Return the color mode of the light."""
        if self._switch.canSetLevel:
            return ColorMode.BRIGHTNESS
        return ColorMode.ONOFF

    @property
    def supported_color_modes(self) -> set[ColorMode]:
        """Flag supported color modes."""
        return {self.color_mode}

    @property
    def supported_features(self) -> LightEntityFeature:
        """Return supported features."""
        if self._switch.canSetLevel:
            return LightEntityFeature.TRANSITION
        return LightEntityFeature(0)

    @property
    def name(self):
        """Return the display name of this switch."""
        return self._switch.name

    @property
    def unique_id(self):
        """Return the ID of this light."""
        return self._switch.serial

    @property
    def brightness(self) -> int:
        """Return the brightness of the dimmer switch."""
        return int(self._switch.brightness * 255 / 100)

    @property
    def is_on(self) -> bool:
        """Return true if switch is on."""
        return self._switch.power == "ON"

    def turn_on(self, **kwargs: Any) -> None:
        """Instruct the switch to turn on & adjust brightness."""
        attribs: dict[str, Any] = {"power": "ON"}

        if ATTR_BRIGHTNESS in kwargs:
            min_level = self._switch.data.get("minLevel", 0)
            max_level = self._switch.data.get("maxLevel", 100)
            brightness = int(kwargs[ATTR_BRIGHTNESS] * max_level / 255)
            brightness = max(brightness, min_level)
            attribs["brightness"] = brightness

        if ATTR_TRANSITION in kwargs:
            transition = int(kwargs[ATTR_TRANSITION])
            attribs["fadeOnTime"] = attribs["fadeOffTime"] = transition

        try:
            self._switch.update_attributes(attribs)
        except ValueError:
            _LOGGER.error("Failed to turn on myLeviton switch")

    def turn_off(self, **kwargs: Any) -> None:
        """Instruct the switch to turn off."""
        attribs = {"power": "OFF"}
        try:
            self._switch.update_attributes(attribs)
        except ValueError:
            _LOGGER.error("Failed to turn off myLeviton switch")

    @Throttle(timedelta(seconds=30))
    def update(self) -> None:
        """Fetch new state data for this switch."""
        try:
            self._switch.refresh()
        except ValueError:
            _LOGGER.error("Failed to update myLeviton switch data")
