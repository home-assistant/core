"""Platform for siren integration."""

from typing import Any

from devolo_home_control_api.devices.zwave import Zwave
from devolo_home_control_api.homecontrol import HomeControl

from homeassistant.components.siren import ATTR_TONE, SirenEntity, SirenEntityFeature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import DevoloHomeControlConfigEntry
from .devolo_multi_level_switch import DevoloMultiLevelSwitchDeviceEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DevoloHomeControlConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Get all binary sensor and multi level sensor devices and setup them via config entry."""

    async_add_entities(
        DevoloSirenDeviceEntity(
            homecontrol=gateway,
            device_instance=device,
            element_uid=multi_level_switch,
        )
        for gateway in entry.runtime_data
        for device in gateway.multi_level_switch_devices
        for multi_level_switch in device.multi_level_switch_property
        if multi_level_switch.startswith("devolo.SirenMultiLevelSwitch")
    )


class DevoloSirenDeviceEntity(DevoloMultiLevelSwitchDeviceEntity, SirenEntity):
    """Representation of a cover device within devolo Home Control."""

    _attr_supported_features = (
        SirenEntityFeature.TURN_OFF
        | SirenEntityFeature.TURN_ON
        | SirenEntityFeature.TONES
    )

    def __init__(
        self, homecontrol: HomeControl, device_instance: Zwave, element_uid: str
    ) -> None:
        """Initialize a devolo multi level switch."""
        super().__init__(
            homecontrol=homecontrol,
            device_instance=device_instance,
            element_uid=element_uid,
        )
        self._attr_available_tones = [
            *range(
                int(self._multi_level_switch_property.min),
                int(self._multi_level_switch_property.max) + 1,
            )
        ]
        self._default_tone = device_instance.settings_property["tone"].tone

    @property
    def is_on(self) -> bool:
        """Whether the device is on or off."""
        return self._value != 0

    def turn_on(self, **kwargs: Any) -> None:
        """Turn the device off."""
        tone = kwargs.get(ATTR_TONE) or self._default_tone
        self._multi_level_switch_property.set(tone)

    def turn_off(self, **kwargs: Any) -> None:
        """Turn the device off."""
        self._multi_level_switch_property.set(0)

    def _generic_message(self, message: tuple) -> None:
        """Handle generic messages."""
        if message[0].startswith("mss"):
            # The default tone was changed
            self._default_tone = message[1]
        else:
            super()._generic_message(message=message)
