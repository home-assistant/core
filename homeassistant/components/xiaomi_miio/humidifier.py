"""Support for Xiaomi Mi Air Purifier and Xiaomi Mi Air Humidifier with humidifier entity."""

import logging
import math
from typing import Any

from miio import Device as MiioDevice
from miio.integrations.humidifier.deerma.airhumidifier_mjjsq import (
    OperationMode as AirhumidifierMjjsqOperationMode,
)
from miio.integrations.humidifier.zhimi.airhumidifier import (
    OperationMode as AirhumidifierOperationMode,
)
from miio.integrations.humidifier.zhimi.airhumidifier_miot import (
    OperationMode as AirhumidifierMiotOperationMode,
)

from homeassistant.components.humidifier import (
    ATTR_HUMIDITY,
    HumidifierDeviceClass,
    HumidifierEntity,
    HumidifierEntityFeature,
)
from homeassistant.const import ATTR_MODE, CONF_DEVICE, CONF_MODEL
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util.percentage import percentage_to_ranged_value

from .const import (
    CONF_FLOW_TYPE,
    MODEL_AIRHUMIDIFIER_CA1,
    MODEL_AIRHUMIDIFIER_CA4,
    MODEL_AIRHUMIDIFIER_CB1,
    MODELS_HUMIDIFIER_MIOT,
    MODELS_HUMIDIFIER_MJJSQ,
)
from .entity import XiaomiCoordinatedMiioEntity
from .typing import XiaomiMiioConfigEntry

_LOGGER = logging.getLogger(__name__)

# Air Humidifier
ATTR_TARGET_HUMIDITY = "target_humidity"

AVAILABLE_ATTRIBUTES = {
    ATTR_MODE: "mode",
    ATTR_TARGET_HUMIDITY: "target_humidity",
    ATTR_HUMIDITY: "humidity",
}

