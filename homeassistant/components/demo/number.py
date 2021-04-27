"""Demo platform that offers a fake Number entity."""
import voluptuous as vol

from homeassistant.components.number import NumberEntity
from homeassistant.const import DEVICE_DEFAULT_NAME

from . import DOMAIN


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the demo Number entity."""
    async_add_entities(
        [
            DemoNumber(
                "volume1",
                "volume",
                42.0,
                "mdi:volume-high",
                False,
            ),
            DemoNumber(
                "pwm1",
                "PWM 1",
                0.42,
                "mdi:square-wave",
                False,
                0.0,
                1.0,
                0.01,
            ),
        ]
    )


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Demo config entry."""
    await async_setup_platform(hass, {}, async_add_entities)


class DemoNumber(NumberEntity):
    """Representation of a demo Number entity."""

    def __init__(
        self,
        unique_id,
        name,
        state,
        icon,
        assumed,
        min_value=None,
        max_value=None,
        step=None,
    ):
        """Initialize the Demo Number entity."""
        self._unique_id = unique_id
        self._name = name or DEVICE_DEFAULT_NAME
        self._state = state
        self._icon = icon
        self._assumed = assumed
        self._min_value = min_value
        self._max_value = max_value
        self._step = step

    @property
    def device_info(self):
        """Return device info."""
        return {
            "identifiers": {
                # Serial numbers are unique identifiers within a specific domain
                (DOMAIN, self.unique_id)
            },
            "name": self.name,
        }

    @property
    def unique_id(self):
        """Return the unique id."""
        return self._unique_id

    @property
    def should_poll(self):
        """No polling needed for a demo Number entity."""
        return False

    @property
    def name(self):
        """Return the name of the device if any."""
        return self._name

    @property
    def icon(self):
        """Return the icon to use for device if any."""
        return self._icon

    @property
    def assumed_state(self):
        """Return if the state is based on assumptions."""
        return self._assumed

    @property
    def value(self):
        """Return the current value."""
        return self._state

    @property
    def min_value(self):
        """Return the minimum value."""
        return self._min_value or super().min_value

    @property
    def max_value(self):
        """Return the maximum value."""
        return self._max_value or super().max_value

    @property
    def step(self):
        """Return the value step."""
        return self._step or super().step

    async def async_set_value(self, value):
        """Update the current value."""
        num_value = float(value)

        if num_value < self.min_value or num_value > self.max_value:
            raise vol.Invalid(
                f"Invalid value for {self.entity_id}: {value} (range {self.min_value} - {self.max_value})"
            )

        self._state = num_value
        self.async_write_ha_state()
