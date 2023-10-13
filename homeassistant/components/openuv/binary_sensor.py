"""Support for OpenUV binary sensors."""
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.dt import as_local, parse_datetime, utcnow

from . import OpenUvEntity
from .const import DATA_PROTECTION_WINDOW, DOMAIN, LOGGER, TYPE_PROTECTION_WINDOW
from .coordinator import OpenUvCoordinator

ATTR_PROTECTION_WINDOW_ENDING_TIME = "end_time"
ATTR_PROTECTION_WINDOW_ENDING_UV = "end_uv"
ATTR_PROTECTION_WINDOW_STARTING_TIME = "start_time"
ATTR_PROTECTION_WINDOW_STARTING_UV = "start_uv"


def in_protection_window(protection_window_data: dict[str, Any]) -> bool:
    """Return true if the current time is in the protection window."""
    from_dt = parse_datetime(protection_window_data["from_time"])
    to_dt = parse_datetime(protection_window_data["to_time"])

    if not from_dt or not to_dt:
        LOGGER.warning(
            "Unable to parse protection window datetimes: %s, %s",
            protection_window_data["from_time"],
            protection_window_data["to_time"],
        )
        return False
    return from_dt <= utcnow() <= to_dt


@dataclass
class OpenUvBinarySensorEntityDescriptionMixin:
    """Define a mixin for OpenUV sensor descriptions."""

    value_fn: Callable[[dict[str, Any]], bool]


@dataclass
class OpenUvBinarySensorDescription(
    BinarySensorEntityDescription, OpenUvBinarySensorEntityDescriptionMixin
):
    """Define a class that describes OpenUV sensor entities."""


BINARY_SENSOR_DESCRIPTION_PROTECTION_WINDOW = OpenUvBinarySensorDescription(
    key=TYPE_PROTECTION_WINDOW,
    translation_key="protection_window",
    icon="mdi:sunglasses",
    value_fn=in_protection_window,
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    # Once we've successfully authenticated, we re-enable client request retries:
    """Set up an OpenUV sensor based on a config entry."""
    coordinators: dict[str, OpenUvCoordinator] = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        [
            OpenUvBinarySensor(
                coordinators[DATA_PROTECTION_WINDOW],
                BINARY_SENSOR_DESCRIPTION_PROTECTION_WINDOW,
            )
        ]
    )


class OpenUvBinarySensor(OpenUvEntity, BinarySensorEntity):
    """Define a binary sensor for OpenUV."""

    entity_description: OpenUvBinarySensorDescription

    @property
    def extra_state_attributes(self) -> Mapping[str, Any]:
        """Return entity specific state attributes."""
        attrs = {}
        attrs[ATTR_PROTECTION_WINDOW_ENDING_UV] = self.coordinator.data["to_uv"]
        attrs[ATTR_PROTECTION_WINDOW_STARTING_UV] = self.coordinator.data["from_uv"]

        if to_dt := parse_datetime(self.coordinator.data["to_time"]):
            attrs[ATTR_PROTECTION_WINDOW_ENDING_TIME] = as_local(to_dt)
        if from_dt := parse_datetime(self.coordinator.data["from_time"]):
            attrs[ATTR_PROTECTION_WINDOW_ENDING_TIME] = as_local(from_dt)

        return attrs

    @property
    def is_on(self) -> bool:
        """Return true if the binary sensor is on."""
        return self.entity_description.value_fn(self.coordinator.data)
