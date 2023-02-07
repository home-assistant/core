"""Platform for sensor integration."""
from __future__ import annotations

from dataclasses import dataclass
import logging
from operator import length_hint

from homeassistant import config_entries
from homeassistant.components import mqtt
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)

# from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfElectricCurrent, UnitOfEnergy, UnitOfPower
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.json import json_dumps, json_loads

from . import ViarisEntityDescription
from .const import (
    ACTIVE_ENERGY_CONN1_KEY,
    ACTIVE_ENERGY_CONN2_KEY,
    ACTIVE_POWER_CONN1_KEY,
    ACTIVE_POWER_CONN2_KEY,
    CONTAX_D0613_KEY,
    ETHERNET_KEY,
    EVSE_POWER_KEY,
    FIRMWARE_APP_KEY,
    FV_POWER_KEY,
    FW_CORTEX_VERSION_KEY,
    FW_POT_VERSION_KEY,
    HARDWARE_VERSION_KEY,
    HOME_POWER_KEY,
    HW_POT_VERSION_KEY,
    KEEP_ALIVE_KEY,
    LIMIT_POWER_KEY,
    MAC_KEY,
    MAX_POWER_KEY,
    MODBUS_KEY,
    MODEL_COMBIPLUS,
    MODEL_KEY,
    MQTT_CLIENT_ID_KEY,
    MQTT_PORT_KEY,
    MQTT_QOS_KEY,
    MQTT_URL_KEY,
    MQTT_USER_KEY,
    OCPP_KEY,
    OVERLOAD_REL_KEY,
    PING_KEY,
    REACTIVE_ENERGY_CONN1_KEY,
    REACTIVE_ENERGY_CONN2_KEY,
    REACTIVE_POWER_CONN1_KEY,
    REACTIVE_POWER_CONN2_KEY,
    RFID_KEY,
    SCHUKO_KEY,
    SELECTOR_POWER_KEY,
    SERIAL_KEY,
    SOLAR_KEY,
    SPL_KEY,
    STATE_CONN1_KEY,
    STATE_CONN2_KEY,
    TMC100_KEY,
    TOTAL_CURRENT_KEY,
    TOTAL_POWER_KEY,
    USER_CONN1_KEY,
    USER_CONN2_KEY,
    ChargerStatusCodes,
)
from .entity import ViarisEntity

_LOGGER = logging.getLogger(__name__)


@dataclass
class ViarisSensorEntityDescription(ViarisEntityDescription, SensorEntityDescription):
    """Describes Viaris sensor entity."""

    domain: str = "sensor"
    precision: int | None = None


def get_state_conn1(value) -> str:
    """Transform codes into a human readable string."""
    data = json_loads(value)

    if length_hint(data["data"]["elements"]) == 0:
        return "Disabled"
    type_connector = data["data"]["elements"][0]["connectorName"]
    if type_connector in ("mennekes", "mennekes1", "mennekes2"):
        connector_name = "mennekes"
    if type_connector in ("schuko", "schuko1", "schuko2"):
        connector_name = "schuko"
    try:
        return getattr(
            # ChargerStatusCodes, data["data"]["elements"][0]["connectorName"]
            ChargerStatusCodes,
            connector_name,
        )[int(data["data"]["elements"][0]["state"])]
    except KeyError:
        return "Unknown"


def get_state_conn2(value) -> str:
    """Transform codes into a human readable string."""
    data = json_loads(value)
    if length_hint(data["data"]["elements"]) > 1:

        type_connector = data["data"]["elements"][1]["connectorName"]
        if type_connector in ("mennekes", "mennekes1", "mennekes2"):
            connector_name = "mennekes"
        if type_connector in ("schuko", "schuko1", "schuko2"):
            connector_name = "schuko"
        try:
            return getattr(
                # ChargerStatusCodes, data["data"]["elements"][1]["connectorName"]
                ChargerStatusCodes,
                connector_name,
            )[int(data["data"]["elements"][1]["state"])]
        except KeyError:
            return "Unknown"

    return "Disabled"


