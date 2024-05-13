"""Support for Aidot lights."""

import ctypes
import logging
from typing import Any

from aidot.lan import Lan

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_RGBW_COLOR,
    ColorMode,
    LightEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import Event, HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import (
    CONNECTION_NETWORK_MAC,
    DeviceInfo,
    format_mac,
)
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Light."""
    device_list = hass.data[DOMAIN].get("device_list", [])
    user_info = hass.data[DOMAIN].get("login_response", {})
    products = hass.data[DOMAIN].get("products", {})
    for product in products:
        for device in device_list:
            if device["productId"] == product["id"]:
                device["product"] = product

    async_add_entities(
        AidotLight(hass, device_info, user_info)
        for device_info in device_list
        if device_info["type"] == "light"
        and "aesKey" in device_info
        and device_info["aesKey"][0] is not None
    )


class AidotLight(LightEntity):
    """Representation of a Aidot Wi-Fi Light."""

    def __init__(self, hass: HomeAssistant, device, user_info) -> None:
        """Initialize the light."""
        super().__init__()
        self.device = device
        self.user_info = user_info
        self._attr_unique_id = device["id"]
        self._attr_name = device["name"]
        modelId = device["modelId"]
        manufacturer = modelId.split(".")[0]
        model = modelId[len(manufacturer) + 1 :]
        mac = format_mac(device["mac"]) if device["mac"] is not None else ""
        identifiers: set[tuple[str, str]] = (
            set({(DOMAIN, self._attr_unique_id)}) if self._attr_unique_id else set()
        )
        self._attr_device_info = DeviceInfo(
            identifiers=identifiers,
            connections={(CONNECTION_NETWORK_MAC, mac)},
            manufacturer=manufacturer,
            model=model,
            name=device["name"],
            hw_version=device["hardwareVersion"],
        )
        self._cct_min = 0
        self._cct_max = 0

        supported_color_modes = set()
        if "product" in device and "serviceModules" in device["product"]:
            for service in device["product"]["serviceModules"]:
                if service["identity"] == "control.light.rgbw":
                    supported_color_modes.add(ColorMode.RGBW)
                elif service["identity"] == "control.light.cct":
                    self._cct_min = int(service["properties"][0]["minValue"])
                    self._cct_max = int(service["properties"][0]["maxValue"])
                    supported_color_modes.add(ColorMode.COLOR_TEMP)
                # elif "control.light.effect.mode" == service["identity"]:
                # self._attr_supported_features = LightEntityFeature.EFFECT | LightEntityFeature.FLASH
                # allowedValues = service["properties"][0]["allowedValues"]
                # print(f"allowedValues: {allowedValues}")
                # self._attr_effect_list = [item["name"] for item in allowedValues]

        if ColorMode.RGBW in supported_color_modes:
            self._attr_color_mode = ColorMode.RGBW
            self._attr_supported_color_modes = {ColorMode.RGBW, ColorMode.COLOR_TEMP}
        elif ColorMode.COLOR_TEMP in supported_color_modes:
            self._attr_color_mode = ColorMode.COLOR_TEMP
            self._attr_supported_color_modes = {ColorMode.COLOR_TEMP}
        else:
            self._attr_color_mode = ColorMode.BRIGHTNESS
            self._attr_supported_color_modes = {ColorMode.BRIGHTNESS}

        self.lanCtrl = Lan(device, user_info)
        self.lanCtrl.setUpdateDeviceCb(self.updateState)

        async def handle_event(event):
            if not self.lanCtrl._connecting and not self.lanCtrl._connectAndLogin:
                await self.lanCtrl.connect(event.data["ipAddress"])
                self.pingtask = hass.loop.create_task(self.lanCtrl.ping_task())
                self.recvtask = hass.loop.create_task(self.lanCtrl.recvData())

        hass.bus.async_listen(device["id"], handle_event)

        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, self.release)

    async def release(self, event: Event):
        """Release task."""
        if hasattr(self, "pingtask") and self.pingtask is not None:
            self.pingtask.cancel()
        if hasattr(self, "recvtask") and self.recvtask is not None:
            self.recvtask.cancel()

    async def updateState(self):
        """Update the state of the entity."""
        if self.hass is not None and self.entity_id is not None:
            await self.async_update_ha_state(True)

    @property
    def available(self):
        """Return True if entity is available."""
        return self.lanCtrl._available

    @property
    def is_on(self) -> bool:
        """Return True if the light is on."""
        return self.lanCtrl._is_on

    @property
    def brightness(self) -> int:
        """Return the brightness of this light between 0..255."""
        return self.lanCtrl.brightness

    @property
    def min_color_temp_kelvin(self) -> int:
        """Return the warmest color_temp_kelvin that this light supports."""
        return self._cct_min

    @property
    def max_color_temp_kelvin(self) -> int:
        """Return the coldest color_temp_kelvin that this light supports."""
        return self._cct_max

    @property
    def color_temp_kelvin(self) -> int | None:
        """Return the CT color value in Kelvin."""
        return self.lanCtrl._cct

    @property
    def rgbw_color(self) -> tuple[int, int, int, int] | None:
        """Return the rgbw color value [int, int, int, int]."""
        if self.lanCtrl._rgdb:
            rgbw = ctypes.c_uint32(self.lanCtrl._rgdb).value
            r = (rgbw >> 24) & 0xFF
            g = (rgbw >> 16) & 0xFF
            b = (rgbw >> 8) & 0xFF
            w = rgbw & 0xFF
            return (r, g, b, w)
        return self._attr_rgbw_color

    @property
    def color_mode(self) -> ColorMode | str | None:
        """Return the color mode of the light."""
        if self.lanCtrl._colorMode == "rgbw":
            colorMode = ColorMode.RGBW
        elif self.lanCtrl._colorMode == "cct":
            colorMode = ColorMode.COLOR_TEMP
        else:
            colorMode = ColorMode.BRIGHTNESS
        return colorMode

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the light on."""
        brightness = kwargs.get(ATTR_BRIGHTNESS, 255)

        if self.lanCtrl._connectAndLogin is False:
            _LOGGER.error(
                "The device is not logged in or may not be on the local area network"
            )
            raise HomeAssistantError(
                "The device is not logged in or may not be on the local area network"
            )

        action = {}
        if ATTR_BRIGHTNESS in kwargs and brightness is not None:
            action.update(self.lanCtrl.getDimingAction(brightness))
        if ATTR_COLOR_TEMP_KELVIN in kwargs:
            cct = kwargs.get(ATTR_COLOR_TEMP_KELVIN)
            action.update(self.lanCtrl.getCCTAction(cct))
        if ATTR_RGBW_COLOR in kwargs:
            rgbw = kwargs.get(ATTR_RGBW_COLOR)
            if rgbw is not None:
                rgbw = (rgbw[0] << 24) | (rgbw[1] << 16) | (rgbw[2] << 8) | rgbw[3]
                ctype_result = ctypes.c_int32(rgbw).value
                action.update(self.lanCtrl.getRGBWAction(ctype_result))
        if not kwargs:
            action.update(self.lanCtrl.getOnOffAction(1))

        await self.lanCtrl.sendDevAttr(action)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        if self.lanCtrl._connectAndLogin is False:
            _LOGGER.error(
                "The device is not logged in or may not be on the local area network"
            )
            raise HomeAssistantError(
                "The device is not logged in or may not be on the local area network"
            )
        await self.lanCtrl.sendDevAttr(self.lanCtrl.getOnOffAction(0))
