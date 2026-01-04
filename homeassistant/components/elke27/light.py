"""Lights for Elke27 outputs."""

from __future__ import annotations

import logging
from typing import Any, Iterable

from elke27_lib.errors import Elke27PinRequiredError

from homeassistant.components.light import ColorMode, LightEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .entity import device_info_for_entry, unique_base
from .hub import Elke27Hub

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Elke27 output lights from a config entry."""
    hub: Elke27Hub = hass.data[DOMAIN][entry.entry_id]
    known_ids: set[int] = set()

    @callback
    def _async_add_outputs() -> None:
        snapshot = hub.snapshot
        if snapshot is None:
            return
        entities: list[Elke27OutputLight] = []
        for output in _iter_outputs(snapshot):
            output_id = getattr(output, "output_id", None)
            if not isinstance(output_id, int):
                continue
            if output_id in known_ids:
                continue
            known_ids.add(output_id)
            entities.append(Elke27OutputLight(hub, entry, output_id, output))
        if entities:
            async_add_entities(entities)

    _async_add_outputs()
    entry.async_on_unload(hub.async_add_output_listener(_async_add_outputs))


class Elke27OutputLight(LightEntity):
    """Representation of an Elke27 output."""

    _attr_color_mode = ColorMode.ONOFF
    _attr_supported_color_modes = {ColorMode.ONOFF}
    _attr_has_entity_name = True
    _attr_translation_key = "output"

    def __init__(
        self,
        hub: Elke27Hub,
        entry: ConfigEntry,
        output_id: int,
        output: Any,
    ) -> None:
        """Initialize the output entity."""
        self._hub = hub
        self._entry = entry
        self._output_id = output_id
        self._attr_name = getattr(output, "name", None) or f"Output {output_id}"
        self._attr_unique_id = f"{unique_base(hub, entry)}_output_{output_id}"
        self._attr_device_info = device_info_for_entry(hub, entry)
        self._missing_logged = False

    async def async_added_to_hass(self) -> None:
        """Register for hub updates."""
        self.async_on_remove(self._hub.async_add_output_listener(self._handle_update))

    @callback
    def _handle_update(self) -> None:
        """Write updated state."""
        self.async_write_ha_state()

    @property
    def is_on(self) -> bool | None:
        """Return if the output is on."""
        output = _get_output(self._hub.snapshot, self._output_id)
        if output is None:
            self._log_missing()
            return None
        is_on = getattr(output, "state", None)
        return bool(is_on) if isinstance(is_on, bool) else None

    @property
    def available(self) -> bool:
        """Return if the entity is available."""
        return (
            self._hub.is_ready
            and _get_output(self._hub.snapshot, self._output_id) is not None
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the output on if supported by the client."""
        try:
            await self._hub.async_set_output(self._output_id, True)
        except Elke27PinRequiredError as err:
            raise HomeAssistantError("PIN required to perform this action.") from err

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the output off if supported by the client."""
        try:
            await self._hub.async_set_output(self._output_id, False)
        except Elke27PinRequiredError as err:
            raise HomeAssistantError("PIN required to perform this action.") from err

    def _log_missing(self) -> None:
        """Log when the output snapshot is missing."""
        if self._missing_logged:
            return
        self._missing_logged = True
        _LOGGER.debug("Output %s missing from snapshot", self._output_id)


def _iter_outputs(snapshot: Any) -> Iterable[Any]:
    outputs = getattr(snapshot, "outputs", None)
    if outputs is None:
        return []
    if isinstance(outputs, dict):
        return list(outputs.values())
    if isinstance(outputs, list | tuple):
        return outputs
    return []


def _get_output(snapshot: Any, output_id: int) -> Any | None:
    for output in _iter_outputs(snapshot):
        if getattr(output, "output_id", None) == output_id:
            return output
    return None
