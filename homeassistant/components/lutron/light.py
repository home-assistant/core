"""Support for Lutron lights."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from pylutron import Output

from homeassistant.components.automation import automations_with_entity
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_FLASH,
    ATTR_TRANSITION,
    ColorMode,
    LightEntity,
    LightEntityFeature,
)
from homeassistant.components.script import scripts_with_entity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.issue_registry import (
    IssueSeverity,
    async_create_issue,
    create_issue,
)

from . import DOMAIN, LutronData
from .entity import LutronDevice

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Lutron light platform.

    Adds dimmers from the Main Repeater associated with the config_entry as
    light entities.
    """
    ent_reg = er.async_get(hass)
    entry_data: LutronData = hass.data[DOMAIN][config_entry.entry_id]
    lights = []

    for area_name, device in entry_data.lights:
        if device.type == "CEILING_FAN_TYPE":
            # If this is a fan, check to see if this entity already exists.
            # If not, do not create a new one.
            entity_id = ent_reg.async_get_entity_id(
                Platform.LIGHT,
                DOMAIN,
                f"{entry_data.client.guid}_{device.uuid}",
            )
            if entity_id:
                entity_entry = ent_reg.async_get(entity_id)
                assert entity_entry
                if entity_entry.disabled:
                    # If the entity exists and is disabled then we want to remove
                    # the entity so that the user is using the new fan entity instead.
                    ent_reg.async_remove(entity_id)
                else:
                    lights.append(LutronLight(area_name, device, entry_data.client))
                    entity_automations = automations_with_entity(hass, entity_id)
                    entity_scripts = scripts_with_entity(hass, entity_id)
                    for item in entity_automations + entity_scripts:
                        async_create_issue(
                            hass,
                            DOMAIN,
                            f"deprecated_light_fan_{entity_id}_{item}",
                            breaks_in_ha_version="2024.8.0",
                            is_fixable=True,
                            is_persistent=True,
                            severity=IssueSeverity.WARNING,
                            translation_key="deprecated_light_fan_entity",
                            translation_placeholders={
                                "entity": entity_id,
                                "info": item,
                            },
                        )
        else:
            lights.append(LutronLight(area_name, device, entry_data.client))

    async_add_entities(
        lights,
        True,
    )


def to_lutron_level(level):
    """Convert the given Home Assistant light level (0-255) to Lutron (0.0-100.0)."""
    return float((level * 100) / 255)


def to_hass_level(level):
    """Convert the given Lutron (0.0-100.0) light level to Home Assistant (0-255)."""
    return int((level * 255) / 100)


class LutronLight(LutronDevice, LightEntity):
    """Representation of a Lutron Light, including dimmable."""

    _attr_color_mode = ColorMode.BRIGHTNESS
    _attr_supported_color_modes = {ColorMode.BRIGHTNESS}
    _attr_supported_features = LightEntityFeature.TRANSITION | LightEntityFeature.FLASH
    _lutron_device: Output
    _prev_brightness: int | None = None
    _attr_name = None

    def __init__(self, area_name, lutron_device, controller) -> None:
        """Initialize the light."""
        super().__init__(area_name, lutron_device, controller)
        self._is_fan = lutron_device.type == "CEILING_FAN_TYPE"

    def turn_on(self, **kwargs: Any) -> None:
        """Turn the light on."""
        if self._is_fan:
            create_issue(
                self.hass,
                DOMAIN,
                "deprecated_light_fan_on",
                breaks_in_ha_version="2024.8.0",
                is_fixable=True,
                is_persistent=True,
                severity=IssueSeverity.WARNING,
                translation_key="deprecated_light_fan_on",
            )
        if flash := kwargs.get(ATTR_FLASH):
            self._lutron_device.flash(0.5 if flash == "short" else 1.5)
        else:
            if ATTR_BRIGHTNESS in kwargs and self._lutron_device.is_dimmable:
                brightness = kwargs[ATTR_BRIGHTNESS]
            elif self._prev_brightness == 0:
                brightness = 255 / 2
            else:
                brightness = self._prev_brightness
            self._prev_brightness = brightness
            args = {"new_level": to_lutron_level(brightness)}
            if ATTR_TRANSITION in kwargs:
                args["fade_time_seconds"] = kwargs[ATTR_TRANSITION]
            self._lutron_device.set_level(**args)

    def turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        if self._is_fan:
            create_issue(
                self.hass,
                DOMAIN,
                "deprecated_light_fan_off",
                breaks_in_ha_version="2024.8.0",
                is_fixable=True,
                is_persistent=True,
                severity=IssueSeverity.WARNING,
                translation_key="deprecated_light_fan_off",
            )
        args = {"new_level": 0}
        if ATTR_TRANSITION in kwargs:
            args["fade_time_seconds"] = kwargs[ATTR_TRANSITION]
        self._lutron_device.set_level(**args)

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Return the state attributes."""
        return {"lutron_integration_id": self._lutron_device.id}

    def _request_state(self) -> None:
        """Request the state from the device."""
        _ = self._lutron_device.level

    def _update_attrs(self) -> None:
        """Update the state attributes."""
        level = self._lutron_device.last_level()
        self._attr_is_on = level > 0
        hass_level = to_hass_level(level)
        self._attr_brightness = hass_level
        if self._prev_brightness is None or hass_level != 0:
            self._prev_brightness = hass_level
