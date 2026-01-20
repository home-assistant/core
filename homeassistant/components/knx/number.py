"""Support for KNX number entities."""

from __future__ import annotations

from typing import cast

from xknx.devices import NumericValue

from homeassistant import config_entries
from homeassistant.components.number import NumberDeviceClass, NumberMode, RestoreNumber
from homeassistant.const import (
    CONF_DEVICE_CLASS,
    CONF_ENTITY_CATEGORY,
    CONF_MODE,
    CONF_NAME,
    CONF_TYPE,
    CONF_UNIT_OF_MEASUREMENT,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    async_get_current_platform,
)
from homeassistant.helpers.typing import ConfigType
from homeassistant.util.enum import try_parse_enum

from .const import (
    CONF_RESPOND_TO_READ,
    CONF_STATE_ADDRESS,
    CONF_SYNC_STATE,
    DOMAIN,
    KNX_ADDRESS,
    KNX_MODULE_KEY,
    NumberConf,
)
from .dpt import get_supported_dpts
from .entity import KnxUiEntity, KnxUiEntityPlatformController, KnxYamlEntity
from .knx_module import KNXModule
from .storage.const import CONF_ENTITY, CONF_GA_SENSOR
from .storage.util import ConfigExtractor


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: config_entries.ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up number(s) for KNX platform."""
    knx_module = hass.data[KNX_MODULE_KEY]
    platform = async_get_current_platform()
    knx_module.config_store.add_platform(
        platform=Platform.NUMBER,
        controller=KnxUiEntityPlatformController(
            knx_module=knx_module,
            entity_platform=platform,
            entity_class=KnxUiNumber,
        ),
    )

    entities: list[KnxYamlEntity | KnxUiEntity] = []
    if yaml_platform_config := knx_module.config_yaml.get(Platform.NUMBER):
        entities.extend(
            KnxYamlNumber(knx_module, entity_config)
            for entity_config in yaml_platform_config
        )
    if ui_config := knx_module.config_store.data["entities"].get(Platform.NUMBER):
        entities.extend(
            KnxUiNumber(knx_module, unique_id, config)
            for unique_id, config in ui_config.items()
        )
    if entities:
        async_add_entities(entities)


class _KnxNumber(RestoreNumber):
    """Representation of a KNX number."""

    _device: NumericValue

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


class KnxYamlNumber(_KnxNumber, KnxYamlEntity):
    """Representation of a KNX number configured from YAML."""

    _device: NumericValue

    def __init__(self, knx_module: KNXModule, config: ConfigType) -> None:
        """Initialize a KNX number."""
        super().__init__(
            knx_module=knx_module,
            device=NumericValue(
                knx_module.xknx,
                name=config[CONF_NAME],
                group_address=config[KNX_ADDRESS],
                group_address_state=config.get(CONF_STATE_ADDRESS),
                respond_to_read=config[CONF_RESPOND_TO_READ],
                value_type=config[CONF_TYPE],
            ),
        )
        self._attr_native_max_value = config.get(
            NumberConf.MAX,
            self._device.sensor_value.dpt_class.value_max,
        )
        self._attr_native_min_value = config.get(
            NumberConf.MIN,
            self._device.sensor_value.dpt_class.value_min,
        )
        self._attr_mode = config[CONF_MODE]
        self._attr_native_step = config.get(
            NumberConf.STEP,
            self._device.sensor_value.dpt_class.resolution,
        )
        self._attr_entity_category = config.get(CONF_ENTITY_CATEGORY)
        self._attr_unique_id = str(self._device.sensor_value.group_address)
        self._attr_native_unit_of_measurement = self._device.unit_of_measurement()
        self._device.sensor_value.value = max(0, self._attr_native_min_value)


class KnxUiNumber(_KnxNumber, KnxUiEntity):
    """Representation of a KNX number configured from UI."""

    _device: NumericValue

    def __init__(
        self,
        knx_module: KNXModule,
        unique_id: str,
        config: ConfigType,
    ) -> None:
        """Initialize a KNX number."""
        super().__init__(
            knx_module=knx_module,
            unique_id=unique_id,
            entity_config=config[CONF_ENTITY],
        )
        knx_conf = ConfigExtractor(config[DOMAIN])
        dpt_string = knx_conf.get_dpt(CONF_GA_SENSOR)
        assert dpt_string is not None  # required for number
        dpt_info = get_supported_dpts()[dpt_string]

        self._device = NumericValue(
            knx_module.xknx,
            name=config[CONF_ENTITY][CONF_NAME],
            group_address=knx_conf.get_write(CONF_GA_SENSOR),
            group_address_state=knx_conf.get_state_and_passive(CONF_GA_SENSOR),
            respond_to_read=knx_conf.get(CONF_RESPOND_TO_READ),
            sync_state=knx_conf.get(CONF_SYNC_STATE),
            value_type=dpt_string,
        )

        if device_class_override := knx_conf.get(CONF_DEVICE_CLASS):
            self._attr_device_class = try_parse_enum(
                NumberDeviceClass, device_class_override
            )
        else:
            self._attr_device_class = try_parse_enum(
                # sensor device classes should, with some exceptions ("enum" etc.), align with number device classes
                NumberDeviceClass,
                dpt_info["sensor_device_class"],
            )
        self._attr_mode = NumberMode(knx_conf.get(CONF_MODE))
        self._attr_native_max_value = knx_conf.get(
            NumberConf.MAX,
            default=self._device.sensor_value.dpt_class.value_max,
        )
        self._attr_native_min_value = knx_conf.get(
            NumberConf.MIN,
            default=self._device.sensor_value.dpt_class.value_min,
        )
        self._attr_native_step = knx_conf.get(
            NumberConf.STEP,
            default=self._device.sensor_value.dpt_class.resolution,
        )
        self._attr_native_unit_of_measurement = (
            knx_conf.get(CONF_UNIT_OF_MEASUREMENT) or dpt_info["unit"]
        )

        self._device.sensor_value.value = max(0, self._attr_native_min_value)
