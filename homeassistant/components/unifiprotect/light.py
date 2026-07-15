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
        # A re-added light overlaps the entity kept from before its removal;
        # the platform rejects the duplicate unique_id with an error, so add
        # only if the mac is not represented yet.
        if any(e.unique_id == device.mac for e in platform.entities.values()):
            return
        async_add_entities([ProtectLight(data, device, None)])

    data.async_subscribe_adopt(_add_new_device)
    entry.async_on_unload(
        async_dispatcher_connect(hass, data.public_add_signal, _add_new_public_device)
    )

    entities: list[ProtectLight] = []
    # Public-master enumeration: iterate the public light list; the private
    # light is paired by shared id (fill) and is None in public-only mode.
    for public, private in data.get_public_lights():
        if private is None:
            # Hybrid: a light not yet in the private bootstrap (adopt race) is
            # created by the adopt dispatch with its private fill, which would
            # otherwise collide on unique_id. In public-only mode every pair
            # carries the public object, so create from it directly.
            if data.api.is_public_only:
                entities.append(ProtectLight(data, public, None))
            continue
        # A private light without a public mirror is still created: the entity
        # reads state from the public object and stays unavailable until its
        # mirror arrives on the public devices websocket (paired by mac).
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
        """Initialize the light.

        The public light is the master; the private light fills gaps the
        public API does not cover and is ``None`` in public-only mode.
        """
        self._private = private
        # Seed the public object; ``async_added_to_hass`` re-reads it from the
        # bootstrap so an update between construction and add is not missed.
        self._ufp_public_obj = public
        # The base tracks the private device in hybrid (unchanged behaviour) and
        # the public device in public-only, so it always has a mac to key on.
        super().__init__(data, cast(ProtectDeviceType, private or public))

    @callback
    @override
    def _async_set_device_info(self) -> None:
        if self._private is not None:
            super()._async_set_device_info()
            return
        # public-only: no market_name/firmware_version/protect_url, and the
        # NVR link is omitted — an API-key-only client has no private
        # bootstrap to read the NVR mac from.
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

        # Copy the device's own settings type (private in hybrid, public in
        # public-only — each serializes its own units) with the new LED level.
        await self.device.api.update_light_public(
            self.device.id,
            is_light_force_enabled=True,
            light_device_settings=(
                self.device.light_device_settings.model_copy(
                    update={"led_level": led_level}
                )
                if led_level is not None
                else None
            ),
        )

    @async_ufp_instance_command
    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        _LOGGER.debug("Turning off light")
        await self.device.api.update_light_public(
            self.device.id, is_light_force_enabled=False
        )
