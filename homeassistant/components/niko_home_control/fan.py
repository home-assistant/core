from homeassistant.components.fan import FanEntity, FanEntityFeature, ATTR_PERCENTAGE, ATTR_PRESET_MODE
from homeassistant.util.percentage import ordered_list_item_to_percentage, percentage_to_ordered_list_item
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .action import Action
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
        self._attr_action_info = DeviceInfo(
            identifiers={(DOMAIN, action.action_id)},
            manufacturer=hub.manufacturer,
            model=f"{hub.model}-action",
            name=action.name,
        )
        self._attr_supported_features = FanEntityFeature.SET_SPEED | FanEntityFeature.PRESET_MODE

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
        _LOGGER.debug("Turn on: %s", self.name)
        self._action.turn_on(ATTR_PERCENTAGE)

    def turn_off(self, **kwargs: Any) -> None:
        """Instruct the light to turn off."""
        _LOGGER.debug("Turn off: %s", self.name)
        self._action.turn_off()

    @property
    def preset_mode(self) -> str:
        return self._action.fan_speed

    @property
    def supported_features(self):
        """Return supported features."""
        return self._attr_supported_features

    def set_percentage(self, percentage: int) -> None:
        """Set the fan speed preset based on a given percentage"""
        self._action.set_fan_speed(self._gateway, percentage_to_ordered_list_item(self._preset_modes, percentage))

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        self._action.set_fan_speed(self._gateway, preset_mode)
        self.schedule_update_ha_state()

    async def async_set_percentage(self, percentage: int) -> None:
        self._action.set_fan_speed(self._gateway, percentage_to_ordered_list_item(self._preset_modes, percentage))
        self.schedule_update_ha_state()
