"""Support for Aidot lights."""

import ctypes
import logging
from typing import Any

from aidot.const import (
    CONF_HARDWARE_VERSION,
    CONF_ID,
    CONF_IDENTITY,
    CONF_MAC,
    CONF_MAXVALUE,
    CONF_MINVALUE,
    CONF_MODEL_ID,
    CONF_NAME,
    CONF_PRODUCT,
    CONF_PROPERTIES,
    CONF_SERVICE_MODULES,
    Attribute,
    Identity,
)
from aidot.lan import Lan

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_RGBW_COLOR,
    ColorMode,
    LightEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import (
    CONNECTION_NETWORK_MAC,
    DeviceInfo,
    format_mac,
)
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import AidotCoordinator, AidotDeviceDiscoverCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Light."""
    coordinator: AidotCoordinator = entry.runtime_data
    async_add_entities(
        AidotLight(hass, device_info, coordinator)
        for device_info in coordinator.filter_light_list()
    )


class AidotLight(CoordinatorEntity[AidotDeviceDiscoverCoordinator], LightEntity):
    """Representation of a Aidot Wi-Fi Light."""

    _attr_has_entity_name = True
    _attr_name = None

    async def async_added_to_hass(self) -> None:
        """Connect to device when this entity is added to HA."""
        await super().async_added_to_hass()
        await self._try_connect()

    async def async_will_remove_from_hass(self) -> None:
        """Cleanup resources when entity will be removed from hass."""
        await super().async_will_remove_from_hass()
        await self._cleanup_resources()

    def __init__(
        self, hass: HomeAssistant, device, coordinator: AidotCoordinator
    ) -> None:
        """Initialize the light."""
        super().__init__(coordinator.discover_coordinator)
        # super().__init__(coordinator, {device[CONF_ID]})
        self.device = device
        self.user_info = coordinator.update_coordinator.client.login_info
        self._attr_unique_id = device[CONF_ID]
        self.pingtask = None
        self.recvtask = None

        modelId = device[CONF_MODEL_ID]
        manufacturer = modelId.split(".")[0]
        model = modelId[len(manufacturer) + 1 :]
        mac = format_mac(device[CONF_MAC]) if device[CONF_MAC] is not None else ""
        identifiers: set[tuple[str, str]] = set({(DOMAIN, self._attr_unique_id)})

        self._attr_device_info = DeviceInfo(
            identifiers=identifiers,
            connections={(CONNECTION_NETWORK_MAC, mac)},
            manufacturer=manufacturer,
            model=model,
            name=device[CONF_NAME],
            hw_version=device[CONF_HARDWARE_VERSION],
        )
        self._cct_min = 0
        self._cct_max = 0

        supported_color_modes = set()
        if CONF_PRODUCT in device and CONF_SERVICE_MODULES in device[CONF_PRODUCT]:
            for service in device[CONF_PRODUCT][CONF_SERVICE_MODULES]:
                if service[CONF_IDENTITY] == Identity.RGBW:
                    supported_color_modes.add(ColorMode.RGBW)
                elif service[CONF_IDENTITY] == Identity.CCT:
                    self._cct_min = int(service[CONF_PROPERTIES][0][CONF_MINVALUE])
                    self._cct_max = int(service[CONF_PROPERTIES][0][CONF_MAXVALUE])
                    supported_color_modes.add(ColorMode.COLOR_TEMP)

        if ColorMode.RGBW in supported_color_modes:
            self._attr_color_mode = ColorMode.RGBW
            self._attr_supported_color_modes = {ColorMode.RGBW, ColorMode.COLOR_TEMP}
        elif ColorMode.COLOR_TEMP in supported_color_modes:
            self._attr_color_mode = ColorMode.COLOR_TEMP
            self._attr_supported_color_modes = {ColorMode.COLOR_TEMP}
        else:
            self._attr_color_mode = ColorMode.BRIGHTNESS
            self._attr_supported_color_modes = {ColorMode.BRIGHTNESS}

        self.lanCtrl = Lan(device, self.user_info)
        self.lanCtrl.setUpdateDeviceCb(self.updateState)

    async def _cleanup_resources(self):
        """Release task."""
        self.lanCtrl.setUpdateDeviceCb(None)
        if hasattr(self, "pingtask") and self.pingtask is not None:
            self.pingtask.cancel()
        if hasattr(self, "recvtask") and self.recvtask is not None:
            self.recvtask.cancel()
        await self.lanCtrl.reset()

    async def _try_connect(self):
        """Try connect."""
        device_ip = self.coordinator.data.get(self.device[CONF_ID])
        if (
            device_ip is not None
            and not self.lanCtrl.connecting
            and not self.lanCtrl.connectAndLogin
        ):
            await self.lanCtrl.connect(device_ip)
            self.pingtask = self.hass.loop.create_task(self.lanCtrl.ping_task())
            self.recvtask = self.hass.loop.create_task(self.lanCtrl.recvData())

    async def updateState(self):
        """Update the state of the entity."""
        if self.hass is not None and self.entity_id is not None:
            await self.async_update_ha_state(True)

    @property
    def available(self):
        """Return True if entity is available."""
        return self.lanCtrl.available

    @property
    def is_on(self) -> bool:
        """Return True if the light is on."""
        return self.lanCtrl.is_on

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
        return self.lanCtrl.cct

    @property
    def rgbw_color(self) -> tuple[int, int, int, int] | None:
        """Return the rgbw color value [int, int, int, int]."""
        if self.lanCtrl.rgdb:
            rgbw = ctypes.c_uint32(self.lanCtrl.rgdb).value
            r = (rgbw >> 24) & 0xFF
            g = (rgbw >> 16) & 0xFF
            b = (rgbw >> 8) & 0xFF
            w = rgbw & 0xFF
            return (r, g, b, w)
        return self._attr_rgbw_color

    @property
    def color_mode(self) -> ColorMode | str | None:
        """Return the color mode of the light."""
        if self.lanCtrl.colorMode == Attribute.RGBW:
            colorMode = ColorMode.RGBW
        elif self.lanCtrl.colorMode == Attribute.CCT:
            colorMode = ColorMode.COLOR_TEMP
        else:
            colorMode = ColorMode.BRIGHTNESS
        return colorMode

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the light on."""
        brightness = kwargs.get(ATTR_BRIGHTNESS, 255)
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
        await self.lanCtrl.sendDevAttr(self.lanCtrl.getOnOffAction(0))

    @callback
    def _handle_coordinator_update(self):
        """Handle updated data from the coordinator."""
        self.hass.async_create_task(self._try_connect())
