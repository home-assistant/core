"""Flukso MQTT discovery."""
import asyncio
import json
import logging
import re

from homeassistant.components.binary_sensor import DEVICE_CLASS_PROBLEM
from homeassistant.components.mqtt import CONF_QOS, CONF_STATE_TOPIC, subscription
from homeassistant.components.mqtt.binary_sensor import (
    CONF_OFF_DELAY,
    PLATFORM_SCHEMA as MQTT_BINARY_SENSOR_PLATFORM_SCHEMA,
)
from homeassistant.components.mqtt.mixins import (
    CONF_CONNECTIONS,
    CONF_ENABLED_BY_DEFAULT,
    CONF_IDENTIFIERS,
    CONF_MANUFACTURER,
    CONF_SW_VERSION,
)
from homeassistant.components.mqtt.sensor import (
    CONF_STATE_CLASS,
    PLATFORM_SCHEMA as MQTT_SENSOR_PLATFORM_SCHEMA,
)
from homeassistant.components.sensor import (
    STATE_CLASS_MEASUREMENT,
    STATE_CLASS_TOTAL_INCREASING,
)
from homeassistant.const import (
    CONF_DEVICE,
    CONF_DEVICE_CLASS,
    CONF_FORCE_UPDATE,
    CONF_ICON,
    CONF_NAME,
    CONF_PLATFORM,
    CONF_UNIQUE_ID,
    CONF_UNIT_OF_MEASUREMENT,
    CONF_VALUE_TEMPLATE,
    DEVICE_CLASS_BATTERY,
    DEVICE_CLASS_CURRENT,
    DEVICE_CLASS_ENERGY,
    DEVICE_CLASS_GAS,
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_ILLUMINANCE,
    DEVICE_CLASS_POWER,
    DEVICE_CLASS_PRESSURE,
    DEVICE_CLASS_TEMPERATURE,
    DEVICE_CLASS_VOLTAGE,
    ELECTRIC_CURRENT_AMPERE,
    ELECTRIC_POTENTIAL_VOLT,
    ENERGY_WATT_HOUR,
    LIGHT_LUX,
    PERCENTAGE,
    POWER_WATT,
    PRESSURE_HPA,
    TEMP_CELSIUS,
    VOLUME_CUBIC_METERS,
    VOLUME_LITERS,
)
from homeassistant.core import callback

