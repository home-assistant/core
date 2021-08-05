"""Common methods used across tests for TotalConnect."""
from unittest.mock import patch

from total_connect_client import TotalConnectClient

from homeassistant.components.totalconnect.const import CONF_USERCODES, DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry

LOCATION_ID = "123456"

LOCATION_INFO_BASIC_NORMAL = {
    "LocationID": LOCATION_ID,
    "LocationName": "test",
    "SecurityDeviceID": "987654",
    "PhotoURL": "http://www.example.com/some/path/to/file.jpg",
    "LocationModuleFlags": "Security=1,Video=0,Automation=0,GPS=0,VideoPIR=0",
    "DeviceList": None,
}

LOCATIONS = {"LocationInfoBasic": [LOCATION_INFO_BASIC_NORMAL]}

MODULE_FLAGS = "Some=0,Fake=1,Flags=2"

USER = {
    "UserID": "1234567",
    "Username": "username",
    "UserFeatureList": "Master=0,User Administration=0,Configuration Administration=0",
}

RESPONSE_AUTHENTICATE = {
    "ResultCode": TotalConnectClient.TotalConnectClient.SUCCESS,
    "SessionID": 1,
    "Locations": LOCATIONS,
    "ModuleFlags": MODULE_FLAGS,
    "UserInfo": USER,
}

RESPONSE_AUTHENTICATE_FAILED = {
    "ResultCode": TotalConnectClient.TotalConnectClient.BAD_USER_OR_PASSWORD,
    "ResultData": "test bad authentication",
}


PARTITION_DISARMED = {
    "PartitionID": "1",
    "ArmingState": TotalConnectClient.TotalConnectLocation.DISARMED,
}

PARTITION_ARMED_STAY = {
    "PartitionID": "1",
    "ArmingState": TotalConnectClient.TotalConnectLocation.ARMED_STAY,
}

PARTITION_ARMED_AWAY = {
    "PartitionID": "1",
    "ArmingState": TotalConnectClient.TotalConnectLocation.ARMED_AWAY,
}

PARTITION_ARMED_CUSTOM = {
    "PartitionID": "1",
    "ArmingState": TotalConnectClient.TotalConnectLocation.ARMED_CUSTOM_BYPASS,
}

PARTITION_ARMED_NIGHT = {
    "PartitionID": "1",
    "ArmingState": TotalConnectClient.TotalConnectLocation.ARMED_STAY_NIGHT,
}

PARTITION_ARMING = {
    "PartitionID": "1",
    "ArmingState": TotalConnectClient.TotalConnectLocation.ARMING,
}
PARTITION_DISARMING = {
    "PartitionID": "1",
    "ArmingState": TotalConnectClient.TotalConnectLocation.DISARMING,
}

PARTITION_TRIGGERED_POLICE = {
    "PartitionID": "1",
    "ArmingState": TotalConnectClient.TotalConnectLocation.ALARMING,
}

PARTITION_TRIGGERED_FIRE = {
    "PartitionID": "1",
    "ArmingState": TotalConnectClient.TotalConnectLocation.ALARMING_FIRE_SMOKE,
}

PARTITION_TRIGGERED_CARBON_MONOXIDE = {
    "PartitionID": "1",
    "ArmingState": TotalConnectClient.TotalConnectLocation.ALARMING_CARBON_MONOXIDE,
}

PARTITION_UNKNOWN = {
    "PartitionID": "1",
    "ArmingState": "99999",
}


PARTITION_INFO_DISARMED = {0: PARTITION_DISARMED}
PARTITION_INFO_ARMED_STAY = {0: PARTITION_ARMED_STAY}
PARTITION_INFO_ARMED_AWAY = {0: PARTITION_ARMED_AWAY}
PARTITION_INFO_ARMED_CUSTOM = {0: PARTITION_ARMED_CUSTOM}
PARTITION_INFO_ARMED_NIGHT = {0: PARTITION_ARMED_NIGHT}
PARTITION_INFO_ARMING = {0: PARTITION_ARMING}
PARTITION_INFO_DISARMING = {0: PARTITION_DISARMING}
PARTITION_INFO_TRIGGERED_POLICE = {0: PARTITION_TRIGGERED_POLICE}
PARTITION_INFO_TRIGGERED_FIRE = {0: PARTITION_TRIGGERED_FIRE}
PARTITION_INFO_TRIGGERED_CARBON_MONOXIDE = {0: PARTITION_TRIGGERED_CARBON_MONOXIDE}
PARTITION_INFO_UNKNOWN = {0: PARTITION_UNKNOWN}

