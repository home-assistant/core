"""Support for Aqara Climate."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from aqara_iot import AqaraDeviceManager, AqaraPoint
from homeassistant.components.climate import ClimateEntity, ClimateEntityDescription
from homeassistant.components.climate.const import (
    HVAC_MODE_COOL,
    HVAC_MODE_DRY,
    HVAC_MODE_FAN_ONLY,
    HVAC_MODE_HEAT,
    HVAC_MODE_AUTO,
    HVAC_MODE_OFF,
    SUPPORT_FAN_MODE,
    SUPPORT_TARGET_TEMPERATURE,
    # SUPPORT_TARGET_HUMIDITY,
    SWING_OFF,
    SWING_ON,
    FAN_AUTO,
    FAN_LOW,
    FAN_MEDIUM,
    FAN_HIGH,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import TEMP_CELSIUS
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import HomeAssistantAqaraData
from .base import (
    AqaraEntity,
    find_aqara_device_points_and_register,
    entity_data_update_binding,
)
from .const import AQARA_DISCOVERY_NEW, DOMAIN

AQARA_FAN_MODE_TO_HA = {  # 0（小风量），1（中风量），2（大风量），3（自动风量）
    "3": FAN_AUTO,
    "0": FAN_LOW,
    "1": FAN_MEDIUM,
    "2": FAN_HIGH,
}

HA_FAN_MODE_TO_AQARA = {  # 0（小风量），1（中风量），2（大风量），3（自动风量）
    FAN_AUTO: "3",
    FAN_LOW: "0",
    FAN_MEDIUM: "1",
    FAN_HIGH: "2",
}

AQARA_HVAC_TO_HA = {
    "2": HVAC_MODE_AUTO,
    "1": HVAC_MODE_COOL,
    "0": HVAC_MODE_HEAT,
    "3": HVAC_MODE_DRY,  # 3（干燥）
    "4": HVAC_MODE_FAN_ONLY,  # 4（送风）
}

HA_HVAC_TO_AQARA = {
    HVAC_MODE_AUTO: "2",
    HVAC_MODE_COOL: "1",
    HVAC_MODE_HEAT: "0",
    HVAC_MODE_DRY: "3",  # 3（干燥）
    HVAC_MODE_FAN_ONLY: "4",  # 4（送风）
}


@dataclass
class AqaraClimateEntityDescription(ClimateEntityDescription):
    """Describe an Aqara climate entity."""

    supported_features: int = 0
    # brightness: str | None = None #最小值: 0 最大值: 100 步长: 1 单位: 1
    temperature_value_res_id: str | None = (
        "0.1.85"  # 温度，单位0.01摄氏度，只读。变化超过±0.5℃就上报，或跟随湿度一起上报。 最小值: -4000 最大值: 10000
    )
    humidity_value_res_id: str | None = ""  #
    # ac_mode_res_id: str | None = "14.25.85"  # 空调模式  空调模式，0：未配置模式。1：空调插插座模式。2：空调不插插座模式。3：红外热水器模式。4:16A插座模式

    on_off_status_res_id: str | None = ""  # 空调开关状态 空调处于打开/关闭状态,0:关闭，1:打开，该资源只读
    quick_cool_res_id: str | None = ""  # 速冷 通过改资源下发到空调伴侣，开启/停止速冷。0，停止速冷。1，开启速冷。
    ac_zip_status_res_id: str | None = ""  # 空调压缩状态
    # P：[31,28]表示开关状态。0（表示关），1（表示开）
    # M：[27,24]表示模式。0（制热），1（制冷），2（自动），3（干燥），4（送风）
    # S：[23,20]表示风速。0（小风量），1（中风量），2（大风量），3（自动风量），15（不支持调节）
    # [19,18]表示风向，暂不支持
    # D：[17,16]表示扫风，0（扫风），1（固定风向）
    # T：[15,8]表示温度。参数为具体的温度值，243（温度+）244（温度-）255（不支持调节）

    current_model_range_res_id: str | None = ""  # 当前匹配的模式范围模式定义：0:制冷，1:制热，2:自动，3:送风
    # 数据格式：string hex
    # 字节顺序：byte0：模式0，byte1：模式1.....
    # 按照模式的定义的value值填充
    # 例如支持制冷制热："0001”
    current_wind_range_res_id: str | None = ""  # 当前匹配的风速范围
    # 风速定义：0:自动，1:低，2:中，3:高
    # 数据格式：string hex
    # 字节顺序：byte0：风速0，byte1：风速1，byte2：风速2 ......
    # 按照风速定义的value值填充，根据实际支持的风速范围依次填充
    # 风速支持自动，低，中，高时："00010203"
    current_temperature_range_res_id: str | None = ""  # 当前匹配的温度范围
    # 数据格式：string hex
    # 字节顺序：byte0：模式0，byte1：模式0最低温度，byte2：模式0最高温度，byte3：模式1，byte4：模式1最低温度，byte5：模式1最高温度 ...
    # 根据：模式x—模式x最低温度—模式x最高温度依次填充
    # 例如制冷（16-30）和制热（17-30）："00101E01111E"

    def set_key(self, key: str) -> AqaraClimateEntityDescription:
        """Set key."""
        self.key = key
        return self

    def set_res_id(
        self,
        temperature_value_res_id: str,
        humidity_value_res_id: str,
        on_off_status_id: str,
        quick_cool_res_id: str,
        ac_zip_status_res_id: str,
    ) -> AqaraClimateEntityDescription:
        """Set resource id for propertity."""
        self.temperature_value_res_id = temperature_value_res_id
        self.humidity_value_res_id = humidity_value_res_id
        self.on_off_status_res_id = on_off_status_id
        self.quick_cool_res_id = quick_cool_res_id
        self.ac_zip_status_res_id = ac_zip_status_res_id
        return self


air_condition = AqaraClimateEntityDescription(
    key="14.32.85",
    temperature_value_res_id="0.1.85",
    humidity_value_res_id="0.2.85",
    on_off_status_res_id="3.1.85",
    # quick_cool_res_id="4.4.85",
    ac_zip_status_res_id="14.32.85",
    supported_features=SUPPORT_TARGET_TEMPERATURE | SUPPORT_FAN_MODE,
)

air_condition_old = AqaraClimateEntityDescription(
    key="14.10.85",
    current_temperature_range_res_id="8.0.8105",
    current_wind_range_res_id="8.0.8104",
    current_model_range_res_id="8.0.8103",
    temperature_value_res_id="",
    humidity_value_res_id="",
    on_off_status_res_id="3.1.85",
    # quick_cool_res_id="4.4.85",
    ac_zip_status_res_id="14.10.85",
    supported_features=SUPPORT_TARGET_TEMPERATURE | SUPPORT_FAN_MODE,
)


# (air_condition,)   air_condition 后面要加逗号,
CLIMATE_DESCRIPTIONS: dict[str, tuple[AqaraClimateEntityDescription, ...]] = {
    "lumi.aircondition.acn05": (air_condition,),  # 空调伴侣 P3
    "lumi.acpartner.eicn01": (air_condition,),  # 空调伴侣 J1
    "lumi.acpartner.v3": (air_condition_old,),  # 空调伴侣（升级版） 空调状态设置 14.10.85
    "lumi.acpartner.v1": (air_condition_old,),  # 空调伴侣
    "lumi.acpartner.es1": (air_condition_old,),  # 空调伴侣
    "lumi.acpartner.aq1": (air_condition_old,),  # 空调伴侣
}


# P：[31,28]表示开关状态。0（表示关），1（表示开）
# M：[27,24]表示模式。0（制热），1（制冷），2（自动），3（干燥），4（送风）
# S：[23,20]表示风速。0（小风量），1（中风量），2（大风量），3（自动风量），15（不支持调节）
# [19,18]表示风向，暂不支持
# D：[17,16]表示扫风，0（扫风），1（固定风向）
# T：[15,8]表示温度。参数为具体的温度值，243（温度+）244（温度-）255（不支持调节）


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Aqara climate dynamically through Aqara discovery."""
    hass_data: HomeAssistantAqaraData = hass.data[DOMAIN][entry.entry_id]

    @callback
    def async_discover_device(device_ids: list[str]) -> None:
        """Discover and add a discovered Aqara climate."""
        entities: list[AqaraClimateEntity] = []

        def append_entity(aqara_point, description: AqaraClimateEntityDescription):
            entity = AqaraClimateEntity(
                aqara_point, hass_data.device_manager, description
            )
            entities.append(entity)
            res_ids: list[str] = [
                description.temperature_value_res_id,
                description.humidity_value_res_id,
                description.on_off_status_res_id,
                description.quick_cool_res_id,
            ]
            entity_data_update_binding(
                hass, hass_data, entity, aqara_point.did, res_ids
            )

        find_aqara_device_points_and_register(
            hass,
            entry.entry_id,
            hass_data,
            device_ids,
            CLIMATE_DESCRIPTIONS,
            append_entity,
        )
        async_add_entities(entities)

    async_discover_device([*hass_data.device_manager.device_map])

    entry.async_on_unload(
        async_dispatcher_connect(hass, AQARA_DISCOVERY_NEW, async_discover_device)
    )


