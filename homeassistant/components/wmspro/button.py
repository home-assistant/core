"""Identify support for WMS WebControl pro."""

from wmspro.const import WMS_WebControl_pro_API_actionDescription
from wmspro.destination import Destination

from homeassistant.components.button import ButtonDeviceClass, ButtonEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import WebControlProConfigEntry
from .entity import WebControlProGenericEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: WebControlProConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the WMS based identify buttons from a config entry."""
    hub = config_entry.runtime_data

    entities: list[WebControlProGenericEntity] = []
    for d in hub.dests.values():
        if d.hasAction(WMS_WebControl_pro_API_actionDescription.Identify):
            entities.append(WebControlProIdentifyButton(config_entry.entry_id, d))
        if d.hasAction(WMS_WebControl_pro_API_actionDescription.SlatRotate):
            entities.append(WebControlProRotationResetButton(config_entry.entry_id, d))

    async_add_entities(entities)


class WebControlProIdentifyButton(WebControlProGenericEntity, ButtonEntity):
    """Representation of a WMS based identify button."""

    _attr_device_class = ButtonDeviceClass.IDENTIFY

    async def async_press(self) -> None:
        """Handle the button press to identify the device."""
        action = self._dest.action(WMS_WebControl_pro_API_actionDescription.Identify)
        await action()


class WebControlProRotationResetButton(WebControlProGenericEntity, ButtonEntity):
    """Representation of a WMS based reset rotation button."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_translation_key = "rotation-reset"

    def __init__(self, config_entry_id: str, dest: Destination) -> None:
        """Initialize the entity with destination channel."""
        super().__init__(config_entry_id, dest)
        if self._attr_unique_id:
            self._attr_unique_id += "-rotation-reset"

    async def async_press(self) -> None:
        """Handle the button press to reset the rotation range to the default."""
        action = self._dest.action(WMS_WebControl_pro_API_actionDescription.SlatRotate)
        # Delete the min and max override values to reset the rotation range to the default
        del action["minValue"]
        del action["maxValue"]