def get_evse_power(value) -> float:
    """Extract Evse power."""
    data = json_loads(value)
    evse_power = round(float(data["data"]["evsePower"]) / 1000, 2)
    return evse_power


def get_total_power(value) -> float:
    """Extract total power."""
    data = json_loads(value)
    total_power = round(float(data["data"]["totalPower"]) / 1000, 2)
    return total_power


def get_home_power(value) -> float:
    """Extract home power."""
    data = json_loads(value)
    total_power = round(float(data["data"]["homePower"]) / 1000, 2)
    return total_power


def get_rel_overload(value) -> float:
    """Extract rel overload."""
    data = json_loads(value)
    rel_overload = round(float(data["data"]["relOverload"]), 2)
    return rel_overload


def get_total_current(value) -> float:
    """Extract total current."""
    data = json_loads(value)
    total_current = round(float(data["data"]["totalCurrent"][0] / 1000), 2)
    return total_current


def get_ctx_detected(value) -> str:
    """Extract contax detected."""
    data = json_loads(value)
    if data["data"]["ctxDetected"] is True:
        return "enable"
    return "disable"


def get_tmc100_detected(value) -> str:
    """Extract tmc100 detected."""
    data = json_loads(value)
    if data["data"]["mbusDetected"] is True:
        return "enable"
    return "disable"


def get_active_power_conn1(value) -> float:
    """Extract active power connector 1."""
    data = json_loads(value)
    active_power = round(float(data["data"]["elements"][0]["now"]["aPow"][0] / 1000), 2)
    return active_power


def get_active_power_conn2(value) -> float:
    """Extract active power connector 2."""
    data = json_loads(value)
    if length_hint(data["data"]["elements"]) > 1:
        active_power = round(
            float(data["data"]["elements"][1]["now"]["aPow"][0] / 1000), 2
        )
        return active_power

    return 0.0


def get_reactive_power_conn1(value) -> float:
    """Extract reactive power connector 1."""
    data = json_loads(value)
    reactive_power = round(
        float(data["data"]["elements"][0]["now"]["rPow"][0] / 1000), 2
    )
    return reactive_power


def get_reactive_power_conn2(value) -> float:
    """Extract reactive power connector 2."""
    data = json_loads(value)
    if length_hint(data["data"]["elements"]) > 1:
        reactive_power = round(
            float(data["data"]["elements"][1]["now"]["rPow"][0] / 1000), 2
        )
        return reactive_power
    return 0.0


def get_active_energy_conn1(value) -> float:
    """Extract active energy connector 1."""
    data = json_loads(value)
    active_energy = round(float(data["data"]["elements"][0]["now"]["active"] / 1000), 2)
    return active_energy


def get_active_energy_conn2(value) -> float:
    """Extract active energy connector 2."""
    data = json_loads(value)
    if length_hint(data["data"]["elements"]) > 1:
        active_energy = round(
            float(data["data"]["elements"][1]["now"]["active"] / 1000), 2
        )
        return active_energy
    return 0.0


def get_reactive_energy_conn1(value) -> float:
    """Extract reactive energy connector 1."""
    data = json_loads(value)
    reactive_energy = round(
        float(data["data"]["elements"][0]["now"]["reactive"] / 1000), 2
    )
    return reactive_energy


def get_reactive_energy_conn2(value) -> float:
    """Extract reactive energy connector 2."""
    data = json_loads(value)
    if length_hint(data["data"]["elements"]) > 1:
        reactive_energy = round(
            float(data["data"]["elements"][1]["now"]["reactive"] / 1000), 2
        )
        return reactive_energy

    return 0.0


def get_state_solar(value) -> float:
    """Extract solar + battery power."""

    data = json_loads(value)
    if "fvPower" in value:
        solar_pw = round(float(data["data"]["fvPower"] / 1000), 2)
        return solar_pw
    return 0.0


