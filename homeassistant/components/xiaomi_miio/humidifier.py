"""Support for Xiaomi Mi Air Purifier and Xiaomi Mi Air Humidifier with humidifier entity."""
import asyncio
from enum import Enum
from functools import partial
import logging

from miio import AirHumidifier, AirHumidifierMiot, DeviceException
from miio.airhumidifier import OperationMode as AirhumidifierOperationMode
from miio.airhumidifier_miot import OperationMode as AirhumidifierMiotOperationMode
import voluptuous as vol

from homeassistant.components.humidifier import (
    PLATFORM_SCHEMA,
    SUPPORT_MODES,
    HumidifierEntity,
)
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_MODE,
    CONF_HOST,
    CONF_NAME,
    CONF_TOKEN,
)
import homeassistant.helpers.config_validation as cv

from .const import (
    CONF_DEVICE,
    CONF_FLOW_TYPE,
    DOMAIN,
    MODEL_AIRHUMIDIFIER_CA1,
    MODEL_AIRHUMIDIFIER_CA4,
    MODEL_AIRHUMIDIFIER_CB1,
    MODELS_FAN,
    MODELS_HUMIDIFIER_MIOT,
    SERVICE_SET_TARGET_HUMIDITY,
)
from .device import XiaomiMiioEntity

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "Xiaomi Miio Device"
DATA_KEY = "fan.xiaomi_miio"

CONF_MODEL = "model"


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_TOKEN): vol.All(cv.string, vol.Length(min=32, max=32)),
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_MODEL): vol.In(MODELS_FAN),
    }
)

ATTR_MODEL = "model"

# Air Humidifier
ATTR_TARGET_HUMIDITY = "target_humidity"
ATTR_TRANS_LEVEL = "trans_level"
ATTR_HARDWARE_VERSION = "hardware_version"

SUCCESS = ["ok"]

SERVICE_TO_METHOD = {
    SERVICE_SET_TARGET_HUMIDITY: {
        "method": "async_set_target_humidity",
    },
}

AVAILABLE_ATTRIBUTES = {
    ATTR_MODE: "mode",
    ATTR_TARGET_HUMIDITY: "target_humidity",
}

AIRHUMIDIFIER_SERVICE_SCHEMA = vol.Schema({vol.Optional(ATTR_ENTITY_ID): cv.entity_ids})


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Import Miio configuration from YAML."""
    _LOGGER.warning(
        "Loading Xiaomi Miio Fan via platform setup is deprecated. "
        "Please remove it from your configuration"
    )
    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data=config,
        )
    )


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Fan from a config entry."""
    entities = []

    if config_entry.data[CONF_FLOW_TYPE] == CONF_DEVICE:
        if DATA_KEY not in hass.data:
            hass.data[DATA_KEY] = {}

        host = config_entry.data[CONF_HOST]
        token = config_entry.data[CONF_TOKEN]
        name = config_entry.title
        model = config_entry.data[CONF_MODEL]
        unique_id = config_entry.unique_id

        _LOGGER.debug("Initializing with host %s (token %s...)", host, token[:5])

        if model in MODELS_HUMIDIFIER_MIOT:
            air_humidifier = AirHumidifierMiot(host, token)
            entity = XiaomiAirHumidifierMiot(
                name, air_humidifier, config_entry, unique_id
            )
        elif model.startswith("zhimi.humidifier."):
            air_humidifier = AirHumidifier(host, token, model=model)
            entity = XiaomiAirHumidifier(name, air_humidifier, config_entry, unique_id)
        else:
            _LOGGER.error(
                "Unsupported humidifier device found! Please create an issue at "
                "https://github.com/syssi/xiaomi_airpurifier/issues "
                "and provide the following data: %s",
                model,
            )
            return

        hass.data[DATA_KEY][host] = entity
        entities.append(entity)

        async def async_service_handler(service):
            """Map services to methods."""
            method = SERVICE_TO_METHOD[service.service]
            params = {
                key: value
                for key, value in service.data.items()
                if key != ATTR_ENTITY_ID
            }
            entity_ids = service.data.get(ATTR_ENTITY_ID)
            if entity_ids:
                entities = [
                    entity
                    for entity in hass.data[DATA_KEY].values()
                    if entity.entity_id in entity_ids
                ]
            else:
                entities = hass.data[DATA_KEY].values()

            update_tasks = []

            for entity in entities:
                entity_method = getattr(entity, method["method"], None)
                if not entity_method:
                    continue
                await entity_method(**params)
                update_tasks.append(
                    hass.async_create_task(entity.async_update_ha_state(True))
                )

            if update_tasks:
                await asyncio.wait(update_tasks)

        for air_purifier_service in SERVICE_TO_METHOD:
            schema = SERVICE_TO_METHOD[air_purifier_service].get(
                "schema", AIRHUMIDIFIER_SERVICE_SCHEMA
            )
            hass.services.async_register(
                DOMAIN, air_purifier_service, async_service_handler, schema=schema
            )

    async_add_entities(entities, update_before_add=True)


