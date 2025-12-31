"""Lights for Elke27 outputs."""

from __future__ import annotations

from typing import Any

from homeassistant.components.light import ColorMode, LightEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .entity import device_info_for_entry, unique_base
from .hub import Elke27Hub


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Elke27 output lights from a config entry."""
    hub: Elke27Hub = hass.data[DOMAIN][entry.entry_id]
    outputs = _iter_outputs(hub.outputs)
    async_add_entities(
        Elke27OutputLight(hub, entry, output_id, output)
        for output_id, output in outputs
    )


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
        output: dict[str, Any],
    ) -> None:
        """Initialize the output entity."""
        self._hub = hub
        self._entry = entry
        self._output_id = output_id
        self._attr_name = output.get("name") or f"Output {output_id}"
        self._attr_unique_id = f"{unique_base(hub, entry)}_output_{output_id}"
        self._attr_device_info = device_info_for_entry(hub, entry)

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
        output = _get_output(self._hub.outputs, self._output_id)
        if not output:
            return None
        if isinstance(output.get("is_on"), bool):
            return output["is_on"]
        if isinstance(output.get("state"), bool):
            return output["state"]
        if isinstance(output.get("on"), bool):
            return output["on"]
        state = output.get("status")
        if state is None:
            return None
        normalized = str(state).lower().replace(" ", "_")
        if normalized in {"on", "enabled", "active", "true"}:
            return True
        if normalized in {"off", "disabled", "inactive", "false"}:
            return False
        return None

    @property
    def available(self) -> bool:
        """Return if the entity is available."""
        return (
            self._hub.is_ready
            and _get_output(self._hub.outputs, self._output_id) is not None
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the output on if supported by the client."""
        await self._hub.async_set_output(self._output_id, True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the output off if supported by the client."""
        await self._hub.async_set_output(self._output_id, False)


def _iter_outputs(snapshot: Any) -> list[tuple[int, dict[str, Any]]]:
    if isinstance(snapshot, dict):
        outputs: list[tuple[int, dict[str, Any]]] = []
        for key, output in snapshot.items():
            if not isinstance(output, dict):
                continue
            output_id = _coerce_output_id(key, output)
            if output_id is None:
                continue
            outputs.append((output_id, output))
        return outputs
    if isinstance(snapshot, list | tuple):
        return [
            (index + 1, output)
            for index, output in enumerate(snapshot)
            if isinstance(output, dict)
        ]
    return []


def _coerce_output_id(key: Any, output: dict[str, Any]) -> int | None:
    for candidate in (output.get("output_index"), output.get("index"), key):
        if isinstance(candidate, int):
            return candidate
        if isinstance(candidate, str) and candidate.isdigit():
            return int(candidate)
    return None


def _get_output(snapshot: Any, output_id: int) -> dict[str, Any] | None:
    if isinstance(snapshot, dict):
        output = snapshot.get(output_id)
        if output is None:
            output = snapshot.get(str(output_id))
        return output if isinstance(output, dict) else None
    if isinstance(snapshot, list | tuple):
        index = output_id - 1
        if 0 <= index < len(snapshot):
            output = snapshot[index]
            return output if isinstance(output, dict) else None
    return None
