"""iNELS light."""
from __future__ import annotations

from typing import Any, cast

from inelsmqtt.const import DA3_22M, DA3_66M, FA3_612M, RC3_610DALI, RFDAC_71B
from inelsmqtt.devices import Device

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_TRANSITION,
    ColorMode,
    LightEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .base_class import InelsBaseEntity
from .const import DEVICES, DOMAIN, ICON_FLASH, ICON_LIGHT, LOGGER

bus_lights = [DA3_22M, DA3_66M, RC3_610DALI, FA3_612M]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Load iNELS lights from config entry."""
    device_list: list[Device] = hass.data[DOMAIN][config_entry.entry_id][DEVICES]

    entities: list[InelsBaseEntity] = []
    for device in device_list:
        if device.inels_type in bus_lights:
            dev_val = device.get_value()
            if "out" in dev_val.ha_value.__dict__:
                out_len = len(dev_val.ha_value.out)
                for k in range(len(dev_val.ha_value.out)):
                    entities.append(
                        InelsLightChannel(
                            device,
                            description=InelsLightChannelDescription(
                                out_len,
                                k,
                                ICON_LIGHT,
                                "out",
                                "light",
                            ),
                        )
                    )
            if "dali" in dev_val.ha_value.__dict__:
                out_len = len(dev_val.ha_value.dali)
                for k in range(len(dev_val.ha_value.dali)):
                    entities.append(
                        InelsLightChannel(
                            device,
                            description=InelsLightChannelDescription(
                                out_len,
                                k,
                                ICON_LIGHT,
                                "dali",
                                "DALI",
                            ),
                        )
                    )
            if "aout" in dev_val.ha_value.__dict__:
                out_len = len(dev_val.ha_value.aout)
                for k in range(len(dev_val.ha_value.temps)):
                    entities.append(
                        InelsLightChannel(
                            device,
                            description=InelsLightChannelDescription(
                                out_len, k, ICON_FLASH, "aout", "Analog output"
                            ),
                        )
                    )
        elif device.device_type == Platform.LIGHT:
            entities.append(InelsLight(device))

    async_add_entities(entities)


class InelsLight(InelsBaseEntity, LightEntity):
    """Light class for HA."""

    def __init__(self, device: Device) -> None:
        """Initialize a light."""
        super().__init__(device=device)

        self._attr_supported_color_modes: set[ColorMode] = set()
        if self._device.inels_type is RFDAC_71B:
            self._attr_supported_color_modes.add(ColorMode.BRIGHTNESS)

    @property
    def is_on(self) -> bool:
        """Return true if light is on."""
        return self._device.state > 0

    @property
    def icon(self) -> str | None:
        """Light icon."""
        return ICON_LIGHT

    @property
    def brightness(self) -> int | None:
        """Light brightness."""
        if self._device.inels_type is not RFDAC_71B:
            return None
        return cast(int, self._device.state * 2.55)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Light to turn off."""
        if not self._device:
            return

        transition = None

        if ATTR_TRANSITION in kwargs:
            transition = int(kwargs[ATTR_TRANSITION]) / 0.065
            print(transition)
        else:
            await self.hass.async_add_executor_job(self._device.set_ha_value, 0)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Light to turn on."""
        if not self._device:
            return

        if ATTR_BRIGHTNESS in kwargs:
            brightness = int(kwargs[ATTR_BRIGHTNESS] / 2.55)
            brightness = min(brightness, 100)

            await self.hass.async_add_executor_job(
                self._device.set_ha_value, brightness
            )
        else:
            last_val = self._device.last_values.ha_value
            brightness = 100 if last_val == 0 else last_val
            await self.hass.async_add_executor_job(
                self._device.set_ha_value, brightness
            )


class InelsLightChannelDescription:
    """iNELS light channel description."""

    def __init__(
        self, channel_number: int, channel_index: int, icon: str, var: str, name: str
    ) -> None:
        """Initialize description."""
        self.channel_number = channel_number
        self.channel_index = channel_index
        self.icon = icon
        self.var = var
        self.name = name


class InelsLightChannel(InelsBaseEntity, LightEntity):
    """Light Channel class for HA."""

    _entity_description: InelsLightChannelDescription

    def __init__(
        self, device: Device, description: InelsLightChannelDescription
    ) -> None:
        """Initialize a light."""
        super().__init__(device=device)
        self._entity_description = description

        self._attr_unique_id = (
            f"{self._attr_unique_id}-{description.name}-{description.channel_index}"
        )

        self._attr_name = (
            f"{self._attr_name} {description.name} {description.channel_index + 1}"
        )

        self._attr_supported_color_modes: set[ColorMode] = set()
        if self._device.inels_type in bus_lights:
            self._attr_supported_color_modes.add(ColorMode.BRIGHTNESS)

    @property
    def available(self) -> bool:
        """If it is available."""
        if self._entity_description.var == "out":
            if "toa" in self._device.state.__dict__:
                if self._device.state.toa[self._entity_description.channel_index]:
                    LOGGER.warning("Thermal overload on light %s", self.name)
                    return False
            if "coa" in self._device.state.__dict__:
                if self._device.state.coa[self._entity_description.channel_index]:
                    LOGGER.warning("Current overload on light %s", self.name)
                    return False
        elif self._entity_description.var == "dali":
            if "alert_dali_power" in self._device.state.__dict__:
                if self._device.state.alert_dali_power:
                    LOGGER.warning("Alert dali power")
                    return False
            if "alert_dali_communication" in self._device.state.__dict__:
                if self._device.state.alert_dali_communication:
                    LOGGER.warning("Alert dali communication")
                    return False

        return super().available

    @property
    def is_on(self) -> bool:
        """Return true if light is on."""
        return (
            self._device.state.__dict__[self._entity_description.var][
                self._entity_description.channel_index
            ]
            > 0
        )

    @property
    def icon(self) -> str | None:
        """Light icon."""
        return self._entity_description.icon

    @property
    def brightness(self) -> int | None:
        """Light brightness."""
        if self._device.inels_type not in bus_lights:
            return None
        return cast(
            int,
            self._device.state.__dict__[self._entity_description.var][
                self._entity_description.channel_index
            ]
            * 2.55,
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Light to turn off."""
        if not self._device:
            return

        transition = None
        if ATTR_TRANSITION in kwargs:
            transition = int(kwargs[ATTR_TRANSITION]) / 0.065
            print(transition)
        else:
            # mount device ha value
            ha_val = self._device.get_value().ha_value
            ha_val.__dict__[self._entity_description.var][
                self._entity_description.channel_index
            ] = 0
            await self.hass.async_add_executor_job(self._device.set_ha_value, ha_val)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Light to turn on."""
        if not self._device:
            return

        if ATTR_BRIGHTNESS in kwargs:
            brightness = int(kwargs[ATTR_BRIGHTNESS] / 2.55)
            brightness = min(brightness, 100)

            ha_val = self._device.get_value().ha_value
            ha_val.__dict__[self._entity_description.var][
                self._entity_description.channel_index
            ] = brightness

            await self.hass.async_add_executor_job(self._device.set_ha_value, ha_val)
        else:
            ha_val = self._device.get_value().ha_value

            last_val = self._device.last_values.ha_value

            # uses previously observed value if it isn't 0
            ha_val.__dict__[self._entity_description.var][
                self._entity_description.channel_index
            ] = (
                100
                if last_val.__dict__[self._entity_description.var][
                    self._entity_description.channel_index
                ]
                == 0
                else last_val.__dict__[self._entity_description.var][
                    self._entity_description.channel_index
                ]
            )

            await self.hass.async_add_executor_job(self._device.set_ha_value, ha_val)
