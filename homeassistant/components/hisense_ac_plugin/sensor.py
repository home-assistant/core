"""Platform for Hisense AC sensor integration."""
from __future__ import annotations

import logging
from typing import Any, Callable

from homeassistant.components.sensor import (
    SensorEntity,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.const import (
    UnitOfTemperature,
    UnitOfEnergy,
)

from .api import HisenseApiClient
from .const import (
    DOMAIN,
    StatusKey,
    ATTR_INDOOR_TEMPERATURE,
    ATTR_ENERGY_CONSUMPTION,
)
from .models import DeviceInfo as HisenseDeviceInfo
from .coordinator import HisenseACPluginDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

# Define sensor types
SENSOR_TYPES = {
    # "indoor_temperature": {
    #     "key": StatusKey.TEMPERATURE,
    #     "name": "Indoor Temperature",
    #     "icon": "mdi:thermometer",
    #     "device_class": SensorDeviceClass.TEMPERATURE,
    #     "state_class": SensorStateClass.MEASUREMENT,
    #     "unit": UnitOfTemperature.CELSIUS,
    #     "description": "Current indoor temperature"
    # },
    "power_consumption": {
        "key": StatusKey.CONSUMPTION,  # 使用设备特定的键名
        "name": "Power Consumption",
        "icon": "mdi:flash",
        "device_class": SensorDeviceClass.ENERGY,
        "state_class": SensorStateClass.TOTAL_INCREASING,
        "unit": UnitOfEnergy.KILO_WATT_HOUR,
        "description": "Accumulated power consumption"
    },
    "indoor_humidity": {
        "key": StatusKey.FHUMIDITY,  # 使用设备特定的键名
        "name": "Indoor Humidity",
        "icon": "mdi:water-percent",  # 使用湿度相关的图标
        "device_class": SensorDeviceClass.HUMIDITY,  # 使用正确的设备类
        "state_class": SensorStateClass.MEASUREMENT,  # 使用正确的状态类
        "unit": "%",  # 使用百分比作为单位
        "description": "Current indoor humidity"  # 更新描述
    },
    # "water_tank_temp": {
    #     "key": StatusKey.WATER_TANK_TEMP,  # 使用设备特定的键名
    #     "name": "Water Tank Temp",  # 水箱温度
    #     "icon": "mdi:thermometer",  # 使用温度相关的图标
    #     "device_class": SensorDeviceClass.TEMPERATURE,  # 使用正确的设备类
    #     "state_class": SensorStateClass.MEASUREMENT,  # 使用正确的状态类
    #     "unit": UnitOfTemperature.CELSIUS,  # 使用摄氏度作为单位
    #     "description": "Current water tank temperature"  # 更新描述
    # },
    "in_water_temp": {
        "key": StatusKey.IN_WATER_TEMP,  # 使用设备特定的键名
        "name": "In Water Temp",  # 进水口温度
        "icon": "mdi:thermometer",  # 使用温度相关的图标
        "device_class": SensorDeviceClass.TEMPERATURE,  # 使用正确的设备类
        "state_class": SensorStateClass.MEASUREMENT,  # 使用正确的状态类
        "unit": UnitOfTemperature.CELSIUS,  # 使用摄氏度作为单位
        "description": "Current in water temperature"  # 更新描述
    },
    "out_water_temp": {
        "key": StatusKey.OUT_WATER_TEMP,  # 使用设备特定的键名
        "name": "Out Water Temp",  # 出水口温度
        "icon": "mdi:thermometer",  # 使用温度相关的图标
        "device_class": SensorDeviceClass.TEMPERATURE,  # 使用正确的设备类
        "state_class": SensorStateClass.MEASUREMENT,  # 使用正确的状态类
        "unit": UnitOfTemperature.CELSIUS,  # 使用摄氏度作为单位
        "description": "Current out water temperature"  # 更新描述
    },
    "f_zone1water_temp1": {
        "key": StatusKey.ZONE1WATER_TEMP1,  # 使用设备特定的键名
        "name": "温区1实际值",  # 温区1实际值
        "icon": "mdi:thermometer",  # 使用温度相关的图标
        "device_class": SensorDeviceClass.TEMPERATURE,  # 使用正确的设备类
        "state_class": SensorStateClass.MEASUREMENT,  # 使用正确的状态类
        "unit": UnitOfTemperature.CELSIUS,  # 使用摄氏度作为单位
        "description": "Current out water temperature"  # 更新描述
    },
    "f_zone2water_temp2": {
        "key": StatusKey.ZONE2WATER_TEMP2,  # 使用设备特定的键名
        "name": "温区2实际值",  # 温区2实际值
        "icon": "mdi:thermometer",  # 使用温度相关的图标
        "device_class": SensorDeviceClass.TEMPERATURE,  # 使用正确的设备类
        "state_class": SensorStateClass.MEASUREMENT,  # 使用正确的状态类
        "unit": UnitOfTemperature.CELSIUS,  # 使用摄氏度作为单位
        "description": "Current out water temperature"  # 更新描述
    },
    "f_e_intemp": {
        "key": StatusKey.F_E_INTEMP,
        "name": "室内温度传感器故障",
        "icon": "mdi:alert",
        "device_class": SensorDeviceClass.ENUM,
        "state_class": None,
        "unit": None,
        "description": "室内温度传感器故障"
    },
    "f_e_incoiltemp": {
        "key": StatusKey.F_E_INCOILTEMP,
        "name": "室内盘管温度传感器故障",
        "icon": "mdi:alert",
        "device_class": SensorDeviceClass.ENUM,
        "state_class": None,
        "unit": None,
        "description": "室内盘管温度传感器故障"
    },
    "f_e_inhumidity": {
        "key": StatusKey.F_E_INHUMIDITY,
        "name": "室内湿度传感器故障",
        "icon": "mdi:alert",
        "device_class": SensorDeviceClass.ENUM,
        "state_class": None,
        "unit": None,
        "description": "室内湿度传感器故障"
    },
    "f_e_infanmotor": {
        "key": StatusKey.F_E_INFANMOTOR,
        "name": "室内风机电机运转异常故障",
        "icon": "mdi:alert",
        "device_class": SensorDeviceClass.ENUM,
        "state_class": None,
        "unit": None,
        "description": "室内风机电机运转异常故障"
    },
    "f_e_arkgrille": {
        "key": StatusKey.F_E_ARKGRILLE,
        "name": "柜机格栅保护告警",
        "icon": "mdi:alert",
        "device_class": SensorDeviceClass.ENUM,
        "state_class": None,
        "unit": None,
        "description": "柜机格栅保护告警"
    },
    "f_e_invzero": {
        "key": StatusKey.F_E_INVZERO,
        "name": "室内电压过零检测故障",
        "icon": "mdi:alert",
        "device_class": SensorDeviceClass.ENUM,
        "state_class": None,
        "unit": None,
        "description": "室内电压过零检测故障"
    },
    "f_e_incom": {
        "key": StatusKey.F_E_INCOM,
        "name": "室内外通信故障",
        "icon": "mdi:alert",
        "device_class": SensorDeviceClass.ENUM,
        "state_class": None,
        "unit": None,
        "description": "室内外通信故障"
    },
    "f_e_indisplay": {
        "key": StatusKey.F_E_INDISPLAY,
        "name": "室内控制板与显示板通信故障",
        "icon": "mdi:alert",
        "device_class": SensorDeviceClass.ENUM,
        "state_class": None,
        "unit": None,
        "description": "室内控制板与显示板通信故障"
    },
    "f_e_inkeys": {
        "key": StatusKey.F_E_INKEYS,
        "name": "室内控制板与按键板通信故障",
        "icon": "mdi:alert",
        "device_class": SensorDeviceClass.ENUM,
        "state_class": None,
        "unit": None,
        "description": "室内控制板与按键板通信故障"
    },
    "f_e_inwifi": {
        "key": StatusKey.F_E_INWIFI,
        "name": "WIFI控制板与室内控制板通信故障",
        "icon": "mdi:alert",
        "device_class": SensorDeviceClass.ENUM,
        "state_class": None,
        "unit": None,
        "description": "WIFI控制板与室内控制板通信故障"
    },
    "f_e_inele": {
        "key": StatusKey.F_E_INELE,
        "name": "室内控制板与室内电量板通信故障",
        "icon": "mdi:alert",
        "device_class": SensorDeviceClass.ENUM,
        "state_class": None,
        "unit": None,
        "description": "室内控制板与室内电量板通信故障"
    },
    "f_e_ineeprom": {
        "key": StatusKey.F_E_INEEPROM,
        "name": "室内控制板EEPROM出错",
        "icon": "mdi:alert",
        "device_class": SensorDeviceClass.ENUM,
        "state_class": None,
        "unit": None,
        "description": "室内控制板EEPROM出错"
    },
    "f_e_outeeprom": {
        "key": StatusKey.F_E_OUTEEPROM,
        "name": "室外EEPROM出错",
        "icon": "mdi:alert",
        "device_class": SensorDeviceClass.ENUM,
        "state_class": None,
        "unit": None,
        "description": "室外EEPROM出错"
    },
    "f_e_outcoiltemp": {
        "key": StatusKey.F_E_OUTCOILTEMP,
        "name": "室外盘管温度传感器故障",
        "icon": "mdi:alert",
        "device_class": SensorDeviceClass.ENUM,
        "state_class": None,
        "unit": None,
        "description": "室外盘管温度传感器故障"
    },
    "f_e_outgastemp": {
        "key": StatusKey.F_E_OUTGASTEMP,
        "name": "排气温度传感器故障",
        "icon": "mdi:alert",
        "device_class": SensorDeviceClass.ENUM,
        "state_class": None,
        "unit": None,
        "description": "排气温度传感器故障"
    },
    "f_e_outtemp": {
        "key": StatusKey.F_E_OUTTEMP,
        "name": "室外环境温度传感器故障",
        "icon": "mdi:alert",
        "device_class": SensorDeviceClass.ENUM,
        "state_class": None,
        "unit": None,
        "description": "室外环境温度传感器故障"
    },
    "f_e_push": {
        "key": StatusKey.F_E_PUSH,
        "name": "推送故障",
        "icon": "mdi:alert",
        "device_class": SensorDeviceClass.ENUM,
        "state_class": None,
        "unit": None,
        "description": "推送故障"
    },
    "f_e_waterfull": {
        "key": StatusKey.F_E_WATERFULL,
        "name": "水满报警",
        "icon": "mdi:alert",
        "device_class": SensorDeviceClass.ENUM,
        "state_class": None,
        "unit": None,
        "description": "水满报警"
    },
    "f_e_upmachine": {
        "key": StatusKey.F_E_UPMACHINE,
        "name": "室内（上部）直流风机电机运转异常故障",
        "icon": "mdi:alert",
        "device_class": SensorDeviceClass.ENUM,
        "state_class": None,
        "unit": None,
        "description": "室内（上部）直流风机电机运转异常故障"
    },
    "f_e_dwmachine": {
        "key": StatusKey.F_E_DWMACHINE,
        "name": "室外（下部）直流风机电机运转异常故障",
        "icon": "mdi:alert",
        "device_class": SensorDeviceClass.ENUM,
        "state_class": None,
        "unit": None,
        "description": "室外（下部）直流风机电机运转异常故障"
    },
    "f_e_filterclean": {
        "key": StatusKey.F_E_FILTERCLEAN,
        "name": "过滤网清洁告警",
        "icon": "mdi:alert",
        "device_class": SensorDeviceClass.ENUM,
        "state_class": None,
        "unit": None,
        "description": "过滤网清洁告警"
    },
    "f_e_wetsensor": {
        "key": StatusKey.F_E_WETSENSOR,
        "name": "湿敏传感器故障",
        "icon": "mdi:alert",
        "device_class": SensorDeviceClass.ENUM,
        "state_class": None,
        "unit": None,
        "description": "湿敏传感器故障"
    },
    "f_e_tubetemp": {
        "key": StatusKey.F_E_TUBETEMP,
        "name": "管温传感器故障",
        "icon": "mdi:alert",
        "device_class": SensorDeviceClass.ENUM,
        "state_class": None,
        "unit": None,
        "description": "管温传感器故障"
    },
    "f_e_temp": {
        "key": StatusKey.F_E_TEMP,
        "name": "室温传感器故障",
        "icon": "mdi:alert",
        "device_class": SensorDeviceClass.ENUM,
        "state_class": None,
        "unit": None,
        "description": "室温传感器故障"
    },
    "f_e_pump": {
        "key": StatusKey.F_E_PUMP,
        "name": "水泵故障",
        "icon": "mdi:alert",
        "device_class": SensorDeviceClass.ENUM,
        "state_class": None,
        "unit": None,
        "description": "水泵故障"
    },
    "f_e_exhaust_hightemp": {
        "key": StatusKey.F_E_EXHAUST_HIGHTEMP,
        "name": "排气温度过高",
        "icon": "mdi:alert",
        "device_class": SensorDeviceClass.ENUM,
        "state_class": None,
        "unit": None,
        "description": "排气温度过高"
    },
    "f_e_high_pressure": {
        "key": StatusKey.F_E_HIGH_PRESSURE,
        "name": "高压故障",
        "icon": "mdi:alert",
        "device_class": SensorDeviceClass.ENUM,
        "state_class": None,
        "unit": None,
        "description": "高压故障"
    },
    "f_e_low_pressure": {
        "key": StatusKey.F_E_LOW_PRESSURE,
        "name": "低压故障",
        "icon": "mdi:alert",
        "device_class": SensorDeviceClass.ENUM,
        "state_class": None,
        "unit": None,
        "description": "低压故障"
    },
    "f_e_wire_drive": {
        "key": StatusKey.F_E_WIRE_DRIVE,
        "name": "通信故障",
        "icon": "mdi:alert",
        "device_class": SensorDeviceClass.ENUM,
        "state_class": None,
        "unit": None,
        "description": "通信故障"
    },
    "f_e_coiltemp": {
        "key": StatusKey.F_E_COILTEMP,
        "name": "盘管温度传感器故障",
        "icon": "mdi:alert",
        "device_class": SensorDeviceClass.ENUM,
        "state_class": None,
        "unit": None,
        "description": "盘管温度传感器故障"
    },
    "f_e_env_temp": {
        "key": StatusKey.F_E_ENV_TEMP,
        "name": "环境温度传感器故障",
        "icon": "mdi:alert",
        "device_class": SensorDeviceClass.ENUM,
        "state_class": None,
        "unit": None,
        "description": "环境温度传感器故障"
    },
    "f_e_exhaust": {
        "key": StatusKey.F_E_EXHAUST,
        "name": "排气温度传感器故障",
        "icon": "mdi:alert",
        "device_class": SensorDeviceClass.ENUM,
        "state_class": None,
        "unit": None,
        "description": "排气温度传感器故障"
    },
    "f_e_inwater": {
        "key": StatusKey.F_E_INWATER,
        "name": "进水温度传感器故障",
        "icon": "mdi:alert",
        "device_class": SensorDeviceClass.ENUM,
        "state_class": None,
        "unit": None,
        "description": "进水温度传感器故障"
    },
    "f_e_water_tank": {
        "key": StatusKey.F_E_WATER_TANK,
        "name": "水箱温度传感器故障",
        "icon": "mdi:alert",
        "device_class": SensorDeviceClass.ENUM,
        "state_class": None,
        "unit": None,
        "description": "水箱温度传感器故障"
    },
    "f_e_return_air": {
        "key": StatusKey.F_E_RETURN_AIR,
        "name": "回气温度传感器故障",
        "icon": "mdi:alert",
        "device_class": SensorDeviceClass.ENUM,
        "state_class": None,
        "unit": None,
        "description": "回气温度传感器故障"
    },
    "f_e_outwater": {
        "key": StatusKey.F_E_OUTWATER,
        "name": "出水温度传感器故障",
        "icon": "mdi:alert",
        "device_class": SensorDeviceClass.ENUM,
        "state_class": None,
        "unit": None,
        "description": "出水温度传感器故障"
    },
    "f_e_solar_temperature": {
        "key": StatusKey.F_E_SOLAR_TEMPERATURE,
        "name": "太阳能温度传感器故障",
        "icon": "mdi:alert",
        "device_class": SensorDeviceClass.ENUM,
        "state_class": None,
        "unit": None,
        "description": "太阳能温度传感器故障"
    },
    "f_e_compressor_overload": {
        "key": StatusKey.F_E_COMPRESSOR_OVERLOAD,
        "name": "压缩机过载",
        "icon": "mdi:alert",
        "device_class": SensorDeviceClass.ENUM,
        "state_class": None,
        "unit": None,
        "description": "压缩机过载"
    },
    "f_e_excessive_current": {
        "key": StatusKey.F_E_EXCESSIVE_CURRENT,
        "name": "电流过大",
        "icon": "mdi:alert",
        "device_class": SensorDeviceClass.ENUM,
        "state_class": None,
        "unit": None,
        "description": "电流过大"
    },
    "f_e_fan_fault": {
        "key": StatusKey.F_E_FAN_FAULT,
        "name": "风机故障",
        "icon": "mdi:alert",
        "device_class": SensorDeviceClass.ENUM,
        "state_class": None,
        "unit": None,
        "description": "风机故障"
    },
    "f_e_displaycom_fault": {
        "key": StatusKey.F_E_DISPLAYCOM_FAULT,
        "name": "显示板通信故障",
        "icon": "mdi:alert",
        "device_class": SensorDeviceClass.ENUM,
        "state_class": None,
        "unit": None,
        "description": "显示板通信故障"
    },
    "f_e_upwatertank_fault": {
        "key": StatusKey.F_E_UPWATERTANK_FAULT,
        "name": "水箱上部温度传感器故障",
        "icon": "mdi:alert",
        "device_class": SensorDeviceClass.ENUM,
        "state_class": None,
        "unit": None,
        "description": "水箱上部温度传感器故障"
    },
    "f_e_downwatertank_fault": {
        "key": StatusKey.F_E_DOWNWATERTANK_FAULT,
        "name": "水箱下部温度传感器故障",
        "icon": "mdi:alert",
        "device_class": SensorDeviceClass.ENUM,
        "state_class": None,
        "unit": None,
        "description": "水箱下部温度传感器故障"
    },
    "f_e_suctiontemp_fault": {
        "key": StatusKey.F_E_SUCTIONTEMP_FAULT,
        "name": "吸气温度传感器故障",
        "icon": "mdi:alert",
        "device_class": SensorDeviceClass.ENUM,
        "state_class": None,
        "unit": None,
        "description": "吸气温度传感器故障"
    },
    "f_e_e2data_fault": {
        "key": StatusKey.F_E_E2DATA_FAULT,
        "name": "EEPROM数据故障",
        "icon": "mdi:alert",
        "device_class": SensorDeviceClass.ENUM,
        "state_class": None,
        "unit": None,
        "description": "EEPROM数据故障"
    },
    "f_e_drivecom_fault": {
        "key": StatusKey.F_E_DRIVECOM_FAULT,
        "name": "驱动板通信故障",
        "icon": "mdi:alert",
        "device_class": SensorDeviceClass.ENUM,
        "state_class": None,
        "unit": None,
        "description": "驱动板通信故障"
    },
    "f_e_drive_fault": {
        "key": StatusKey.F_E_DRIVE_FAULT,
        "name": "驱动板故障",
        "icon": "mdi:alert",
        "device_class": SensorDeviceClass.ENUM,
        "state_class": None,
        "unit": None,
        "description": "驱动板故障"
    },
    "f_e_returnwatertemp_fault": {
        "key": StatusKey.F_E_RETURNWATERTEMP_FAULT,
        "name": "回水温度传感器故障",
        "icon": "mdi:alert",
        "device_class": SensorDeviceClass.ENUM,
        "state_class": None,
        "unit": None,
        "description": "回水温度传感器故障"
    },
    "f_e_clockchip_fault": {
        "key": StatusKey.F_E_CLOCKCHIP_FAULT,
        "name": "时钟芯片故障",
        "icon": "mdi:alert",
        "device_class": SensorDeviceClass.ENUM,
        "state_class": None,
        "unit": None,
        "description": "时钟芯片故障"
    },
    "f_e_eanode_fault": {
        "key": StatusKey.F_E_EANODE_FAULT,
        "name": "电子阳极故障",
        "icon": "mdi:alert",
        "device_class": SensorDeviceClass.ENUM,
        "state_class": None,
        "unit": None,
        "description": "电子阳极故障"
    },
    "f_e_powermodule_fault": {
        "key": StatusKey.F_E_POWERMODULE_FAULT,
        "name": "电量模块故障",
        "icon": "mdi:alert",
        "device_class": SensorDeviceClass.ENUM,
        "state_class": None,
        "unit": None,
        "description": "电量模块故障"
    },
    "f_e_fan_fault_tip": {
        "key": StatusKey.F_E_FAN_FAULT_TIP,
        "name": "外风机故障",
        "icon": "mdi:alert",
        "device_class": SensorDeviceClass.ENUM,
        "state_class": None,
        "unit": None,
        "description": "外风机故障"
    },
    "f_e_pressuresensor_fault_tip": {
        "key": StatusKey.F_E_PRESSURESENSOR_FAULT_TIP,
        "name": "压力传感器故障",
        "icon": "mdi:alert",
        "device_class": SensorDeviceClass.ENUM,
        "state_class": None,
        "unit": None,
        "description": "压力传感器故障"
    },
    "f_e_tempfault_solarwater_tip": {
        "key": StatusKey.F_E_TEMPFAULT_SOLARWATER_TIP,
        "name": "太阳能水温感温故障",
        "icon": "mdi:alert",
        "device_class": SensorDeviceClass.ENUM,
        "state_class": None,
        "unit": None,
        "description": "太阳能水温感温故障"
    },
    "f_e_tempfault_mixedwater_tip": {
        "key": StatusKey.F_E_TEMPFAULT_MIXEDWATER_TIP,
        "name": "混水感温故障",
        "icon": "mdi:alert",
        "device_class": SensorDeviceClass.ENUM,
        "state_class": None,
        "unit": None,
        "description": "混水感温故障"
    },
    "f_e_tempfault_balance_watertank_tip": {
        "key": StatusKey.F_E_TEMPFAULT_BALANCE_WATERTANK_TIP,
        "name": "平衡水箱感温故障",
        "icon": "mdi:alert",
        "device_class": SensorDeviceClass.ENUM,
        "state_class": None,
        "unit": None,
        "description": "平衡水箱感温故障"
    },
    "f_e_tempfault_eheating_outlet_tip": {
        "key": StatusKey.F_E_TEMPFAULT_EHEATING_OUTLET_TIP,
        "name": "内置电加热出水感温故障",
        "icon": "mdi:alert",
        "device_class": SensorDeviceClass.ENUM,
        "state_class": None,
        "unit": None,
        "description": "内置电加热出水感温故障"
    },
    "f_e_tempfault_refrigerant_outlet_tip": {
        "key": StatusKey.F_E_TEMPFAULT_REFRIGERANT_OUTLET_TIP,
        "name": "冷媒出口温感故障",
        "icon": "mdi:alert",
        "device_class": SensorDeviceClass.ENUM,
        "state_class": None,
        "unit": None,
        "description": "冷媒出口温感故障"
    },
    "f_e_tempfault_refrigerant_inlet_tip": {
        "key": StatusKey.F_E_TEMPFAULT_REFRIGERANT_INLET_TIP,
        "name": "冷媒进口温感故障",
        "icon": "mdi:alert",
        "device_class": SensorDeviceClass.ENUM,
        "state_class": None,
        "unit": None,
        "description": "冷媒进口温感故障"
    },
    "f_e_inwaterpump_tip": {
        "key": StatusKey.F_E_INWATERPUMP_TIP,
        "name": "内置水泵故障",
        "icon": "mdi:alert",
        "device_class": SensorDeviceClass.ENUM,
        "state_class": None,
        "unit": None,
        "description": "内置水泵故障"
    },
    "f_e_outeeprom_tip": {
        "key": StatusKey.F_E_OUTEEPROM_TIP,
        "name": "外机EEPROM故障",
        "icon": "mdi:alert",
        "device_class": SensorDeviceClass.ENUM,
        "state_class": None,
        "unit": None,
        "description": "外机EEPROM故障"
    }
}

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Hisense AC sensor platform."""
    coordinator: HisenseACPluginDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    try:
        # Get devices from coordinator
        devices = coordinator.data
        _LOGGER.debug("Setting up sensors with coordinator data: %s", devices)

        if not devices:
            _LOGGER.warning("No devices found in coordinator data")
            return

        entities = []
        for device_id, device in devices.items():
            _LOGGER.debug("Processing device for sensors: %s", device.to_dict())
            if isinstance(device, HisenseDeviceInfo) and device.is_devices():
                # Add sensors for each supported feature
                for sensor_type, sensor_info in SENSOR_TYPES.items():
                    # Check if the device supports this attribute
                    parser = coordinator.api_client.parsers.get(device.device_id)
                    if device.has_attribute(sensor_info["key"],parser):
                        if device.status.get("f_zone2_select") == "0" and sensor_type == "f_zone2water_temp2":
                            continue
                        _LOGGER.info(
                            "Adding  sensor for device    %s: %s",
                            device.feature_code,
                            sensor_info["name"]
                        )
                        # 判断是否是故障传感器
                        is_fault_sensor = sensor_info["device_class"] == SensorDeviceClass.ENUM

                        # 获取当前值
                        current_value = device.status.get(sensor_info["key"])
                        static_data = coordinator.api_client.static_data.get(device.device_id)
                        _LOGGER.info("获取到静态数据: %s: %s", device.feature_code, static_data)
                        if static_data is not None:
                            hasHumidity = static_data.get("f_humidity")
                            if sensor_info["key"] == StatusKey.FHUMIDITY and hasHumidity != "1":
                                continue

                        # 故障传感器特殊处理：值为0或None时跳过
                        if is_fault_sensor:
                            if current_value is None or current_value == "0":
                                continue
                        entity = HisenseSensor(
                            coordinator,
                            device,
                            sensor_type,
                            sensor_info
                        )
                        entities.append(entity)
                    status_list = device.failed_data
                    if not status_list:
                        continue
                    # 在遍历传感器类型时：
                    if sensor_type in status_list:  # 仅检查键是否存在
                        _LOGGER.info(
                            "添加告警 %s sensor for device: %s",
                            sensor_info["name"],
                            device.name
                        )
                        entity = HisenseSensor(
                            coordinator,
                            device,
                            sensor_type,
                            sensor_info
                        )
                        entities.append(entity)
            else:
                _LOGGER.warning(
                    "Skipping unsupported device: %s-%s (%s)",
                    getattr(device, 'type_code', None),
                    getattr(device, 'feature_code', None),
                    getattr(device, 'name', None)
                )

        if not entities:
            _LOGGER.warning("No supported sensors found")
            return

        _LOGGER.info("Adding %d sensor entities", len(entities))
        async_add_entities(entities)

    except Exception as err:
        _LOGGER.error("Failed to set up sensor platform: %s", err)
        raise

class HisenseSensor(CoordinatorEntity, SensorEntity):
    """Representation of a Hisense AC sensor."""

    _attr_has_entity_name = True

    def __init__(
            self,
            coordinator: HisenseACPluginDataUpdateCoordinator,
            device: HisenseDeviceInfo,
            sensor_type: str,
            sensor_info: dict,
    ) -> None:
        super().__init__(coordinator)
        self._device_id = device.device_id
        self._sensor_type = sensor_type
        self._sensor_key = sensor_info["key"]
        self._sensor_info = sensor_info
        self._attr_unique_id = f"{device.device_id}_{sensor_type}"
        self._attr_name = sensor_info["name"]
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device.device_id)},
            name=device.name,
            manufacturer="Hisense",
            model=f"{device.type_name} ({device.feature_name})",
        )
        self._attr_icon = sensor_info["icon"]
        self._attr_device_class = sensor_info.get("device_class")
        self._attr_state_class = sensor_info.get("state_class")
        self._attr_native_unit_of_measurement = sensor_info.get("unit")
        self._attr_entity_registry_enabled_default = True

    def _handle_coordinator_update(self) -> None:
        device = self.coordinator.get_device(self._device_id)
        if not device:
            _LOGGER.warning("Device %s not found during sensor update", self._device_id)
            return
        """处理协调器更新，实现动态实体管理"""
        # 获取当前设备状态
        device = self.coordinator.get_device(self._device_id)
        current_value = device.get_status_value(self._sensor_key)

        # 故障传感器特殊处理
        if self._sensor_info["device_class"] == SensorDeviceClass.ENUM:
            # 当值变为0或无效时移除实体
            if current_value in (None, "0"):
                _LOGGER.info("Removing fault sensor %s (current value: %s)",
                             self.entity_id, current_value)
                self.hass.async_create_task(
                    self.hass.services.async_call(
                        "entity_registry",
                        "remove",
                        {"entity_id": self.entity_id}
                    )
                )
                return  # 终止后续处理

        # 调用父类处理更新
        super()._handle_coordinator_update()

    @property
    def name(self) -> str:
        """动态获取翻译后的名称"""
        hass = self.hass
        translation_key = self._sensor_type  # 使用传感器类型作为键
        current_lang = hass.config.language
        translations = hass.data.get(f"{DOMAIN}.translations", {}).get(current_lang, {})
        translated_name = translations.get(translation_key, self._sensor_info["name"])
        return translated_name

    @property
    def _device(self):
        """Get current device data from coordinator."""
        return self.coordinator.get_device(self._device_id)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        if not super().available:  # 继承父类的可用性检查（设备在线）
            return False
        current_mode = self._device.get_status_value(StatusKey.MODE)  # 使用正确键名
        # 判断自动模式
        if current_mode in ["3"]:
            _LOGGER.debug("设备处于自动模式，温度控制不可用")
            return False
        if self._sensor_type == "f_zone2water_temp2":
            allowed_modes = {"0", "6"}  # 仅允许制热和制热+制热水模式
            if current_mode not in allowed_modes:
                return False

        return True

    @property
    def native_value(self) -> float | None:
        """Return the sensor value."""
        if not self._device:
            return None
        value = self._device.get_status_value(self._sensor_key)
        if value is None:
            return None
            
        try:
            # Convert to float for numeric sensors
            if self._attr_device_class in [
                SensorDeviceClass.TEMPERATURE,
                SensorDeviceClass.ENERGY
            ]:
                return float(value)
            return value
        except (ValueError, TypeError):
            _LOGGER.warning(
                "Could not convert %s value '%s' to float",
                self._attr_name,
                value
            )
            return None
