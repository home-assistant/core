"""Platform for light integration."""
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    SUPPORT_BRIGHTNESS,
    LightEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.typing import HomeAssistantType

from .const import DOMAIN
from .devolo_multi_level_switch import DevoloMultiLevelSwitchDeviceEntity


async def async_setup_entry(
    hass: HomeAssistantType, entry: ConfigEntry, async_add_entities
) -> None:
    """Get all light devices and setup them via config entry."""
    entities = []

    for device in hass.data[DOMAIN]["homecontrol"].multi_level_switch_devices:
        for multi_level_switch in device.multi_level_switch_property.values():
            if multi_level_switch.switch_type == "dimmer":
                entities.append(
                    DevoloLightDeviceEntity(
                        homecontrol=hass.data[DOMAIN]["homecontrol"],
                        device_instance=device,
                        element_uid=multi_level_switch.element_uid,
                    )
                )

    async_add_entities(entities, False)


class DevoloLightDeviceEntity(DevoloMultiLevelSwitchDeviceEntity, LightEntity):
    """Representation of a light within devolo Home Control."""

    def __init__(self, homecontrol, device_instance, element_uid):
        """Initialize a devolo multi level switch."""
        super().__init__(
            homecontrol=homecontrol,
            device_instance=device_instance,
            element_uid=element_uid,
        )

        self._binary_switch_property = device_instance.binary_switch_property.get(
            element_uid.replace("Dimmer", "BinarySwitch")
        )

    @property
    def brightness(self):
        """Return the brightness value of the light."""
        return round(self._value / 100 * 255)

    @property
    def is_on(self):
        """Return the state of the light."""
        return bool(self._value)

    @property
    def supported_features(self):
        """Return the supported features."""
        return SUPPORT_BRIGHTNESS

    def turn_on(self, **kwargs) -> None:
        """Turn device on."""
        if kwargs.get(ATTR_BRIGHTNESS) is not None:
            self._multi_level_switch_property.set(
                round(kwargs[ATTR_BRIGHTNESS] / 255 * 100)
            )
        else:
            if self._binary_switch_property is not None:
                # Turn on the light device to the latest known value. The value is known by the device itself.
                self._binary_switch_property.set(True)
            else:
                # If there is no binary switch attached to the device, turn it on to 100 %.
                self._multi_level_switch_property.set(100)

    def turn_off(self, **kwargs) -> None:
        """Turn device off."""
        self._multi_level_switch_property.set(0)
