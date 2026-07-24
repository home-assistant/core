"""Valve platform for GARDENA smart local."""

import logging
from typing import Any, override

from gardena_smart_local_api.devices import Device

from homeassistant.components.valve import ValveEntity, ValveEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import GardenaSmartLocalCoordinator
from .entity import GardenaEntity, find_device_subentry_id

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up valve entities as devices are discovered."""
    coordinator: GardenaSmartLocalCoordinator = entry.runtime_data
    known_valves: set[tuple[str, int]] = set()

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
                    GardenaValve(coordinator, device, valve_id)
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
        device: Device,
        valve_id: int = 0,
    ) -> None:
        """Initialize the valve."""
        super().__init__(coordinator, device)
        self._valve_id = valve_id
        # pylint: disable-next=home-assistant-entity-unique-id-redundant-platform
        self._attr_unique_id = f"{device.id}_valve_{valve_id}"
        self._attr_name = f"Valve {valve_id + 1}" if len(device.valve_ids) > 1 else None
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
        await self.coordinator.send_request(
            self._device.id,
            self._device.build_open_valve_obj(self._valve_id, 1800),
        )
        _LOGGER.info("Opening valve %s valve_id=%s", self._device.id, self._valve_id)

    @override
    async def async_close_valve(self, **kwargs: Any) -> None:
        """Close the valve."""
        await self.coordinator.send_request(
            self._device.id,
            self._device.build_close_valve_obj(self._valve_id),
        )
        _LOGGER.info("Closing valve %s valve_id=%s", self._device.id, self._valve_id)
