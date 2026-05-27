"""Binary sensor platform for ALLNET."""

from typing import Any

from allnet.models import ChannelKind

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import AllnetConfigEntry
from .coordinator import AllnetDataUpdateCoordinator
from .entity import AllnetEntity

# Name heuristics — only used when chipid-based mapping is ambiguous.
_NAME_MOTION = ("motion", "bewegung", "pir")
_NAME_OPENING = ("door", "tür", "window", "fenster", "contact", "kontakt")
_NAME_SMOKE = ("smoke", "rauch", "gas")
_NAME_MOISTURE = ("leak", "leck", "water", "wasser", "moisture", "feucht")


def _device_class_from_channel(chipid: str, digital_to_text: str, name: str) -> BinarySensorDeviceClass | None:
    """Return the best-matching BinarySensorDeviceClass, or None."""
    # chipid "74" (PCF8574 single digital input)
    if chipid == "74":
        dtt_lower = digital_to_text.lower()
        if "erkannt" in dtt_lower or "motion" in dtt_lower or "bewegung" in dtt_lower:
            return BinarySensorDeviceClass.MOTION
        # Generic single-bit input — no device class
        return None

    # Name-based heuristics (fragile; prefer no class over wrong one)
    name_lower = name.lower()
    if any(k in name_lower for k in _NAME_MOTION):
        return BinarySensorDeviceClass.MOTION
    if any(k in name_lower for k in _NAME_OPENING):
        return BinarySensorDeviceClass.OPENING
    if any(k in name_lower for k in _NAME_SMOKE):
        return BinarySensorDeviceClass.SMOKE
    if any(k in name_lower for k in _NAME_MOISTURE):
        return BinarySensorDeviceClass.MOISTURE
    return None


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AllnetConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up ALLNET binary sensors."""
    runtime = entry.runtime_data
    coordinator = runtime.coordinator
    device_info = runtime.ha_device_info
    device_unique_id = entry.unique_id or entry.entry_id

    known_ids: set[str] = set()

    def _check_new_entities() -> None:
        new_entities: list[AllnetBinarySensorEntity] = []
        for channel in coordinator.data.values():
            if channel.kind != ChannelKind.BINARY_SENSOR:
                continue
            if channel.id in known_ids:
                continue
            known_ids.add(channel.id)

            raw_info = channel.raw.get("info", {})
            chipid = str(raw_info.get("chipid", ""))
            digital_to_text = str(channel.raw.get("digitalToText", ""))
            dev_class = _device_class_from_channel(chipid, digital_to_text, channel.name)

            unique_id = f"{device_unique_id}_{channel.id}_binary_sensor"
            new_entities.append(
                AllnetBinarySensorEntity(
                    coordinator=coordinator,
                    channel_id=channel.id,
                    device_info=device_info,
                    unique_id=unique_id,
                    name=channel.name,
                    device_class=dev_class,
                )
            )
        if new_entities:
            async_add_entities(new_entities)

    _check_new_entities()

    entry.async_on_unload(
        coordinator.async_add_listener(_check_new_entities)
    )


class AllnetBinarySensorEntity(AllnetEntity, BinarySensorEntity):
    """Representation of an ALLNET binary sensor channel."""

    def __init__(
        self,
        coordinator: AllnetDataUpdateCoordinator,
        channel_id: str,
        device_info: Any,
        unique_id: str,
        name: str,
        device_class: BinarySensorDeviceClass | None,
    ) -> None:
        """Initialize the binary sensor entity."""
        super().__init__(coordinator, channel_id, device_info)
        self._attr_unique_id = unique_id
        self._attr_name = name
        self._attr_device_class = device_class

    @property
    def is_on(self) -> bool | None:
        """Return True when the binary sensor is active."""
        channel = self.coordinator.data.get(self._channel_id)
        if channel is None or channel.value is None:
            return None
        return bool(channel.value)