SENSOR_TYPES_RT: tuple[ViarisSensorEntityDescription, ...] = (
    ViarisSensorEntityDescription(
        key=STATE_CONN1_KEY,
        state=get_state_conn1,
        # icon="mdi:ev-plug-type2",
        name="Status connector 1",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=True,
        disabled=False,
    ),
    ViarisSensorEntityDescription(
        key=STATE_CONN2_KEY,
        state=get_state_conn2,
        # icon="mdi:power-socket-de",
        name="Status connector 2",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=True,
        disabled=False,
    ),
    ViarisSensorEntityDescription(
        key=ACTIVE_ENERGY_CONN1_KEY,
        icon="mdi:lightning-bolt",
        name="Active Energy connector 1",
        precision=2,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
        state=get_active_energy_conn1,
    ),
    ViarisSensorEntityDescription(
        key=ACTIVE_ENERGY_CONN2_KEY,
        icon="mdi:lightning-bolt",
        name="Active Energy connector 2",
        precision=2,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
        state=get_active_energy_conn2,
    ),
    ViarisSensorEntityDescription(
        key=REACTIVE_ENERGY_CONN1_KEY,
        icon="mdi:lightning-bolt",
        name="Reactive Energy connector 1",
        precision=2,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
        state=get_reactive_energy_conn1,
    ),
    ViarisSensorEntityDescription(
        key=REACTIVE_ENERGY_CONN2_KEY,
        icon="mdi:lightning-bolt",
        name="Reactive Energy connector 2",
        precision=2,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
        state=get_reactive_energy_conn2,
    ),
    ViarisSensorEntityDescription(
        key=EVSE_POWER_KEY,
        icon="mdi:lightning-bolt",
        name="Evse Power",
        precision=2,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        state=get_evse_power,
    ),
    ViarisSensorEntityDescription(
        key=TOTAL_CURRENT_KEY,
        name="Total Current",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.TOTAL,
        entity_category=EntityCategory.DIAGNOSTIC,
        state=get_total_current,
    ),
    ViarisSensorEntityDescription(
        key=HOME_POWER_KEY,
        name="Home power",
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        state=get_home_power,
    ),
    ViarisSensorEntityDescription(
        key=TOTAL_POWER_KEY,
        name="Total power",
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        state=get_total_power,
    ),
    ViarisSensorEntityDescription(
        key=FV_POWER_KEY,
        icon="mdi:solar-power-variant",
        name="Solar and battery power",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        entity_registry_enabled_default=True,
        state=get_state_solar,
        disabled=False,
    ),
    ViarisSensorEntityDescription(
        key=TMC100_KEY,
        name="TMC100",
        icon="mdi:meter-electric",
        entity_category=EntityCategory.CONFIG,
        state=get_tmc100_detected,
    ),
    ViarisSensorEntityDescription(
        key=CONTAX_D0613_KEY,
        name="Contax D0613",
        icon="mdi:meter-electric-outline",
        entity_category=EntityCategory.CONFIG,
        state=get_ctx_detected,
    ),
    ViarisSensorEntityDescription(
        key=OVERLOAD_REL_KEY,
        name="Overload rel",
        icon="mdi:checkbox-blank-circle",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        state=get_rel_overload,
    ),
    ViarisSensorEntityDescription(
        key=ACTIVE_POWER_CONN1_KEY,
        name="Active power connector 1",
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        state=get_active_power_conn1,
    ),
    ViarisSensorEntityDescription(
        key=ACTIVE_POWER_CONN2_KEY,
        name="Active power connector 2",
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        state=get_active_power_conn2,
    ),
    ViarisSensorEntityDescription(
        key=REACTIVE_POWER_CONN2_KEY,
        name="Reactive power connector 2",
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        state=get_reactive_power_conn2,
    ),
    ViarisSensorEntityDescription(
        key=REACTIVE_POWER_CONN1_KEY,
        name="Reactive power connector 1",
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        state=get_reactive_power_conn1,
    ),
)


