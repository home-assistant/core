"""Common methods used across tests for TotalConnect."""
from total_connect_client import TotalConnectClient

from homeassistant.components.totalconnect import DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.setup import async_setup_component

from tests.async_mock import patch
from tests.common import MockConfigEntry

LOCATION_INFO_BASIC_NORMAL = {
    "LocationID": "123456",
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
    "ResultCode": 0,
    "SessionID": 1,
    "Locations": LOCATIONS,
    "ModuleFlags": MODULE_FLAGS,
    "UserInfo": USER,
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

PARTITION_INFO_DISARMED = {0: PARTITION_DISARMED}
PARTITION_INFO_ARMED_STAY = {0: PARTITION_ARMED_STAY}
PARTITION_INFO_ARMED_AWAY = {0: PARTITION_ARMED_AWAY}

PARTITIONS_DISARMED = {"PartitionInfo": PARTITION_INFO_DISARMED}
PARTITIONS_ARMED_STAY = {"PartitionInfo": PARTITION_INFO_ARMED_STAY}
PARTITIONS_ARMED_AWAY = {"PartitionInfo": PARTITION_INFO_ARMED_AWAY}

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

RESPONSE_DISARMED = {"ResultCode": 0, "PanelMetadataAndStatus": METADATA_DISARMED}
RESPONSE_ARMED_STAY = {"ResultCode": 0, "PanelMetadataAndStatus": METADATA_ARMED_STAY}
RESPONSE_ARMED_AWAY = {"ResultCode": 0, "PanelMetadataAndStatus": METADATA_ARMED_AWAY}

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


async def setup_platform(hass, platform):
    """Set up the TotalConnect platform."""
    # first set up a config entry and add it to hass
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_USERNAME: "user@email.com", CONF_PASSWORD: "password"},
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
