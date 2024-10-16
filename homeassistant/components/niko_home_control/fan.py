from homeassistant.components.fan import FanEntity, FanEntityFeature, ATTR_PERCENTAGE, ATTR_PRESET_MODE
from homeassistant.util.percentage import ordered_list_item_to_percentage, percentage_to_ordered_list_item
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from typing import Any
from .const import DOMAIN

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Niko Home Control light platform."""
    hub = hass.data[DOMAIN][entry.entry_id]
    entities = []

    for action in hub.actions:
        entity = None
        action_type = action.action_type
        if action_type == 3:
            NikoHomeControlFan(action, hub)

        if entity:
            hub.entities.append(entity)
            entities.append(entity)

    async_add_entities(entities, True)


class NikoHomeControlFan(FanEntity):
    def __init__(self, action, hub):
        """Set up the Niko Home Control action platform."""
        self._hub = hub
        self._action = action
        self._attr_name = action.name
        self._attr_is_on = action.is_on
        self._attr_unique_id = f"fan-{action.action_id}"
        self._fan_speed = action.state

        self._attr_action_info = DeviceInfo(
            identifiers={(DOMAIN, action.action_id)},
            manufacturer=hub.manufacturer,
            model=f"{hub.model}-action",
            name=action.name,
        )
        self._attr_supported_features = FanEntityFeature.SET_SPEED | FanEntityFeature.PRESET_MODE
        self._preset_modes = ["low", "medium", "high", "very_high"]

    @property
    def should_poll(self) -> bool:
        """No polling needed for a Niko light."""
        return False

    @property
    def id(self):
        """A Niko Action action_id."""
        return self._action.action_id

    def turn_on(self, **kwargs: Any) -> None:
        """Instruct the light to turn on."""
        self._action.turn_on(ATTR_PERCENTAGE)

    def turn_off(self, **kwargs: Any) -> None:
        """Instruct the light to turn off."""
        self._action.turn_off()

    @property
    def preset_mode(self) -> str:
        return self._fan_speed

    @property
    def supported_features(self):
        """Return supported features."""
        return self._attr_supported_features

    def set_percentage(self, percentage: int) -> None:
        """Set the fan speed preset based on a given percentage"""
        mode = percentage_to_ordered_list_item(self._preset_modes, percentage)
        if mode == "low":
            self._action.set_fan_speed(0)
        elif mode == "medium":
            self._action.set_fan_speed(1)
        elif mode == "high":
            self._action.set_fan_speed(2)
        elif mode == "very_high":
            self._action.set_fan_speed(3)

        self.schedule_update_ha_state()

    def set_preset_mode(self, preset_mode: str) -> None:
        if preset_mode == "low":
            self._action.set_fan_speed(0)
        elif preset_mode == "medium":
            self._action.set_fan_speed(1)
        elif preset_mode == "high":
            self._action.set_fan_speed(2)
        elif preset_mode == "very_high":
            self._action.set_fan_speed(3)

        self.schedule_update_ha_state()