def get_user_connector1(value) -> str:
    """Extract user connector1."""
    data = json_loads(value)
    if data["data"]["name"] == "mennekes" or data["data"]["name"] == "mennekes1":
        read_value = data["data"]["stat"]["user"]
        return read_value
    return "Unknown"


def get_user_connector2(value) -> str:
    """Extract user connector2."""
    data = json_loads(value)
    if data["data"]["name"] == "mennekes2":
        read_value = data["data"]["stat"]["user"]
        return read_value
    return "Unknown"


SENSOR_TYPES_MENNEKES1: tuple[ViarisSensorEntityDescription, ...] = (
    ViarisSensorEntityDescription(
        key=USER_CONN1_KEY,
        name="User connector 1",
        icon="mdi:account-card",
        entity_category=EntityCategory.DIAGNOSTIC,
        state=get_user_connector1,
    ),
)
SENSOR_TYPES_MENNEKES2: tuple[ViarisSensorEntityDescription, ...] = (
    ViarisSensorEntityDescription(
        key=USER_CONN2_KEY,
        name="User connector 2",
        icon="mdi:account-card",
        entity_category=EntityCategory.DIAGNOSTIC,
        state=get_user_connector2,
    ),
)


def get_firmware_app(value) -> str:
    """Extract firmware application."""
    data = json_loads(value)
    read_value = data["data"]["fwv"]
    return read_value


def get_hardware_version(value) -> str:
    """Extract hardware version."""
    data = json_loads(value)
    read_value = data["data"]["hwv"]
    return read_value


def get_fw_pot_version(value) -> str:
    """Extract fw power version."""
    data = json_loads(value)
    read_value = data["data"]["fwv_pot"]
    return read_value


def get_fw_cortex_version(value) -> str:
    """Extract fw cortex version."""
    data = json_loads(value)
    read_value = data["data"]["fwv_cortex"]
    return read_value


def get_hw_pot_version(value) -> str:
    """Extract hw power version."""
    data = json_loads(value)
    read_value = data["data"]["hwv_pot"]
    return read_value


def get_schuko_present(value) -> str:
    """Extract schuko present."""
    data = json_loads(value)
    if data["data"]["model"] == "VIARIS COMBIPLUS":
        return "Unknown"
    read_value = data["data"]["schuko"]
    if read_value is True:
        return "Yes"

    return "No"


def get_rfid(value) -> str:
    """Extract rfid enable."""
    data = json_loads(value)
    read_value = data["data"]["rfid"]
    if read_value is True:
        return "Enable"
    return "Disable"


def get_ethernet(value) -> str:
    """Extract ethernet enable."""
    data = json_loads(value)
    read_value = data["data"]["ethernet"]
    if read_value is True:
        return "Enable"
    return "Disable"


def get_spl(value) -> str:
    """Extract spl enable."""
    data = json_loads(value)
    read_value = data["data"]["spl"]
    if read_value is True:
        return "Enable"

    return "Disable"


def get_ocpp(value) -> str:
    """Extract ocpp enable."""
    data = json_loads(value)
    read_value = data["data"]["ocpp"]
    if read_value is True:
        return "Enable"
    return "Disable"


def get_solar(value) -> str:
    """Extract solar enable."""
    data = json_loads(value)
    read_value = data["data"]["solar"]
    if read_value is True:
        return "Enable"

    return "Disable"


def get_modbus(value) -> str:
    """Extract modbus enable."""
    data = json_loads(value)
    read_value = data["data"]["modbus"]
    if read_value is True:
        return "Enable"
    return "Disable"


def get_serial(value) -> str:
    """Extract serial number."""
    data = json_loads(value)
    read_value = data["data"]["serial"]
    return read_value


