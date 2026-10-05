"""Platform for light integration."""

from typing import Any, override

from devolo_home_control_api.devices.zwave import Zwave
from devolo_home_control_api.exceptions import SwitchingProtected
from devolo_home_control_api.homecontrol import HomeControl

from homeassistant.components.light import ATTR_BRIGHTNESS, ColorMode, LightEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import DevoloHomeControlConfigEntry
from .const import DOMAIN
from .entity import DevoloMultiLevelSwitchDeviceEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DevoloHomeControlConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Get all light devices and setup them via config entry."""

    async_add_entities(
        DevoloLightDeviceEntity(
            homecontrol=gateway,
            device_instance=device,
            element_uid=multi_level_switch.element_uid,
        )
        for gateway in entry.runtime_data
        for device in gateway.multi_level_switch_devices
        for multi_level_switch in device.multi_level_switch_property.values()
        if multi_level_switch.switch_type == "dimmer"
    )


class DevoloLightDeviceEntity(DevoloMultiLevelSwitchDeviceEntity, LightEntity):
    """Representation of a light within devolo Home Control."""

    _attr_color_mode = ColorMode.BRIGHTNESS

    def __init__(
        self, homecontrol: HomeControl, device_instance: Zwave, element_uid: str
    ) -> None:
        """Initialize a devolo multi level switch."""
        super().__init__(
            homecontrol=homecontrol,
            device_instance=device_instance,
            element_uid=element_uid,
        )

        self._attr_supported_color_modes = {ColorMode.BRIGHTNESS}
        self._binary_switch_property = device_instance.binary_switch_property.get(
            element_uid.replace("Dimmer", "BinarySwitch")
        )

    @property
    @override
    def brightness(self) -> int:
        """Return the brightness value of the light."""
        return round(self._value / 100 * 255)

    @property
    @override
    def is_on(self) -> bool:
        """Return the state of the light."""
        return bool(self._value)

    @override
    def turn_on(self, **kwargs: Any) -> None:
        """Turn device on."""
        if kwargs.get(ATTR_BRIGHTNESS) is not None:
            self._set_brightness(round(kwargs[ATTR_BRIGHTNESS] / 255 * 100))
        else:
            # Turn on the light device to the latest known
            # value. The value is known by the device itself.
            self._set_switch(True)

    @override
    def turn_off(self, **kwargs: Any) -> None:
        """Turn device off."""
        self._set_switch(False)

    def _set_brightness(self, value: int) -> None:
        """Set the brightness to the given value."""
        if not self._multi_level_switch_property.set(value):
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="set_brightness",
            )

    def _set_switch(self, state: bool) -> None:
        """Set the switch to the given state."""
        if self._binary_switch_property is None:
            # Without a binary switch, fall back to full or zero brightness.
            self._set_brightness(100 if state else 0)
            return
        try:
            if not self._binary_switch_property.set(state):
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="set_switch",
                )
        except SwitchingProtected as err:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="switch_protected",
            ) from err
