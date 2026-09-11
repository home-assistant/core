"""Initializer helpers for HomematicIP fake server."""

from typing import Any
from unittest.mock import AsyncMock, Mock, patch

from homematicip.async_home import AsyncHome
from homematicip.auth import Auth
from homematicip.base.enums import WeatherCondition, WeatherDayTime
from homematicip.connection.rest_connection import RestConnection
import pytest

from homeassistant.components.homematicip_cloud import (
    DOMAIN,
    async_setup as hmip_async_setup,
)
from homeassistant.components.homematicip_cloud.const import (
    HMIPC_AUTHTOKEN,
    HMIPC_HAPID,
    HMIPC_NAME,
    HMIPC_PIN,
)
from homeassistant.components.homematicip_cloud.hap import HomematicipHAP
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType

from .helper import AUTH_TOKEN, HAPID, HAPPIN, HomeFactory

from tests.common import MockConfigEntry
from tests.components.light.conftest import mock_light_profiles  # noqa: F401


@pytest.fixture(name="mock_connection")
def mock_connection_fixture() -> RestConnection:
    """Return a mocked connection."""
    connection = AsyncMock(spec=RestConnection)

    def _rest_call_side_effect(path, body=None, custom_header=None):
        return path, body

    connection.async_post.side_effect = _rest_call_side_effect

    return connection


@pytest.fixture(name="hmip_config_entry")
def hmip_config_entry_fixture() -> MockConfigEntry:
    """Create a mock config entry for homematic ip cloud."""
    entry_data = {
        HMIPC_HAPID: HAPID,
        HMIPC_AUTHTOKEN: AUTH_TOKEN,
        HMIPC_NAME: "",
        HMIPC_PIN: HAPPIN,
    }
    return MockConfigEntry(
        version=1,
        domain=DOMAIN,
        title="Home Test SN",
        unique_id=HAPID,
        data=entry_data,
        source=SOURCE_IMPORT,
    )


@pytest.fixture(name="default_mock_hap_factory")
async def default_mock_hap_factory_fixture(
    hass: HomeAssistant, mock_connection, hmip_config_entry: MockConfigEntry
) -> HomeFactory:
    """Create a mocked homematic access point."""
    return HomeFactory(hass, mock_connection, hmip_config_entry)