class XiaomiGenericHumidifierDevice(XiaomiMiioEntity, HumidifierEntity):
    """Representation of a generic Xiaomi device."""

    def __init__(self, name, device, entry, unique_id):
        """Initialize the generic Xiaomi device."""
        super().__init__(name, device, entry, unique_id)

        self._available = False
        self._state = None
        self._state_attrs = {ATTR_MODEL: self._model}
        self._skip_update = False
        self._available_modes = []
        self._mode = None
        self._available_attributes = AVAILABLE_ATTRIBUTES

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_MODES

    @property
    def should_poll(self):
        """Poll the device."""
        return True

    @property
    def available(self):
        """Return true when state is known."""
        return self._available

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._state

    @staticmethod
    def _extract_value_from_attribute(state, attribute):
        value = getattr(state, attribute)
        if isinstance(value, Enum):
            return value.value

        return value

    async def _try_command(self, mask_error, func, *args, **kwargs):
        """Call a miio device command handling error messages."""
        try:
            result = await self.hass.async_add_executor_job(
                partial(func, *args, **kwargs)
            )

            _LOGGER.debug("Response received from miio device: %s", result)

            return result == SUCCESS
        except DeviceException as exc:
            if self._available:
                _LOGGER.error(mask_error, exc)
                self._available = False

            return False

    @property
    def available_modes(self) -> list:
        """Get the list of available modes."""
        return self._available_modes

    @property
    def mode(self):
        """Get the current mode."""
        return self._mode

    async def async_turn_on(
        self,
        **kwargs,
    ) -> None:
        """Turn the device on."""
        result = await self._try_command(
            "Turning the miio device on failed.", self._device.on
        )

        if result:
            self._state = True
            self._skip_update = True

    async def async_turn_off(self, **kwargs) -> None:
        """Turn the device off."""
        result = await self._try_command(
            "Turning the miio device off failed.", self._device.off
        )

        if result:
            self._state = False
            self._skip_update = True


class XiaomiAirHumidifier(XiaomiGenericHumidifierDevice):
    """Representation of a Xiaomi Air Humidifier."""

    def __init__(self, name, device, entry, unique_id):
        """Initialize the plug switch."""
        super().__init__(name, device, entry, unique_id)

        if self._model in [MODEL_AIRHUMIDIFIER_CA1, MODEL_AIRHUMIDIFIER_CB1]:
            self._available_modes = []
            self._available_modes = [
                mode.name
                for mode in AirhumidifierOperationMode
                if mode is not AirhumidifierOperationMode.Strong
            ]
        elif self._model in [MODEL_AIRHUMIDIFIER_CA4]:
            self._available_modes = [
                mode.name for mode in AirhumidifierMiotOperationMode
            ]
        else:
            self._available_modes = [
                mode.name
                for mode in AirhumidifierOperationMode
                if mode is not AirhumidifierOperationMode.Auto
            ]

        self._state_attrs.update(
            {attribute: None for attribute in self._available_attributes}
        )

    async def async_update(self):
        """Fetch state from the device."""
        # On state change the device doesn't provide the new state immediately.
        if self._skip_update:
            self._skip_update = False
            return

        try:
            state = await self.hass.async_add_executor_job(self._device.status)
            _LOGGER.debug("Got new state: %s", state)

            self._available = True
            self._state = state.is_on
            self._state_attrs.update(
                {
                    key: self._extract_value_from_attribute(state, value)
                    for key, value in self._available_attributes.items()
                }
            )

        except DeviceException as ex:
            if self._available:
                self._available = False
                _LOGGER.error("Got exception while fetching the state: %s", ex)

    @property
    def mode(self):
        """Return the current mode."""
        if self._state:
            return AirhumidifierOperationMode(self._state_attrs[ATTR_MODE]).name

    @property
    def target_humidity(self):
        """Return the current target humidity."""
        if self._state:
            return self._state_attrs[ATTR_TARGET_HUMIDITY]

    @property
    def min_humidity(self):
        """Return the current target humidity."""
        return 30

    @property
    def max_humidity(self):
        """Return the current target humidity."""
        return 80

    async def async_set_humidity(self, humidity) -> None:
        """Set the mode of the humidifier."""
        _LOGGER.debug("Setting the humidity to: %s", humidity)

        await self._try_command(
            "Setting operation mode of the miio device failed.",
            self._device.set_target_humidity,
            humidity,
        )

    async def async_set_mode(self, mode) -> None:
        """Set the mode of the humidifier."""
        if self.supported_features & SUPPORT_MODES == 0:
            return

        _LOGGER.debug("Setting the operation mode to: %s", mode)

        await self._try_command(
            "Setting operation mode of the miio device failed.",
            self._device.set_mode,
            AirhumidifierOperationMode[mode.title()],
        )


class XiaomiAirHumidifierMiot(XiaomiAirHumidifier):
    """Representation of a Xiaomi Air Humidifier (MiOT protocol)."""

    MODE_MAPPING = {
        AirhumidifierMiotOperationMode.Auto: "Auto",
        AirhumidifierMiotOperationMode.Low: "Low",
        AirhumidifierMiotOperationMode.Mid: "Mid",
        AirhumidifierMiotOperationMode.High: "High",
    }

    REVERSE_MODE_MAPPING = {v: k for k, v in MODE_MAPPING.items()}

    @property
    def mode(self):
        """Return the current mode."""
        return AirhumidifierMiotOperationMode(self._state_attrs[ATTR_MODE]).name

    async def async_set_mode(self, mode: str) -> None:
        """Set the mode of the fan."""
        if self._state:
            await self._try_command(
                "Setting operation mode of the miio device failed.",
                self._device.set_mode,
                self.REVERSE_MODE_MAPPING[mode],
            )
