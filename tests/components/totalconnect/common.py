"""Common methods used across tests for TotalConnect."""
from unittest.mock import patch

from total_connect_client.client import TotalConnectClient
from total_connect_client.const import ArmingState
from total_connect_client.zone import ZoneStatus, ZoneType

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
    "ResultCode": TotalConnectClient.SUCCESS,
    "SessionID": 1,
    "Locations": LOCATIONS,
    "ModuleFlags": MODULE_FLAGS,
    "UserInfo": USER,
}

RESPONSE_AUTHENTICATE_FAILED = {
    "ResultCode": TotalConnectClient.BAD_USER_OR_PASSWORD,
    "ResultData": "test bad authentication",
}


PARTITION_DISARMED = {
    "PartitionID": "1",
    "ArmingState": ArmingState.DISARMED,
}

PARTITION_ARMED_STAY = {
    "PartitionID": "1",
    "ArmingState": ArmingState.ARMED_STAY,
}

PARTITION_ARMED_AWAY = {
    "PartitionID": "1",
    "ArmingState": ArmingState.ARMED_AWAY,
}

PARTITION_ARMED_CUSTOM = {
    "PartitionID": "1",
    "ArmingState": ArmingState.ARMED_CUSTOM_BYPASS,
}

PARTITION_ARMED_NIGHT = {
    "PartitionID": "1",
    "ArmingState": ArmingState.ARMED_STAY_NIGHT,
}

PARTITION_ARMING = {
    "PartitionID": "1",
    "ArmingState": ArmingState.ARMING,
}
PARTITION_DISARMING = {
    "PartitionID": "1",
    "ArmingState": ArmingState.DISARMING,
}

PARTITION_TRIGGERED_POLICE = {
    "PartitionID": "1",
    "ArmingState": ArmingState.ALARMING,
}

PARTITION_TRIGGERED_FIRE = {
    "PartitionID": "1",
    "ArmingState": ArmingState.ALARMING_FIRE_SMOKE,
}

PARTITION_TRIGGERED_CARBON_MONOXIDE = {
    "PartitionID": "1",
    "ArmingState": ArmingState.ALARMING_CARBON_MONOXIDE,
}

PARTITION_UNKNOWN = {
    "PartitionID": "1",
    "ArmingState": "99999",
}


PARTITION_INFO_DISARMED = [PARTITION_DISARMED]
PARTITION_INFO_ARMED_STAY = [PARTITION_ARMED_STAY]
PARTITION_INFO_ARMED_AWAY = [PARTITION_ARMED_AWAY]
PARTITION_INFO_ARMED_CUSTOM = [PARTITION_ARMED_CUSTOM]
PARTITION_INFO_ARMED_NIGHT = [PARTITION_ARMED_NIGHT]
PARTITION_INFO_ARMING = [PARTITION_ARMING]
PARTITION_INFO_DISARMING = [PARTITION_DISARMING]
PARTITION_INFO_TRIGGERED_POLICE = [PARTITION_TRIGGERED_POLICE]
PARTITION_INFO_TRIGGERED_FIRE = [PARTITION_TRIGGERED_FIRE]
PARTITION_INFO_TRIGGERED_CARBON_MONOXIDE = [PARTITION_TRIGGERED_CARBON_MONOXIDE]
PARTITION_INFO_UNKNOWN = [PARTITION_UNKNOWN]

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
    "ZoneStatus": ZoneStatus.NORMAL,
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

RESPONSE_DISARMED = {
    "ResultCode": 0,
    "PanelMetadataAndStatus": METADATA_DISARMED,
    "ArmingState": ArmingState.DISARMED,
}
RESPONSE_ARMED_STAY = {
    "ResultCode": 0,
    "PanelMetadataAndStatus": METADATA_ARMED_STAY,
    "ArmingState": ArmingState.ARMED_STAY,
}
RESPONSE_ARMED_AWAY = {
    "ResultCode": 0,
    "PanelMetadataAndStatus": METADATA_ARMED_AWAY,
    "ArmingState": ArmingState.ARMED_AWAY,
}
RESPONSE_ARMED_CUSTOM = {
    "ResultCode": 0,
    "PanelMetadataAndStatus": METADATA_ARMED_CUSTOM,
    "ArmingState": ArmingState.ARMED_CUSTOM_BYPASS,
}
RESPONSE_ARMED_NIGHT = {
    "ResultCode": 0,
    "PanelMetadataAndStatus": METADATA_ARMED_NIGHT,
    "ArmingState": ArmingState.ARMED_STAY_NIGHT,
}
RESPONSE_ARMING = {
    "ResultCode": 0,
    "PanelMetadataAndStatus": METADATA_ARMING,
    "ArmingState": ArmingState.ARMING,
}
RESPONSE_DISARMING = {
    "ResultCode": 0,
    "PanelMetadataAndStatus": METADATA_DISARMING,
    "ArmingState": ArmingState.DISARMING,
}
RESPONSE_TRIGGERED_POLICE = {
    "ResultCode": 0,
    "PanelMetadataAndStatus": METADATA_TRIGGERED_POLICE,
    "ArmingState": ArmingState.ALARMING,
}
RESPONSE_TRIGGERED_FIRE = {
    "ResultCode": 0,
    "PanelMetadataAndStatus": METADATA_TRIGGERED_FIRE,
    "ArmingState": ArmingState.ALARMING_FIRE_SMOKE,
}
RESPONSE_TRIGGERED_CARBON_MONOXIDE = {
    "ResultCode": 0,
    "PanelMetadataAndStatus": METADATA_TRIGGERED_CARBON_MONOXIDE,
    "ArmingState": ArmingState.ALARMING_CARBON_MONOXIDE,
}
RESPONSE_UNKNOWN = {
    "ResultCode": 0,
    "PanelMetadataAndStatus": METADATA_UNKNOWN,
    "ArmingState": ArmingState.DISARMED,
}

