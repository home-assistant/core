"""Matter light."""
from __future__ import annotations

from dataclasses import dataclass
from functools import partial
from typing import TYPE_CHECKING, Any

from chip.clusters import Objects as clusters
from matter_server.common.models import device_types

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ColorMode,
    LightEntity,
    LightEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import MatterEntity, MatterEntityDescriptionBaseClass
from .util import renormalize

if TYPE_CHECKING:
    from .adapter import MatterAdapter


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Matter Light from Config Entry."""
    matter: MatterAdapter = hass.data[DOMAIN][config_entry.entry_id]
    matter.register_platform_handler(Platform.LIGHT, async_add_entities)


class MatterLight(MatterEntity, LightEntity):
    """Representation of a Matter light."""

    entity_description: MatterLightEntityDescription

    def _supports_brightness(self) -> bool:
        """Return if device supports brightness."""
        return (
            clusters.LevelControl.Attributes.CurrentLevel
            in self.entity_description.subscribe_attributes
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn light on."""
        if ATTR_BRIGHTNESS not in kwargs or not self._supports_brightness():
            await self.matter_client.send_device_command(
                node_id=self._device_type_instance.node.node_id,
                endpoint=self._device_type_instance.endpoint,
                command=clusters.OnOff.Commands.On(),
            )
            return

        level_control = self._device_type_instance.get_cluster(clusters.LevelControl)
        level = round(
            renormalize(
                kwargs[ATTR_BRIGHTNESS],
                (0, 255),
                (level_control.minLevel, level_control.maxLevel),
            )
        )

        await self.matter_client.send_device_command(
            node_id=self._device_type_instance.node.node_id,
            endpoint=self._device_type_instance.endpoint,
            command=clusters.LevelControl.Commands.MoveToLevelWithOnOff(
                level=level,
                # It's required in TLV. We don't implement transition time yet.
                transitionTime=0,
            ),
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn light off."""
        await self.matter_client.send_device_command(
            node_id=self._device_type_instance.node.node_id,
            endpoint=self._device_type_instance.endpoint,
            command=clusters.OnOff.Commands.Off(),
        )

    @callback
    def _update_from_device(self) -> None:
        """Update from device."""
        if self._attr_supported_color_modes is None:
            if self._supports_brightness():
                self._attr_supported_color_modes = {ColorMode.BRIGHTNESS}

        if attr := self.get_matter_attribute(clusters.OnOff.Attributes.OnOff):
            self._attr_is_on = attr.value

        if (
            clusters.LevelControl.Attributes.CurrentLevel
            in self.entity_description.subscribe_attributes
        ):
            level_control = self._device_type_instance.get_cluster(
                clusters.LevelControl
            )

            # Convert brightness to Home Assistant = 0..255
            self._attr_brightness = round(
                renormalize(
                    level_control.currentLevel,
                    (level_control.minLevel, level_control.maxLevel),
                    (0, 255),
                )
            )


@dataclass
class MatterLightEntityDescription(
    LightEntityDescription,
    MatterEntityDescriptionBaseClass,
):
    """Matter light entity description."""


# You can't set default values on inherited data classes
MatterLightEntityDescriptionFactory = partial(
    MatterLightEntityDescription, entity_cls=MatterLight
)

# Mapping of a Matter Device type to Light Entity Description.
# A Matter device type (instance) can consist of multiple attributes.
# For example a Color Light which has an attribute to control brightness
# but also for color.

DEVICE_ENTITY: dict[
    type[device_types.DeviceType],
    MatterEntityDescriptionBaseClass | list[MatterEntityDescriptionBaseClass],
] = {
    device_types.OnOffLight: MatterLightEntityDescriptionFactory(
        key=device_types.OnOffLight,
        subscribe_attributes=(clusters.OnOff.Attributes.OnOff,),
    ),
    device_types.DimmableLight: MatterLightEntityDescriptionFactory(
        key=device_types.DimmableLight,
        subscribe_attributes=(
            clusters.OnOff.Attributes.OnOff,
            clusters.LevelControl.Attributes.CurrentLevel,
        ),
    ),
    device_types.DimmablePlugInUnit: MatterLightEntityDescriptionFactory(
        key=device_types.DimmablePlugInUnit,
        subscribe_attributes=(
            clusters.OnOff.Attributes.OnOff,
            clusters.LevelControl.Attributes.CurrentLevel,
        ),
    ),
    device_types.ColorTemperatureLight: MatterLightEntityDescriptionFactory(
        key=device_types.ColorTemperatureLight,
        subscribe_attributes=(
            clusters.OnOff.Attributes.OnOff,
            clusters.LevelControl.Attributes.CurrentLevel,
            clusters.ColorControl,
        ),
    ),
    device_types.ExtendedColorLight: MatterLightEntityDescriptionFactory(
        key=device_types.ExtendedColorLight,
        subscribe_attributes=(
            clusters.OnOff.Attributes.OnOff,
            clusters.LevelControl.Attributes.CurrentLevel,
            clusters.ColorControl,
        ),
    ),
}
