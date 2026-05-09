"""Switches for Elke27 outputs."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
import logging
from typing import TYPE_CHECKING, Any

from elke27_lib.errors import Elke27PinRequiredError

from homeassistant.components.switch import SwitchEntity
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import Elke27DataUpdateCoordinator
from .entity import build_unique_id, device_info_for_entry, sanitize_name, unique_base

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

    from .hub import Elke27Hub
    from .models import Elke27RuntimeData

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0


async def async_setup_entry(
    _hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Elke27 switches from a config entry."""
    data: Elke27RuntimeData | None = entry.runtime_data
    if data is None:
        _LOGGER.debug("Skipping switch setup because runtime data is missing")
        return
    hub = data.hub
    coordinator = data.coordinator
    known_output_ids: set[int] = set()

    def _async_add_outputs() -> None:
        snapshot = coordinator.data
        if snapshot is None:
            _LOGGER.debug("Output switches skipped because snapshot is unavailable")
            return
        entities: list[Elke27OutputSwitch] = []
        outputs = list(_iter_outputs(snapshot))
        if not outputs:
            _LOGGER.debug("No outputs available for entity creation")
            return
        for output in outputs:
            output_id = getattr(output, "output_id", None)
            if not isinstance(output_id, int):
                continue
            if output_id in known_output_ids:
                continue
            known_output_ids.add(output_id)
            entities.append(
                Elke27OutputSwitch(coordinator, hub, entry, output_id, output)
            )
        if entities:
            async_add_entities(entities)

    _async_add_outputs()
    entry.async_on_unload(coordinator.async_add_listener(_async_add_outputs))


class Elke27OutputSwitch(CoordinatorEntity[Elke27DataUpdateCoordinator], SwitchEntity):
    """Representation of an Elke27 output."""

    _attr_has_entity_name = True
    _attr_translation_key = "output"

    def __init__(
        self,
        coordinator: Elke27DataUpdateCoordinator,
        hub: Elke27Hub,
        entry: ConfigEntry,
        output_id: int,
        output: Any,
    ) -> None:
        """Initialize the output entity."""
        super().__init__(coordinator)
        self._hub = hub
        self._output_id = output_id
        self._attr_name = (
            sanitize_name(getattr(output, "name", None)) or f"Output {output_id}"
        )
        self._attr_unique_id = build_unique_id(
            unique_base(hub, coordinator, entry),
            "output",
            output_id,
        )
        self._attr_device_info = device_info_for_entry(hub, coordinator, entry)
        self._missing_logged = False

    @property
    def is_on(self) -> bool | None:
        """Return if the output is on."""
        output = _get_output(self.coordinator.data, self._output_id)
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
            and _get_output(self.coordinator.data, self._output_id) is not None
        )

    async def async_turn_on(self, **_kwargs: Any) -> None:
        """Turn the output on if supported by the client."""
        try:
            await self._hub.async_set_output(self._output_id, state=True)
        except Elke27PinRequiredError as err:
            msg = "PIN required to perform this action."
            raise HomeAssistantError(msg) from err

    async def async_turn_off(self, **_kwargs: Any) -> None:
        """Turn the output off if supported by the client."""
        try:
            await self._hub.async_set_output(self._output_id, state=False)
        except Elke27PinRequiredError as err:
            msg = "PIN required to perform this action."
            raise HomeAssistantError(msg) from err

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
    if isinstance(outputs, Mapping):
        return list(outputs.values())
    if isinstance(outputs, list | tuple):
        return outputs
    return []


def _get_output(snapshot: Any, output_id: int) -> Any | None:
    for output in _iter_outputs(snapshot):
        if getattr(output, "output_id", None) == output_id:
            return output
    return None
