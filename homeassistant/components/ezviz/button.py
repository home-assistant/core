"""Support for EZVIZ button controls."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from pyezviz.exceptions import HTTPError, PyEzvizError

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DATA_COORDINATOR, DOMAIN
from .coordinator import EzvizDataUpdateCoordinator
from .entity import EzvizEntity

PARALLEL_UPDATES = 1


@dataclass
class EzvizButtonEntityDescriptionMixin:
    """Mixin values for EZVIZ button entities."""

    method: Callable[[Any, Any, Any], Any]


@dataclass
class EzvizButtonEntityDescription(
    ButtonEntityDescription, EzvizButtonEntityDescriptionMixin
):
    """Describe a EZVIZ Button."""


BUTTON_ENTITIES = (
    EzvizButtonEntityDescription(
        key="ptz_up",
        entity_registry_enabled_default=False,
        name="PTZ up",
        icon="mdi:pan",
        method=lambda pyezviz_client, serial, run: pyezviz_client.ptz_control(
            "UP", serial, run
        ),
    ),
    EzvizButtonEntityDescription(
        key="ptz_down",
        entity_registry_enabled_default=False,
        name="PTZ down",
        icon="mdi:pan",
        method=lambda pyezviz_client, serial, run: pyezviz_client.ptz_control(
            "DOWN", serial, run
        ),
    ),
    EzvizButtonEntityDescription(
        key="ptz_left",
        entity_registry_enabled_default=False,
        name="PTZ left",
        icon="mdi:pan",
        method=lambda pyezviz_client, serial, run: pyezviz_client.ptz_control(
            "LEFT", serial, run
        ),
    ),
    EzvizButtonEntityDescription(
        key="ptz_right",
        entity_registry_enabled_default=False,
        name="PTZ right",
        icon="mdi:pan",
        method=lambda pyezviz_client, serial, run: pyezviz_client.ptz_control(
            "RIGHT", serial, run
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up EZVIZ button based on a config entry."""
    coordinator: EzvizDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id][
        DATA_COORDINATOR
    ]

    async_add_entities(
        EzvizButton(coordinator, camera, entity_description)
        for camera in coordinator.data
        for entity_description in BUTTON_ENTITIES
    )


class EzvizButton(EzvizEntity, ButtonEntity):
    """Representation of a EZVIZ button entity."""

    entity_description: EzvizButtonEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: EzvizDataUpdateCoordinator,
        serial: str,
        description: EzvizButtonEntityDescription,
    ) -> None:
        """Initialize the button."""
        super().__init__(coordinator, serial)
        self._attr_unique_id = f"{serial}_{description.name}"
        self.entity_description = description

    def press(self) -> None:
        """Execute the button action."""
        try:
            self.entity_description.method(
                self.coordinator.ezviz_client, self._serial, "START"
            )
            self.entity_description.method(
                self.coordinator.ezviz_client, self._serial, "STOP"
            )
        except (HTTPError, PyEzvizError) as err:
            raise HomeAssistantError(
                f"Cannot perform PTZ action on {self.name}"
            ) from err