@pytest.fixture(name="full_flush_lock_controller_device_data")
def full_flush_lock_controller_device_data_fixture() -> dict[str, Any]:
    """Return fixture data for an HmIP-FLC device."""
    return {
        "availableFirmwareVersion": "0.0.0",
        "connectionType": "HMIP_RF",
        "deviceArchetype": "HMIP",
        "firmwareVersion": "1.0.10",
        "firmwareVersionInteger": 65546,
        "functionalChannels": {
            "0": {
                "configPending": False,
                "deviceId": "3014F7110000000000000026",
                "dutyCycle": False,
                "functionalChannelType": "DEVICE_BASE",
                "groupIndex": 0,
                "groups": [],
                "index": 0,
                "label": "",
                "lowBat": None,
                "routerModuleEnabled": False,
                "routerModuleSupported": False,
                "rssiDeviceValue": -82,
                "rssiPeerValue": -97,
                "supportedOptionalFeatures": {
                    "IFeatureRssiValue": True,
                    "IOptionalFeatureDutyCycle": True,
                    "IOptionalFeatureLowBat": False,
                },
                "unreach": False,
            },
            "1": {
                "actionParameter": "NOT_CUSTOMISABLE",
                "binaryBehaviorType": "NORMALLY_OPEN",
                "channelRole": "DOOR_LOCK_SENSOR",
                "corrosionPreventionActive": False,
                "deviceId": "3014F7110000000000000026",
                "doorBellSensorEventTimestamp": None,
                "eventDelay": 0,
                "functionalChannelType": "MULTI_MODE_LOCK_INPUT_CHANNEL",
                "glassBroken": True,
                "groupIndex": 1,
                "groups": [],
                "index": 1,
                "label": "",
                "lockState": "LOCKED",
                "multiModeInputMode": "BINARY_BEHAVIOR",
                "supportedOptionalFeatures": {},
                "windowState": "OPEN",
            },
            "3": {
                "channelRole": "DOOR_LOCK_ACTUATOR",
                "deviceId": "3014F7110000000000000026",
                "doorLockActive": False,
                "functionalChannelType": "DOOR_SWITCH_CHANNEL",
                "groupIndex": 3,
                "groups": [],
                "impulseDuration": 111600.0,
                "index": 3,
                "internalLinkConfiguration": {
                    "firstInputAction": "TOGGLE",
                    "internalLinkConfigurationType": "SINGLE_INPUT_DOOR_SWITCH",
                },
                "label": "",
                "multiModeInputMode": "KEY_BEHAVIOR",
                "processing": False,
                "profileMode": "AUTOMATIC",
                "supportedOptionalFeatures": {},
                "userDesiredProfileMode": "AUTOMATIC",
            },
            "4": {
                "channelRole": "DOOR_OPENER_ACTUATOR",
                "deviceId": "3014F7110000000000000026",
                "doorLockActive": False,
                "functionalChannelType": "DOOR_SWITCH_CHANNEL",
                "groupIndex": 4,
                "groups": [],
                "impulseDuration": 0.9,
                "index": 4,
                "internalLinkConfiguration": {
                    "firstInputAction": "LOCK_OPEN",
                    "internalLinkConfigurationType": "SINGLE_INPUT_DOOR_SWITCH",
                },
                "label": "",
                "multiModeInputMode": "SWITCH_BEHAVIOR",
                "processing": False,
                "profileMode": "AUTOMATIC",
                "supportedOptionalFeatures": {},
                "userDesiredProfileMode": "AUTOMATIC",
            },
            "5": {
                "authorized": True,
                "channelRole": "DOOR_LOCK_ACTUATOR",
                "deviceId": "3014F7110000000000000026",
                "functionalChannelType": "ACCESS_AUTHORIZATION_CHANNEL",
                "groupIndex": 3,
                "groups": [],
                "index": 5,
                "label": "",
                "supportedOptionalFeatures": {},
            },
            "9": {
                "authorized": True,
                "channelRole": "DOOR_OPENER_ACTUATOR",
                "deviceId": "3014F7110000000000000026",
                "functionalChannelType": "ACCESS_AUTHORIZATION_CHANNEL",
                "groupIndex": 4,
                "groups": [],
                "index": 9,
                "label": "",
                "supportedOptionalFeatures": {},
            },
        },
        "homeId": "00000000-0000-0000-0000-000000000001",
        "id": "3014F7110000000000000026",
        "label": "Universal Motorschloss Controller",
        "lastStatusUpdate": 1760619002144,
        "liveUpdateState": "LIVE_UPDATE_NOT_SUPPORTED",
        "manufacturerCode": 1,
        "modelId": 546,
        "modelType": "HmIP-FLC",
        "oem": "eQ-3",
        "permanentlyReachable": True,
        "serializedGlobalTradeItemNumber": "3014F7110000000000000026",
        "type": "FULL_FLUSH_LOCK_CONTROLLER",
        "updateState": "UP_TO_DATE",
    }