PARTITIONS_DISARMED = {"PartitionInfo": PARTITION_INFO_DISARMED}
PARTITIONS_ARMED_STAY = {"PartitionInfo": PARTITION_INFO_ARMED_STAY}
PARTITIONS_ARMED_AWAY = {"PartitionInfo": PARTITION_INFO_ARMED_AWAY}
PARTITIONS_ARMED_CUSTOM = {"PartitionInfo": PARTITION_INFO_ARMED_CUSTOM}
PARTITIONS_ARMED_NIGHT = {"PartitionInfo": PARTITION_INFO_ARMED_NIGHT}
PARTITIONS_ARMING = {"PartitionInfo": PARTITION_INFO_ARMING}
PARTITIONS_DISARMING = {"PartitionInfo": PARTITION_INFO_DISARMING}
PARTITIONS_TRIGGERED_POLICE = {"PartitionInfo": PARTITION_INFO_TRIGGERED_POLICE}
PARTITIONS_TRIGGERED_FIRE = {"PartitionInfo": PARTITION_INFO_TRIGGERED_FIRE}
PARTITIONS_TRIGGERED_CARBON_MONOXIDE = {
    "PartitionInfo": PARTITION_INFO_TRIGGERED_CARBON_MONOXIDE
}
PARTITIONS_UNKNOWN = {"PartitionInfo": PARTITION_INFO_UNKNOWN}

ZONE_NORMAL = {
    "ZoneID": "1",
    "ZoneDescription": "Normal",
    "ZoneStatus": TotalConnectClient.ZONE_STATUS_NORMAL,
    "PartitionId": "1",
}

ZONE_INFO = [ZONE_NORMAL]
ZONES = {"ZoneInfo": ZONE_INFO}

METADATA_DISARMED = {
    "Partitions": PARTITIONS_DISARMED,
    "Zones": ZONES,
    "PromptForImportSecuritySettings": False,
    "IsInACLoss": False,
    "IsCoverTampered": False,
    "Bell1SupervisionFailure": False,
    "Bell2SupervisionFailure": False,
    "IsInLowBattery": False,
}

METADATA_ARMED_STAY = METADATA_DISARMED.copy()
METADATA_ARMED_STAY["Partitions"] = PARTITIONS_ARMED_STAY

METADATA_ARMED_AWAY = METADATA_DISARMED.copy()
METADATA_ARMED_AWAY["Partitions"] = PARTITIONS_ARMED_AWAY

METADATA_ARMED_CUSTOM = METADATA_DISARMED.copy()
METADATA_ARMED_CUSTOM["Partitions"] = PARTITIONS_ARMED_CUSTOM

METADATA_ARMED_NIGHT = METADATA_DISARMED.copy()
METADATA_ARMED_NIGHT["Partitions"] = PARTITIONS_ARMED_NIGHT

METADATA_ARMING = METADATA_DISARMED.copy()
METADATA_ARMING["Partitions"] = PARTITIONS_ARMING

METADATA_DISARMING = METADATA_DISARMED.copy()
METADATA_DISARMING["Partitions"] = PARTITIONS_DISARMING

METADATA_TRIGGERED_POLICE = METADATA_DISARMED.copy()
METADATA_TRIGGERED_POLICE["Partitions"] = PARTITIONS_TRIGGERED_POLICE

METADATA_TRIGGERED_FIRE = METADATA_DISARMED.copy()
METADATA_TRIGGERED_FIRE["Partitions"] = PARTITIONS_TRIGGERED_FIRE

METADATA_TRIGGERED_CARBON_MONOXIDE = METADATA_DISARMED.copy()
METADATA_TRIGGERED_CARBON_MONOXIDE["Partitions"] = PARTITIONS_TRIGGERED_CARBON_MONOXIDE

METADATA_UNKNOWN = METADATA_DISARMED.copy()
METADATA_UNKNOWN["Partitions"] = PARTITIONS_UNKNOWN

