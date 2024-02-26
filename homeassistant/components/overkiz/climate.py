"""Support for Overkiz climate devices."""
from __future__ import annotations

from typing import cast

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import HomeAssistantOverkizData
from .climate_entities import (
    WIDGET_AND_CONTROLLABLE_TO_CLIMATE_ENTITY,
    WIDGET_AND_PROTOCOL_TO_CLIMATE_ENTITY,
    WIDGET_TO_CLIMATE_ENTITY,
    Controllable,
)
from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Overkiz climate from a config entry."""
    data: HomeAssistantOverkizData = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        WIDGET_TO_CLIMATE_ENTITY[device.widget](device.device_url, data.coordinator)
        for device in data.platforms[Platform.CLIMATE]
        if device.widget in WIDGET_TO_CLIMATE_ENTITY
    )

    # Match devices based on the widget and controllableName
    # This is for example used for Atlantic APC, where devices with different functionality share the same uiClass and widget.
    async_add_entities(
        WIDGET_AND_CONTROLLABLE_TO_CLIMATE_ENTITY[device.widget][
            cast(Controllable, device.controllable_name)
        ](device.device_url, data.coordinator)
        for device in data.platforms[Platform.CLIMATE]
        if device.widget in WIDGET_AND_CONTROLLABLE_TO_CLIMATE_ENTITY
        and device.controllable_name
        in WIDGET_AND_CONTROLLABLE_TO_CLIMATE_ENTITY[device.widget]
    )

    # Hitachi Air To Air Heat Pumps
    async_add_entities(
        WIDGET_AND_PROTOCOL_TO_CLIMATE_ENTITY[device.widget][device.protocol](
            device.device_url, data.coordinator
        )
        for device in data.platforms[Platform.CLIMATE]
        if device.widget in WIDGET_AND_PROTOCOL_TO_CLIMATE_ENTITY
        and device.protocol in WIDGET_AND_PROTOCOL_TO_CLIMATE_ENTITY[device.widget]
    )