@pytest.fixture(name="full_flush_door_controller_device_data")
def full_flush_door_controller_device_data_fixture() -> dict[str, Any]:
    """Return fixture data for an HmIP-FDC device."""
    return {
        "availableFirmwareVersion": "1.0.0",
        "connectionType": "HMIP_RF",
        "firmwareVersion": "1.0.0",
        "firmwareVersionInteger": 65536,
        "functionalChannels": {
            "0": {
                "configPending": False,
                "deviceId": "3014F711000000000000FDC1",
                "dutyCycle": False,
                "functionalChannelType": "DEVICE_BASE",
                "groupIndex": 0,
                "groups": [],
                "index": 0,
                "label": "",
                "lowBat": None,
                "multicastRoutingEnabled": False,
                "routerModuleEnabled": False,
                "routerModuleSupported": False,
                "rssiDeviceValue": -60,
                "rssiPeerValue": -60,
                "supportedOptionalFeatures": {
                    "IFeatureDeviceIdentify": True,
                    "IFeatureRssiValue": True,
                    "IOptionalFeatureDutyCycle": True,
                },
                "unreach": False,
            },
            "1": {
                "actionParameter": "NOT_CUSTOMISABLE",
                "binaryBehaviorType": "NORMALLY_CLOSE",
                "channelRole": None,
                "corrosionPreventionActive": False,
                "deviceId": "3014F711000000000000FDC1",
                "doorBellSensorEventTimestamp": None,
                "eventDelay": 0,
                "functionalChannelType": "MULTI_MODE_LOCK_INPUT_CHANNEL",
                "glassBroken": False,
                "groupIndex": 1,
                "groups": [],
                "index": 1,
                "label": "",
                "lockState": "UNLOCKED",
                "multiModeInputMode": "KEY_BEHAVIOR",
                "supportedOptionalFeatures": {
                    "IOptionalFeatureLongPressSupported": True
                },
                "windowState": "CLOSED",
            },
            "2": {
                "actionParameter": "NOT_CUSTOMISABLE",
                "binaryBehaviorType": "NORMALLY_CLOSE",
                "channelRole": None,
                "corrosionPreventionActive": False,
                "deviceId": "3014F711000000000000FDC1",
                "doorBellSensorEventTimestamp": None,
                "eventDelay": 0,
                "functionalChannelType": "MULTI_MODE_LOCK_INPUT_CHANNEL",
                "glassBroken": False,
                "groupIndex": 2,
                "groups": [],
                "index": 2,
                "label": "",
                "lockState": "UNLOCKED",
                "multiModeInputMode": "KEY_BEHAVIOR",
                "supportedOptionalFeatures": {
                    "IOptionalFeatureLongPressSupported": True
                },
                "windowState": "CLOSED",
            },
            "3": {
                "channelRole": "DOOR_OPENER_ACTUATOR",
                "deviceId": "3014F711000000000000FDC1",
                "doorLockActive": False,
                "functionalChannelType": "DOOR_SWITCH_CHANNEL",
                "groupIndex": 3,
                "groups": [],
                "impulseDuration": 3.0,
                "index": 3,
                "internalLinkConfiguration": None,
                "label": "",
                "multiModeInputMode": "KEY_BEHAVIOR",
                "processing": False,
                "profileMode": "AUTOMATIC",
                "supportedOptionalFeatures": {
                    "IOptionalFeatureImpulseDuration": True,
                    "IOptionalFeatureImpulseOutputState": True,
                },
                "userDesiredProfileMode": "AUTOMATIC",
            },
            "4": {
                "authorized": True,
                "channelRole": "DOOR_OPENER_ACTUATOR",
                "deviceId": "3014F711000000000000FDC1",
                "functionalChannelType": "ACCESS_AUTHORIZATION_CHANNEL",
                "groupIndex": 3,
                "groups": [],
                "index": 4,
                "label": "",
                "supportedOptionalFeatures": {
                    "IFeatureAccessAuthorizationActuatorChannel": True
                },
            },
        },
        "homeId": "00000000-0000-0000-0000-000000000001",
        "id": "3014F711000000000000FDC1",
        "label": "Turoffner Haustuer",
        "lastStatusUpdate": 1778954102356,
        "liveUpdateState": "LIVE_UPDATE_NOT_SUPPORTED",
        "manuallyUpdateForced": True,
        "manufacturerCode": 1,
        "measuredAttributes": {},
        "modelId": 571,
        "modelType": "HmIP-FDC",
        "oem": "eQ-3",
        "permanentlyReachable": True,
        "serializedGlobalTradeItemNumber": "3014F711000000000000FDC1",
        "type": "FULL_FLUSH_DOOR_CONTROLLER",
        "updateState": "UP_TO_DATE",
    }


@pytest.fixture(name="hmip_config")
def hmip_config_fixture() -> ConfigType:
    """Create a config for homematic ip cloud."""

    entry_data = {
        HMIPC_HAPID: HAPID,
        HMIPC_AUTHTOKEN: AUTH_TOKEN,
        HMIPC_NAME: "",
        HMIPC_PIN: HAPPIN,
    }

    return {DOMAIN: [entry_data]}


@pytest.fixture(name="dummy_config")
def dummy_config_fixture() -> ConfigType:
    """Create a dummy config."""
    return {"blabla": None}


