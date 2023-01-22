"""PrusaLink sensors."""
from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any, Generic, TypeVar, cast

from pyprusalink import Conflict, JobInfo, PrinterInfo, PrusaLink

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DOMAIN, PrusaLinkEntity, PrusaLinkUpdateCoordinator

T = TypeVar("T", PrinterInfo, JobInfo)


@dataclass
class PrusaLinkButtonEntityDescriptionMixin(Generic[T]):
    """Mixin for required keys."""

    press_fn: Callable[[PrusaLink], Coroutine[Any, Any, None]]


@dataclass
class PrusaLinkButtonEntityDescription(
    ButtonEntityDescription, PrusaLinkButtonEntityDescriptionMixin[T], Generic[T]
):
    """Describes PrusaLink button entity."""

    available_fn: Callable[[T], bool] = lambda _: True


BUTTONS: dict[str, tuple[PrusaLinkButtonEntityDescription, ...]] = {
    "printer": (
        PrusaLinkButtonEntityDescription[PrinterInfo](
            key="printer.cancel_job",
            name="Cancel Job",
            press_fn=lambda api: cast(Coroutine, api.cancel_job()),
            available_fn=lambda data: any(
                data["state"]["flags"][flag]
                for flag in ("printing", "pausing", "paused")
            ),
        ),
        PrusaLinkButtonEntityDescription[PrinterInfo](
            key="job.pause_job",
            name="Pause Job",
            press_fn=lambda api: cast(Coroutine, api.pause_job()),
            available_fn=lambda data: (
                data["state"]["flags"]["printing"]
                and not data["state"]["flags"]["paused"]
            ),
        ),
        PrusaLinkButtonEntityDescription[PrinterInfo](
            key="job.resume_job",
            name="Resume Job",
            press_fn=lambda api: cast(Coroutine, api.resume_job()),
            available_fn=lambda data: cast(bool, data["state"]["flags"]["paused"]),
        ),
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up PrusaLink buttons based on a config entry."""
    coordinators: dict[str, PrusaLinkUpdateCoordinator] = hass.data[DOMAIN][
        entry.entry_id
    ]

    entities: list[PrusaLinkEntity] = []

    for coordinator_type, sensors in BUTTONS.items():
        coordinator = coordinators[coordinator_type]
        entities.extend(
            PrusaLinkButtonEntity(coordinator, sensor_description)
            for sensor_description in sensors
        )

    async_add_entities(entities)


class PrusaLinkButtonEntity(PrusaLinkEntity, ButtonEntity):
    """Defines a PrusaLink button."""

    entity_description: PrusaLinkButtonEntityDescription

    def __init__(
        self,
        coordinator: PrusaLinkUpdateCoordinator,
        description: PrusaLinkButtonEntityDescription,
    ) -> None:
        """Initialize a PrusaLink sensor entity."""
        super().__init__(coordinator=coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{description.key}"

    @property
    def available(self) -> bool:
        """Return if sensor is available."""
        return super().available and self.entity_description.available_fn(
            self.coordinator.data
        )

    async def async_press(self) -> None:
        """Press the button."""
        try:
            await self.entity_description.press_fn(self.coordinator.api)
        except Conflict as err:
            raise HomeAssistantError(
                "Action conflicts with current printer state"
            ) from err

        coordinators: dict[str, PrusaLinkUpdateCoordinator] = self.hass.data[DOMAIN][
            self.coordinator.config_entry.entry_id
        ]

        for coordinator in coordinators.values():
            coordinator.expect_change()
            await coordinator.async_request_refresh()
