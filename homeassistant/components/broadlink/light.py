"""Support for Broadlink lights."""

import logging
from typing import Any, override

from broadlink_async.exceptions import BroadlinkException
from broadlink_async.magic import (
    ImportedDevice,
    encode_light_brightness,
    encode_light_power,
    encode_rgbcw_light,
)

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_HS_COLOR,
    ATTR_RGB_COLOR,
    ColorMode,
    LightEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import area_registry as ar, device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import BROADLINK_DATA, DOMAIN, is_magic_entry, magic_device_identifier
from .coordinator import BroadLinkMagicConfigEntry, FamilyCoordinator
from .entity import BroadlinkEntity, BroadLinkMagicEntity

_LOGGER = logging.getLogger(__name__)

BROADLINK_COLOR_MODE_RGB = 0
BROADLINK_COLOR_MODE_WHITE = 1
BROADLINK_COLOR_MODE_SCENES = 2


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Broadlink light."""
    if is_magic_entry(config_entry):
        await _async_setup_magic_entry(hass, config_entry, async_add_entities)
        return

    device = hass.data[BROADLINK_DATA].devices[config_entry.entry_id]
    lights = []

    if device.api.type in {"LB1", "LB2"}:
        lights.append(BroadlinkLight(device))

    async_add_entities(lights)


class BroadlinkLight(BroadlinkEntity, LightEntity):
    """Representation of a Broadlink light."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_min_color_temp_kelvin = 2700
    _attr_max_color_temp_kelvin = 6500

    def __init__(self, device):
        """Initialize the light."""
        super().__init__(device)
        self._attr_unique_id = device.unique_id
        self._attr_supported_color_modes = set()

        data = self._coordinator.data

        if {"hue", "saturation"}.issubset(data):
            self._attr_supported_color_modes.add(ColorMode.HS)
        if "colortemp" in data:
            self._attr_supported_color_modes.add(ColorMode.COLOR_TEMP)
        if not self.supported_color_modes:
            self._attr_supported_color_modes = {ColorMode.BRIGHTNESS}

        self._update_state(data)

    @override
    def _update_state(self, data):
        """Update the state of the entity."""
        if "pwr" in data:
            self._attr_is_on = bool(data["pwr"])

        if "brightness" in data:
            self._attr_brightness = round(data["brightness"] * 2.55)

        if self.supported_color_modes == {ColorMode.BRIGHTNESS}:
            self._attr_color_mode = ColorMode.BRIGHTNESS
            return

        if {"hue", "saturation"}.issubset(data):
            self._attr_hs_color = [data["hue"], data["saturation"]]

        if "colortemp" in data:
            self._attr_color_temp_kelvin = data["colortemp"]

        if "bulb_colormode" in data:
            if data["bulb_colormode"] == BROADLINK_COLOR_MODE_RGB:
                self._attr_color_mode = ColorMode.HS
            elif data["bulb_colormode"] == BROADLINK_COLOR_MODE_WHITE:
                self._attr_color_mode = ColorMode.COLOR_TEMP
            else:
                # Scenes are not yet supported.
                self._attr_color_mode = ColorMode.UNKNOWN

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the light."""
        state = {"pwr": 1}

        if ATTR_BRIGHTNESS in kwargs:
            brightness = kwargs[ATTR_BRIGHTNESS]
            state["brightness"] = round(brightness / 2.55)

        if self.supported_color_modes == {ColorMode.BRIGHTNESS}:
            state["bulb_colormode"] = BROADLINK_COLOR_MODE_WHITE

        elif ATTR_HS_COLOR in kwargs:
            hs_color = kwargs[ATTR_HS_COLOR]
            state["hue"] = int(hs_color[0])
            state["saturation"] = int(hs_color[1])
            state["bulb_colormode"] = BROADLINK_COLOR_MODE_RGB

        elif ATTR_COLOR_TEMP_KELVIN in kwargs:
            color_temp = kwargs[ATTR_COLOR_TEMP_KELVIN]
            state["colortemp"] = color_temp
            state["bulb_colormode"] = BROADLINK_COLOR_MODE_WHITE

        await self._async_set_state(state)

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the light."""
        await self._async_set_state({"pwr": 0})

    async def _async_set_state(self, state):
        """Set the state of the light."""
        device = self._device

        try:
            state = await device.async_request(device.api.set_state, **state)
        except (BroadlinkException, OSError) as err:
            _LOGGER.error("Failed to set state: %s", err)
            return

        self._update_state(state)
        self.async_write_ha_state()