RESPONSE_DISARMED = {"ResultCode": 0, "PanelMetadataAndStatus": METADATA_DISARMED}
RESPONSE_ARMED_STAY = {"ResultCode": 0, "PanelMetadataAndStatus": METADATA_ARMED_STAY}
RESPONSE_ARMED_AWAY = {"ResultCode": 0, "PanelMetadataAndStatus": METADATA_ARMED_AWAY}
RESPONSE_ARMED_CUSTOM = {
    "ResultCode": 0,
    "PanelMetadataAndStatus": METADATA_ARMED_CUSTOM,
}
RESPONSE_ARMED_NIGHT = {"ResultCode": 0, "PanelMetadataAndStatus": METADATA_ARMED_NIGHT}
RESPONSE_ARMING = {"ResultCode": 0, "PanelMetadataAndStatus": METADATA_ARMING}
RESPONSE_DISARMING = {"ResultCode": 0, "PanelMetadataAndStatus": METADATA_DISARMING}
RESPONSE_TRIGGERED_POLICE = {
    "ResultCode": 0,
    "PanelMetadataAndStatus": METADATA_TRIGGERED_POLICE,
}
RESPONSE_TRIGGERED_FIRE = {
    "ResultCode": 0,
    "PanelMetadataAndStatus": METADATA_TRIGGERED_FIRE,
}
RESPONSE_TRIGGERED_CARBON_MONOXIDE = {
    "ResultCode": 0,
    "PanelMetadataAndStatus": METADATA_TRIGGERED_CARBON_MONOXIDE,
}
RESPONSE_UNKNOWN = {"ResultCode": 0, "PanelMetadataAndStatus": METADATA_UNKNOWN}

RESPONSE_ARM_SUCCESS = {"ResultCode": TotalConnectClient.TotalConnectClient.ARM_SUCCESS}
RESPONSE_ARM_FAILURE = {
    "ResultCode": TotalConnectClient.TotalConnectClient.COMMAND_FAILED
}
RESPONSE_DISARM_SUCCESS = {
    "ResultCode": TotalConnectClient.TotalConnectClient.DISARM_SUCCESS
}
RESPONSE_DISARM_FAILURE = {
    "ResultCode": TotalConnectClient.TotalConnectClient.COMMAND_FAILED,
    "ResultData": "Command Failed",
}
RESPONSE_USER_CODE_INVALID = {
    "ResultCode": TotalConnectClient.TotalConnectClient.USER_CODE_INVALID,
    "ResultData": "testing user code invalid",
}
RESPONSE_SUCCESS = {"ResultCode": TotalConnectClient.TotalConnectClient.SUCCESS}

USERNAME = "username@me.com"
PASSWORD = "password"
USERCODES = {123456: "7890"}
CONFIG_DATA = {
    CONF_USERNAME: USERNAME,
    CONF_PASSWORD: PASSWORD,
    CONF_USERCODES: USERCODES,
}
CONFIG_DATA_NO_USERCODES = {CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD}


USERNAME = "username@me.com"
PASSWORD = "password"
USERCODES = {123456: "7890"}
CONFIG_DATA = {
    CONF_USERNAME: USERNAME,
    CONF_PASSWORD: PASSWORD,
    CONF_USERCODES: USERCODES,
}
CONFIG_DATA_NO_USERCODES = {CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD}


async def setup_platform(hass, platform):
    """Set up the TotalConnect platform."""
    # first set up a config entry and add it to hass
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        data=CONFIG_DATA,
    )
    mock_entry.add_to_hass(hass)

    responses = [RESPONSE_AUTHENTICATE, RESPONSE_DISARMED]

    with patch("homeassistant.components.totalconnect.PLATFORMS", [platform]), patch(
        "zeep.Client", autospec=True
    ), patch(
        "homeassistant.components.totalconnect.TotalConnectClient.TotalConnectClient.request",
        side_effect=responses,
    ) as mock_request, patch(
        "homeassistant.components.totalconnect.TotalConnectClient.TotalConnectClient.get_zone_details",
        return_value=True,
    ):
        assert await async_setup_component(hass, DOMAIN, {})
        assert mock_request.call_count == 2
    await hass.async_block_till_done()

    return mock_entry
