"""Matter switches."""
from __future__ import annotations

from dataclasses import dataclass
from functools import partial
from typing import TYPE_CHECKING, Any

from chip.clusters import Objects as clusters
from matter_server.common.models import device_types

from homeassistant.components.switch import (
    SwitchDeviceClass,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import MatterEntity, MatterEntityDescriptionBaseClass

if TYPE_CHECKING:
    from .adapter import MatterAdapter


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Matter switches from Config Entry."""
    matter: MatterAdapter = hass.data[DOMAIN][config_entry.entry_id]
    matter.register_platform_handler(Platform.SWITCH, async_add_entities)


class MatterSwitch(MatterEntity, SwitchEntity):
    """Representation of a Matter switch."""

    entity_description: MatterSwitchEntityDescription

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn switch on."""
        await self.matter_client.send_device_command(
            node_id=self._device_type_instance.node.node_id,
            endpoint=self._device_type_instance.endpoint,
            command=clusters.OnOff.Commands.On(),
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn switch off."""
        await self.matter_client.send_device_command(
            node_id=self._device_type_instance.node.node_id,
            endpoint=self._device_type_instance.endpoint,
            command=clusters.OnOff.Commands.Off(),
        )

    @callback
    def _update_from_device(self) -> None:
        """Update from device."""
        self._attr_is_on = self._device_type_instance.get_cluster(clusters.OnOff).onOff


@dataclass
class MatterSwitchEntityDescription(
    SwitchEntityDescription,
    MatterEntityDescriptionBaseClass,
):
    """Matter Switch entity description."""


# You can't set default values on inherited data classes
MatterSwitchEntityDescriptionFactory = partial(
    MatterSwitchEntityDescription, entity_cls=MatterSwitch
)


DEVICE_ENTITY: dict[
    type[device_types.DeviceType],
    MatterEntityDescriptionBaseClass | list[MatterEntityDescriptionBaseClass],
] = {
    device_types.OnOffPlugInUnit: MatterSwitchEntityDescriptionFactory(
        key=device_types.OnOffPlugInUnit,
        subscribe_attributes=(clusters.OnOff.Attributes.OnOff,),
        device_class=SwitchDeviceClass.OUTLET,
    ),
}
