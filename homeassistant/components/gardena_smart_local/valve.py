"""Valve platform for GARDENA smart local."""

import logging
from typing import Any, override

from gardena_smart_local_api.devices import Device
import voluptuous as vol

from homeassistant.components.valve import ValveEntity, ValveEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_platform
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import GardenaSmartLocalCoordinator
from .entity import GardenaEntity, find_device_subentry_id, get_valve_duration_minutes

_LOGGER = logging.getLogger(__name__)

# Actions send commands to the gateway's local websocket, cap at 1 so HA
# serializes them instead of firing concurrent commands at the same connection
PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up valve entities as devices are discovered."""
    coordinator: GardenaSmartLocalCoordinator = entry.runtime_data
    known_valves: set[tuple[str, int]] = set()

    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        "open_valve",
        {
            vol.Optional("duration"): vol.All(
                vol.Coerce(int), vol.Range(min=60, max=10800)
            )
        },
        "async_open_valve_for",
    )

    def _add_new_devices() -> None:
        if not coordinator.data:
            return
        known_valves.intersection_update(
            (device.id, valve_id)
            for device in coordinator.data.values()
            if hasattr(device, "valve_ids")
            for valve_id in device.valve_ids
        )
        entities_by_subentry_id: dict[str | None, list] = {}
        for device in coordinator.data.values():
            if not hasattr(device, "valve_ids"):
                continue
            sid = find_device_subentry_id(entry, device.id)
            for valve_id in device.valve_ids:
                key = (device.id, valve_id)
                if key in known_valves:
                    continue
                known_valves.add(key)
                entities_by_subentry_id.setdefault(sid, []).append(
                    GardenaValve(coordinator, entry, device, valve_id)
                )
                _LOGGER.info(
                    "Adding new valve entity for device %s, valve %s",
                    device.id,
                    valve_id,
                )
        for sid, entities in entities_by_subentry_id.items():
            async_add_entities(entities, config_subentry_id=sid)

    entry.async_on_unload(coordinator.async_add_listener(_add_new_devices))
    _add_new_devices()


class GardenaValve(GardenaEntity, ValveEntity):
    """Representation of a single GARDENA smart valve output."""

    def __init__(
        self,
        coordinator: GardenaSmartLocalCoordinator,
        entry: ConfigEntry,
        device: Device,
        valve_id: int = 0,
    ) -> None:
        """Initialize the valve."""
        super().__init__(coordinator, device)
        self._entry = entry
        self._valve_id = valve_id
        # pylint: disable-next=home-assistant-entity-unique-id-redundant-platform
        self._attr_unique_id = f"{device.id}_valve_{valve_id}"
        if len(device.valve_ids) > 1:
            self._attr_translation_key = "valve"
            self._attr_translation_placeholders = {"number": str(valve_id + 1)}
        else:
            self._attr_name = None
        self._attr_reports_position = False
        self._attr_supported_features = (
            ValveEntityFeature.OPEN | ValveEntityFeature.CLOSE
        )

    @property
    @override
    def is_closed(self) -> bool | None:
        """Return True if the valve is closed."""
        device = self.coordinator.data.get(self._device.id)
        if not device:
            return None
        is_opened = device.is_valve_open(self._valve_id)
        _LOGGER.debug(
            "Valve %s valve_id=%s, is_opened=%s, returning is_closed=%s",
            self._device.id,
            self._valve_id,
            is_opened,
            not is_opened,
        )
        if is_opened is None:
            return None
        return not is_opened

    @override
    async def async_open_valve(self, **kwargs: Any) -> None:
        """Open the valve."""
        await self.async_open_valve_for()

    async def async_open_valve_for(self, duration: int | None = None) -> None:
        """Open the valve for a given duration, or the configured default."""
        if duration is None:
            minutes = get_valve_duration_minutes(
                self._entry, self._device.id, self._valve_id
            )
            duration = minutes * 60
        await self._send_confirmed_command(
            self._device.build_open_valve_obj(self._valve_id, duration)
        )
        _LOGGER.info(
            "Opening valve %s valve_id=%s duration=%s seconds",
            self._device.id,
            self._valve_id,
            duration,
        )

    @override
    async def async_close_valve(self, **kwargs: Any) -> None:
        """Close the valve."""
        await self._send_confirmed_command(
            self._device.build_close_valve_obj(self._valve_id)
        )
        _LOGGER.info("Closing valve %s valve_id=%s", self._device.id, self._valve_id)
