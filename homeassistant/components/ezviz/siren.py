"""Support for EZVIZ sirens."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from pyezviz import HTTPError, PyEzvizError, SupportExt

from homeassistant.components.siren import (
    SirenEntity,
    SirenEntityDescription,
    SirenEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_ON
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
import homeassistant.helpers.event as evt
from homeassistant.helpers.restore_state import RestoreEntity

from .const import DATA_COORDINATOR, DOMAIN
from .coordinator import EzvizDataUpdateCoordinator
from .entity import EzvizBaseEntity

PARALLEL_UPDATES = 1
OFF_DELAY = timedelta(seconds=60)  # Camera firmware has hard coded turn off.

SIREN_ENTITY_TYPE = SirenEntityDescription(
    key="siren",
    translation_key="siren",
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up EZVIZ sensors based on a config entry."""
    coordinator: EzvizDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id][
        DATA_COORDINATOR
    ]

    async_add_entities(
        EzvizSirenEntity(coordinator, camera, SIREN_ENTITY_TYPE)
        for camera in coordinator.data
        for capability, value in coordinator.data[camera]["supportExt"].items()
        if capability == str(SupportExt.SupportActiveDefense.value)
        if value != "0"
    )


class EzvizSirenEntity(EzvizBaseEntity, SirenEntity, RestoreEntity):
    """Representation of a EZVIZ Siren entity."""

    _attr_supported_features = SirenEntityFeature.TURN_ON | SirenEntityFeature.TURN_OFF
    _attr_should_poll = False

    def __init__(
        self,
        coordinator: EzvizDataUpdateCoordinator,
        serial: str,
        description: SirenEntityDescription,
    ) -> None:
        """Initialize the Siren."""
        super().__init__(coordinator, serial)
        self._attr_unique_id = f"{serial}_{description.key}"
        self.entity_description = description
        self._attr_is_on = False

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        if not (last_state := await self.async_get_last_state()):
            return
        self._attr_is_on = last_state.state == STATE_ON

        if self._attr_is_on:
            evt.async_call_later(self.hass, OFF_DELAY, self.off_delay_listener)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off camera siren."""
        try:
            if await self.hass.async_add_executor_job(
                self.coordinator.ezviz_client.sound_alarm, self._serial, 1
            ):
                self._attr_is_on = False
                self.async_write_ha_state()

        except (HTTPError, PyEzvizError) as err:
            raise HomeAssistantError(
                f"Failed to turn siren off for {self.name}"
            ) from err

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on camera siren."""
        try:
            if await self.hass.async_add_executor_job(
                self.coordinator.ezviz_client.sound_alarm, self._serial, 2
            ):
                self._attr_is_on = True
                evt.async_call_later(self.hass, OFF_DELAY, self.off_delay_listener)
                self.async_write_ha_state()

        except (HTTPError, PyEzvizError) as err:
            raise HomeAssistantError(
                f"Failed to turn siren on for {self.name}"
            ) from err

    @callback
    def off_delay_listener(self, now: datetime) -> None:
        """Switch device off after a delay.

        Camera firmware has hard coded turn off after 60 seconds.
        """
        self._attr_is_on = False
        self.async_write_ha_state()