def get_model(value) -> str:
    """Extract model."""
    data = json_loads(value)
    read_value = data["data"]["model"]
    return read_value


def get_mac(value) -> str:
    """Extract mac."""
    data = json_loads(value)
    read_value = data["data"]["mac"]
    return read_value


def get_max_power(value) -> float:
    """Extract max power."""
    data = json_loads(value)
    read_value = round(float(data["data"]["maxPower"] / 1000), 2)
    return read_value


def get_limit_power(value) -> float:
    """Extract max power."""
    data = json_loads(value)
    read_value = round(float(data["data"]["limitPower"] / 1000), 2)
    return read_value


def get_selector_power(value) -> float:
    """Extract max power."""
    data = json_loads(value)
    read_value = round(float(data["data"]["selectorPower"] / 1000), 2)
    return read_value


SENSOR_TYPES_CONFIG: tuple[ViarisSensorEntityDescription, ...] = (
    ViarisSensorEntityDescription(
        key=FIRMWARE_APP_KEY,
        icon="mdi:content-save",
        name="Firmware application version",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=True,
        state=get_firmware_app,
        disabled=False,
    ),
    ViarisSensorEntityDescription(
        key=HARDWARE_VERSION_KEY,
        icon="mdi:select-inverse",
        name="Hardware version",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=True,
        state=get_hardware_version,
        disabled=False,
    ),
    ViarisSensorEntityDescription(
        key=FW_POT_VERSION_KEY,
        icon="mdi:content-save",
        name="Firmware power version",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=True,
        state=get_fw_pot_version,
        disabled=False,
    ),
    ViarisSensorEntityDescription(
        key=HW_POT_VERSION_KEY,
        icon="mdi:select-inverse",
        name="Hardware power version",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=True,
        state=get_hw_pot_version,
        disabled=False,
    ),
    ViarisSensorEntityDescription(
        key=FW_CORTEX_VERSION_KEY,
        icon="mdi:content-save",
        name="Firmware cortex version",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=True,
        state=get_fw_cortex_version,
        disabled=False,
    ),
    ViarisSensorEntityDescription(
        key=SCHUKO_KEY,
        icon="mdi:power-socket-de",
        name="Schuko present",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=True,
        state=get_schuko_present,
        disabled=False,
    ),
    ViarisSensorEntityDescription(
        key=RFID_KEY,
        icon="mdi:credit-card-wireless",
        name="Rfid",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=True,
        state=get_rfid,
        disabled=False,
    ),
    ViarisSensorEntityDescription(
        key=ETHERNET_KEY,
        icon="mdi:ethernet",
        name="Ethernet",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=True,
        state=get_ethernet,
        disabled=False,
    ),
    ViarisSensorEntityDescription(
        key=SPL_KEY,
        icon="mdi:sitemap",
        name="Spl",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=True,
        state=get_spl,
        disabled=False,
    ),
    ViarisSensorEntityDescription(
        key=OCPP_KEY,
        icon="mdi:lightning-bolt-circle",
        name="Ocpp",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=True,
        state=get_ocpp,
        disabled=False,
    ),
    ViarisSensorEntityDescription(
        key=MODBUS_KEY,
        icon="mdi:lan",
        name="Modbus",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=True,
        state=get_modbus,
        disabled=False,
    ),
    ViarisSensorEntityDescription(
        key=SOLAR_KEY,
        icon="mdi:solar-power",
        name="Solar",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=True,
        state=get_solar,
        disabled=False,
    ),
    ViarisSensorEntityDescription(
        key=SERIAL_KEY,
        icon="mdi:ev-station",
        name="Serial",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=True,
        state=get_serial,
        disabled=False,
    ),
    ViarisSensorEntityDescription(
        key=MODEL_KEY,
        icon="mdi:ev-station",
        name="Model",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=True,
        state=get_model,
        disabled=False,
    ),
    ViarisSensorEntityDescription(
        key=MAC_KEY,
        icon="mdi:checkbox-marked-outline",
        name="Mac",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=True,
        state=get_mac,
        disabled=False,
    ),
    ViarisSensorEntityDescription(
        key=MAX_POWER_KEY,
        name="Max power",
        device_class=SensorDeviceClass.POWER,
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=True,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        state=get_max_power,
        disabled=False,
    ),
    ViarisSensorEntityDescription(
        key=LIMIT_POWER_KEY,
        name="Limit power",
        device_class=SensorDeviceClass.POWER,
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=True,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        state=get_limit_power,
        disabled=False,
    ),
    ViarisSensorEntityDescription(
        key=SELECTOR_POWER_KEY,
        icon="mdi:selection-ellipse-remove",
        name="Selector power",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=True,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        state=get_selector_power,
        disabled=False,
    ),
)


