"""Support for SwitchBee light."""

import logging
from typing import Any

from switchbee import SWITCHBEE_BRAND
from switchbee.api import (
    ApiAttribute,
    ApiStatus,
    SwitchBeeDeviceOfflineError,
    SwitchBeeError,
)
from switchbee.device import ApiStateCommand, DeviceType

from homeassistant.components.light import ATTR_BRIGHTNESS, ColorMode, LightEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_SWITCHES_AS_LIGHTS, DOMAIN

MAX_BRIGHTNESS = 255

_LOGGER = logging.getLogger(__name__)


def brightness_hass_to_switchbee(value: int):
    """Convert hass brightness to SwitchBee."""
    return int((value * 100) / MAX_BRIGHTNESS)


def brightness_switchbee_to_hass(value: int):
    """Convert SwitchBee brightness to hass."""
    return int((value * MAX_BRIGHTNESS) / 100)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up SwitchBee light."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    switch_as_light = entry.data[CONF_SWITCHES_AS_LIGHTS]

    device_types = (
        [
            DeviceType.Dimmer,
            DeviceType.Switch,
            DeviceType.TimedSwitch,
            DeviceType.GroupSwitch,
        ]
        if switch_as_light
        else [DeviceType.Dimmer]
    )

    async_add_entities(
        Device(hass, device, coordinator)
        for device in coordinator.data.values()
        if device.type in device_types
    )


class Device(CoordinatorEntity, LightEntity):
    """Representation of an SwitchBee light."""

    def __init__(self, hass, device, coordinator):
        """Initialize the SwitchBee light."""
        super().__init__(coordinator)
        self._session = aiohttp_client.async_get_clientsession(hass)
        self._attr_name = f"{device.name}"
        self._device_id = device.id
        self._attr_unique_id = f"{coordinator.mac_formated}-{device.id}"
        self._is_dimmer = device.type == DeviceType.Dimmer
        self._attr_is_on = False
        self._attr_brightness = 0
        self._attr_supported_features = ColorMode.BRIGHTNESS if self._is_dimmer else 0
        self._last_brightness = None
        self._attr_available = True
        self._attr_has_entity_name = True
        self._device = device
        self._attr_device_info = DeviceInfo(
            name=f"SwitchBee_{str(device.unit_id)}",
            identifiers={
                (
                    DOMAIN,
                    f"{str(device.unit_id)}-{coordinator.mac_formated}",
                )
            },
            manufacturer=SWITCHBEE_BRAND,
            model=coordinator.api.module_display(device.unit_id),
            suggested_area=device.zone,
            via_device=(
                DOMAIN,
                f"{coordinator.api.name} ({coordinator.api.mac})",
            ),
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""

        async def async_refresh_state():
            try:
                await self.coordinator.api.set_state(self._device_id, "dummy")
            except SwitchBeeDeviceOfflineError:
                return
            except SwitchBeeError:
                return

        if self._is_dimmer:
            state = self.coordinator.data[self._device_id].brightness
        else:
            state = self.coordinator.data[self._device_id].state

        if state == -1:
            # This specific call will refresh the state of the device in the CU
            self.hass.async_create_task(async_refresh_state())

            if self.available:
                _LOGGER.warning(
                    "%s light is not responding, check the status in the SwitchBee mobile app",
                    self.name,
                )
            self._attr_available = False
            self.async_write_ha_state()
            return None

        if not self.available:
            _LOGGER.info(
                "%s light is now responding",
                self.name,
            )
        self._attr_available = True

        if self._is_dimmer:
            if state <= 2:
                self._attr_is_on = False
            else:
                self._attr_is_on = True

                self._attr_brightness = brightness_switchbee_to_hass(state)
                self._last_brightness = self._attr_brightness
        else:
            self._attr_is_on = bool(state == ApiStateCommand.ON)

        super()._handle_coordinator_update()

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self._handle_coordinator_update()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Async function to set on to light."""

        if ATTR_BRIGHTNESS in kwargs:
            if brightness_hass_to_switchbee(kwargs[ATTR_BRIGHTNESS]) <= 2:
                state = 0
            else:
                state = brightness_hass_to_switchbee(kwargs[ATTR_BRIGHTNESS])

        else:
            # Set the last brightness we know
            if not self._last_brightness:
                # First turn on, set the light brightness to the last brightness the HUB remembers
                state = ApiStateCommand.ON
            else:
                state = brightness_hass_to_switchbee(self._last_brightness)

        try:
            ret = await self.coordinator.api.set_state(self._device_id, state)
        except (SwitchBeeError, SwitchBeeDeviceOfflineError) as exp:
            _LOGGER.error(
                "Failed to set %s state %s, error: %s", self._attr_name, state, exp
            )
            self._attr_is_on = False
            self._async_write_ha_state()
        else:
            if ret[ApiAttribute.STATUS] == ApiStatus.OK:
                if self._is_dimmer:
                    self.coordinator.data[self._device_id].brightness = state
                else:
                    self.coordinator.data[self._device_id].state = state
                if (
                    ATTR_BRIGHTNESS in kwargs
                    and brightness_hass_to_switchbee(kwargs[ATTR_BRIGHTNESS]) >= 2
                ):
                    self._last_brightness = kwargs[ATTR_BRIGHTNESS]
                self.coordinator.async_set_updated_data(self.coordinator.data)
            else:
                _LOGGER.error(
                    "Failed to set %s state to %s: error %s",
                    self._attr_name,
                    str(state),
                    ret,
                )
                self._attr_is_on = False
                self._async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off SwitchBee light."""
        try:
            ret = await self.coordinator.api.set_state(
                self._device_id, ApiStateCommand.OFF
            )
        except (SwitchBeeError, SwitchBeeDeviceOfflineError) as exp:
            _LOGGER.error("Failed to turn off %s, error: %s", self._attr_name, exp)
            self._attr_is_on = True
            self._async_write_ha_state()
        else:
            if ret[ApiAttribute.STATUS] == ApiStatus.OK:
                if self._is_dimmer:
                    self.coordinator.data[self._device_id].brightness = 0
                else:
                    self.coordinator.data[self._device_id].state = ApiStateCommand.OFF
                self.coordinator.async_set_updated_data(self.coordinator.data)
            else:
                _LOGGER.error("Failed to turn off %s, error: %s", self._attr_name, ret)
                self._attr_is_on = True
                self._async_write_ha_state()
