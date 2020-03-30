"""Component to interface with switches that can be controlled remotely."""
from datetime import timedelta
import logging
import typing

import voluptuous as vol

from homeassistant.const import (
    ATTR_EDITABLE,
    ATTR_MODE,
    ATTR_UNIT_OF_MEASUREMENT,
    CONF_ICON,
    CONF_MAXIMUM,
    CONF_MINIMUM,
    CONF_MODE,
    CONF_NAME,
    SERVICE_TOGGLE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.config_validation import (  # noqa: F401
    PLATFORM_SCHEMA,
    PLATFORM_SCHEMA_BASE,
    make_entity_service_schema,
)
from homeassistant.helpers.entity import ToggleEntity
from homeassistant.helpers.entity_component import EntityComponent

# mypy: allow-untyped-defs, no-check-untyped-defs

DOMAIN = "analog_output"
SCAN_INTERVAL = timedelta(seconds=30)
ENTITY_ID_FORMAT = DOMAIN + ".{}"

CONF_INITIAL_VALUE = "initial_value"
CONF_INITIAL_STATE = "initial_state"

CONF_STEP = "step"

MODE_SLIDER = "slider"
MODE_BOX = "box"

ATTR_INITIAL = "initial"
ATTR_VALUE = "value"
ATTR_VALUE_PCT = "value_pct"
ATTR_MINIMAL = "min"
ATTR_MAXIMAL = "max"
ATTR_STEP = "step"

SERVICE_SET_VALUE = "set_value"
SERVICE_INCREMENT = "increment"
SERVICE_DECREMENT = "decrement"


def _cv_input_number(cfg):
    """Configure validation helper for input number (voluptuous)."""
    minimum = cfg.get(CONF_MINIMUM)
    maximum = cfg.get(CONF_MAXIMUM)
    if minimum >= maximum:
        raise vol.Invalid(
            f"Maximum ({minimum}) is not greater than minimum ({maximum})"
        )
    state = cfg.get(CONF_INITIAL_VALUE)
    if state is not None and (state < minimum or state > maximum):
        raise vol.Invalid(f"Initial value {state} not in range {minimum}-{maximum}")
    state = cfg.get(CONF_INITIAL_STATE)
    if state is not None and (state < minimum or state > maximum):
        raise vol.Invalid(f"Initial state {state} not in range {minimum}-{maximum}")

    return cfg


VALID_VALUE_PCT = vol.All(vol.Coerce(float), vol.Range(min=0, max=100))

OUTPUT_TURN_ON_SCHEMA = {
    vol.Exclusive(ATTR_VALUE, ATTR_VALUE): int,
    vol.Exclusive(ATTR_VALUE_PCT, ATTR_VALUE): VALID_VALUE_PCT,
}


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_NAME): cv.string,
        vol.Optional(CONF_MINIMUM, default=0): vol.Coerce(float),
        vol.Optional(CONF_MAXIMUM, default=255): vol.Coerce(float),
        vol.Optional(CONF_INITIAL_VALUE, default=100): vol.Coerce(float),
        vol.Optional(CONF_INITIAL_STATE, default=0): vol.Coerce(float),
        vol.Optional(CONF_STEP, default=1): vol.All(
            vol.Coerce(float), vol.Range(min=1e-3)
        ),
        vol.Optional(CONF_MODE, default=MODE_SLIDER): vol.In([MODE_BOX, MODE_SLIDER]),
        vol.Optional(CONF_ICON): cv.icon,
    },
    _cv_input_number,
)


_LOGGER = logging.getLogger(__name__)


async def async_setup(hass, config):
    """Track states and offer events for switches."""
    component = hass.data[DOMAIN] = EntityComponent(
        _LOGGER, DOMAIN, hass, SCAN_INTERVAL
    )
    await component.async_setup(config)

    async def async_handle_output_on_service(output, call):
        """Handle turning an analog output on.

        If value is set to 0, this service will turn the output off.
        """
        # Copy attributes to adict that we can modify
        data_cp = {}
        for entity_field in call.data:
            data_cp[entity_field] = call.data[entity_field]

        value_pct = data_cp.pop(ATTR_VALUE_PCT, None)
        if value_pct is not None:
            data_cp[ATTR_VALUE] = float(
                output.minimum + ((output.maximum - output.minimum) * value_pct / 100.0)
            )

        value = data_cp.get(ATTR_VALUE, None)
        if value == 0:
            await output.async_turn_off()
        else:
            await output.async_turn_on(**data_cp)

    component.async_register_entity_service(
        SERVICE_TURN_ON,
        vol.All(cv.make_entity_service_schema(OUTPUT_TURN_ON_SCHEMA)),
        async_handle_output_on_service,
    )

    component.async_register_entity_service(SERVICE_TURN_OFF, {}, "async_turn_off")

    component.async_register_entity_service(
        SERVICE_TOGGLE, OUTPUT_TURN_ON_SCHEMA, "async_toggle"
    )

    component.async_register_entity_service(
        SERVICE_SET_VALUE,
        {vol.Required(ATTR_VALUE): vol.Coerce(float)},
        "async_set_value",
    )

    component.async_register_entity_service(SERVICE_INCREMENT, {}, "async_increment")

    component.async_register_entity_service(SERVICE_DECREMENT, {}, "async_decrement")

    return True