def get_mqtt_keep_alive(value) -> int:
    """Extract keep alive."""
    data = json_loads(value)
    read_value = data["data"]["cfg"]["keepAlive"]
    return read_value


def get_mqtt_port(value) -> int:
    """Extract mqtt port."""
    data = json_loads(value)
    read_value = data["data"]["cfg"]["mqttPort"]
    return read_value


def get_mqtt_client(value) -> str:
    """Extract mqtt client."""
    data = json_loads(value)
    read_value = data["data"]["cfg"]["mqttClientId"]
    return read_value


def get_mqtt_qos(value) -> int:
    """Extract qos."""
    data = json_loads(value)
    read_value = data["data"]["cfg"]["qos"]
    return read_value


def get_mqtt_user(value) -> str:
    """Extract mqtt user."""
    data = json_loads(value)
    read_value = data["data"]["cfg"]["mqttUser"]
    return read_value


def get_mqtt_ping(value) -> int:
    """Extract ping interval."""
    data = json_loads(value)
    read_value = data["data"]["cfg"]["pingInterval"]
    return read_value


def get_mqtt_url(value) -> str:
    """Extract MQTT URL."""
    data = json_loads(value)
    read_value = data["data"]["cfg"]["mqttUrl"]
    return read_value


SENSOR_TYPES_MQTT: tuple[ViarisSensorEntityDescription, ...] = (
    ViarisSensorEntityDescription(
        key=KEEP_ALIVE_KEY,
        icon="mdi:clock-time-two-outline",
        name="Keep alive",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=True,
        state=get_mqtt_keep_alive,
        disabled=False,
    ),
    ViarisSensorEntityDescription(
        key=MQTT_PORT_KEY,
        icon="mdi:hdmi-port",
        name="Mqtt port",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=True,
        state=get_mqtt_port,
        disabled=False,
    ),
    ViarisSensorEntityDescription(
        key=MQTT_QOS_KEY,
        icon="mdi:checkbox-marked-outline",
        name="Mqtt QoS",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=True,
        state=get_mqtt_qos,
        disabled=False,
    ),
    ViarisSensorEntityDescription(
        key=MQTT_CLIENT_ID_KEY,
        icon="mdi:account",
        name="Mqtt client Id",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=True,
        state=get_mqtt_client,
        disabled=False,
    ),
    ViarisSensorEntityDescription(
        key=MQTT_USER_KEY,
        icon="mdi:account",
        name="Mqtt user",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=True,
        state=get_mqtt_user,
        disabled=False,
    ),
    ViarisSensorEntityDescription(
        key=PING_KEY,
        icon="mdi:access-point",
        name="Mqtt ping interval",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=True,
        state=get_mqtt_ping,
        disabled=False,
    ),
    ViarisSensorEntityDescription(
        key=MQTT_URL_KEY,
        icon="mdi:web",
        name="Mqtt URL",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=True,
        state=get_mqtt_url,
        disabled=False,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: config_entries.ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Viaris method."""
    async_add_entities(
        ViarisSensorConfig(entry, description) for description in SENSOR_TYPES_CONFIG
    )
    async_add_entities(
        ViarisSensorMennekes(entry, description)
        for description in SENSOR_TYPES_MENNEKES1
    )
    async_add_entities(
        ViarisSensorMqttCfg(entry, description) for description in SENSOR_TYPES_MQTT
    )
    async_add_entities(
        ViarisSensorRt(entry, description) for description in SENSOR_TYPES_RT
    )
    async_add_entities(
        ViarisSensorMennekes2(entry, description)
        for description in SENSOR_TYPES_MENNEKES2
    )


class ViarisSensorRt(ViarisEntity, SensorEntity):
    """Representation of the Viaris portal."""

    entity_description: ViarisSensorEntityDescription

    def __init__(
        self,
        config_entry: config_entries.ConfigEntry,
        description: ViarisSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(config_entry, description)

        self.entity_description = description

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._attr_native_value is not None

    async def async_added_to_hass(self) -> None:
        """Publish start rt and subscribe MQTT events."""
        # value = {"idTrans": 0, "data": {"status": True, "period": 3, "timeout": 10000}}
        # value_json = json_dumps(value)
        # await mqtt.async_publish(self.hass, self._topic_rt_pub, value_json)

        @callback
        def message_received_rt(message):
            """Handle new MQTT messages."""

            if self.entity_description.state is not None:
                self._attr_native_value = self.entity_description.state(message.payload)
            else:
                self._attr_native_value = message.payload

            if self.entity_description.key == STATE_CONN1_KEY:
                if self._attr_native_value != "Disabled":
                    if self._attr_native_value[0:6] != "Schuko":
                        self._attr_icon = "mdi:ev-plug-type2"
                    else:
                        self._attr_icon = "mdi:power-socket-de"

            if self.entity_description.key == STATE_CONN2_KEY:
                if self._attr_native_value != "Disabled":
                    if self._attr_native_value[0:6] != "Schuko":
                        self._attr_icon = "mdi:ev-plug-type2"
                    else:
                        self._attr_icon = "mdi:power-socket-de"
                    # _LOGGER.info(self._attr_native_value)

            self.async_write_ha_state()

        await mqtt.async_subscribe(
            self.hass, self._topic_rt_subs, message_received_rt, 0
        )
        value = {"idTrans": 2}
        value_json = json_dumps(value)
        await mqtt.async_publish(self.hass, self._topic_boot_sys_pub, value_json)


class ViarisSensorConfig(ViarisEntity, SensorEntity):
    """Representation of the Viaris portal."""

    entity_description: ViarisSensorEntityDescription

    def __init__(
        self,
        config_entry: config_entries.ConfigEntry,
        description: ViarisSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(config_entry, description)

        self.entity_description = description

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._attr_native_value is not None

    async def async_added_to_hass(self) -> None:
        """Publish boot sys and subscribe MQTT events."""

        @callback
        def message_received_boot_sys(message):
            """Handle new MQTT messages."""
            value = {
                "idTrans": 0,
                "data": {"status": True, "period": 3, "timeout": 10000},
            }
            value_json = json_dumps(value)
            mqtt.publish(self.hass, self._topic_rt_pub, value_json)

            if self.entity_description.state is not None:
                self._attr_native_value = self.entity_description.state(message.payload)

            else:
                self._attr_native_value = message.payload

            self.async_write_ha_state()

        await mqtt.async_subscribe(
            self.hass, self._topic_init_boot_sys_subs, message_received_boot_sys, 1
        )
        await mqtt.async_subscribe(
            self.hass, self._topic_boot_sys_subs, message_received_boot_sys, 0
        )

        value = {"idTrans": 0}
        value_json = json_dumps(value)
        await mqtt.async_publish(self.hass, self._topic_evsm_mennekes_pub, value_json)

        # value = {"idTrans": 0}
        # value_json = json_dumps(value)
        # await mqtt.async_publish(self.hass, self._topic_evsm_schuko_pub, value_json)


class ViarisSensorMennekes(ViarisEntity, SensorEntity):
    """Representation of the Viaris portal."""

    entity_description: ViarisSensorEntityDescription

    def __init__(
        self,
        config_entry: config_entries.ConfigEntry,
        description: ViarisSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(config_entry, description)

        self.entity_description = description

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._attr_native_value is not None

    async def async_added_to_hass(self) -> None:
        """Publish mennekes and subscribe MQTT events."""

        @callback
        def message_received_mennekes_schuko(message):
            """Handle new MQTT messages."""
            if self.entity_description.state is not None:
                self._attr_native_value = self.entity_description.state(message.payload)

            else:
                self._attr_native_value = message.payload

            self.async_write_ha_state()

        await mqtt.async_subscribe(
            self.hass,
            self._topic_evsm_mennekes_subs,
            message_received_mennekes_schuko,
            0,
        )
        await mqtt.async_subscribe(
            self.hass,
            self._topic_evsm_menek_value_subs,
            message_received_mennekes_schuko,
            0,
        )
        # await mqtt.async_subscribe(
        # self.hass, self._topic_evsm_schuko_subs, message_received_mennekes_schuko, 0
        # )
        # await mqtt.async_subscribe(
        # self.hass,
        # self._topic_evsm_schuko_value_subs,
        # message_received_mennekes_schuko,
        # 0,
        # )
        if self._model == MODEL_COMBIPLUS:
            value = {"idTrans": 0}
            value_json = json_dumps(value)
            await mqtt.async_publish(
                self.hass, self._topic_evsm_mennekes2_pub, value_json
            )


class ViarisSensorMennekes2(ViarisEntity, SensorEntity):
    """Representation of the Viaris portal."""

    entity_description: ViarisSensorEntityDescription

    def __init__(
        self,
        config_entry: config_entries.ConfigEntry,
        description: ViarisSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(config_entry, description)

        self.entity_description = description

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._attr_native_value is not None

    async def async_added_to_hass(self) -> None:
        """Publish mennekes and subscribe MQTT events."""

        @callback
        def message_received_mennekes2(message):
            """Handle new MQTT messages."""
            if self.entity_description.state is not None:
                self._attr_native_value = self.entity_description.state(message.payload)

            else:
                self._attr_native_value = message.payload

            self.async_write_ha_state()

        if self._model == MODEL_COMBIPLUS:
            await mqtt.async_subscribe(
                self.hass,
                self._topic_evsm_mennekes2_subs,
                message_received_mennekes2,
                0,
            )
            await mqtt.async_subscribe(
                self.hass,
                self._topic_evsm_menek2_value_subs,
                message_received_mennekes2,
                0,
            )
            value = {"idTrans": 0}
            value_json = json_dumps(value)
            await mqtt.async_publish(
                self.hass, self._topic_evsm_mennekes2_pub, value_json
            )


class ViarisSensorMqttCfg(ViarisEntity, SensorEntity):
    """Representation of the Viaris portal."""

    entity_description: ViarisSensorEntityDescription

    def __init__(
        self,
        config_entry: config_entries.ConfigEntry,
        description: ViarisSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(config_entry, description)

        self.entity_description = description

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._attr_native_value is not None

    async def async_added_to_hass(self) -> None:
        """Publish mqtt config and subscribe MQTT events."""

        @callback
        def message_received_mqtt_cfg(message):
            """Handle new MQTT messages."""
            if self.entity_description.state is not None:
                self._attr_native_value = self.entity_description.state(message.payload)

            else:
                self._attr_native_value = message.payload

            self.async_write_ha_state()

        await mqtt.async_subscribe(
            self.hass, self._topic_mqtt_subs, message_received_mqtt_cfg, 0
        )
        value = {"idTrans": 0}
        value_json = json_dumps(value)
        await mqtt.async_publish(self.hass, self._topic_mqtt_pub, value_json)
