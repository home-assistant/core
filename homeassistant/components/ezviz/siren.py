"""Support for EZVIZ sirens."""
from __future__ import annotations

from typing import Any

from pyezviz import HTTPError, PyEzvizError

from homeassistant.components.siren import SirenEntity, SirenEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import DATA_COORDINATOR, DOMAIN
from .coordinator import EzvizDataUpdateCoordinator
from .entity import EzvizEntity

PARALLEL_UPDATES = 1


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


class EzvizSirenEntity(EzvizEntity, SirenEntity, RestoreEntity):
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
        self._attr_is_on = False

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added."""
        await super().async_added_to_hass()
        if not (last_state := await self.async_get_last_state()):
            return
        self._attr_is_on = last_state.state == STATE_ON

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off camera siren."""
        try:
            success = await self.hass.async_add_executor_job(
                self.coordinator.ezviz_client.sound_alarm, self._serial, 1
            )

        except (HTTPError, PyEzvizError) as err:
            raise HomeAssistantError(
                f"Failed to turn siren off for {self.name}"
            ) from err

        if success:
            self._attr_is_on = False

        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on camera siren."""
        try:
            success = await self.hass.async_add_executor_job(
                self.coordinator.ezviz_client.sound_alarm, self._serial, 2
            )

        except (HTTPError, PyEzvizError) as err:
            raise HomeAssistantError(
                f"Failed to turn siren on for {self.name}"
            ) from err

        if success:
            self._attr_is_on = True

        self.async_write_ha_state()