async def _async_setup_magic_entry(
    hass: HomeAssistant,
    entry: BroadLinkMagicConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up imported lights and light groups."""
    coordinator = entry.runtime_data
    async_add_entities(
        BroadLinkMagicLight(coordinator, device)
        for device in coordinator.family.light_devices
    )


class _BroadLinkMagicLightBase(BroadLinkMagicEntity, LightEntity):
    """Shared optimistic light behavior."""

    _attr_is_on = False
    _attr_max_color_temp_kelvin = 6500
    _attr_min_color_temp_kelvin = 2700
    _attr_name = None
    _attr_brightness = 255
    _area_name: str | None = None
    _state_id: str | None = None

    def __init__(
        self,
        coordinator: FamilyCoordinator,
        *,
        rgbcw: bool,
    ) -> None:
        """Initialize shared light capabilities."""
        super().__init__(coordinator)
        self._rgbcw = rgbcw
        self._report_serial = 0
        if rgbcw:
            self._attr_supported_color_modes = {
                ColorMode.COLOR_TEMP,
                ColorMode.RGB,
            }
            self._attr_color_mode = ColorMode.COLOR_TEMP
            self._attr_rgb_color = (255, 255, 255)
            self._attr_color_temp_kelvin = 4600
        else:
            self._attr_supported_color_modes = {ColorMode.BRIGHTNESS}
            self._attr_color_mode = ColorMode.BRIGHTNESS

    async def _async_send(self, payload: bytes) -> None:
        raise NotImplementedError

    @override
    @callback
    def _handle_coordinator_update(self) -> None:
        """Apply a real FastCon status report."""
        serial = (
            self.coordinator.report_serials.get(self._state_id, 0)
            if self._state_id is not None
            else 0
        )
        if self._state_id is not None and serial != self._report_serial:
            self._report_serial = serial
            state = self.coordinator.device_states.get(self._state_id, {})
            if "is_on" in state:
                self._attr_is_on = bool(state["is_on"])
            if "brightness" in state:
                self._attr_brightness = int(state["brightness"])
            if rgb := state.get("rgb_color"):
                self._attr_rgb_color = tuple(rgb)
                if any(self._attr_rgb_color):
                    self._attr_color_mode = ColorMode.RGB
            if "color_temp_kelvin" in state and not any(state.get("rgb_color", ())):
                self._attr_color_temp_kelvin = int(state["color_temp_kelvin"])
                self._attr_color_mode = ColorMode.COLOR_TEMP
        super()._handle_coordinator_update()

    @override
    async def async_added_to_hass(self) -> None:
        """Assign the imported room without overriding user changes."""
        await super().async_added_to_hass()
        if self._area_name and self.registry_entry is not None:
            device_id = self.registry_entry.device_id
            registry = dr.async_get(self.hass)
            device = registry.async_get(device_id) if device_id else None
            if device is not None and device.area_id is None:
                area = ar.async_get(self.hass).async_get_or_create(self._area_name)
                if isinstance(device, dr.ChildDeviceEntry):
                    registry.async_update_child_device(device.id, area_id=area.id)
                else:
                    registry.async_update_device(device.id, area_id=area.id)

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on and update brightness, RGB, or color temperature."""
        has_level_or_color = any(
            key in kwargs
            for key in (
                ATTR_BRIGHTNESS,
                ATTR_RGB_COLOR,
                ATTR_COLOR_TEMP_KELVIN,
            )
        )
        if ATTR_BRIGHTNESS in kwargs:
            self._attr_brightness = int(kwargs[ATTR_BRIGHTNESS])
        if ATTR_RGB_COLOR in kwargs:
            self._attr_rgb_color = tuple(kwargs[ATTR_RGB_COLOR])
            self._attr_color_mode = ColorMode.RGB
        if ATTR_COLOR_TEMP_KELVIN in kwargs:
            self._attr_color_temp_kelvin = int(kwargs[ATTR_COLOR_TEMP_KELVIN])
            self._attr_color_mode = ColorMode.COLOR_TEMP

        if self._rgbcw and has_level_or_color:
            cold_percent = None
            rgb = None
            if self._attr_color_mode is ColorMode.RGB:
                rgb = self._attr_rgb_color
            elif (
                self._attr_color_mode is ColorMode.COLOR_TEMP
                and self._attr_color_temp_kelvin is not None
            ):
                cold_percent = round(
                    (self._attr_color_temp_kelvin - 2700) * 100 / (6500 - 2700)
                )
            payload = encode_rgbcw_light(
                on=True,
                brightness=self._attr_brightness,
                rgb=rgb,
                cold_percent=cold_percent,
            )
            self._attr_is_on = self._attr_brightness > 0
        elif ATTR_BRIGHTNESS in kwargs:
            payload = encode_light_brightness(self._attr_brightness)
            self._attr_is_on = self._attr_brightness > 0
        else:
            payload = encode_light_power(True)
            self._attr_is_on = True
        await self._async_send(payload)
        self.async_write_ha_state()

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off."""
        await self._async_send(encode_light_power(False))
        self._attr_is_on = False
        self.async_write_ha_state()


class BroadLinkMagicLight(_BroadLinkMagicLightBase):
    """An imported Bluetooth light."""

    def __init__(
        self,
        coordinator: FamilyCoordinator,
        device: ImportedDevice,
    ) -> None:
        """Initialize an imported light."""
        super().__init__(
            coordinator,
            rgbcw=(
                "RGB" in device.ble_category.upper()
                or device.effective_pid.endswith("2aa80000")
            ),
        )
        self._device = device
        self._state_id = device.stable_id
        self._area_name = coordinator.room_name(device.room_id)
        self._attr_icon = "mdi:lightbulb"
        self._attr_unique_id = f"{coordinator.family.family_id}_{device.stable_id}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, magic_device_identifier(device.stable_id))},
            manufacturer="BroadLink",
            model="Magic Home Light",
            name=device.name,
            suggested_area=coordinator.room_name(device.room_id),
            via_device_id=self._family_device_id(),
        )

    @override
    async def _async_send(self, payload: bytes) -> None:
        await self.coordinator.async_send_light(self._device, payload)
