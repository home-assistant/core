"""Support for Xiaomi Mi Air Purifier and Xiaomi Mi Air Humidifier with humidifier entity."""
from enum import Enum
import logging
import math

from miio.airhumidifier import OperationMode as AirhumidifierOperationMode
from miio.airhumidifier_miot import OperationMode as AirhumidifierMiotOperationMode

from homeassistant.components.humidifier import HumidifierEntity
from homeassistant.components.humidifier.const import (
    DEFAULT_MAX_HUMIDITY,
    DEFAULT_MIN_HUMIDITY,
    DEVICE_CLASS_HUMIDIFIER,
    SUPPORT_MODES,
)
from homeassistant.const import ATTR_MODE
from homeassistant.core import callback
from homeassistant.util.percentage import percentage_to_ranged_value

from .const import (
    CONF_DEVICE,
    CONF_FLOW_TYPE,
    CONF_MODEL,
    DOMAIN,
    KEY_COORDINATOR,
    KEY_DEVICE,
    MODEL_AIRHUMIDIFIER_CA1,
    MODEL_AIRHUMIDIFIER_CA4,
    MODEL_AIRHUMIDIFIER_CB1,
    MODELS_HUMIDIFIER_MIOT,
)
from .device import XiaomiCoordinatedMiioEntity

_LOGGER = logging.getLogger(__name__)

# Air Humidifier
ATTR_TARGET_HUMIDITY = "target_humidity"

