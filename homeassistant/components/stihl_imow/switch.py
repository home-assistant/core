"""Platform for sensor integration."""
import logging

from imow.common.mowerstate import MowerState

from homeassistant import config_entries, core
from homeassistant.components.switch import SwitchEntity
from homeassistant.const import STATE_OFF, STATE_ON

from . import extract_properties_by_type
from .const import DOMAIN
from .entity import ImowBaseEntity
from .maps import IMOW_SENSORS_MAP

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: core.HomeAssistant,
    config_entry: config_entries.ConfigEntry,
    async_add_entities,
):
    """Add sensors for passed config_entry in HA."""
    config = hass.data[DOMAIN][config_entry.entry_id]

    coordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]
    switch_entities = {}
    mower_state: MowerState = config["coordinator"].data
    entities, device = extract_properties_by_type(mower_state, bool)

    for entity in entities:
        if IMOW_SENSORS_MAP[entity]["switch"]:
            switch_entities[entity] = entities[entity]

    async_add_entities(
        ImowSwitchSensorEntity(coordinator, device, idx, mower_state_property)
        for idx, mower_state_property in enumerate(switch_entities)
    )


class ImowSwitchSensorEntity(ImowBaseEntity, SwitchEntity):
    """Representation of a Sensor."""

    def __init__(self, coordinator, device_info, idx, mower_state_property):
        """Override the BaseEntity with Switch Entity content."""
        super().__init__(coordinator, device_info, idx, mower_state_property)
        self._is_on = self.sensor_data.__dict__[self.property_name]
        self.api = self.coordinator.data.imow
        self._state = STATE_ON if self._is_on else STATE_OFF

    @property
    def state(self):
        """Return the state of the entity."""
        return self._state

    @property
    def is_on(self) -> bool:
        """State of the entity."""
        return self._is_on

    async def async_turn_on(self, **kwargs):
        """Turn the entity on."""
        new_mower_state: MowerState = await self.api.update_setting(
            self.key_device_infos["id"], self.property_name, True
        )
        self._is_on = new_mower_state.__dict__[self.property_name]
        self._state = STATE_ON if self._is_on else STATE_OFF

    async def async_turn_off(self, **kwargs):
        """Turn the entity off."""
        new_mower_state: MowerState = await self.api.update_setting(
            self.key_device_infos["id"], self.property_name, False
        )

        self._is_on = new_mower_state.__dict__[self.property_name]
        self._state = STATE_ON if self._is_on else STATE_OFF
