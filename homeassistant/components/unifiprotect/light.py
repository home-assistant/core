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
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DEFAULT_BRAND, DOMAIN
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
        if isinstance(device, PublicLight):
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
    # State comes from the public API; the base class primes the object and
    # subscribes to the public devices websocket on this flag.
    _ufp_uses_public = True

    def __init__(
        self,
        data: ProtectData,
        public: PublicLight | None,
        private: Light | None,
    ) -> None:
        """Initialize the light."""
        self._private = private
        self._ufp_public_obj = public
        # unique_id and device info derive from the base device, so hybrid must
        # keep the private one to leave existing entities unchanged.
        super().__init__(data, cast(ProtectDeviceType, private or public))

    @callback
    @override
    def _async_set_device_info(self) -> None:
        if self._private is not None:
            super()._async_set_device_info()
            return
        # market_name/firmware/URL are private-only; the NVR link uses the
        # device id registered at setup.
        public = cast(PublicLight, self.device)
        self._attr_device_info = DeviceInfo(
            name=public.display_name,
            model=public.type,
            model_id=public.type,
            manufacturer=DEFAULT_BRAND,
            connections={(dr.CONNECTION_NETWORK_MAC, public.mac)},
            via_device_id=self.data.nvr_device_id,
        )

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

    def _public_or_raise(self) -> PublicLight:
        """Return the public object, or raise if it vanished mid-command."""
        if (public := self._ufp_public_obj) is None:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="light_not_available",
                translation_placeholders={"light_name": self.device.display_name},
            )
        return cast(PublicLight, public)

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

        # led_level is range-checked by the setter, not by HA.
        await self._public_or_raise().set_light(True, led_level)

    @async_ufp_instance_command
    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        _LOGGER.debug("Turning off light")
        await self._public_or_raise().set_light(False)
