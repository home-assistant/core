"""Synthetic ``light`` integration used inside the spike sandbox.

This is the integration the spike runs *inside* the sandbox HA instance.
It owns N real ``LightEntity`` instances and tracks their on/off state in
memory. The sandbox-side bridge in both Options A and B dispatches into
these entities via either a direct method call or a service call.
"""

from collections.abc import Iterable
from typing import Any

from homeassistant.components.light import ColorMode, LightEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback


class SyntheticLight(LightEntity):
    """A trivial on/off light kept entirely in memory."""

    _attr_should_poll = False
    _attr_supported_color_modes = {ColorMode.ONOFF}
    _attr_color_mode = ColorMode.ONOFF
    _attr_has_entity_name = False

    def __init__(self, unique_id: str, name: str) -> None:
        """Create the light with stable identifiers and an off state."""
        self._attr_unique_id = unique_id
        self._attr_name = name
        self._is_on = False

    @property
    def is_on(self) -> bool:
        """Return the cached on/off state."""
        return self._is_on

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the light on."""
        self._is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        self._is_on = False
        self.async_write_ha_state()


async def install_synthetic_lights(
    hass: HomeAssistant, count: int, prefix: str = "spike"
) -> list[SyntheticLight]:
    """Install ``count`` synthetic lights into ``hass`` under the ``light`` domain.

    Returns the entity instances so the caller can grab their ``entity_id``s
    for proxy registration.
    """
    component: EntityComponent[LightEntity] = hass.data["light"]
    lights = [
        SyntheticLight(f"{prefix}_{i}", f"{prefix.title()} Light {i}")
        for i in range(count)
    ]
    await component.async_add_entities(lights)
    return lights


async def add_lights_via_platform(
    hass: HomeAssistant,
    add_entities: AddConfigEntryEntitiesCallback,
    lights: Iterable[SyntheticLight],
) -> None:
    """Helper for tests that drive entity setup through a real platform."""
    add_entities(list(lights))
