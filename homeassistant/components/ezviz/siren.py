"""Support for EZVIZ sirens."""
from __future__ import annotations

from typing import Any

from pyezviz import HTTPError, PyEzvizError

from homeassistant.components.siren import (
    SirenEntity,
    SirenEntityDescription,
    SirenEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DATA_COORDINATOR, DOMAIN
from .coordinator import EzvizDataUpdateCoordinator
from .entity import EzvizEntity

PARALLEL_UPDATES = 1

SIREN_ENTITY_TYPES = SirenEntityDescription(
    key="siren",
    name="Siren",
    icon="mdi:eye",
    entity_category=EntityCategory.CONFIG,
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up EZVIZ sensors based on a config entry."""
    coordinator: EzvizDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id][
        DATA_COORDINATOR
    ]

    async_add_entities(
        EzvizSirenEntity(coordinator, camera) for camera in coordinator.data
    )


class EzvizSirenEntity(EzvizEntity, SirenEntity):
    """Representation of a EZVIZ Siren entity."""

    _attr_has_entity_name = True
    _attr_name = "Siren"
    _attr_supported_features = SirenEntityFeature.TURN_ON | SirenEntityFeature.TURN_OFF

    def __init__(
        self,
        coordinator: EzvizDataUpdateCoordinator,
        serial: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, serial)
        self._attr_unique_id = f"{serial}_siren"

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off camera siren."""
        try:
            await self.hass.async_add_executor_job(
                self.coordinator.ezviz_client.sound_alarm, self._serial, 1
            )

        except (HTTPError, PyEzvizError) as err:
            raise HomeAssistantError(
                f"Failed to turn siren off for {self.name}"
            ) from err

        _attr_is_on = False

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on camera siren."""
        try:
            await self.hass.async_add_executor_job(
                self.coordinator.ezviz_client.sound_alarm, self._serial, 2
            )

        except (HTTPError, PyEzvizError) as err:
            raise HomeAssistantError(
                f"Failed to turn siren on for {self.name}"
            ) from err

        _attr_is_on = True