@pytest.fixture(name="mock_hap_with_service")
async def mock_hap_with_service_fixture(
    hass: HomeAssistant, default_mock_hap_factory: HomeFactory, dummy_config
) -> HomematicipHAP:
    """Create a fake homematic access point with hass services."""
    mock_hap = await default_mock_hap_factory.async_get_mock_hap()
    await hmip_async_setup(hass, dummy_config)
    await hass.async_block_till_done()
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    entry.runtime_data = mock_hap
    return mock_hap


@pytest.fixture(name="simple_mock_home")
def simple_mock_home_fixture():
    """Return a simple mocked connection."""

    mock_home = AsyncMock(
        spec=AsyncHome,
        name="Demo",
        devices=[],
        groups=[],
        location=Mock(),
        weather=Mock(
            temperature=0.0,
            weatherCondition=WeatherCondition.UNKNOWN,
            weatherDayTime=WeatherDayTime.DAY,
            minTemperature=0.0,
            maxTemperature=0.0,
            humidity=0,
            windSpeed=0.0,
            windDirection=0,
            vaporAmount=0.0,
        ),
        id=42,
        dutyCycle=88,
        connected=True,
        currentAPVersion="2.0.36",
        init_async=AsyncMock(),
        get_current_state_async=AsyncMock(),
    )

    with (
        patch(
            "homeassistant.components.homematicip_cloud.hap.AsyncHome",
            autospec=True,
            return_value=mock_home,
        ),
        patch(
            "homeassistant.components.homematicip_cloud.hap.ConnectionContextBuilder.build_context_async",
        ),
    ):
        yield


@pytest.fixture(name="mock_connection_init")
def mock_connection_init_fixture():
    """Return a simple mocked connection."""

    with (
        patch(
            "homeassistant.components.homematicip_cloud.hap.AsyncHome.init_async",
            return_value=None,
            new_callable=AsyncMock,
        ),
    ):
        yield


@pytest.fixture(name="simple_mock_auth")
def simple_mock_auth_fixture() -> Auth:
    """Return a simple AsyncAuth Mock."""
    return AsyncMock(spec=Auth, pin=HAPPIN, create=True)


