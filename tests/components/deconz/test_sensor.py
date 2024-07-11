"""deCONZ sensor platform tests."""

from datetime import timedelta
from typing import Any

import pytest

from homeassistant.components.deconz.const import CONF_ALLOW_CLIP_SENSOR
from homeassistant.components.sensor import (
    DOMAIN as SENSOR_DOMAIN,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.config_entries import RELOAD_AFTER_UPDATE_DELAY, ConfigEntry
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    CONCENTRATION_PARTS_PER_BILLION,
    CONCENTRATION_PARTS_PER_MILLION,
    STATE_UNAVAILABLE,
    EntityCategory,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.util import dt as dt_util

from .conftest import ConfigEntryFactoryType, WebsocketDataType

from tests.common import async_fire_time_changed

TEST_DATA = [
    (  # Air quality sensor
        {
            "config": {
                "on": True,
                "reachable": True,
            },
            "ep": 2,
            "etag": "c2d2e42396f7c78e11e46c66e2ec0200",
            "lastseen": "2020-11-20T22:48Z",
            "manufacturername": "BOSCH",
            "modelid": "AIR",
            "name": "BOSCH Air quality sensor",
            "state": {
                "airquality": "poor",
                "airqualityppb": 809,
                "lastupdated": "2020-11-20T22:48:00.209",
            },
            "swversion": "20200402",
            "type": "ZHAAirQuality",
            "uniqueid": "00:12:4b:00:14:4d:00:07-02-fdef",
        },
        {
            "entity_count": 2,
            "device_count": 3,
            "entity_id": "sensor.bosch_air_quality_sensor",
            "unique_id": "00:12:4b:00:14:4d:00:07-02-fdef-air_quality",
            "state": "poor",
            "entity_category": None,
            "device_class": None,
            "state_class": None,
            "attributes": {
                "friendly_name": "BOSCH Air quality sensor",
            },
            "websocket_event": {"state": {"airquality": "excellent"}},
            "next_state": "excellent",
        },
    ),
    (  # Air quality PPB sensor
        {
            "config": {
                "on": True,
                "reachable": True,
            },
            "ep": 2,
            "etag": "c2d2e42396f7c78e11e46c66e2ec0200",
            "lastseen": "2020-11-20T22:48Z",
            "manufacturername": "BOSCH",
            "modelid": "AIR",
            "name": "BOSCH Air quality sensor",
            "state": {
                "airquality": "poor",
                "airqualityppb": 809,
                "lastupdated": "2020-11-20T22:48:00.209",
            },
            "swversion": "20200402",
            "type": "ZHAAirQuality",
            "uniqueid": "00:12:4b:00:14:4d:00:07-02-fdef",
        },
        {
            "entity_count": 2,
            "device_count": 3,
            "entity_id": "sensor.bosch_air_quality_sensor_ppb",
            "unique_id": "00:12:4b:00:14:4d:00:07-02-fdef-air_quality_ppb",
            "state": "809",
            "entity_category": None,
            "device_class": None,
            "state_class": SensorStateClass.MEASUREMENT,
            "attributes": {
                "friendly_name": "BOSCH Air quality sensor PPB",
                "state_class": "measurement",
                "unit_of_measurement": CONCENTRATION_PARTS_PER_BILLION,
            },
            "websocket_event": {"state": {"airqualityppb": 1000}},
            "next_state": "1000",
        },
    ),
    (  # Air quality 6 in 1 (without airquality) -> airquality_co2_density
        {
            "config": {
                "on": True,
                "reachable": True,
            },
            "etag": "e1a406dbbe1438fa924007309ef46a01",
            "lastseen": "2023-03-29T18:25Z",
            "manufacturername": "_TZE200_dwcarsat",
            "modelid": "TS0601",
            "name": "AirQuality 1",
            "state": {
                "airquality_co2_density": 359,
                "airquality_formaldehyde_density": 4,
                "airqualityppb": 15,
                "lastupdated": "2023-03-29T19:05:41.903",
                "pm2_5": 8,
            },
            "type": "ZHAAirQuality",
            "uniqueid": "00:00:00:00:00:00:00:01-02-0113",
        },
        {
            "entity_count": 4,
            "device_count": 3,
            "entity_id": "sensor.airquality_1_co2",
            "unique_id": "00:00:00:00:00:00:00:01-02-0113-air_quality_co2",
            "state": "359",
            "entity_category": None,
            "device_class": SensorDeviceClass.CO2,
            "state_class": SensorStateClass.MEASUREMENT,
            "attributes": {
                "friendly_name": "AirQuality 1 CO2",
                "device_class": SensorDeviceClass.CO2,
                "state_class": SensorStateClass.MEASUREMENT,
                "unit_of_measurement": CONCENTRATION_PARTS_PER_MILLION,
            },
            "websocket_event": {"state": {"airquality_co2_density": 332}},
            "next_state": "332",
        },
    ),
    (  # Air quality 6 in 1 (without airquality) -> airquality_formaldehyde_density
        {
            "config": {
                "on": True,
                "reachable": True,
            },
            "etag": "e1a406dbbe1438fa924007309ef46a01",
            "lastseen": "2023-03-29T18:25Z",
            "manufacturername": "_TZE200_dwcarsat",
            "modelid": "TS0601",
            "name": "AirQuality 1",
            "state": {
                "airquality_co2_density": 359,
                "airquality_formaldehyde_density": 4,
                "airqualityppb": 15,
                "lastupdated": "2023-03-29T19:05:41.903",
                "pm2_5": 8,
            },
            "type": "ZHAAirQuality",
            "uniqueid": "00:00:00:00:00:00:00:01-02-0113",
        },
        {
            "entity_count": 4,
            "device_count": 3,
            "entity_id": "sensor.airquality_1_ch2o",
            "unique_id": "00:00:00:00:00:00:00:01-02-0113-air_quality_formaldehyde",
            "state": "4",
            "entity_category": None,
            "device_class": SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS,
            "state_class": SensorStateClass.MEASUREMENT,
            "attributes": {
                "friendly_name": "AirQuality 1 CH2O",
                "device_class": SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS,
                "state_class": SensorStateClass.MEASUREMENT,
                "unit_of_measurement": CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
            },
            "websocket_event": {"state": {"airquality_formaldehyde_density": 5}},
            "next_state": "5",
        },
    ),
    (  # Air quality 6 in 1 (without airquality) -> pm2_5
        {
            "config": {
                "on": True,
                "reachable": True,
            },
            "etag": "e1a406dbbe1438fa924007309ef46a01",
            "lastseen": "2023-03-29T18:25Z",
            "manufacturername": "_TZE200_dwcarsat",
            "modelid": "TS0601",
            "name": "AirQuality 1",
            "state": {
                "airquality_co2_density": 359,
                "airquality_formaldehyde_density": 4,
                "airqualityppb": 15,
                "lastupdated": "2023-03-29T19:05:41.903",
                "pm2_5": 8,
            },
            "type": "ZHAAirQuality",
            "uniqueid": "00:00:00:00:00:00:00:01-02-0113",
        },
        {
            "entity_count": 4,
            "device_count": 3,
            "entity_id": "sensor.airquality_1_pm25",
            "unique_id": "00:00:00:00:00:00:00:01-02-0113-air_quality_pm2_5",
            "state": "8",
            "entity_category": None,
            "device_class": SensorDeviceClass.PM25,
            "state_class": SensorStateClass.MEASUREMENT,
            "attributes": {
                "friendly_name": "AirQuality 1 PM25",
                "device_class": SensorDeviceClass.PM25,
                "state_class": SensorStateClass.MEASUREMENT,
                "unit_of_measurement": CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
            },
            "websocket_event": {"state": {"pm2_5": 11}},
            "next_state": "11",
        },
    ),
    (  # Battery sensor
        {
            "config": {
                "alert": "none",
                "on": True,
                "reachable": True,
            },
            "ep": 1,
            "etag": "23a8659f1cb22df2f51bc2da0e241bb4",
            "manufacturername": "IKEA of Sweden",
            "modelid": "FYRTUR block-out roller blind",
            "name": "FYRTUR block-out roller blind",
            "state": {
                "battery": 100,
                "lastupdated": "none",
            },
            "swversion": "2.2.007",
            "type": "ZHABattery",
            "uniqueid": "00:0d:6f:ff:fe:01:23:45-01-0001",
        },
        {
            "entity_count": 1,
            "device_count": 3,
            "entity_id": "sensor.fyrtur_block_out_roller_blind_battery",
            "unique_id": "00:0d:6f:ff:fe:01:23:45-01-0001-battery",
            "state": "100",
            "entity_category": EntityCategory.DIAGNOSTIC,
            "device_class": SensorDeviceClass.BATTERY,
            "state_class": SensorStateClass.MEASUREMENT,
            "attributes": {
                "state_class": "measurement",
                "on": True,
                "unit_of_measurement": "%",
                "device_class": "battery",
                "friendly_name": "FYRTUR block-out roller blind Battery",
            },
            "websocket_event": {"state": {"battery": 50}},
            "next_state": "50",
        },
    ),
    (  # Carbon dioxide sensor
        {
            "capabilities": {
                "measured_value": {
                    "unit": "PPB",
                }
            },
            "config": {
                "on": True,
                "reachable": True,
            },
            "etag": "dc3a3788ddd2a2d175ead376ea4d814c",
            "lastannounced": None,
            "lastseen": "2024-02-02T21:13Z",
            "manufacturername": "_TZE200_dwcarsat",
            "modelid": "TS0601",
            "name": "CarbonDioxide 35",
            "state": {
                "lastupdated": "2024-02-02T21:14:37.745",
                "measured_value": 370,
            },
            "type": "ZHACarbonDioxide",
            "uniqueid": "xx:xx:xx:xx:xx:xx:xx:xx-01-040d",
        },
        {
            "entity_count": 1,
            "device_count": 3,
            "entity_id": "sensor.carbondioxide_35",
            "unique_id": "xx:xx:xx:xx:xx:xx:xx:xx-01-040d-carbon_dioxide",
            "state": "370",
            "entity_category": None,
            "device_class": SensorDeviceClass.CO2,
            "state_class": CONCENTRATION_PARTS_PER_BILLION,
            "attributes": {
                "device_class": "carbon_dioxide",
                "friendly_name": "CarbonDioxide 35",
                "state_class": SensorStateClass.MEASUREMENT,
                "unit_of_measurement": CONCENTRATION_PARTS_PER_BILLION,
            },
            "websocket_event": {"state": {"measured_value": 500}},
            "next_state": "500",
        },
    ),
    (  # Consumption sensor
        {
            "config": {"on": True, "reachable": True},
            "ep": 1,
            "etag": "a99e5bc463d15c23af7e89946e784cca",
            "manufacturername": "Heiman",
            "modelid": "SmartPlug",
            "name": "Consumption 15",
            "state": {
                "consumption": 11342,
                "lastupdated": "2018-03-12T19:19:08",
                "power": 123,
            },
            "type": "ZHAConsumption",
            "uniqueid": "00:0d:6f:00:0b:7a:64:29-01-0702",
        },
        {
            "entity_count": 1,
            "device_count": 3,
            "entity_id": "sensor.consumption_15",
            "unique_id": "00:0d:6f:00:0b:7a:64:29-01-0702-consumption",
            "state": "11.342",
            "entity_category": None,
            "device_class": SensorDeviceClass.ENERGY,
            "state_class": SensorStateClass.TOTAL_INCREASING,
            "attributes": {
                "state_class": "total_increasing",
                "on": True,
                "power": 123,
                "unit_of_measurement": "kWh",
                "device_class": "energy",
                "friendly_name": "Consumption 15",
            },
            "websocket_event": {"state": {"consumption": 10000}},
            "next_state": "10.0",
        },
    ),
    (  # Daylight sensor
        {
            "config": {
                "configured": True,
                "on": True,
                "sunriseoffset": 30,
                "sunsetoffset": -30,
            },
            "etag": "55047cf652a7e594d0ee7e6fae01dd38",
            "manufacturername": "Philips",
            "modelid": "PHDL00",
            "name": "Daylight",
            "state": {
                "daylight": True,
                "lastupdated": "2018-03-24T17:26:12",
                "status": 170,
            },
            "swversion": "1.0",
            "type": "Daylight",
            "uniqueid": "01:23:4E:FF:FF:56:78:9A-01",
        },
        {
            "enable_entity": True,
            "entity_count": 1,
            "device_count": 3,
            "entity_id": "sensor.daylight",
            "unique_id": "01:23:4E:FF:FF:56:78:9A-01-daylight_status",
            "old-unique_id": "01:23:4E:FF:FF:56:78:9A-01",
            "state": "solar_noon",
            "entity_category": None,
            "device_class": None,
            "state_class": None,
            "attributes": {
                "on": True,
                "daylight": True,
                "icon": "mdi:white-balance-sunny",
                "friendly_name": "Daylight",
            },
            "websocket_event": {"state": {"status": 210}},
            "next_state": "dusk",
        },
    ),
    (  # Formaldehyde
        {
            "capabilities": {
                "measured_value": {
                    "unit": "PPM",
                }
            },
            "config": {
                "on": True,
                "reachable": True,
            },
            "etag": "bb01ac0313b6724e8c540a6eef7cc3cb",
            "lastannounced": None,
            "lastseen": "2024-02-02T21:13Z",
            "manufacturername": "_TZE200_dwcarsat",
            "modelid": "TS0601",
            "name": "Formaldehyde 34",
            "state": {
                "lastupdated": "2024-02-02T21:14:46.810",
                "measured_value": 1,
            },
            "type": "ZHAFormaldehyde",
            "uniqueid": "xx:xx:xx:xx:xx:xx:xx:xx-01-042b",
        },
        {
            "entity_count": 1,
            "device_count": 3,
            "entity_id": "sensor.formaldehyde_34",
            "unique_id": "xx:xx:xx:xx:xx:xx:xx:xx-01-042b-formaldehyde",
            "state": "1",
            "entity_category": None,
            "device_class": SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS,
            "state_class": SensorStateClass.MEASUREMENT,
            "attributes": {
                "device_class": "volatile_organic_compounds",
                "friendly_name": "Formaldehyde 34",
                "state_class": SensorStateClass.MEASUREMENT,
                "unit_of_measurement": CONCENTRATION_PARTS_PER_BILLION,
            },
            "websocket_event": {"state": {"measured_value": 2}},
            "next_state": "2",
        },
    ),
    (  # Generic status sensor
        {
            "config": {
                "on": True,
                "reachable": True,
            },
            "etag": "aacc83bc7d6e4af7e44014e9f776b206",
            "manufacturername": "Phoscon",
            "modelid": "PHOSCON_FSM_STATE",
            "name": "FSM_STATE Motion stair",
            "state": {
                "lastupdated": "2019-04-24T00:00:25",
                "status": 0,
            },
            "swversion": "1.0",
            "type": "CLIPGenericStatus",
            "uniqueid": "fsm-state-1520195376277",
        },
        {
            "entity_count": 1,
            "device_count": 2,
            "entity_id": "sensor.fsm_state_motion_stair",
            "unique_id": "fsm-state-1520195376277-status",
            "state": "0",
            "entity_category": None,
            "device_class": None,
            "state_class": None,
            "attributes": {
                "on": True,
                "friendly_name": "FSM_STATE Motion stair",
            },
            "websocket_event": {"state": {"status": 1}},
            "next_state": "1",
        },
    ),
    (  # Humidity sensor
        {
            "config": {
                "battery": 100,
                "offset": 0,
                "on": True,
                "reachable": True,
            },
            "ep": 1,
            "etag": "1220e5d026493b6e86207993703a8a71",
            "manufacturername": "LUMI",
            "modelid": "lumi.weather",
            "name": "Mi temperature 1",
            "state": {
                "humidity": 3555,
                "lastupdated": "2019-05-05T14:39:00",
            },
            "swversion": "20161129",
            "type": "ZHAHumidity",
            "uniqueid": "00:15:8d:00:02:45:dc:53-01-0405",
        },
        {
            "entity_count": 2,
            "device_count": 3,
            "entity_id": "sensor.mi_temperature_1",
            "unique_id": "00:15:8d:00:02:45:dc:53-01-0405-humidity",
            "state": "35.55",
            "entity_category": None,
            "device_class": SensorDeviceClass.HUMIDITY,
            "state_class": SensorStateClass.MEASUREMENT,
            "attributes": {
                "state_class": "measurement",
                "on": True,
                "unit_of_measurement": "%",
                "device_class": "humidity",
                "friendly_name": "Mi temperature 1",
            },
            "options": {
                "suggested_display_precision": 1,
            },
            "websocket_event": {"state": {"humidity": 1000}},
            "next_state": "10.0",
        },
    ),
    (  # Moisture Sensor
        {
            "config": {"battery": 100, "offset": 0, "on": True, "reachable": True},
            "etag": "1ba99c68975111c04367b67cf95ead44",
            "lastannounced": None,
            "lastseen": "2023-05-19T09:55Z",
            "manufacturername": "_TZE200_myd45weu",
            "modelid": "TS0601",
            "name": "Soil Sensor",
            "state": {
                "lastupdated": "2023-05-19T09:42:00.472",
                "lowbattery": False,
                "moisture": 7213,
            },
            "swversion": "1.0.8",
            "type": "ZHAMoisture",
            "uniqueid": "a4:c1:38:fe:86:8f:07:a3-01-0408",
        },
        {
            "entity_count": 3,
            "device_count": 3,
            "entity_id": "sensor.soil_sensor",
            "unique_id": "a4:c1:38:fe:86:8f:07:a3-01-0408-moisture",
            "state": "72.13",
            "entity_category": None,
            "device_class": SensorDeviceClass.MOISTURE,
            "state_class": SensorStateClass.MEASUREMENT,
            "attributes": {
                "state_class": "measurement",
                "unit_of_measurement": "%",
                "device_class": "moisture",
                "friendly_name": "Soil Sensor",
            },
            "websocket_event": {"state": {"moisture": 6923}},
            "next_state": "69.23",
        },
    ),
    (  # Light level sensor
        {
            "config": {
                "alert": "none",
                "battery": 100,
                "ledindication": False,
                "on": True,
                "pending": [],
                "reachable": True,
                "tholddark": 12000,
                "tholdoffset": 7000,
                "usertest": False,
            },
            "ep": 2,
            "etag": "5cfb81765e86aa53ace427cfd52c6d52",
            "manufacturername": "Philips",
            "modelid": "SML001",
            "name": "Motion sensor 4",
            "state": {
                "dark": True,
                "daylight": False,
                "lastupdated": "2019-05-05T14:37:06",
                "lightlevel": 6955,
                "lux": 5,
            },
            "swversion": "6.1.0.18912",
            "type": "ZHALightLevel",
            "uniqueid": "00:17:88:01:03:28:8c:9b-02-0400",
        },
        {
            "entity_count": 2,
            "device_count": 3,
            "entity_id": "sensor.motion_sensor_4",
            "unique_id": "00:17:88:01:03:28:8c:9b-02-0400-light_level",
            "state": "5.0",
            "entity_category": None,
            "device_class": SensorDeviceClass.ILLUMINANCE,
            "state_class": SensorStateClass.MEASUREMENT,
            "attributes": {
                "on": True,
                "dark": True,
                "daylight": False,
                "unit_of_measurement": "lx",
                "device_class": "illuminance",
                "friendly_name": "Motion sensor 4",
                "state_class": "measurement",
            },
            "websocket_event": {"state": {"lightlevel": 1000}},
            "next_state": "1.3",
        },
    ),
    (  # Particulate matter -> pm2_5
        {
            "capabilities": {
                "measured_value": {
                    "max": 999,
                    "min": 0,
                    "quantity": "density",
                    "substance": "PM2.5",
                    "unit": "ug/m^3",
                }
            },
            "config": {"on": True, "reachable": True},
            "ep": 1,
            "etag": "2a67a4b5cbcc20532c0ee75e2abac0c3",
            "lastannounced": None,
            "lastseen": "2023-10-29T12:59Z",
            "manufacturername": "IKEA of Sweden",
            "modelid": "STARKVIND Air purifier table",
            "name": "STARKVIND AirPurifier",
            "productid": "E2006",
            "state": {
                "airquality": "excellent",
                "lastupdated": "2023-10-29T12:59:27.976",
                "measured_value": 1,
                "pm2_5": 1,
            },
            "swversion": "1.1.001",
            "type": "ZHAParticulateMatter",
            "uniqueid": "xx:xx:xx:xx:xx:xx:xx:xx-01-042a",
        },
        {
            "entity_count": 1,
            "device_count": 3,
            "entity_id": "sensor.starkvind_airpurifier_pm25",
            "unique_id": "xx:xx:xx:xx:xx:xx:xx:xx-01-042a-particulate_matter_pm2_5",
            "state": "1",
            "entity_category": None,
            "device_class": SensorDeviceClass.PM25,
            "state_class": SensorStateClass.MEASUREMENT,
            "attributes": {
                "friendly_name": "STARKVIND AirPurifier PM25",
                "device_class": SensorDeviceClass.PM25,
                "state_class": SensorStateClass.MEASUREMENT,
                "unit_of_measurement": CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
            },
            "websocket_event": {"state": {"measured_value": 2}},
            "next_state": "2",
        },
    ),
    (  # Power sensor
        {
            "config": {
                "on": True,
                "reachable": True,
            },
            "ep": 1,
            "etag": "96e71c7db4685b334d3d0decc3f11868",
            "manufacturername": "Heiman",
            "modelid": "SmartPlug",
            "name": "Power 16",
            "state": {
                "current": 34,
                "lastupdated": "2018-03-12T19:22:13",
                "power": 64,
                "voltage": 231,
            },
            "type": "ZHAPower",
            "uniqueid": "00:0d:6f:00:0b:7a:64:29-01-0b04",
        },
        {
            "entity_count": 1,
            "device_count": 3,
            "entity_id": "sensor.power_16",
            "unique_id": "00:0d:6f:00:0b:7a:64:29-01-0b04-power",
            "state": "64",
            "entity_category": None,
            "device_class": SensorDeviceClass.POWER,
            "state_class": SensorStateClass.MEASUREMENT,
            "attributes": {
                "state_class": "measurement",
                "on": True,
                "current": 34,
                "voltage": 231,
                "unit_of_measurement": "W",
                "device_class": "power",
                "friendly_name": "Power 16",
            },
            "websocket_event": {"state": {"power": 1000}},
            "next_state": "1000",
        },
    ),
    (  # Pressure sensor
        {
            "config": {
                "battery": 100,
                "on": True,
                "reachable": True,
            },
            "ep": 1,
            "etag": "1220e5d026493b6e86207993703a8a71",
            "manufacturername": "LUMI",
            "modelid": "lumi.weather",
            "name": "Mi temperature 1",
            "state": {
                "lastupdated": "2019-05-05T14:39:00",
                "pressure": 1010,
            },
            "swversion": "20161129",
            "type": "ZHAPressure",
            "uniqueid": "00:15:8d:00:02:45:dc:53-01-0403",
        },
        {
            "entity_count": 2,
            "device_count": 3,
            "entity_id": "sensor.mi_temperature_1",
            "unique_id": "00:15:8d:00:02:45:dc:53-01-0403-pressure",
            "state": "1010",
            "entity_category": None,
            "device_class": SensorDeviceClass.PRESSURE,
            "state_class": SensorStateClass.MEASUREMENT,
            "attributes": {
                "state_class": "measurement",
                "on": True,
                "unit_of_measurement": "hPa",
                "device_class": "pressure",
                "friendly_name": "Mi temperature 1",
            },
            "websocket_event": {"state": {"pressure": 500}},
            "next_state": "500",
        },
    ),
    (  # Temperature sensor
        {
            "config": {
                "battery": 100,
                "offset": 0,
                "on": True,
                "reachable": True,
            },
            "ep": 1,
            "etag": "1220e5d026493b6e86207993703a8a71",
            "manufacturername": "LUMI",
            "modelid": "lumi.weather",
            "name": "Mi temperature 1",
            "state": {
                "lastupdated": "2019-05-05T14:39:00",
                "temperature": 2182,
            },
            "swversion": "20161129",
            "type": "ZHATemperature",
            "uniqueid": "00:15:8d:00:02:45:dc:53-01-0402",
        },
        {
            "entity_count": 2,
            "device_count": 3,
            "entity_id": "sensor.mi_temperature_1",
            "unique_id": "00:15:8d:00:02:45:dc:53-01-0402-temperature",
            "state": "21.82",
            "entity_category": None,
            "device_class": SensorDeviceClass.TEMPERATURE,
            "state_class": SensorStateClass.MEASUREMENT,
            "attributes": {
                "state_class": "measurement",
                "on": True,
                "unit_of_measurement": "°C",
                "device_class": "temperature",
                "friendly_name": "Mi temperature 1",
            },
            "options": {
                "suggested_display_precision": 1,
            },
            "websocket_event": {"state": {"temperature": 1800}},
            "next_state": "18.0",
        },
    ),
    (  # Time sensor
        {
            "config": {
                "battery": 40,
                "on": True,
                "reachable": True,
            },
            "ep": 1,
            "etag": "28e796678d9a24712feef59294343bb6",
            "lastseen": "2020-11-22T11:26Z",
            "manufacturername": "Danfoss",
            "modelid": "eTRV0100",
            "name": "eTRV Séjour",
            "state": {
                "lastset": "2020-11-19T08:07:08Z",
                "lastupdated": "2020-11-22T10:51:03.444",
                "localtime": "2020-11-22T10:51:01",
                "utc": "2020-11-22T10:51:01Z",
            },
            "swversion": "20200429",
            "type": "ZHATime",
            "uniqueid": "cc:cc:cc:ff:fe:38:4d:b3-01-000a",
        },
        {
            "entity_count": 2,
            "device_count": 3,
            "entity_id": "sensor.etrv_sejour",
            "unique_id": "cc:cc:cc:ff:fe:38:4d:b3-01-000a-last_set",
            "state": "2020-11-19T08:07:08+00:00",
            "entity_category": None,
            "device_class": SensorDeviceClass.TIMESTAMP,
            "attributes": {
                "device_class": "timestamp",
                "friendly_name": "eTRV Séjour",
            },
            "websocket_event": {"state": {"lastset": "2020-12-14T10:12:14Z"}},
            "next_state": "2020-12-14T10:12:14+00:00",
        },
    ),
    (  # Internal temperature sensor
        {
            "config": {
                "battery": 100,
                "on": True,
                "reachable": True,
                "temperature": 2600,
            },
            "ep": 1,
            "etag": "18c0f3c2100904e31a7f938db2ba9ba9",
            "manufacturername": "dresden elektronik",
            "modelid": "lumi.sensor_motion.aq2",
            "name": "Alarm 10",
            "state": {
                "alarm": False,
                "lastupdated": "none",
                "lowbattery": None,
                "tampered": None,
            },
            "swversion": "20170627",
            "type": "ZHAAlarm",
            "uniqueid": "00:15:8d:00:02:b5:d1:80-01-0500",
        },
        {
            "entity_count": 3,
            "device_count": 3,
            "entity_id": "sensor.alarm_10_temperature",
            "unique_id": "00:15:8d:00:02:b5:d1:80-01-0500-internal_temperature",
            "state": "26.0",
            "entity_category": None,
            "device_class": SensorDeviceClass.TEMPERATURE,
            "state_class": SensorStateClass.MEASUREMENT,
            "attributes": {
                "state_class": "measurement",
                "unit_of_measurement": "°C",
                "device_class": "temperature",
                "friendly_name": "Alarm 10 Temperature",
            },
            "websocket_event": {"state": {"temperature": 1800}},
            "next_state": "26.0",
        },
    ),
    (  # Battery from switch
        {
            "config": {
                "battery": 90,
                "group": "201",
                "on": True,
                "reachable": True,
            },
            "ep": 2,
            "etag": "233ae541bbb7ac98c42977753884b8d2",
            "manufacturername": "Philips",
            "mode": 1,
            "modelid": "RWL021",
            "name": "Dimmer switch 3",
            "state": {
                "buttonevent": 1002,
                "lastupdated": "2019-04-28T20:29:13",
            },
            "swversion": "5.45.1.17846",
            "type": "ZHASwitch",
            "uniqueid": "00:17:88:01:02:0e:32:a3-02-fc00",
        },
        {
            "entity_count": 1,
            "device_count": 3,
            "entity_id": "sensor.dimmer_switch_3_battery",
            "unique_id": "00:17:88:01:02:0e:32:a3-02-fc00-battery",
            "state": "90",
            "entity_category": EntityCategory.DIAGNOSTIC,
            "device_class": SensorDeviceClass.BATTERY,
            "state_class": SensorStateClass.MEASUREMENT,
            "attributes": {
                "state_class": "measurement",
                "on": True,
                "event_id": "dimmer_switch_3",
                "unit_of_measurement": "%",
                "device_class": "battery",
                "friendly_name": "Dimmer switch 3 Battery",
            },
            "websocket_event": {"config": {"battery": 80}},
            "next_state": "80",
        },
    ),
]


@pytest.mark.parametrize(("sensor_1_payload", "expected"), TEST_DATA)
@pytest.mark.parametrize("config_entry_options", [{CONF_ALLOW_CLIP_SENSOR: True}])
async def test_sensors(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    config_entry_setup: ConfigEntry,
    mock_websocket_data: WebsocketDataType,
    expected: dict[str, Any],
) -> None:
    """Test successful creation of sensor entities."""
    # Enable in entity registry
    if expected.get("enable_entity"):
        entity_registry.async_update_entity(
            entity_id=expected["entity_id"], disabled_by=None
        )
        await hass.async_block_till_done()

        async_fire_time_changed(
            hass,
            dt_util.utcnow() + timedelta(seconds=RELOAD_AFTER_UPDATE_DELAY + 1),
        )
        await hass.async_block_till_done()

    assert len(hass.states.async_all()) == expected["entity_count"]

    # Verify entity state
    sensor = hass.states.get(expected["entity_id"])
    assert sensor.state == expected["state"]
    assert sensor.attributes.get(ATTR_DEVICE_CLASS) == expected["device_class"]
    assert sensor.attributes == expected["attributes"]

    # Verify entity registry
    assert (
        entity_registry.async_get(expected["entity_id"]).entity_category
        is expected["entity_category"]
    )
    ent_reg_entry = entity_registry.async_get(expected["entity_id"])
    assert ent_reg_entry.entity_category is expected["entity_category"]
    assert ent_reg_entry.unique_id == expected["unique_id"]

    # Verify device registry
    assert (
        len(
            dr.async_entries_for_config_entry(
                device_registry, config_entry_setup.entry_id
            )
        )
        == expected["device_count"]
    )

    # Change state

    event_changed_sensor = {"r": "sensors", "id": "1"}
    event_changed_sensor |= expected["websocket_event"]
    await mock_websocket_data(event_changed_sensor)
    await hass.async_block_till_done()
    assert hass.states.get(expected["entity_id"]).state == expected["next_state"]

    # Unload entry

    await hass.config_entries.async_unload(config_entry_setup.entry_id)
    assert hass.states.get(expected["entity_id"]).state == STATE_UNAVAILABLE

    # Remove entry

    await hass.config_entries.async_remove(config_entry_setup.entry_id)
    await hass.async_block_till_done()
    assert len(hass.states.async_all()) == 0


@pytest.mark.parametrize(
    "sensor_payload",
    [
        {
            "1": {
                "name": "CLIP temperature sensor",
                "type": "CLIPTemperature",
                "state": {"temperature": 2600},
                "config": {},
                "uniqueid": "00:00:00:00:00:00:00:02-00",
            },
        }
    ],
)
@pytest.mark.parametrize("config_entry_options", [{CONF_ALLOW_CLIP_SENSOR: False}])
@pytest.mark.usefixtures("config_entry_setup")
async def test_not_allow_clip_sensor(hass: HomeAssistant) -> None:
    """Test that CLIP sensors are not allowed."""
    assert len(hass.states.async_all()) == 0


@pytest.mark.parametrize(
    "sensor_payload",
    [
        {
            "1": {
                "name": "Light level sensor",
                "type": "ZHALightLevel",
                "state": {"lightlevel": 30000, "dark": False},
                "config": {"on": True, "reachable": True, "temperature": 10},
                "uniqueid": "00:00:00:00:00:00:00:00-00",
            },
            "2": {
                "id": "CLIP light sensor id",
                "name": "CLIP light level sensor",
                "type": "CLIPLightLevel",
                "state": {"lightlevel": 30000},
                "config": {"reachable": True},
                "uniqueid": "00:00:00:00:00:00:00:01-00",
            },
            "3": {
                "config": {"on": True, "reachable": True},
                "etag": "a5ed309124d9b7a21ef29fc278f2625e",
                "manufacturername": "Philips",
                "modelid": "CLIPGenericStatus",
                "name": "CLIP Flur",
                "state": {"lastupdated": "2021-10-01T10:23:06.779", "status": 0},
                "swversion": "1.0",
                "type": "CLIPGenericStatus",
                "uniqueid": "/sensors/3",
            },
        }
    ],
)
@pytest.mark.parametrize("config_entry_options", [{CONF_ALLOW_CLIP_SENSOR: True}])
async def test_allow_clip_sensors(
    hass: HomeAssistant, config_entry_setup: ConfigEntry
) -> None:
    """Test that CLIP sensors can be allowed."""
    assert len(hass.states.async_all()) == 4
    assert hass.states.get("sensor.clip_light_level_sensor").state == "999.8"
    assert hass.states.get("sensor.clip_flur").state == "0"

    # Disallow clip sensors

    hass.config_entries.async_update_entry(
        config_entry_setup, options={CONF_ALLOW_CLIP_SENSOR: False}
    )
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 2
    assert not hass.states.get("sensor.clip_light_level_sensor")
    assert not hass.states.get("sensor.clip_flur")

    # Allow clip sensors

    hass.config_entries.async_update_entry(
        config_entry_setup, options={CONF_ALLOW_CLIP_SENSOR: True}
    )
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 4
    assert hass.states.get("sensor.clip_light_level_sensor").state == "999.8"
    assert hass.states.get("sensor.clip_flur").state == "0"


@pytest.mark.usefixtures("config_entry_setup")
async def test_add_new_sensor(
    hass: HomeAssistant,
    mock_websocket_data: WebsocketDataType,
) -> None:
    """Test that adding a new sensor works."""
    event_added_sensor = {
        "e": "added",
        "r": "sensors",
        "id": "1",
        "sensor": {
            "id": "Light sensor id",
            "name": "Light level sensor",
            "type": "ZHALightLevel",
            "state": {"lightlevel": 30000, "dark": False},
            "config": {"on": True, "reachable": True, "temperature": 10},
            "uniqueid": "00:00:00:00:00:00:00:00-00",
        },
    }

    assert len(hass.states.async_all()) == 0

    await mock_websocket_data(event_added_sensor)
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 2
    assert hass.states.get("sensor.light_level_sensor").state == "999.8"


BAD_SENSOR_DATA = [
    ("ZHAConsumption", "consumption"),
    ("ZHAHumidity", "humidity"),
    ("ZHALightLevel", "lightlevel"),
    ("ZHATemperature", "temperature"),
]


@pytest.mark.parametrize(("sensor_type", "sensor_property"), BAD_SENSOR_DATA)
async def test_dont_add_sensor_if_state_is_none(
    hass: HomeAssistant,
    config_entry_factory: ConfigEntryFactoryType,
    sensor_payload: dict[str, Any],
    sensor_type: str,
    sensor_property: str,
) -> None:
    """Test sensor with scaled data is not created if state is None."""
    sensor_payload |= {
        "1": {
            "name": "Sensor 1",
            "type": sensor_type,
            "state": {sensor_property: None},
            "config": {},
            "uniqueid": "00:00:00:00:00:00:00:00-00",
        }
    }
    await config_entry_factory()

    assert len(hass.states.async_all()) == 0


@pytest.mark.parametrize(
    "sensor_payload",
    [
        {
            "1": {
                "config": {
                    "on": True,
                    "reachable": True,
                },
                "ep": 2,
                "etag": "c2d2e42396f7c78e11e46c66e2ec0200",
                "lastseen": "2020-11-20T22:48Z",
                "manufacturername": "BOSCH",
                "modelid": "AIR",
                "name": "BOSCH Air quality sensor",
                "state": {
                    "airquality": "poor",
                    "lastupdated": "2020-11-20T22:48:00.209",
                },
                "swversion": "20200402",
                "type": "ZHAAirQuality",
                "uniqueid": "00:00:00:00:00:00:00:00-02-fdef",
            }
        }
    ],
)
@pytest.mark.usefixtures("config_entry_setup")
async def test_air_quality_sensor_without_ppb(hass: HomeAssistant) -> None:
    """Test sensor with scaled data is not created if state is None."""
    assert len(hass.states.async_all()) == 1


@pytest.mark.parametrize(
    "sensor_payload",
    [
        {
            "1": {
                "name": "Switch 1",
                "type": "ZHASwitch",
                "state": {"buttonevent": 1000},
                "config": {},
                "uniqueid": "00:00:00:00:00:00:00:00-00-0000",
            },
            "2": {
                "name": "Switch 2",
                "type": "ZHASwitch",
                "state": {"buttonevent": 1000},
                "config": {},
                "uniqueid": "00:00:00:00:00:00:00:00-00-0001",
            },
        }
    ],
)
@pytest.mark.usefixtures("config_entry_setup")
async def test_add_battery_later(
    hass: HomeAssistant,
    mock_websocket_data: WebsocketDataType,
) -> None:
    """Test that a battery sensor can be created later on.

    Without an initial battery state a battery sensor
    can be created once a value is reported.
    """
    assert len(hass.states.async_all()) == 0

    event_changed_sensor = {
        "e": "changed",
        "r": "sensors",
        "id": "2",
        "config": {"battery": 50},
    }
    await mock_websocket_data(event_changed_sensor)
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 0

    event_changed_sensor = {
        "e": "changed",
        "r": "sensors",
        "id": "1",
        "config": {"battery": 50},
    }
    await mock_websocket_data(event_changed_sensor)
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 1

    assert hass.states.get("sensor.switch_1_battery").state == "50"


@pytest.mark.parametrize("model_id", ["0x8030", "0x8031", "0x8034", "0x8035"])
async def test_special_danfoss_battery_creation(
    hass: HomeAssistant,
    config_entry_factory: ConfigEntryFactoryType,
    sensor_payload: dict[str, Any],
    model_id: str,
) -> None:
    """Test the special Danfoss battery creation works.

    Normally there should only be one battery sensor per device from deCONZ.
    With specific Danfoss devices each endpoint can report its own battery state.
    """
    sensor_payload |= {
        "1": {
            "config": {
                "battery": 70,
                "heatsetpoint": 2300,
                "offset": 0,
                "on": True,
                "reachable": True,
                "schedule": {},
                "schedule_on": False,
            },
            "ep": 1,
            "etag": "982d9acc38bee5b251e24a9be26558e4",
            "lastseen": "2021-02-15T12:23Z",
            "manufacturername": "Danfoss",
            "modelid": model_id,
            "name": "0x8030",
            "state": {
                "lastupdated": "2021-02-15T12:23:07.994",
                "on": False,
                "temperature": 2307,
            },
            "swversion": "YYYYMMDD",
            "type": "ZHAThermostat",
            "uniqueid": "58:8e:81:ff:fe:00:11:22-01-0201",
        },
        "2": {
            "config": {
                "battery": 86,
                "heatsetpoint": 2300,
                "offset": 0,
                "on": True,
                "reachable": True,
                "schedule": {},
                "schedule_on": False,
            },
            "ep": 2,
            "etag": "62f12749f9f51c950086aff37dd02b61",
            "lastseen": "2021-02-15T12:23Z",
            "manufacturername": "Danfoss",
            "modelid": model_id,
            "name": "0x8030",
            "state": {
                "lastupdated": "2021-02-15T12:23:22.399",
                "on": False,
                "temperature": 2316,
            },
            "swversion": "YYYYMMDD",
            "type": "ZHAThermostat",
            "uniqueid": "58:8e:81:ff:fe:00:11:22-02-0201",
        },
        "3": {
            "config": {
                "battery": 86,
                "heatsetpoint": 2350,
                "offset": 0,
                "on": True,
                "reachable": True,
                "schedule": {},
                "schedule_on": False,
            },
            "ep": 3,
            "etag": "f50061174bb7f18a3d95789bab8b646d",
            "lastseen": "2021-02-15T12:23Z",
            "manufacturername": "Danfoss",
            "modelid": model_id,
            "name": "0x8030",
            "state": {
                "lastupdated": "2021-02-15T12:23:25.466",
                "on": False,
                "temperature": 2337,
            },
            "swversion": "YYYYMMDD",
            "type": "ZHAThermostat",
            "uniqueid": "58:8e:81:ff:fe:00:11:22-03-0201",
        },
        "4": {
            "config": {
                "battery": 85,
                "heatsetpoint": 2300,
                "offset": 0,
                "on": True,
                "reachable": True,
                "schedule": {},
                "schedule_on": False,
            },
            "ep": 4,
            "etag": "eea97adf8ce1b971b8b6a3a31793f96b",
            "lastseen": "2021-02-15T12:23Z",
            "manufacturername": "Danfoss",
            "modelid": model_id,
            "name": "0x8030",
            "state": {
                "lastupdated": "2021-02-15T12:23:41.939",
                "on": False,
                "temperature": 2333,
            },
            "swversion": "YYYYMMDD",
            "type": "ZHAThermostat",
            "uniqueid": "58:8e:81:ff:fe:00:11:22-04-0201",
        },
        "5": {
            "config": {
                "battery": 83,
                "heatsetpoint": 2300,
                "offset": 0,
                "on": True,
                "reachable": True,
                "schedule": {},
                "schedule_on": False,
            },
            "ep": 5,
            "etag": "1f7cd1a5d66dc27ac5eb44b8c47362fb",
            "lastseen": "2021-02-15T12:23Z",
            "manufacturername": "Danfoss",
            "modelid": model_id,
            "name": "0x8030",
            "state": {"lastupdated": "none", "on": False, "temperature": 2325},
            "swversion": "YYYYMMDD",
            "type": "ZHAThermostat",
            "uniqueid": "58:8e:81:ff:fe:00:11:22-05-0201",
        },
    }

    await config_entry_factory()

    assert len(hass.states.async_all()) == 10
    assert len(hass.states.async_entity_ids(SENSOR_DOMAIN)) == 5


@pytest.mark.parametrize(
    "sensor_payload",
    [{"0": {"type": "not supported", "name": "name", "state": {}, "config": {}}}],
)
@pytest.mark.usefixtures("config_entry_setup")
async def test_unsupported_sensor(hass: HomeAssistant) -> None:
    """Test that unsupported sensors doesn't break anything."""
    assert len(hass.states.async_all()) == 0
