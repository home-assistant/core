"""Component providing Lights for UniFi Protect."""

import logging
from typing import Any, cast, override

from uiprotect.data import (
    Light,
    ModelType,
    ProtectAdoptableDeviceModel,
    PublicDeviceModel,
)
from uiprotect.data.public_devices import PublicLight

from homeassistant.components.light import ATTR_BRIGHTNESS, ColorMode, LightEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr, entity_platform
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DEFAULT_BRAND
from .data import ProtectData, ProtectDeviceType, UFPConfigEntry
from .entity import ProtectDeviceEntity
from .utils import async_ufp_instance_command

_LOGGER = logging.getLogger(__name__)
PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: UFPConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up lights for UniFi Protect integration."""
    data = entry.runtime_data
    platform = entity_platform.async_get_current_platform()

    @callback
    def _add_new_device(device: ProtectAdoptableDeviceModel) -> None:
        if device.model is ModelType.LIGHT and device.can_write(
            data.api.bootstrap.auth_user
        ):
            light = cast(Light, device)
            public = data.async_get_public_device(light)
            async_add_entities(
                [
                    ProtectLight(
                        data,
                        public if isinstance(public, PublicLight) else None,
                        light,
                    )
                ]
            )

    @callback
    def _add_new_public_device(device: PublicDeviceModel) -> None:
        if not isinstance(device, PublicLight):
            return
        # Skip a re-add whose entity still exists; the platform errors on a
        # duplicate unique_id.
        if any(e.unique_id == device.mac for e in platform.entities.values()):
            return
        async_add_entities([ProtectLight(data, device, None)])

    data.async_subscribe_adopt(_add_new_device)
    entry.async_on_unload(
        async_dispatcher_connect(hass, data.public_add_signal, _add_new_public_device)
    )

    entities: list[ProtectLight] = []
    for public, private in data.get_public_lights():
        if private is None:
            # Public-only creates from the public object; hybrid defers to the
            # adopt dispatch (its private fill would clash on unique_id).
            if data.api.is_public_only:
                entities.append(ProtectLight(data, public, None))
            continue
        # Created even without a public mirror; unavailable until one arrives.
        if private.can_write(data.api.bootstrap.auth_user):
            entities.append(ProtectLight(data, public, private))
    async_add_entities(entities)


def unifi_brightness_to_hass(value: int) -> int:
    """Convert unifi brightness 1..6 to hass format 0..255."""
    return min(255, round((value / 6) * 255))


def hass_to_unifi_brightness(value: int) -> int:
    """Convert hass brightness 0..255 to unifi 1..6 scale."""
    return max(1, round((value / 255) * 6))


class ProtectLight(ProtectDeviceEntity, LightEntity):
    """A Ubiquiti UniFi Protect Light Entity."""

    device: Light

    _attr_icon = "mdi:spotlight-beam"
    _attr_color_mode = ColorMode.BRIGHTNESS
    _attr_supported_color_modes = {ColorMode.BRIGHTNESS}
    _state_attrs = ("_attr_available", "_attr_is_on", "_attr_brightness")

    def __init__(
        self,
        data: ProtectData,
        public: PublicLight | None,
        private: Light | None,
    ) -> None:
        """Initialize the light."""
        self._private = private
        self._ufp_public_obj = public
        # Key the base on the private device in hybrid, the public one otherwise.
        super().__init__(data, cast(ProtectDeviceType, private or public))

    @callback
    @override
    def _async_set_device_info(self) -> None:
        if self._private is not None:
            super()._async_set_device_info()
            return
        # market_name/firmware/URL and the NVR link are private-only.
        public = cast(PublicLight, self.device)
        self._attr_device_info = DeviceInfo(
            name=public.display_name,
            model=public.type,
            manufacturer=DEFAULT_BRAND,
            connections={(dr.CONNECTION_NETWORK_MAC, public.mac)},
        )

    @override
    async def async_added_to_hass(self) -> None:
        """Read state from the public API (primed before the first update)."""
        self._ufp_uses_public = True
        self._ufp_public_obj = self.data.async_get_public_device(self.device)
        self.async_on_remove(
            self.data.async_subscribe_public(
                self.device.mac, self._async_public_updated
            )
        )
        await super().async_added_to_hass()

    @callback
    @override
    def _async_update_device_from_protect(self, device: ProtectDeviceType) -> None:
        super()._async_update_device_from_protect(device)
        if (public := self._ufp_public_obj) is None:
            return
        light = cast(PublicLight, public)
        self._attr_is_on = light.is_light_on
        led_level = light.light_device_settings.led_level
        self._attr_brightness = (
            None if led_level is None else unifi_brightness_to_hass(led_level)
        )

    @async_ufp_instance_command
    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the light on."""
        brightness = kwargs.get(ATTR_BRIGHTNESS)
        led_level: int | None = None
        if brightness is not None:
            led_level = hass_to_unifi_brightness(brightness)
            _LOGGER.debug(
                "Turning on light with brightness %s (led_level=%s)",
                brightness,
                led_level,
            )
        else:
            _LOGGER.debug("Turning on light")

        # Reachable only while available (public object present); the setter
        # validates the level and writes through the light's own settings.
        await cast(PublicLight, self._ufp_public_obj).set_light(True, led_level)

    @async_ufp_instance_command
    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        _LOGGER.debug("Turning off light")
        await cast(PublicLight, self._ufp_public_obj).set_light(False)
