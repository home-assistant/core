"""Light platform Niko Home Control."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

import voluptuous as vol

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    PLATFORM_SCHEMA as LIGHT_PLATFORM_SCHEMA,
    ColorMode,
    LightEntity,
    brightness_supported,
)
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import CONF_HOST
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import issue_registry as ir
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import NikoHomeControlConfigEntry
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)
SCAN_INTERVAL = timedelta(seconds=30)

# delete after 2025.7.0
PLATFORM_SCHEMA = LIGHT_PLATFORM_SCHEMA.extend({vol.Required(CONF_HOST): cv.string})


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Niko Home Control light platform."""
    # Start import flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data=config
    )
    if (
        result.get("type") == FlowResultType.ABORT
        and result.get("reason") != "already_configured"
    ):
        ir.async_create_issue(
            hass,
            DOMAIN,
            f"deprecated_yaml_import_issue_{result['reason']}",
            breaks_in_ha_version="2025.7.0",
            is_fixable=False,
            issue_domain=DOMAIN,
            severity=ir.IssueSeverity.WARNING,
            translation_key=f"deprecated_yaml_import_issue_{result['reason']}",
            translation_placeholders={
                "domain": DOMAIN,
                "integration_title": "Niko Home Control",
            },
        )
        return

    ir.async_create_issue(
        hass,
        HOMEASSISTANT_DOMAIN,
        f"deprecated_yaml_{DOMAIN}",
        breaks_in_ha_version="2025.7.0",
        is_fixable=False,
        issue_domain=DOMAIN,
        severity=ir.IssueSeverity.WARNING,
        translation_key="deprecated_yaml",
        translation_placeholders={
            "domain": DOMAIN,
            "integration_title": "Niko Home Control",
        },
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NikoHomeControlConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Niko Home Control light entry."""
    niko_data = entry.runtime_data

    async_add_entities(
        NikoHomeControlLight(light, niko_data) for light in niko_data.nhc.list_actions()
    )


class NikoHomeControlLight(LightEntity):
    """Representation of an Niko Light."""

    def __init__(self, light, data):
        """Set up the Niko Home Control light platform."""
        self._data = data
        self._light = light
        self._attr_unique_id = f"light-{light.id}"
        self._attr_name = light.name
        self._attr_is_on = light.is_on
        self._attr_color_mode = ColorMode.ONOFF
        self._attr_supported_color_modes = {ColorMode.ONOFF}
        if light._state["type"] == 2:  # noqa: SLF001
            self._attr_color_mode = ColorMode.BRIGHTNESS
            self._attr_supported_color_modes = {ColorMode.BRIGHTNESS}

    def turn_on(self, **kwargs: Any) -> None:
        """Instruct the light to turn on."""
        _LOGGER.debug("Turn on: %s", self.name)
        self._light.turn_on(kwargs.get(ATTR_BRIGHTNESS, 255) / 2.55)

    def turn_off(self, **kwargs: Any) -> None:
        """Instruct the light to turn off."""
        _LOGGER.debug("Turn off: %s", self.name)
        self._light.turn_off()

    async def async_update(self) -> None:
        """Get the latest data from NikoHomeControl API."""
        await self._data.async_update()
        state = self._data.get_state(self._light.id)
        self._attr_is_on = state != 0
        if brightness_supported(self.supported_color_modes):
            self._attr_brightness = state * 2.55
