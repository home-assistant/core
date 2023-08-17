"""Support for EZVIZ light entity."""
from __future__ import annotations

from typing import Any

from pyezviz.constants import DeviceCatagories, DeviceSwitchType, SupportExt
from pyezviz.exceptions import HTTPError, PyEzvizError

from homeassistant.components.light import ATTR_BRIGHTNESS, ColorMode, LightEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.percentage import (
    percentage_to_ranged_value,
    ranged_value_to_percentage,
)

from .const import DATA_COORDINATOR, DOMAIN
from .coordinator import EzvizDataUpdateCoordinator
from .entity import EzvizEntity

PARALLEL_UPDATES = 1
BRIGHTNESS_RANGE = (1, 255)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up EZVIZ lights based on a config entry."""
    coordinator: EzvizDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id][
        DATA_COORDINATOR
    ]

    async_add_entities(
        EzvizLight(coordinator, camera)
        for camera in coordinator.data
        for capibility, value in coordinator.data[camera]["supportExt"].items()
        if capibility == str(SupportExt.SupportAlarmLight.value)
        if value == "1"
    )


class EzvizLight(EzvizEntity, LightEntity):
    """Representation of a EZVIZ light."""

    _attr_translation_key = "light"
    _attr_color_mode = ColorMode.BRIGHTNESS
    _attr_supported_color_modes = {ColorMode.BRIGHTNESS}

    def __init__(
        self,
        coordinator: EzvizDataUpdateCoordinator,
        serial: str,
    ) -> None:
        """Initialize the light."""
        super().__init__(coordinator, serial)
        self.battery_cam_type = bool(
            self.data["device_category"]
            == DeviceCatagories.BATTERY_CAMERA_DEVICE_CATEGORY.value
        )
        self._attr_unique_id = f"{serial}_Light"
        self._attr_is_on = self.data["switches"][DeviceSwitchType.ALARM_LIGHT.value]
        self._attr_brightness = round(
            percentage_to_ranged_value(
                BRIGHTNESS_RANGE,
                self.coordinator.data[self._serial]["alarm_light_luminance"],
            )
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on light."""
        try:
            if ATTR_BRIGHTNESS in kwargs:
                data = ranged_value_to_percentage(
                    BRIGHTNESS_RANGE, kwargs[ATTR_BRIGHTNESS]
                )

                if await self.hass.async_add_executor_job(
                    self.coordinator.ezviz_client.set_floodlight_brightness,
                    self._serial,
                    data,
                ):
                    self._attr_brightness = kwargs[ATTR_BRIGHTNESS]

            if await self.hass.async_add_executor_job(
                self.coordinator.ezviz_client.switch_status,
                self._serial,
                DeviceSwitchType.ALARM_LIGHT.value,
                1,
            ):
                self._attr_is_on = True
                self.async_write_ha_state()

        except (HTTPError, PyEzvizError) as err:
            raise HomeAssistantError(
                f"Failed to turn on light {self._attr_name}"
            ) from err

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off light."""
        try:
            if await self.hass.async_add_executor_job(
                self.coordinator.ezviz_client.switch_status,
                self._serial,
                DeviceSwitchType.ALARM_LIGHT.value,
                0,
            ):
                self._attr_is_on = False
                self.async_write_ha_state()

        except (HTTPError, PyEzvizError) as err:
            raise HomeAssistantError(
                f"Failed to turn off light {self._attr_name}"
            ) from err

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._attr_is_on = self.data["switches"].get(DeviceSwitchType.ALARM_LIGHT.value)

        if isinstance(self.data["alarm_light_luminance"], int):
            self._attr_brightness = round(
                percentage_to_ranged_value(
                    BRIGHTNESS_RANGE,
                    self.data["alarm_light_luminance"],
                )
            )

        super()._handle_coordinator_update()
