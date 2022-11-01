"""Configure number in a device through MQTT topic."""
from __future__ import annotations

import functools
import logging

import voluptuous as vol

from homeassistant.components import number
from homeassistant.components.number import (
    DEFAULT_MAX_VALUE,
    DEFAULT_MIN_VALUE,
    DEFAULT_STEP,
    DEVICE_CLASSES_SCHEMA,
    NumberDeviceClass,
    NumberMode,
    RestoreNumber,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_DEVICE_CLASS,
    CONF_MODE,
    CONF_NAME,
    CONF_OPTIMISTIC,
    CONF_UNIT_OF_MEASUREMENT,
    CONF_VALUE_TEMPLATE,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import subscription
from .config import MQTT_RW_SCHEMA
from .const import (
    CONF_COMMAND_TEMPLATE,
    CONF_COMMAND_TOPIC,
    CONF_ENCODING,
    CONF_QOS,
    CONF_RETAIN,
    CONF_STATE_TOPIC,
)
from .debug_info import log_messages
from .mixins import (
    MQTT_ENTITY_COMMON_SCHEMA,
    MqttEntity,
    async_setup_entry_helper,
    async_setup_platform_helper,
    warn_for_legacy_schema,
)
from .models import MqttCommandTemplate, MqttValueTemplate
from .util import get_mqtt_data

_LOGGER = logging.getLogger(__name__)

CONF_MIN = "min"
CONF_MAX = "max"
CONF_PAYLOAD_RESET = "payload_reset"
CONF_STEP = "step"

DEFAULT_NAME = "MQTT Number"
DEFAULT_OPTIMISTIC = False
DEFAULT_PAYLOAD_RESET = "None"

MQTT_NUMBER_ATTRIBUTES_BLOCKED = frozenset(
    {
        number.ATTR_MAX,
        number.ATTR_MIN,
        number.ATTR_STEP,
    }
)


def validate_config(config):
    """Validate that the configuration is valid, throws if it isn't."""
    if config.get(CONF_MIN) >= config.get(CONF_MAX):
        raise vol.Invalid(f"'{CONF_MAX}' must be > '{CONF_MIN}'")

    return config


_PLATFORM_SCHEMA_BASE = MQTT_RW_SCHEMA.extend(
    {
        vol.Optional(CONF_COMMAND_TEMPLATE): cv.template,
        vol.Optional(CONF_DEVICE_CLASS): DEVICE_CLASSES_SCHEMA,
        vol.Optional(CONF_MAX, default=DEFAULT_MAX_VALUE): vol.Coerce(float),
        vol.Optional(CONF_MIN, default=DEFAULT_MIN_VALUE): vol.Coerce(float),
        vol.Optional(CONF_MODE, default=NumberMode.AUTO): vol.Coerce(NumberMode),
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_OPTIMISTIC, default=DEFAULT_OPTIMISTIC): cv.boolean,
        vol.Optional(CONF_PAYLOAD_RESET, default=DEFAULT_PAYLOAD_RESET): cv.string,
        vol.Optional(CONF_STEP, default=DEFAULT_STEP): vol.All(
            vol.Coerce(float), vol.Range(min=1e-3)
        ),
        vol.Optional(CONF_UNIT_OF_MEASUREMENT): cv.string,
        vol.Optional(CONF_VALUE_TEMPLATE): cv.template,
    },
).extend(MQTT_ENTITY_COMMON_SCHEMA.schema)

PLATFORM_SCHEMA_MODERN = vol.All(
    _PLATFORM_SCHEMA_BASE,
    validate_config,
)

# Configuring MQTT Number under the number platform key is deprecated in HA Core 2022.6
PLATFORM_SCHEMA = vol.All(
    cv.PLATFORM_SCHEMA.extend(_PLATFORM_SCHEMA_BASE.schema),
    validate_config,
    warn_for_legacy_schema(number.DOMAIN),
)

