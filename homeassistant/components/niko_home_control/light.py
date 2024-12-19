"""Light platform Niko Home Control."""

from __future__ import annotations

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
    controller = entry.runtime_data

    entities = []
    for light in controller.lights:
        entity = NikoHomeControlLight(light, controller, entry)
        controller.register_callback(entity.async_update_callback)
        entities.append(entity)
    return async_add_entities(entities)


class NikoHomeControlLight(LightEntity):
    """Representation of an Niko Light."""

    def __init__(self, action, controller, entry: NikoHomeControlConfigEntry) -> None:
        """Set up the Niko Home Control light platform."""
        self._controller = controller
        self._action = action
        self._attr_unique_id = f"{entry.entry_id}.niko_home_control_{action.id}"
        self._attr_name = action.name
        self._attr_is_on = action.is_on
        self._attr_color_mode = ColorMode.ONOFF
        self._attr_supported_color_modes = {ColorMode.ONOFF}
        if action.type == 2:
            self._attr_color_mode = ColorMode.BRIGHTNESS
            self._attr_supported_color_modes = {ColorMode.BRIGHTNESS}

    @property
    def action_id(self):
        """Return action id."""
        return self._action.id

    def turn_on(self, **kwargs: Any) -> None:
        """Instruct the light to turn on."""
        self._action.turn_on(kwargs.get(ATTR_BRIGHTNESS, 255) / 2.55)

    def turn_off(self, **kwargs: Any) -> None:
        """Instruct the light to turn off."""
        self._action.turn_off()

    async def async_update_callback(self, action_id: str, state) -> None:
        """Handle updates from the controller."""
        if action_id == self._action.id:
            self._action.update_state(state)
            self._attr_is_on = state > 0
            if brightness_supported(self.supported_color_modes):
                self._attr_brightness = state * 2.55
            self.async_write_ha_state()