async def async_setup_entry(hass, entry):
    """Set up a config entry."""
    return await hass.data[DOMAIN].async_setup_entry(entry)


async def async_unload_entry(hass, entry):
    """Unload a config entry."""
    return await hass.data[DOMAIN].async_unload_entry(entry)


class AnalogOutputDevice(ToggleEntity):
    """Representation of an analog output device."""

    def __init__(self, config: typing.Dict):
        """Initialize analog output entity."""
        self._config = config
        self._name = config[CONF_NAME]
        self.editable = True
        self._value = config[CONF_INITIAL_STATE]
        self._restore_value = config[CONF_INITIAL_VALUE]

    @property
    def should_poll(self):
        """If entity should be polled."""
        return False

    @property
    def state(self):
        """Return the value this device between min..max."""
        return self._value

    @property
    def minimum(self) -> float:
        """Return minimum allowed value."""
        return self._config[CONF_MINIMUM]

    @property
    def maximum(self) -> float:
        """Return maximum allowed value."""
        return self._config[CONF_MAXIMUM]

    @property
    def name(self):
        """Name of the device."""
        return self._name

    @property
    def step(self) -> int:
        """Return entity's increment/decrement step."""
        return self._config[CONF_STEP]

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return self._config.get(ATTR_UNIT_OF_MEASUREMENT)

    @property
    def is_on(self):
        """Return true if the analog output is switched on."""
        return self._value != 0

    @property
    def icon(self):
        """Return the icon to be used for this entity."""
        return self._config.get(CONF_ICON)

    @property
    def state_attributes(self):
        """Return the optional state attributes."""
        return {
            ATTR_VALUE: self._restore_value,
            ATTR_INITIAL: self._config.get(CONF_INITIAL_VALUE),
            ATTR_EDITABLE: self.editable,
            ATTR_MINIMAL: self.minimum,
            ATTR_MAXIMAL: self.maximum,
            ATTR_STEP: self.step,
            ATTR_MODE: self._config[CONF_MODE],
        }

    async def async_set_value(self, value):
        """Set new value."""
        num_value = float(value)
        if num_value < self.minimum or num_value > self.maximum:
            raise vol.Invalid(
                f"Invalid value for {self.entity_id}: {value} (range {self.minimum} - {self.maximum})"
            )
        # Only set actual value if in on-state
        if self._value != 0:
            self._value = num_value
        if num_value != 0:
            self._restore_value = num_value
        self.async_write_ha_state()

    async def async_increment(self):
        """Increment value."""
        await self.async_set_value(min(self._value + self.step, self.maximum))

    async def async_decrement(self):
        """Decrement value."""
        await self.async_set_value(max(self._value - self.step, self.minimum))

    async def async_update_config(self, config: typing.Dict) -> None:
        """Handle when the config is updated."""
        self._config = config
        # just in case min/max values changed
        self._value = min(self._value, self.maximum)
        self._value = max(self._value, self.minimum)
        self._restore_value = self._value
        self.async_write_ha_state()

    async def turn_on(self, **kwargs):
        """Turn the switch on."""
        # If value was given in argumenst, set value. Else use restore_value
        value = kwargs.get(ATTR_VALUE, None)
        if value is None:
            value = self._restore_value
        else:
            self._restore_value = value
        num_value = float(value)
        if num_value < self.minimum or num_value > self.maximum:
            raise vol.Invalid(
                f"Invalid value for {self.entity_id}: {value} (range {self.minimum} - {self.maximum})"
            )
        self._value = value
        self.async_write_ha_state()

    async def turn_off(self, **kwargs):
        """Turn the switch off."""
        self._value = 0
        self.async_write_ha_state()
