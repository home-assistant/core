"""Support for LiteJet lights."""
import logging

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_TRANSITION,
    ColorMode,
    LightEntity,
    LightEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_DEFAULT_TRANSITION, DOMAIN

_LOGGER = logging.getLogger(__name__)

ATTR_NUMBER = "number"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up entry."""

    system = hass.data[DOMAIN]

    def get_entities(system):
        entities = []
        for i in system.loads():
            name = system.get_load_name(i)
            entities.append(LiteJetLight(config_entry, system, i, name))
        return entities

    async_add_entities(await hass.async_add_executor_job(get_entities, system), True)


class LiteJetLight(LightEntity):
    """Representation of a single LiteJet light."""

    _attr_color_mode = ColorMode.BRIGHTNESS
    _attr_supported_color_modes = {ColorMode.BRIGHTNESS}
    _attr_supported_features = LightEntityFeature.TRANSITION

    def __init__(self, config_entry, lj, i, name):  # pylint: disable=invalid-name
        """Initialize a LiteJet light."""
        self._config_entry = config_entry
        self._lj = lj
        self._index = i
        self._brightness = 0
        self._name = name

    async def async_added_to_hass(self):
        """Run when this Entity has been added to HA."""
        self._lj.on_load_activated(self._index, self._on_load_changed)
        self._lj.on_load_deactivated(self._index, self._on_load_changed)

    async def async_will_remove_from_hass(self):
        """Entity being removed from hass."""
        self._lj.unsubscribe(self._on_load_changed)

    def _on_load_changed(self):
        """Handle state changes."""
        _LOGGER.debug("Updating due to notification for %s", self._name)
        self.schedule_update_ha_state(True)

    @property
    def name(self):
        """Return the light's name."""
        return self._name

    @property
    def unique_id(self):
        """Return a unique identifier for this light."""
        return f"{self._config_entry.entry_id}_{self._index}"

    @property
    def brightness(self):
        """Return the light's brightness."""
        return self._brightness

    @property
    def is_on(self):
        """Return if the light is on."""
        return self._brightness != 0

    @property
    def should_poll(self):
        """Return that lights do not require polling."""
        return False

    @property
    def extra_state_attributes(self):
        """Return the device state attributes."""
        return {ATTR_NUMBER: self._index}

    def turn_on(self, **kwargs):
        """Turn on the light."""

        # If neither attribute is specified then the simple activate load
        # LiteJet API will use the per-light default brightness and
        # transition values programmed in the LiteJet system.
        if ATTR_BRIGHTNESS not in kwargs and ATTR_TRANSITION not in kwargs:
            self._lj.activate_load(self._index)
            return

        # If either attribute is specified then Home Assistant must
        # control both values.
        default_transition = self._config_entry.options.get(CONF_DEFAULT_TRANSITION, 0)
        transition = kwargs.get(ATTR_TRANSITION, default_transition)
        brightness = int(kwargs.get(ATTR_BRIGHTNESS, 255) / 255 * 99)

        self._lj.activate_load_at(self._index, brightness, int(transition))

    def turn_off(self, **kwargs):
        """Turn off the light."""
        if ATTR_TRANSITION in kwargs:
            self._lj.activate_load_at(self._index, 0, kwargs[ATTR_TRANSITION])
            return

        # If transition attribute is not specified then the simple
        # deactivate load LiteJet API will use the per-light default
        # transition value programmed in the LiteJet system.
        self._lj.deactivate_load(self._index)

    def update(self):
        """Retrieve the light's brightness from the LiteJet system."""
        self._brightness = int(self._lj.get_load_level(self._index) / 99 * 255)