from .const import (
    CONF_DEVICE_FIRMWARE,
    CONF_DEVICE_HASH,
    CONF_DEVICE_SERIAL,
    DEFAULT_TIMEOUT,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

CONFIGS = ["kube", "flx", "sensor"]

DATA_TYPE_MAP = {
    "electricity": {
        "gauge": {
            "pf": ["gauge"],
            "vrms": ["gauge"],
            "irms": ["gauge"],
            "vthd": ["gauge"],
            "ithd": ["gauge"],
            "alpha": ["gauge"],
        },
        "counter": {
            "q1": ["gauge", "counter"],
            "q2": ["gauge", "counter"],
            "q3": ["gauge", "counter"],
            "q4": ["gauge", "counter"],
            "pplus": ["gauge", "counter"],
            "pminus": ["gauge", "counter"],
        },
    },
    "gas": {"counter": ["gauge", "counter"]},
    "water": {"counter": ["gauge", "counter"]},
    "temperature": {"gauge": ["gauge"]},
    "pressure": {"gauge": ["gauge"]},
    "battery": {"gauge": ["gauge"]},
    "light": {"gauge": ["gauge"]},
    "humidity": {"gauge": ["gauge"]},
    "error": {"gauge": ["gauge"]},
    "proximity": {"counter": ["gauge"]},
    "movement": {"counter": ["gauge"]},
    "vibration": {"counter": ["gauge"]},
}

UNIT_OF_MEASUREMENT_MAP = {
    "electricity": {
        "gauge": {
            "q1": "VAR",
            "q2": "VAR",
            "q3": "VAR",
            "q4": "VAR",
            "pplus": POWER_WATT,
            "pminus": POWER_WATT,
            "vrms": ELECTRIC_POTENTIAL_VOLT,
            "irms": ELECTRIC_CURRENT_AMPERE,
        },
        "counter": {
            "q1": "VARh",
            "q2": "VARh",
            "q3": "VARh",
            "q4": "VARh",
            "pplus": ENERGY_WATT_HOUR,
            "pminus": ENERGY_WATT_HOUR,
        },
    },
    "temperature": TEMP_CELSIUS,
    "pressure": PRESSURE_HPA,
    "battery": PERCENTAGE,
    "water": VOLUME_LITERS,
    "light": LIGHT_LUX,
    "humidity": PERCENTAGE,
    "gas": VOLUME_CUBIC_METERS,
}

DEVICE_CLASS_MAP = {
    "electricity": {
        "gauge": {
            "pplus": DEVICE_CLASS_POWER,
            "pminus": DEVICE_CLASS_POWER,
            "vrms": DEVICE_CLASS_VOLTAGE,
            "irms": DEVICE_CLASS_CURRENT,
        },
        "counter": {"pplus": DEVICE_CLASS_ENERGY, "pminus": DEVICE_CLASS_ENERGY},
    },
    "temperature": DEVICE_CLASS_TEMPERATURE,
    "pressure": DEVICE_CLASS_PRESSURE,
    "battery": DEVICE_CLASS_BATTERY,
    "light": DEVICE_CLASS_ILLUMINANCE,
    "humidity": DEVICE_CLASS_HUMIDITY,
    "gas": DEVICE_CLASS_GAS,
    "error": DEVICE_CLASS_PROBLEM,
}

ICON_MAP = {
    "electricity": "mdi:lightning-bolt",
    "water": "mdi:water",
    "proximity": "mdi:ruler",
    "gas": "mdi:fire",
}

STATE_CLASS_MAP = {
    "electricity": {
        "counter": STATE_CLASS_TOTAL_INCREASING,
        "gauge": STATE_CLASS_MEASUREMENT,
    },
    "water": {
        "counter": STATE_CLASS_TOTAL_INCREASING,
        "gauge": STATE_CLASS_MEASUREMENT,
    },
    "gas": {"counter": STATE_CLASS_TOTAL_INCREASING, "gauge": STATE_CLASS_MEASUREMENT},
    "temperature": STATE_CLASS_MEASUREMENT,
    "pressure": STATE_CLASS_MEASUREMENT,
    "battery": STATE_CLASS_MEASUREMENT,
    "light": STATE_CLASS_MEASUREMENT,
    "humidity": STATE_CLASS_MEASUREMENT,
    "error": STATE_CLASS_MEASUREMENT,
    "proximity": STATE_CLASS_MEASUREMENT,
    "movement": STATE_CLASS_MEASUREMENT,
    "vibration": STATE_CLASS_MEASUREMENT,
}


def _get_sensor_detail(sensor, detail_map):
    m = detail_map
    levels = ["type", "data_type", "subtype"]
    while isinstance(m, dict) and levels:
        level = levels.pop(0)
        if level in sensor:
            if sensor[level] in m:
                m = m[sensor[level]]
            else:
                m = None
    return m


def _get_sensor_name(sensor, entry_data):
    """Generate a name based on the kube and flx config, and the data type and sub type."""
    name = "unknown"
    if "class" in sensor and sensor["class"] == "kube":
        if (
            "kube" in entry_data
            and "name" in entry_data["kube"][str(sensor["kid"])]
            and entry_data["kube"][str(sensor["kid"])]["name"]
        ):
            name = entry_data["kube"][str(sensor["kid"])]["name"]
    else:
        if "port" in sensor:
            if (
                "flx" in entry_data
                and "name" in entry_data["flx"][str(sensor["port"][0])]
                and entry_data["flx"][str(sensor["port"][0])]["name"]
            ):
                name = entry_data["flx"][str(sensor["port"][0])]["name"]

    if "type" in sensor:
        name = f'{name} {sensor["type"]}'
        if "data_type" in sensor:
            if sensor["type"] == "electricity" and "subtype" in sensor:
                name = f'{name} {sensor["subtype"]} {sensor["data_type"]}'
            elif sensor["type"] == "water":
                name = f'{name} {sensor["data_type"]}'
            elif sensor["type"] == "gas":
                name = f'{name} {sensor["data_type"]}'
    return name


def _is_binary_sensor(sensor):
    if "class" in sensor and "type" in sensor:
        return (sensor["class"] == "kube") and (
            sensor["type"] in ("movement", "vibration", "error")
        )
    return False


def _get_binary_sensor_entities(entry_data, device_info):
    """Generate binary sensor configuration."""
    entities = []

    for sensor in entry_data["sensor"].values():
        if "enable" not in sensor or sensor["enable"] == 0:
            continue

        if not _is_binary_sensor(sensor):
            continue

        sensorconfig = {}
        sensorconfig[CONF_NAME] = _get_sensor_name(sensor, entry_data)
        sensorconfig[CONF_DEVICE] = device_info
        sensorconfig[CONF_ENABLED_BY_DEFAULT] = True
        sensorconfig[CONF_PLATFORM] = "mqtt"
        sensorconfig[CONF_STATE_TOPIC] = f'/sensor/{sensor["id"]}/{sensor["data_type"]}'
        sensorconfig[CONF_QOS] = 0
        sensorconfig[CONF_FORCE_UPDATE] = False
        discovery_hash = (
            entry_data[CONF_DEVICE_HASH],
            sensor["id"],
            sensor["data_type"],
        )
        sensorconfig[CONF_UNIQUE_ID] = "_".join(discovery_hash)
        device_class = _get_sensor_detail(sensor, DEVICE_CLASS_MAP)
        if device_class:
            sensorconfig[CONF_DEVICE_CLASS] = device_class
        icon = _get_sensor_detail(sensor, ICON_MAP)
        if icon:
            sensorconfig[CONF_ICON] = icon
        uom = _get_sensor_detail(sensor, UNIT_OF_MEASUREMENT_MAP)
        if uom:
            sensorconfig[CONF_UNIT_OF_MEASUREMENT] = uom
        if device_class and (device_class == DEVICE_CLASS_PROBLEM):
            sensorconfig[
                CONF_VALUE_TEMPLATE
            ] = """
                    {% if (value.split(",")[1]|int) > 0 %}
                        ON
                    {% else %}
                        OFF
                    {% endif %}"""
        else:
            sensorconfig[CONF_OFF_DELAY] = DEFAULT_TIMEOUT
            sensorconfig[
                CONF_VALUE_TEMPLATE
            ] = """
                    {% if value %}
                        ON
                    {% else %}
                        OFF
                    {% endif %}"""

        entities.append(MQTT_BINARY_SENSOR_PLATFORM_SCHEMA(sensorconfig))

    return entities


def _get_sensor_config(sensor, entry_data, device_info):
    sensorconfig = {}
    sensorconfig[CONF_NAME] = _get_sensor_name(sensor, entry_data)
    sensorconfig[CONF_DEVICE] = device_info
    sensorconfig[CONF_ENABLED_BY_DEFAULT] = True
    sensorconfig[CONF_PLATFORM] = "mqtt"
    sensorconfig[CONF_STATE_TOPIC] = f'/sensor/{sensor["id"]}/{sensor["data_type"]}'
    sensorconfig[CONF_STATE_CLASS] = _get_sensor_detail(sensor, STATE_CLASS_MAP)
    sensorconfig[CONF_QOS] = 0
    sensorconfig[CONF_FORCE_UPDATE] = True
    discovery_hash = (
        entry_data[CONF_DEVICE_HASH],
        sensor["id"],
        sensor["data_type"],
    )
    sensorconfig[CONF_UNIQUE_ID] = "_".join(discovery_hash)
    device_class = _get_sensor_detail(sensor, DEVICE_CLASS_MAP)
    if device_class:
        sensorconfig[CONF_DEVICE_CLASS] = device_class
    icon = _get_sensor_detail(sensor, ICON_MAP)
    if icon:
        sensorconfig[CONF_ICON] = icon
    uom = _get_sensor_detail(sensor, UNIT_OF_MEASUREMENT_MAP)
    if uom:
        sensorconfig[CONF_UNIT_OF_MEASUREMENT] = uom

    sensorconfig[CONF_VALUE_TEMPLATE] = """{{ value.split(",")[1] | float }}"""
    if "type" in sensor:
        if sensor["type"] == "temperature":
            sensorconfig[
                CONF_VALUE_TEMPLATE
            ] = """{{ value.split(",")[1] | round(1) }}"""
        elif sensor["type"] == "battery":
            sensorconfig[
                CONF_VALUE_TEMPLATE
            ] = """{{ (((value.split(",")[1]|round(1)) / 3.3) * 100) | round(2) }}"""

    return sensorconfig


def _get_sensor_entities(entry_data, device_info):
    entities = []

    for sensor in entry_data["sensor"].values():
        if "enable" not in sensor or sensor["enable"] == 0:
            continue

        if _is_binary_sensor(sensor):
            continue

        for dt in _get_sensor_detail(sensor, DATA_TYPE_MAP):
            s = sensor.copy()
            s["data_type"] = dt
            config = _get_sensor_config(s, entry_data, device_info)
            entities.append(MQTT_SENSOR_PLATFORM_SCHEMA(config))

    return entities


def _get_device_info(entry_data):
    return {
        CONF_CONNECTIONS: [],
        CONF_IDENTIFIERS: {
            (DOMAIN, entry_data[CONF_DEVICE_HASH]),
        },
        CONF_MANUFACTURER: "Flukso",
        CONF_NAME: entry_data.get(CONF_DEVICE_SERIAL, entry_data[CONF_DEVICE_HASH]),
        CONF_SW_VERSION: entry_data.get(CONF_DEVICE_FIRMWARE, "unknown"),
    }


def get_entities_for_platform(platform, entry_data):
    """Generate configuration for the given platform."""
    entities = []
    device_info = _get_device_info(entry_data)
    if platform == "binary_sensor":
        entities.extend(_get_binary_sensor_entities(entry_data, device_info))
    elif platform == "sensor":
        entities.extend(_get_sensor_entities(entry_data, device_info))
    return entities


async def async_discover_device(hass, entry):
    """Get the Flukso configs JSON's using MQTT."""
    config_futures = {config: asyncio.Future() for config in CONFIGS}
    tap_future = asyncio.Future()
    sub_state = None

    @callback
    def config_message_received(msg):
        splitted_topic = msg.topic.split("/")

        device = splitted_topic[2]
        conftype = splitted_topic[4]

        _LOGGER.debug("storing config type %s for device %s", conftype, device)
        hass.data[DOMAIN][entry.entry_id][conftype] = json.loads(msg.payload)

        if conftype in config_futures:
            config_futures[conftype].set_result(True)

    @callback
    def tap_message_received(msg):
        serial = re.findall("# serial: (.*)", msg.payload)[0]
        firmware = re.findall("# firmware: (.*)", msg.payload)[0]

        _LOGGER.debug("Found device with serial %s and firmware %s", serial, firmware)
        hass.data[DOMAIN][entry.entry_id][CONF_DEVICE_SERIAL] = serial
        hass.data[DOMAIN][entry.entry_id][CONF_DEVICE_FIRMWARE] = firmware

        tap_future.set_result(True)

    sub_state = await subscription.async_subscribe_topics(
        hass,
        sub_state,
        {
            f"tap_topic_{hass.data[DOMAIN][entry.entry_id][CONF_DEVICE_HASH]}": {
                "topic": f"/device/{hass.data[DOMAIN][entry.entry_id][CONF_DEVICE_HASH]}/test/tap",
                "msg_callback": tap_message_received,
            },
            f"config_topic_{hass.data[DOMAIN][entry.entry_id][CONF_DEVICE_HASH]}": {
                "topic": f"/device/{hass.data[DOMAIN][entry.entry_id][CONF_DEVICE_HASH]}/config/+",
                "msg_callback": config_message_received,
            },
        },
    )

    _, pending = await asyncio.wait(config_futures.values(), timeout=2)
    if len(pending) == 1 and config_futures["kube"] == pending[0]:
        _LOGGER.debug("kube config pending, FLM02?")

    _, pending = await asyncio.wait([tap_future], timeout=2)
    if len(pending) == 1:
        _LOGGER.debug("test tap pending, FLM02?")

    _LOGGER.debug("all configs and tap received")
    await subscription.async_unsubscribe_topics(hass, sub_state)