@pytest.fixture(name="wall_mounted_thermostat_with_carbon_device_data")
def wall_mounted_thermostat_with_carbon_device_data_fixture() -> dict[str, Any]:
    """Return fixture data for an HmIP-WGTC device."""
    return {
        "availableFirmwareVersion": "1.0.18",
        "connectionType": "HMIP_RF",
        "deviceArchetype": "HMIP",
        "firmwareVersion": "1.0.18",
        "firmwareVersionInteger": 65554,
        "functionalChannels": {
            "0": {
                "altitude": None,
                "bootedRecently": False,
                "busConfigMismatch": None,
                "coProFaulty": False,
                "coProRestartNeeded": False,
                "coProUpdateFailure": False,
                "configPending": False,
                "controlsMountingOrientation": None,
                "daliBusState": None,
                "dataDecodingFailedError": None,
                "defaultLinkedGroup": [],
                "deviceAliveSignalEnabled": None,
                "deviceCanBusError": None,
                "deviceCommunicationError": None,
                "deviceDriveError": None,
                "deviceDriveModeError": None,
                "deviceId": "3014F711000000000000WGTC",
                "deviceOperationMode": None,
                "deviceOverheated": False,
                "deviceOverloaded": False,
                "devicePowerFailureDetected": False,
                "deviceUndervoltage": False,
                "displayContrast": None,
                "displayMode": None,
                "displayMountingOrientation": None,
                "dutyCycle": False,
                "fanControlMode": None,
                "frostProtectionError": None,
                "frostProtectionErrorAcknowledged": None,
                "functionalChannelType": "DEVICE_OPERATIONLOCK",
                "groupIndex": 0,
                "groups": [],
                "index": 0,
                "input1CoproEnabled": None,
                "input2CoproEnabled": None,
                "input3CoproEnabled": None,
                "input4CoproEnabled": None,
                "inputLayoutMode": None,
                "invertedDisplayColors": None,
                "label": "",
                "lastBootTimestamp": 1784278839458,
                "lockJammed": None,
                "lowBat": None,
                "mountingModuleError": None,
                "mountingOrientation": None,
                "multicastRoutingEnabled": False,
                "noDataFromLinkyError": None,
                "notRechargeableBattery": None,
                "operationDays": None,
                "operationLockActive": False,
                "particulateMatterSensorCommunicationError": None,
                "particulateMatterSensorError": None,
                "powerShortCircuit": None,
                "profilePeriodLimitReached": None,
                "routerModuleEnabled": False,
                "routerModuleSupported": False,
                "rssiDeviceValue": -75,
                "rssiPeerValue": None,
                "sensorCommunicationError": None,
                "sensorError": None,
                "shortCircuitDataLine": None,
                "supportedOptionalFeatures": {
                    "IFeatureDeviceIdentify": True,
                    "IFeatureDeviceMountingModuleError": True,
                    "IFeatureDeviceOverloaded": True,
                    "IFeatureProfilePeriodLimit": True,
                    "IFeatureRssiValue": True,
                    "IOptionalFeatureDeviceSwitchChannelMode": True,
                    "IOptionalFeatureDutyCycle": True,
                },
                "switchChannelMode": "FLOOR_HEATING",
                "temperatureHumiditySensorCommunicationError": None,
                "temperatureHumiditySensorError": None,
                "temperatureOutOfRange": False,
                "ticVersionError": None,
                "unreach": False,
                "valveFlowError": None,
                "valveWaterError": None,
            },
            "1": {
                "channelRole": "KEY_OR_SWITCH_FOR_GROUP",
                "deviceId": "3014F711000000000000WGTC",
                "functionalChannelType": "INPUT_QUICK_ACTION_DISPLAY_CHANNEL",
                "groupIndex": 1,
                "groups": [],
                "index": 1,
                "label": "",
                "supportedOptionalFeatures": {
                    "IFeatureLightGroupSensorChannel": True,
                    "IFeatureShadingGroupSensorChannel": True,
                },
            },
            "2": {
                "channelRole": "DIMMING_ACTUATOR",
                "deviceId": "3014F711000000000000WGTC",
                "dimLevel": 0.02,
                "functionalChannelType": "BACKLIGHT_CHANNEL",
                "groupIndex": 2,
                "groups": [],
                "index": 2,
                "label": "",
                "on": True,
                "powerUpDimLevel": 0.02,
                "powerUpSwitchState": "PERMANENT_ON",
                "profileMode": "AUTOMATIC",
                "supportedOptionalFeatures": {
                    "IFeatureLightProfileActuatorChannel": True
                },
                "switchVisualization": "LIGHT",
                "userDesiredProfileMode": "AUTOMATIC",
            },
            "3": {
                "actualTemperature": 22.6,
                "carbonDioxideConcentration": 440.0,
                "channelRole": "WALL_MOUNTED_THERMOSTAT",
                "deviceId": "3014F711000000000000WGTC",
                "display": "ACTUAL",
                "functionalChannelType": "WALL_MOUNTED_THERMOSTAT_WITH_CARBON_CHANNEL",
                "groupIndex": 3,
                "groups": [],
                "humidity": 48,
                "index": 3,
                "label": "Wandthermostat (3 + 4) Child",
                "setPointTemperature": 18.0,
                "supportedOptionalFeatures": {
                    "IOptionalFeatureClimateControlDisplayCarbonSupported": True,
                    "IOptionalFeatureClimateControlDisplayHumidityOnlySupported": True,
                    "IOptionalFeatureThermostatCoolingSupported": True,
                },
                "temperatureOffset": -0.5,
                "vaporAmount": 9.619851889906071,
            },
            "4": {
                "climateControlType": "PWM_CONTROL",
                "deviceId": "3014F711000000000000WGTC",
                "frostProtectionTemperature": 8.0,
                "functionalChannelType": "INTERNAL_SWITCH_CHANNEL",
                "groupIndex": 3,
                "groups": [],
                "heatingValveType": "NORMALLY_CLOSE",
                "index": 4,
                "internalSwitchOutputEnabled": False,
                "label": "Wandthermostat (3 + 4) Child",
                "supportedOptionalFeatures": {
                    "IOptionalFeatureClimateControlType": True,
                    "IOptionalFeatureFloorHeatingSpecificGroupSupported": True,
                },
                "valvePosition": 0.0,
                "valveProtectionDuration": 5,
                "valveProtectionSwitchingInterval": 14,
            },
            "5": {
                "channelRole": None,
                "deviceId": "3014F711000000000000WGTC",
                "functionalChannelType": "SWITCH_CHANNEL",
                "groupIndex": 0,
                "groups": [],
                "index": 5,
                "internalLinkConfiguration": None,
                "label": "",
                "on": False,
                "powerUpSwitchState": "PERMANENT_OFF",
                "profileMode": "AUTOMATIC",
                "supportedOptionalFeatures": {
                    "IOptionalFeaturePowerUpSwitchState": True
                },
                "switchVisualization": None,
                "userDesiredProfileMode": "AUTOMATIC",
            },
            "6": {
                "deviceId": "3014F711000000000000WGTC",
                "functionalChannelType": "HEAT_DEMAND_CHANNEL",
                "groupIndex": 0,
                "groups": [],
                "index": 6,
                "label": "",
            },
            "7": {
                "deviceId": "3014F711000000000000WGTC",
                "functionalChannelType": "DEHUMIDIFIER_DEMAND_CHANNEL",
                "groupIndex": 0,
                "groups": [],
                "index": 7,
                "label": "",
            },
            "8": {
                "deviceId": "3014F711000000000000WGTC",
                "functionalChannelType": "CHANGE_OVER_CHANNEL",
                "groupIndex": 0,
                "groups": [],
                "index": 8,
                "label": "",
            },
        },
        "homeId": "00000000-0000-0000-0000-000000000001",
        "id": "3014F711000000000000WGTC",
        "label": "Wandthermostat mit CO2",
        "lastStatusUpdate": 1784553668564,
        "liveUpdateState": "LIVE_UPDATE_NOT_SUPPORTED",
        "manuallyUpdateForced": False,
        "manufacturerCode": 1,
        "measuredAttributes": {
            "3": {
                "actualTemperature": True,
                "carbonDioxideConcentration": True,
                "humidity": True,
                "setPointTemperature": True,
            }
        },
        "modelId": 568,
        "modelType": "HmIP-WGTC",
        "oem": "eQ-3",
        "permanentlyReachable": True,
        "serializedGlobalTradeItemNumber": "3014F711000000000000WGTC",
        "type": "WALL_MOUNTED_GLASS_THERMOSTAT_CARBON",
        "updateState": "UP_TO_DATE",
    }