AVAILABLE_ATTRIBUTES = {
    ATTR_MODE: "mode",
    ATTR_TARGET_HUMIDITY: "target_humidity",
}


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Humidifier from a config entry."""
    if not config_entry.data[CONF_FLOW_TYPE] == CONF_DEVICE:
        return

    entities = []
    model = config_entry.data[CONF_MODEL]
    unique_id = config_entry.unique_id
    coordinator = hass.data[DOMAIN][config_entry.entry_id][KEY_COORDINATOR]
    name = config_entry.title

    if model in MODELS_HUMIDIFIER_MIOT:
        air_humidifier = hass.data[DOMAIN][config_entry.entry_id][KEY_DEVICE]
        entity = XiaomiAirHumidifierMiot(
            name,
            air_humidifier,
            config_entry,
            unique_id,
            coordinator,
        )
    else:
        air_humidifier = hass.data[DOMAIN][config_entry.entry_id][KEY_DEVICE]
        entity = XiaomiAirHumidifier(
            name,
            air_humidifier,
            config_entry,
            unique_id,
            coordinator,
        )

    entities.append(entity)

    async_add_entities(entities)


class XiaomiGenericHumidifier(XiaomiCoordinatedMiioEntity, HumidifierEntity):
    """Representation of a generic Xiaomi humidifier device."""

    _attr_device_class = DEVICE_CLASS_HUMIDIFIER
    _attr_supported_features = SUPPORT_MODES

    def __init__(self, name, device, entry, unique_id, coordinator):
        """Initialize the generic Xiaomi device."""
        super().__init__(name, device, entry, unique_id, coordinator=coordinator)

        self._state = None
        self._attributes = {}
        self._available_modes = []
        self._mode = None
        self._min_humidity = DEFAULT_MIN_HUMIDITY
        self._max_humidity = DEFAULT_MAX_HUMIDITY
        self._humidity_steps = 100
        self._target_humidity = None

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

    @property
    def available_modes(self) -> list:
        """Get the list of available modes."""
        return self._available_modes

    @property
    def mode(self):
        """Get the current mode."""
        return self._mode

    @property
    def min_humidity(self):
        """Return the minimum target humidity."""
        return self._min_humidity

    @property
    def max_humidity(self):
        """Return the maximum target humidity."""
        return self._max_humidity

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
            self.async_write_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        """Turn the device off."""
        result = await self._try_command(
            "Turning the miio device off failed.", self._device.off
        )

        if result:
            self._state = False
            self.async_write_ha_state()

    def translate_humidity(self, humidity):
        """Translate the target humidity to the first valid step."""
        return (
            math.ceil(percentage_to_ranged_value((1, self._humidity_steps), humidity))
            * 100
            / self._humidity_steps
            if 0 < humidity <= 100
            else None
        )


class XiaomiAirHumidifier(XiaomiGenericHumidifier, HumidifierEntity):
    """Representation of a Xiaomi Air Humidifier."""

    def __init__(self, name, device, entry, unique_id, coordinator):
        """Initialize the plug switch."""
        super().__init__(name, device, entry, unique_id, coordinator)
        if self._model in [MODEL_AIRHUMIDIFIER_CA1, MODEL_AIRHUMIDIFIER_CB1]:
            self._available_modes = []
            self._available_modes = [
                mode.name
                for mode in AirhumidifierOperationMode
                if mode is not AirhumidifierOperationMode.Strong
            ]
            self._min_humidity = 30
            self._max_humidity = 80
            self._humidity_steps = 10
        elif self._model in [MODEL_AIRHUMIDIFIER_CA4]:
            self._available_modes = [
                mode.name for mode in AirhumidifierMiotOperationMode
            ]
            self._min_humidity = 30
            self._max_humidity = 80
            self._humidity_steps = 100
        else:
            self._available_modes = [
                mode.name
                for mode in AirhumidifierOperationMode
                if mode is not AirhumidifierOperationMode.Auto
            ]
            self._min_humidity = 30
            self._max_humidity = 80
            self._humidity_steps = 10

        self._state = self.coordinator.data.is_on
        self._attributes.update(
            {
                key: self._extract_value_from_attribute(self.coordinator.data, value)
                for key, value in AVAILABLE_ATTRIBUTES.items()
            }
        )
        self._target_humidity = self._attributes[ATTR_TARGET_HUMIDITY]
        self._mode = self._attributes[ATTR_MODE]

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._state

    @callback
    def _handle_coordinator_update(self):
        """Fetch state from the device."""
        self._state = self.coordinator.data.is_on
        self._attributes.update(
            {
                key: self._extract_value_from_attribute(self.coordinator.data, value)
                for key, value in AVAILABLE_ATTRIBUTES.items()
            }
        )
        self._target_humidity = self._attributes[ATTR_TARGET_HUMIDITY]
        self._mode = self._attributes[ATTR_MODE]
        self.async_write_ha_state()

    @property
    def mode(self):
        """Return the current mode."""
        return AirhumidifierOperationMode(self._mode).name

    @property
    def target_humidity(self):
        """Return the target humidity."""
        return (
            self._target_humidity
            if self._mode == AirhumidifierOperationMode.Auto.value
            or AirhumidifierOperationMode.Auto.name not in self.available_modes
            else None
        )

    async def async_set_humidity(self, humidity: int) -> None:
        """Set the target humidity of the humidifier and set the mode to auto."""
        target_humidity = self.translate_humidity(humidity)
        if not target_humidity:
            return

        _LOGGER.debug("Setting the target humidity to: %s", target_humidity)
        if await self._try_command(
            "Setting target humidity of the miio device failed.",
            self._device.set_target_humidity,
            target_humidity,
        ):
            self._target_humidity = target_humidity
        if (
            self.supported_features & SUPPORT_MODES == 0
            or AirhumidifierOperationMode(self._attributes[ATTR_MODE])
            == AirhumidifierOperationMode.Auto
            or AirhumidifierOperationMode.Auto.name not in self.available_modes
        ):
            self.async_write_ha_state()
            return
        _LOGGER.debug("Setting the operation mode to: Auto")
        if await self._try_command(
            "Setting operation mode of the miio device to MODE_AUTO failed.",
            self._device.set_mode,
            AirhumidifierOperationMode.Auto,
        ):
            self._mode = AirhumidifierOperationMode.Auto.value
            self.async_write_ha_state()

    async def async_set_mode(self, mode: str) -> None:
        """Set the mode of the humidifier."""
        if self.supported_features & SUPPORT_MODES == 0 or not mode:
            return

        if mode not in self.available_modes:
            _LOGGER.warning("Mode %s is not a valid operation mode", mode)
            return

        _LOGGER.debug("Setting the operation mode to: %s", mode)
        if await self._try_command(
            "Setting operation mode of the miio device failed.",
            self._device.set_mode,
            AirhumidifierOperationMode[mode],
        ):
            self._mode = mode.lower()
            self.async_write_ha_state()


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
        return AirhumidifierMiotOperationMode(self._mode).name

    @property
    def target_humidity(self):
        """Return the target humidity."""
        if self._state:
            return (
                self._target_humidity
                if AirhumidifierMiotOperationMode(self._mode)
                == AirhumidifierMiotOperationMode.Auto
                else None
            )
        return None

    async def async_set_humidity(self, humidity: int) -> None:
        """Set the target humidity of the humidifier and set the mode to auto."""
        target_humidity = self.translate_humidity(humidity)
        if not target_humidity:
            return

        _LOGGER.debug("Setting the humidity to: %s", target_humidity)
        if await self._try_command(
            "Setting operation mode of the miio device failed.",
            self._device.set_target_humidity,
            target_humidity,
        ):
            self._target_humidity = target_humidity
        if (
            self.supported_features & SUPPORT_MODES == 0
            or AirhumidifierMiotOperationMode(self._attributes[ATTR_MODE])
            == AirhumidifierMiotOperationMode.Auto
        ):
            self.async_write_ha_state()
            return
        _LOGGER.debug("Setting the operation mode to: Auto")
        if await self._try_command(
            "Setting operation mode of the miio device to MODE_AUTO failed.",
            self._device.set_mode,
            AirhumidifierMiotOperationMode.Auto,
        ):
            self._mode = 0
            self.async_write_ha_state()

    async def async_set_mode(self, mode: str) -> None:
        """Set the mode of the fan."""
        if self.supported_features & SUPPORT_MODES == 0 or not mode:
            return

        if mode not in self.REVERSE_MODE_MAPPING:
            _LOGGER.warning("Mode %s is not a valid operation mode", mode)
            return

        _LOGGER.debug("Setting the operation mode to: %s", mode)
        if self._state:
            if await self._try_command(
                "Setting operation mode of the miio device failed.",
                self._device.set_mode,
                self.REVERSE_MODE_MAPPING[mode],
            ):
                self._mode = self.REVERSE_MODE_MAPPING[mode].value
                self.async_write_ha_state()