AVAILABLE_MODES_CA1_CB1 = [
    mode.name
    for mode in AirhumidifierOperationMode
    if mode is not AirhumidifierOperationMode.Strong
]
AVAILABLE_MODES_CA4 = [mode.name for mode in AirhumidifierMiotOperationMode]
AVAILABLE_MODES_MJJSQ = [
    mode.name
    for mode in AirhumidifierMjjsqOperationMode
    if mode is not AirhumidifierMjjsqOperationMode.WetAndProtect
]
AVAILABLE_MODES_OTHER = [
    mode.name
    for mode in AirhumidifierOperationMode
    if mode is not AirhumidifierOperationMode.Auto
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: XiaomiMiioConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Humidifier from a config entry."""
    if config_entry.data[CONF_FLOW_TYPE] != CONF_DEVICE:
        return

    entities: list[HumidifierEntity] = []
    entity: HumidifierEntity
    model = config_entry.data[CONF_MODEL]
    unique_id = config_entry.unique_id
    device = config_entry.runtime_data.device
    coordinator = config_entry.runtime_data.device_coordinator

    if model in MODELS_HUMIDIFIER_MIOT:
        entity = XiaomiAirHumidifierMiot(
            device,
            config_entry,
            unique_id,
            coordinator,
        )
    elif model in MODELS_HUMIDIFIER_MJJSQ:
        entity = XiaomiAirHumidifierMjjsq(
            device,
            config_entry,
            unique_id,
            coordinator,
        )
    else:
        entity = XiaomiAirHumidifier(
            device,
            config_entry,
            unique_id,
            coordinator,
        )

    entities.append(entity)

    async_add_entities(entities)


class XiaomiGenericHumidifier(
    XiaomiCoordinatedMiioEntity[DataUpdateCoordinator[Any]], HumidifierEntity
):
    """Representation of a generic Xiaomi humidifier device."""

    _attr_device_class = HumidifierDeviceClass.HUMIDIFIER
    _attr_supported_features = HumidifierEntityFeature.MODES
    _attr_name = None

    def __init__(
        self,
        device: MiioDevice,
        entry: XiaomiMiioConfigEntry,
        unique_id: str | None,
        coordinator: DataUpdateCoordinator[Any],
    ) -> None:
        """Initialize the generic Xiaomi device."""
        super().__init__(device, entry, unique_id, coordinator=coordinator)

        self._attributes: dict[str, Any] = {}
        self._mode: str | int | None = None
        self._humidity_steps = 100
        self._target_humidity: float | None = None

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the device on."""
        result = await self._try_command(
            "Turning the miio device on failed.",
            self._device.on,  # type: ignore[attr-defined]
        )
        if result:
            self._attr_is_on = True
            self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the device off."""
        result = await self._try_command(
            "Turning the miio device off failed.",
            self._device.off,  # type: ignore[attr-defined]
        )

        if result:
            self._attr_is_on = False
            self.async_write_ha_state()

    def translate_humidity(self, humidity: float) -> float | None:
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

    available_modes: list[str]

    def __init__(
        self,
        device: MiioDevice,
        entry: XiaomiMiioConfigEntry,
        unique_id: str | None,
        coordinator: DataUpdateCoordinator[Any],
    ) -> None:
        """Initialize the plug switch."""
        super().__init__(device, entry, unique_id, coordinator)

        self._attr_min_humidity = 30
        self._attr_max_humidity = 80
        if self._model in [MODEL_AIRHUMIDIFIER_CA1, MODEL_AIRHUMIDIFIER_CB1]:
            self._attr_available_modes = AVAILABLE_MODES_CA1_CB1
            self._humidity_steps = 10
        elif self._model in [MODEL_AIRHUMIDIFIER_CA4]:
            self._attr_available_modes = AVAILABLE_MODES_CA4
            self._humidity_steps = 100
        elif self._model in MODELS_HUMIDIFIER_MJJSQ:
            self._attr_available_modes = AVAILABLE_MODES_MJJSQ
            self._humidity_steps = 100
        else:
            self._attr_available_modes = AVAILABLE_MODES_OTHER
            self._humidity_steps = 10

        self._attr_is_on = self.coordinator.data.is_on
        self._attributes.update(
            {
                key: self._extract_value_from_attribute(self.coordinator.data, value)
                for key, value in AVAILABLE_ATTRIBUTES.items()
            }
        )
        self._target_humidity = self._attributes[ATTR_TARGET_HUMIDITY]
        self._attr_current_humidity = self._attributes[ATTR_HUMIDITY]
        self._mode = self._attributes[ATTR_MODE]

    @callback
    def _handle_coordinator_update(self):
        """Fetch state from the device."""
        self._attr_is_on = self.coordinator.data.is_on
        self._attributes.update(
            {
                key: self._extract_value_from_attribute(self.coordinator.data, value)
                for key, value in AVAILABLE_ATTRIBUTES.items()
            }
        )
        self._target_humidity = self._attributes[ATTR_TARGET_HUMIDITY]
        self._attr_current_humidity = self._attributes[ATTR_HUMIDITY]
        self._attr_mode = self._attributes[ATTR_MODE]
        self.async_write_ha_state()

    @property
    def mode(self) -> str:
        """Return the current mode."""
        return AirhumidifierOperationMode(self._mode).name

    @property
    def target_humidity(self) -> float | None:
        """Return the target humidity."""
        return (
            self._target_humidity
            if self._mode == AirhumidifierOperationMode.Auto.value
            or AirhumidifierOperationMode.Auto.name not in self.available_modes
            else None
        )

    async def async_set_humidity(self, humidity: float) -> None:
        """Set the target humidity of the humidifier and set the mode to auto."""
        target_humidity = self.translate_humidity(humidity)
        if not target_humidity:
            return

        _LOGGER.debug("Setting the target humidity to: %s", target_humidity)
        if await self._try_command(
            "Setting target humidity of the miio device failed.",
            self._device.set_target_humidity,  # type: ignore[attr-defined]
            target_humidity,
        ):
            self._target_humidity = target_humidity
        if (
            self.supported_features & HumidifierEntityFeature.MODES == 0
            or AirhumidifierOperationMode(self._attributes[ATTR_MODE])
            == AirhumidifierOperationMode.Auto
            or AirhumidifierOperationMode.Auto.name not in self.available_modes
        ):
            self.async_write_ha_state()
            return
        _LOGGER.debug("Setting the operation mode to: Auto")
        if await self._try_command(
            "Setting operation mode of the miio device to MODE_AUTO failed.",
            self._device.set_mode,  # type: ignore[attr-defined]
            AirhumidifierOperationMode.Auto,
        ):
            self._mode = AirhumidifierOperationMode.Auto.value
            self.async_write_ha_state()

    async def async_set_mode(self, mode: str) -> None:
        """Set the mode of the humidifier."""
        if self.supported_features & HumidifierEntityFeature.MODES == 0 or not mode:
            return

        if mode not in self.available_modes:
            _LOGGER.warning("Mode %s is not a valid operation mode", mode)
            return

        _LOGGER.debug("Setting the operation mode to: %s", mode)
        if await self._try_command(
            "Setting operation mode of the miio device failed.",
            self._device.set_mode,  # type: ignore[attr-defined]
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
    def mode(self) -> str:
        """Return the current mode."""
        return AirhumidifierMiotOperationMode(self._mode).name

    @property
    def target_humidity(self) -> float | None:
        """Return the target humidity."""
        if self.is_on:
            return (
                self._target_humidity
                if AirhumidifierMiotOperationMode(self._mode)
                == AirhumidifierMiotOperationMode.Auto
                else None
            )
        return None

    async def async_set_humidity(self, humidity: float) -> None:
        """Set the target humidity of the humidifier and set the mode to auto."""
        target_humidity = self.translate_humidity(humidity)
        if not target_humidity:
            return

        _LOGGER.debug("Setting the humidity to: %s", target_humidity)
        if await self._try_command(
            "Setting operation mode of the miio device failed.",
            self._device.set_target_humidity,  # type: ignore[attr-defined]
            target_humidity,
        ):
            self._target_humidity = target_humidity
        if (
            self.supported_features & HumidifierEntityFeature.MODES == 0
            or AirhumidifierMiotOperationMode(self._attributes[ATTR_MODE])
            == AirhumidifierMiotOperationMode.Auto
        ):
            self.async_write_ha_state()
            return
        _LOGGER.debug("Setting the operation mode to: Auto")
        if await self._try_command(
            "Setting operation mode of the miio device to MODE_AUTO failed.",
            self._device.set_mode,  # type: ignore[attr-defined]
            AirhumidifierMiotOperationMode.Auto,
        ):
            self._mode = 0
            self.async_write_ha_state()

    async def async_set_mode(self, mode: str) -> None:
        """Set the mode of the fan."""
        if self.supported_features & HumidifierEntityFeature.MODES == 0 or not mode:
            return

        if mode not in self.REVERSE_MODE_MAPPING:
            _LOGGER.warning("Mode %s is not a valid operation mode", mode)
            return

        _LOGGER.debug("Setting the operation mode to: %s", mode)
        if self.is_on:
            if await self._try_command(
                "Setting operation mode of the miio device failed.",
                self._device.set_mode,  # type: ignore[attr-defined]
                self.REVERSE_MODE_MAPPING[mode],
            ):
                self._mode = self.REVERSE_MODE_MAPPING[mode].value
                self.async_write_ha_state()


class XiaomiAirHumidifierMjjsq(XiaomiAirHumidifier):
    """Representation of a Xiaomi Air MJJSQ Humidifier."""

    MODE_MAPPING = {
        "Low": AirhumidifierMjjsqOperationMode.Low,
        "Medium": AirhumidifierMjjsqOperationMode.Medium,
        "High": AirhumidifierMjjsqOperationMode.High,
        "Humidity": AirhumidifierMjjsqOperationMode.Humidity,
    }

    @property
    def mode(self) -> str:
        """Return the current mode."""
        return AirhumidifierMjjsqOperationMode(self._mode).name

    @property
    def target_humidity(self) -> float | None:
        """Return the target humidity."""
        if self.is_on:
            if (
                AirhumidifierMjjsqOperationMode(self._mode)
                == AirhumidifierMjjsqOperationMode.Humidity
            ):
                return self._target_humidity
        return None

    async def async_set_humidity(self, humidity: float) -> None:
        """Set the target humidity of the humidifier and set the mode to Humidity."""
        target_humidity = self.translate_humidity(humidity)
        if not target_humidity:
            return

        _LOGGER.debug("Setting the humidity to: %s", target_humidity)
        if await self._try_command(
            "Setting operation mode of the miio device failed.",
            self._device.set_target_humidity,  # type: ignore[attr-defined]
            target_humidity,
        ):
            self._target_humidity = target_humidity
        if (
            self.supported_features & HumidifierEntityFeature.MODES == 0
            or AirhumidifierMjjsqOperationMode(self._attributes[ATTR_MODE])
            == AirhumidifierMjjsqOperationMode.Humidity
        ):
            self.async_write_ha_state()
            return
        _LOGGER.debug("Setting the operation mode to: Humidity")
        if await self._try_command(
            "Setting operation mode of the miio device to MODE_HUMIDITY failed.",
            self._device.set_mode,  # type: ignore[attr-defined]
            AirhumidifierMjjsqOperationMode.Humidity,
        ):
            self._mode = 3
            self.async_write_ha_state()

    async def async_set_mode(self, mode: str) -> None:
        """Set the mode of the fan."""
        if mode not in self.MODE_MAPPING:
            _LOGGER.warning("Mode %s is not a valid operation mode", mode)
            return

        _LOGGER.debug("Setting the operation mode to: %s", mode)
        if self.is_on:
            if await self._try_command(
                "Setting operation mode of the miio device failed.",
                self._device.set_mode,  # type: ignore[attr-defined]
                self.MODE_MAPPING[mode],
            ):
                self._mode = self.MODE_MAPPING[mode].value
                self.async_write_ha_state()
