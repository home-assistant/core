"""Identify support for WMS WebControl pro."""

from typing import override

from wmspro.const import WMS_WebControl_pro_API_actionDescription as ACTION_DESC

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
    for dest in hub.dests.values():
        if dest.hasAction(ACTION_DESC.Identify):
            entities.append(WebControlProIdentifyButton(config_entry.entry_id, dest))
        if dest.hasAction(ACTION_DESC.SlatRotate):
            entities.append(
                WebControlProRotationResetButton(config_entry.entry_id, dest)
            )

    async_add_entities(entities)


class WebControlProIdentifyButton(WebControlProGenericEntity, ButtonEntity):
    """Representation of a WMS based identify button."""

    _attr_device_class = ButtonDeviceClass.IDENTIFY

    @override
    async def async_press(self) -> None:
        """Handle the button press to identify the device."""
        action = self._dest.action(ACTION_DESC.Identify)
        await action()


class WebControlProRotationResetButton(WebControlProGenericEntity, ButtonEntity):
    """Representation of a WMS based reset rotation button."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_translation_key = "rotation-reset"

    @override
    async def async_press(self) -> None:
        """Handle the button press to reset the rotation range to the default."""
        action = self._dest.action(ACTION_DESC.SlatRotate)
        # Delete the min and max override values to reset the rotation range to the default
        del action["minValue"]
        del action["maxValue"]
        # The library will take care of the update and persistence on the next poll refresh