DISCOVERY_SCHEMA = vol.All(
    _PLATFORM_SCHEMA_BASE.extend({}, extra=vol.REMOVE_EXTRA),
    validate_config,
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up MQTT number configured under the number platform key (deprecated)."""
    # Deprecated in HA Core 2022.6
    await async_setup_platform_helper(
        hass,
        number.DOMAIN,
        discovery_info or config,
        async_add_entities,
        _async_setup_entity,
    )


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up MQTT number through configuration.yaml and dynamically through MQTT discovery."""
    setup = functools.partial(
        _async_setup_entity, hass, async_add_entities, config_entry=config_entry
    )
    await async_setup_entry_helper(hass, number.DOMAIN, setup, DISCOVERY_SCHEMA)


async def _async_setup_entity(
    hass: HomeAssistant,
    async_add_entities: AddEntitiesCallback,
    config: ConfigType,
    config_entry: ConfigEntry | None = None,
    discovery_data: dict | None = None,
) -> None:
    """Set up the MQTT number."""
    async_add_entities([MqttNumber(hass, config, config_entry, discovery_data)])


class MqttNumber(MqttEntity, RestoreNumber):
    """representation of an MQTT number."""

    _entity_id_format = number.ENTITY_ID_FORMAT
    _attributes_extra_blocked = MQTT_NUMBER_ATTRIBUTES_BLOCKED

    def __init__(self, hass, config, config_entry, discovery_data):
        """Initialize the MQTT Number."""
        self._config = config
        self._optimistic = False
        self._sub_state = None

        self._current_number = None

        RestoreNumber.__init__(self)
        MqttEntity.__init__(self, hass, config, config_entry, discovery_data)

    @staticmethod
    def config_schema():
        """Return the config schema."""
        return DISCOVERY_SCHEMA

    def _setup_from_config(self, config):
        """(Re)Setup the entity."""
        self._optimistic = config[CONF_OPTIMISTIC]

        self._templates = {
            CONF_COMMAND_TEMPLATE: MqttCommandTemplate(
                config.get(CONF_COMMAND_TEMPLATE), entity=self
            ).async_render,
            CONF_VALUE_TEMPLATE: MqttValueTemplate(
                config.get(CONF_VALUE_TEMPLATE),
                entity=self,
            ).async_render_with_possible_json_value,
        }

    def _prepare_subscribe_topics(self):
        """(Re)Subscribe to topics."""

        @callback
        @log_messages(self.hass, self.entity_id)
        def message_received(msg):
            """Handle new MQTT messages."""
            payload = self._templates[CONF_VALUE_TEMPLATE](msg.payload)
            try:
                if payload == self._config[CONF_PAYLOAD_RESET]:
                    num_value = None
                elif payload.isnumeric():
                    num_value = int(payload)
                else:
                    num_value = float(payload)
            except ValueError:
                _LOGGER.warning("Payload '%s' is not a Number", msg.payload)
                return

            if num_value is not None and (
                num_value < self.min_value or num_value > self.max_value
            ):
                _LOGGER.error(
                    "Invalid value for %s: %s (range %s - %s)",
                    self.entity_id,
                    num_value,
                    self.min_value,
                    self.max_value,
                )
                return

            self._current_number = num_value
            get_mqtt_data(self.hass).state_write_requests.write_state_request(self)

        if self._config.get(CONF_STATE_TOPIC) is None:
            # Force into optimistic mode.
            self._optimistic = True
        else:
            self._sub_state = subscription.async_prepare_subscribe_topics(
                self.hass,
                self._sub_state,
                {
                    "state_topic": {
                        "topic": self._config.get(CONF_STATE_TOPIC),
                        "msg_callback": message_received,
                        "qos": self._config[CONF_QOS],
                        "encoding": self._config[CONF_ENCODING] or None,
                    }
                },
            )

    async def _subscribe_topics(self):
        """(Re)Subscribe to topics."""
        await subscription.async_subscribe_topics(self.hass, self._sub_state)

        if self._optimistic and (
            last_number_data := await self.async_get_last_number_data()
        ):
            self._current_number = last_number_data.native_value

    @property
    def native_min_value(self) -> float:
        """Return the minimum value."""
        return self._config[CONF_MIN]

    @property
    def native_max_value(self) -> float:
        """Return the maximum value."""
        return self._config[CONF_MAX]

    @property
    def native_step(self) -> float:
        """Return the increment/decrement step."""
        return self._config[CONF_STEP]

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the unit of measurement."""
        return self._config.get(CONF_UNIT_OF_MEASUREMENT)

    @property
    def native_value(self) -> float | None:
        """Return the current value."""
        return self._current_number

    @property
    def mode(self) -> NumberMode:
        """Return the mode of the entity."""
        return self._config[CONF_MODE]

    async def async_set_native_value(self, value: float) -> None:
        """Update the current value."""
        current_number = value

        if value.is_integer():
            current_number = int(value)
        payload = self._templates[CONF_COMMAND_TEMPLATE](current_number)

        if self._optimistic:
            self._current_number = current_number
            self.async_write_ha_state()

        await self.async_publish(
            self._config[CONF_COMMAND_TOPIC],
            payload,
            self._config[CONF_QOS],
            self._config[CONF_RETAIN],
            self._config[CONF_ENCODING],
        )

    @property
    def assumed_state(self) -> bool:
        """Return true if we do optimistic updates."""
        return self._optimistic

    @property
    def device_class(self) -> NumberDeviceClass | None:
        """Return the device class of the sensor."""
        return self._config.get(CONF_DEVICE_CLASS)