RESPONSE_ARM_SUCCESS = {"ResultCode": TotalConnectClient.ARM_SUCCESS}
RESPONSE_ARM_FAILURE = {"ResultCode": TotalConnectClient.COMMAND_FAILED}
RESPONSE_DISARM_SUCCESS = {"ResultCode": TotalConnectClient.DISARM_SUCCESS}
RESPONSE_DISARM_FAILURE = {
    "ResultCode": TotalConnectClient.COMMAND_FAILED,
    "ResultData": "Command Failed",
}
RESPONSE_USER_CODE_INVALID = {
    "ResultCode": TotalConnectClient.USER_CODE_INVALID,
    "ResultData": "testing user code invalid",
}
RESPONSE_SUCCESS = {"ResultCode": TotalConnectClient.SUCCESS}

USERNAME = "username@me.com"
PASSWORD = "password"
USERCODES = {123456: "7890"}
CONFIG_DATA = {
    CONF_USERNAME: USERNAME,
    CONF_PASSWORD: PASSWORD,
    CONF_USERCODES: USERCODES,
}
CONFIG_DATA_NO_USERCODES = {CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD}

PARTITION_DETAILS_1 = {
    "PartitionID": 1,
    "ArmingState": ArmingState.DISARMED.value,
    "PartitionName": "Test1",
}

PARTITION_DETAILS_2 = {
    "PartitionID": 2,
    "ArmingState": ArmingState.DISARMED.value,
    "PartitionName": "Test2",
}

PARTITION_DETAILS = {"PartitionDetails": [PARTITION_DETAILS_1]}
RESPONSE_PARTITION_DETAILS = {
    "ResultCode": TotalConnectClient.SUCCESS,
    "ResultData": "testing partition details",
    "PartitionsInfoList": PARTITION_DETAILS,
}

ZONE_DETAILS_NORMAL = {
    "PartitionId": "1",
    "Batterylevel": "-1",
    "Signalstrength": "-1",
    "zoneAdditionalInfo": None,
    "ZoneID": "1",
    "ZoneStatus": ZoneStatus.NORMAL,
    "ZoneTypeId": ZoneType.SECURITY,
    "CanBeBypassed": 1,
    "ZoneFlags": None,
}

ZONE_STATUS_INFO = [ZONE_DETAILS_NORMAL]
ZONE_DETAILS = {"ZoneStatusInfoWithPartitionId": ZONE_STATUS_INFO}
ZONE_DETAIL_STATUS = {"Zones": ZONE_DETAILS}

RESPONSE_GET_ZONE_DETAILS_SUCCESS = {
    "ResultCode": 0,
    "ResultData": "Success",
    "ZoneStatus": ZONE_DETAIL_STATUS,
}

TOTALCONNECT_REQUEST = (
    "homeassistant.components.totalconnect.TotalConnectClient.request"
)


async def setup_platform(hass, platform):
    """Set up the TotalConnect platform."""
    # first set up a config entry and add it to hass
    mock_entry = MockConfigEntry(domain=DOMAIN, data=CONFIG_DATA)
    mock_entry.add_to_hass(hass)

    responses = [
        RESPONSE_AUTHENTICATE,
        RESPONSE_PARTITION_DETAILS,
        RESPONSE_GET_ZONE_DETAILS_SUCCESS,
        RESPONSE_DISARMED,
        RESPONSE_DISARMED,
    ]

    with patch("homeassistant.components.totalconnect.PLATFORMS", [platform]), patch(
        TOTALCONNECT_REQUEST,
        side_effect=responses,
    ) as mock_request:
        assert await async_setup_component(hass, DOMAIN, {})
        assert mock_request.call_count == 5
    await hass.async_block_till_done()

    return mock_entry