class StatusValue:
    """Aqara aircondition value status convert utility."""

    def __init__(self, value: int) -> None:
        """init value."""
        self.value = value

    def shift_bits(self, shift_bits: int, right_shift: bool = True) -> StatusValue:
        """shift value."""
        if right_shift:
            self.value = self.value >> shift_bits
        else:
            self.value = self.value << shift_bits
        return self

    def set_zero(self, start_bits: int, end_shift: int) -> StatusValue:
        """set the bits to zero."""
        for i in range(start_bits, end_shift + 1):
            self.value = self.value & ~(1 << i)
        return self


class AqaraClimateEntity(AqaraEntity, ClimateEntity):
    """Aqara Climate Device."""

    entity_description: AqaraClimateEntityDescription

    def __init__(  # noqa: C901
        self,
        point: AqaraPoint,
        device_manager: AqaraDeviceManager,
        description: AqaraClimateEntityDescription,
    ) -> None:
        """Determine which values to use."""
        self._attr_target_temperature_step = 1.0
        self._attr_supported_features = description.supported_features
        self.entity_description = description
        self._attr_temperature_unit = TEMP_CELSIUS

        self._attr_hvac_modes = [  # 0（制热），1（制冷），2（自动），3（干燥），4（送风）
            HVAC_MODE_OFF,
            HVAC_MODE_COOL,
            HVAC_MODE_HEAT,
            HVAC_MODE_AUTO,
            HVAC_MODE_DRY,
            HVAC_MODE_FAN_ONLY,
        ]
        self._attr_fan_modes = [  # 0（小风量），1（中风量），2（大风量），3（自动风量），15（不支持调节）
            FAN_AUTO,
            FAN_LOW,
            FAN_MEDIUM,
            FAN_HIGH,
        ]
        # self._attr_swing_modes = []
        # self._attr_preset_modes = []

        super().__init__(point, device_manager)

    # async def async_added_to_hass(self) -> None:
    #     """Call when entity is added to hass."""
    #     await super().async_added_to_hass()

    def set_hvac_mode(self, hvac_mode: str) -> None:
        """Set new target hvac mode.
        M:[27,24]表示模式。0(制热),1(制冷),2(自动),3(干燥),4(送风)
        """
        if hvac_mode == "off":
            self.turn_off()
            return None

        if hvac_mode not in HA_HVAC_TO_AQARA:  # ["0", "1", "2", "3", "4"]:
            return None

        value = self._set_ac_zip_status_value(
            start_bit=24, end_bit=27, setting_value=HA_HVAC_TO_AQARA[hvac_mode]
        )
        self._send_command([{self.entity_description.ac_zip_status_res_id: value}])

    def _shift_value(
        self, start_bit: int, end_bit: int, org_value: str, setting_value: str
    ) -> str:
        if setting_value == "":
            return org_value

        temp_value = (
            StatusValue(int(org_value)).set_zero(start_bit, end_bit).value
            | StatusValue(int(setting_value)).shift_bits(start_bit, False).value
        )
        return str(temp_value)

    def _set_ac_zip_status_value(
        self, start_bit: int, end_bit: int, setting_value: str
    ) -> str:
        """Set air condition status."""
        value = self.device_manager.get_point_value(
            self.point.did, self.entity_description.ac_zip_status_res_id
        )
        if setting_value == "":
            return value

        temp_value = (
            StatusValue(int(value)).set_zero(start_bit, end_bit).value
            | StatusValue(int(setting_value)).shift_bits(start_bit, False).value
        )
        return str(temp_value)

    def _get_ac_zip_status_value(self, start_bit: int, end_bit: int) -> str:
        status_value = self.device_manager.get_point_value(
            self.point.did, self.entity_description.ac_zip_status_res_id
        )
        temp_status = StatusValue(int(status_value))
        if end_bit < 31:
            return str(
                temp_status.set_zero(end_bit + 1, 32).shift_bits(start_bit).value
            )
        else:
            return str(temp_status.shift_bits(start_bit).value)

    # P：[31,28]表示开关状态。0（表示关），1（表示开）
    # M：[27,24]表示模式。0（制热），1（制冷），2（自动），3（干燥），4（送风）
    # S：[23,20]表示风速。0（小风量），1（中风量），2（大风量），3（自动风量），15（不支持调节）
    # [19,18]表示风向，暂不支持
    # D：[17,16]表示扫风，0（扫风），1（固定风向）
    # T：[15,8]表示温度。参数为具体的温度值，243（温度+）244（温度-）255（不支持调节）
    def set_fan_mode(
        self, fan_mode: str
    ) -> None:  # FAN_SPEED_ENUM 0（小风量），1（中风量），2（大风量），3（自动风量），15（不支持调节）
        """Set new target fan mode."""
        if fan_mode not in HA_FAN_MODE_TO_AQARA:
            return

        value = self._set_ac_zip_status_value(
            start_bit=28, end_bit=31, setting_value="1"
        )
        value = self._shift_value(
            start_bit=20,
            end_bit=23,
            org_value=value,
            setting_value=HA_FAN_MODE_TO_AQARA[fan_mode],
        )

        # value = self._set_ac_zip_status_value(
        #     start_bit=20, end_bit=23, setting_value=HA_FAN_MODE_TO_AQARA[fan_mode]
        # )
        self._send_command([{self.entity_description.ac_zip_status_res_id: value}])

    def set_humidity(self, humidity: float) -> None:
        """Set new target humidity."""
        return None

    def set_swing_mode(self, swing_mode: str) -> None:
        """Set new target swing operation.
        [19,18]表示风向,暂不支持
        D:[17,16]表示扫风,0(扫风),1(固定风向)
        """
        # if swing_mode not in ["0", "1"]:
        #     return None
        value = "0" if swing_mode == "on" else "1"
        value = self._set_ac_zip_status_value(
            start_bit=16, end_bit=17, setting_value=value
        )
        self._send_command([{self.entity_description.ac_zip_status_res_id: value}])

    def set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        # setting_value = round(self._set_temperature_type.scale_value_back(kwargs["temperature"])
        value = self._set_ac_zip_status_value(
            start_bit=28, end_bit=31, setting_value="1"
        )
        value = self._shift_value(
            start_bit=8,
            end_bit=15,
            org_value=value,
            setting_value=str(int(kwargs["temperature"])),
        )

        # value = self._set_ac_zip_status_value(
        #     start_bit=8, end_bit=15, setting_value=str(int(kwargs["temperature"]))
        # )
        self._send_command([{self.entity_description.ac_zip_status_res_id: value}])

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        value = self.device_manager.get_point_value(
            self.point.did, self.entity_description.temperature_value_res_id
        )
        if value == "":
            return None
        return float(value) / 100

    @property
    def target_temperature_high(self) -> float | None:
        """Return the highbound target temperature we try to reach.

        Requires SUPPORT_TARGET_TEMPERATURE_RANGE.
        """
        return self._attr_target_temperature_high

    @property
    def target_temperature_low(self) -> float | None:
        """Return the lowbound target temperature we try to reach.

        Requires SUPPORT_TARGET_TEMPERATURE_RANGE.
        """
        return self._attr_target_temperature_low

    @property
    def current_humidity(self) -> int | None:
        """Return the current humidity."""
        # return round(self._current_humidity_type.scale_value(humidity))
        value = self.device_manager.get_point_value(
            self.point.did, self.entity_description.humidity_value_res_id
        )
        if value == "":
            return None
        return int(value)

    @property
    def target_temperature(self) -> float | None:
        """Return the temperature currently set to be reached."""
        # return self._set_temperature_type.scale_value(temperature)
        value = self._get_ac_zip_status_value(start_bit=8, end_bit=15)
        return float(value)

    @property
    def target_humidity(self) -> int | None:
        """Return the humidity currently set to be reached."""
        # return round(self._set_humidity_type.scale_value(humidity))
        return None

    @property
    def hvac_mode(self) -> str:
        """Return hvac mode.
        M:[27,24]表示模式。0(制热),1(制冷),2(自动),3(干燥),4(送风)
        """
        value = self._get_ac_zip_status_value(start_bit=24, end_bit=27)
        return AQARA_HVAC_TO_HA.get(value, "off")

    @property
    def fan_mode(
        self,
    ) -> str | None:  # FAN_SPEED_ENUM  {  # 0（小风量），1（中风量），2（大风量），3（自动风量）
        """Return fan mode."""
        key = self._get_ac_zip_status_value(start_bit=16, end_bit=17)
        return AQARA_FAN_MODE_TO_HA.get(key, None)

    @property
    def swing_mode(self) -> str:
        """Return swing mode.
        [19,18]表示风向,暂不支持
        D:[17,16]表示扫风,0(扫风),1(固定风向)
        """

        value = self._get_ac_zip_status_value(start_bit=16, end_bit=17)
        if value == "0":
            return SWING_ON
        else:
            return SWING_OFF

    def turn_on(self) -> None:  # P：[31,28]表示开关状态。0（表示关），1（表示开）
        """Turn the device on, retaining current HVAC (if supported)."""
        value = self._set_ac_zip_status_value(
            start_bit=28, end_bit=31, setting_value="1"
        )
        self._send_command([{self.entity_description.ac_zip_status_res_id: value}])

    def turn_off(self) -> None:
        """Turn the device on, retaining current HVAC (if supported)."""
        value = self._set_ac_zip_status_value(
            start_bit=28, end_bit=31, setting_value="0"
        )
        self._send_command([{self.entity_description.ac_zip_status_res_id: value}])