@pytest.fixture(name="carbon_dioxide_sensor_device_data")
def carbon_dioxide_sensor_device_data_fixture() -> dict[str, Any]:
    """Return fixture data for an HmIP-SCTH230 device."""
    return {
        "availableFirmwareVersion": "1.0.6",
        "connectionType": "HMIP_RF",
        "deviceArchetype": "HMIP",
        "firmwareVersion": "1.0.6",
        "firmwareVersionInteger": 65542,
        "functionalChannels": {
            "0": {
                "busConfigMismatch": None,
                "coProFaulty": False,
                "coProRestartNeeded": False,
                "coProUpdateFailure": False,
                "configPending": False,
                "controlsMountingOrientation": None,
                "deviceCommunicationError": None,
                "deviceDriveError": None,
                "deviceDriveModeError": None,
                "deviceId": "3014F711000000000SCTH230",
                "deviceOperationMode": None,
                "deviceOverheated": False,
                "deviceOverloaded": False,
                "devicePowerFailureDetected": False,
                "deviceUndervoltage": False,
                "displayContrast": None,
                "dutyCycle": False,
                "functionalChannelType": "DEVICE_BASE",
                "groupIndex": 0,
                "groups": ["00000000-0000-0000-0000-000000000052"],
                "index": 0,
                "label": "",
                "lockJammed": None,
                "lowBat": None,
                "mountingOrientation": None,
                "multicastRoutingEnabled": False,
                "particulateMatterSensorCommunicationError": None,
                "particulateMatterSensorError": None,
                "powerShortCircuit": None,
                "profilePeriodLimitReached": None,
                "routerModuleEnabled": False,
                "routerModuleSupported": False,
                "rssiDeviceValue": -66,
                "rssiPeerValue": None,
                "shortCircuitDataLine": None,
                "supportedOptionalFeatures": {
                    "IFeatureBusConfigMismatch": False,
                    "IFeatureDeviceCoProError": False,
                    "IFeatureDeviceCoProRestart": False,
                    "IFeatureDeviceCoProUpdate": False,
                    "IFeatureDeviceCommunicationError": False,
                    "IFeatureDeviceDriveError": False,
                    "IFeatureDeviceDriveModeError": False,
                    "IFeatureDeviceIdentify": False,
                    "IFeatureDeviceOverheated": False,
                    "IFeatureDeviceOverloaded": False,
                    "IFeatureDeviceParticulateMatterSensorCommunicationError": False,
                    "IFeatureDeviceParticulateMatterSensorError": False,
                    "IFeatureDevicePowerFailure": False,
                    "IFeatureDeviceTemperatureHumiditySensorCommunicationError": False,
                    "IFeatureDeviceTemperatureHumiditySensorError": False,
                    "IFeatureDeviceTemperatureOutOfRange": False,
                    "IFeatureDeviceUndervoltage": False,
                    "IFeatureMulticastRouter": False,
                    "IFeaturePowerShortCircuit": False,
                    "IFeatureProfilePeriodLimit": True,
                    "IFeatureRssiValue": True,
                    "IFeatureShortCircuitDataLine": False,
                    "IOptionalFeatureDeviceErrorLockJammed": False,
                    "IOptionalFeatureDeviceOperationMode": False,
                    "IOptionalFeatureDisplayContrast": False,
                    "IOptionalFeatureDutyCycle": True,
                    "IOptionalFeatureLowBat": False,
                    "IOptionalFeatureMountingOrientation": False,
                },
                "temperatureHumiditySensorCommunicationError": None,
                "temperatureHumiditySensorError": None,
                "temperatureOutOfRange": False,
                "unreach": False,
            },
            "1": {
                "actualTemperature": 25.5,
                "carbonDioxideConcentration": 1181.0,
                "carbonDioxideVisualisationEnabled": True,
                "channelRole": "CARBON_DIOXIDE_SENSOR",
                "deviceId": "3014F711000000000SCTH230",
                "functionalChannelType": "CARBON_DIOXIDE_SENSOR_CHANNEL",
                "groupIndex": 1,
                "groups": ["00000000-0000-0000-0000-000000000053"],
                "humidity": 37,
                "index": 1,
                "label": "",
                "vaporAmount": 8.739326558877478,
            },
            "2": {
                "channelRole": "SWITCH_ACTUATOR",
                "deviceId": "3014F711000000000SCTH230",
                "functionalChannelType": "SWITCH_CHANNEL",
                "groupIndex": 2,
                "groups": ["00000000-0000-0000-0000-000000000054"],
                "index": 2,
                "internalLinkConfiguration": None,
                "label": "",
                "on": False,
                "powerUpSwitchState": "PERMANENT_OFF",
                "profileMode": "AUTOMATIC",
                "supportedOptionalFeatures": {
                    "IFeatureAccessAuthorizationActuatorChannel": False,
                    "IFeatureLightGroupActuatorChannel": True,
                    "IFeatureLightProfileActuatorChannel": True,
                    "IOptionalFeatureInternalLinkConfiguration": False,
                    "IOptionalFeaturePowerUpSwitchState": True,
                },
                "userDesiredProfileMode": "AUTOMATIC",
            },
        },
        "homeId": "00000000-0000-0000-0000-000000000001",
        "id": "3014F711000000000SCTH230",
        "label": "CO2 Sensor miko ",
        "lastStatusUpdate": 1676606756797,
        "liveUpdateState": "LIVE_UPDATE_NOT_SUPPORTED",
        "manufacturerCode": 1,
        "modelId": 435,
        "modelType": "HmIP-SCTH230",
        "oem": "eQ-3",
        "permanentlyReachable": True,
        "serializedGlobalTradeItemNumber": "3014F711000000000SCTH230",
        "type": "CARBON_DIOXIDE_SENSOR",
        "updateState": "UP_TO_DATE",
    }
