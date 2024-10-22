"""Setup NikoHomeControlFan."""
from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.percentage import percentage_to_ordered_list_item

from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Niko Home Control fan platform."""
    hub = hass.data[DOMAIN][entry.entry_id]["hub"]
    enabled_entities = hass.data[DOMAIN][entry.entry_id]["enabled_entities"]
    if enabled_entities["fans"] is False:
        return

    entities: list[NikoHomeControlFan] = []

    for action in hub.actions:
        entity = None
        action_type = action.action_type
        if action_type == 3:
            entity = NikoHomeControlFan(action, hub, options=entry.data["options"])

        if entity:
            hub.entities.append(entity)
            entities.append(entity)

    async_add_entities(entities, True)


class NikoHomeControlFan(FanEntity):
    """Representation of an Niko fan."""

    def __init__(self, action, hub, options):
        """Set up the Niko Home Control action platform."""
        self._hub = hub
        self._action = action
        self._attr_name = action.name
        self._attr_is_on = action.is_on
        self._attr_unique_id = f"fan-{action.action_id}"
        self._attr_speed_count = 3
        self._enable_turn_on_off_backwards_compatibility = False
        self._attr_supported_features = (
            FanEntityFeature.SET_SPEED
        )
        self._percentages = [33, 66, 100]
        self._attr_percentage = self._percentages[action.state]

        area = None
        if options["importLocations"] is not False:
            area = action.location
        if options["treatAsDevice"] is not False:
            self._attr_device_info = {
                "identifiers": {(DOMAIN, self._attr_unique_id)},
                "manufacturer": "Niko",
                "name": action.name,
                "model": "P.O.M",
                "suggested_area": action.location,
                "via_device": hub._via_device,
                "suggested_area": area,
            }
        else:
            self._attr_device_info = hub._device_info

    @property
    def should_poll(self) -> bool:
        """No polling needed for a Niko light."""
        return False

    @property
    def id(self):
        """A Niko Action action_id."""
        return self._action.action_id

    @property
    def supported_features(self):
        """Return supported features."""
        return self._attr_supported_features

    def set_percentage(self, percentage: int) -> None:
        """Set the fan speed preset based on a given percentage."""
        mode = 0 # low
        if percentage > 67:
            mode = 2 # high
        elif percentage <= 67 and percentage > 33:
            mode = 1 # medium

        self._attr_percentage = self._percentages[mode]
        self._action.set_fan_speed(mode)
        self.schedule_update_ha_state()

    def update_state(self, state):
        """Update HA state."""
        if state > 2: # map "boost" to high state
            state = 2

        self._attr_percentage = self._percentages[state]
        self.async_write_ha_state()

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the speed of the fan, as a percentage."""
        """Implemeted here as we do not want to call turn_off() when percentage == 0"""
        await self.hass.async_add_executor_job(self.set_percentage, percentage)