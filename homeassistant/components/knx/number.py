"""Support for KNX/IP numeric values."""

from __future__ import annotations

from typing import cast

from xknx import XKNX
from xknx.devices import NumericValue

from homeassistant import config_entries
from homeassistant.components.number import RestoreNumber
from homeassistant.const import (
    CONF_ENTITY_CATEGORY,
    CONF_MODE,
    CONF_NAME,
    CONF_TYPE,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType

from . import KNXModule
from .const import CONF_RESPOND_TO_READ, CONF_STATE_ADDRESS, KNX_ADDRESS, KNX_MODULE_KEY
from .entity import KnxYamlEntity
from .schema import NumberSchema


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: config_entries.ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up number(s) for KNX platform."""
    knx_module = hass.data[KNX_MODULE_KEY]
    config: list[ConfigType] = knx_module.config_yaml[Platform.NUMBER]

    async_add_entities(KNXNumber(knx_module, entity_config) for entity_config in config)


def _create_numeric_value(xknx: XKNX, config: ConfigType) -> NumericValue:
    """Return a KNX NumericValue to be used within XKNX."""
    return NumericValue(
        xknx,
        name=config[CONF_NAME],
        group_address=config[KNX_ADDRESS],
        group_address_state=config.get(CONF_STATE_ADDRESS),
        respond_to_read=config[CONF_RESPOND_TO_READ],
        value_type=config[CONF_TYPE],
    )


class KNXNumber(KnxYamlEntity, RestoreNumber):
    """Representation of a KNX number."""

    _device: NumericValue

    def __init__(self, knx_module: KNXModule, config: ConfigType) -> None:
        """Initialize a KNX number."""
        super().__init__(
            knx_module=knx_module,
            device=_create_numeric_value(knx_module.xknx, config),
        )
        self._attr_native_max_value = config.get(
            NumberSchema.CONF_MAX,
            self._device.sensor_value.dpt_class.value_max,
        )
        self._attr_native_min_value = config.get(
            NumberSchema.CONF_MIN,
            self._device.sensor_value.dpt_class.value_min,
        )
        self._attr_mode = config[CONF_MODE]
        self._attr_native_step = config.get(
            NumberSchema.CONF_STEP,
            self._device.sensor_value.dpt_class.resolution,
        )
        self._attr_entity_category = config.get(CONF_ENTITY_CATEGORY)
        self._attr_unique_id = str(self._device.sensor_value.group_address)
        self._attr_native_unit_of_measurement = self._device.unit_of_measurement()
        self._device.sensor_value.value = max(0, self._attr_native_min_value)

    async def async_added_to_hass(self) -> None:
        """Restore last state."""
        await super().async_added_to_hass()
        if (
            not self._device.sensor_value.readable
            and (last_state := await self.async_get_last_state())
            and (last_number_data := await self.async_get_last_number_data())
        ):
            if last_state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE):
                self._device.sensor_value.value = last_number_data.native_value

    @property
    def native_value(self) -> float:
        """Return the entity value to represent the entity state."""
        # self._device.sensor_value.value is set in __init__ so it is never None
        return cast(float, self._device.resolve_state())

    async def async_set_native_value(self, value: float) -> None:
        """Set new value."""
        await self._device.set(value)
