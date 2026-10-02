"""Alexa Devices tests const."""

from datetime import UTC, datetime

from aioamazondevices.const.devices import DEVICE_TYPE_AQM
from aioamazondevices.const.schedules import (
    NOTIFICATION_ALARM,
    NOTIFICATION_REMINDER,
    NOTIFICATION_TIMER,
)
from aioamazondevices.structures import (
    AmazonDevice,
    AmazonDeviceSensor,
    AmazonSchedule,
    AmazonVocalRecord,
)

TEST_CODE = "023123"
TEST_PASSWORD = "fake_password"
TEST_USERNAME = "fake_email@gmail.com"
TEST_USER_ID = "amzn1.account.fake_user_id"

TEST_DEVICE_1_SN = "echo_test_serial_number"
TEST_DEVICE_1_ID = "echo_test_device_id"
TEST_DEVICE_1 = AmazonDevice(
    account_name="Echo Test",
    capabilities=["AUDIO_PLAYER", "MICROPHONE", "ALEXA_DEVICE_REBOOT"],
    device_family="mine",
    device_type="echo",
    household_device=False,
    device_owner_customer_id="amazon_ower_id",
    device_cluster_members={TEST_DEVICE_1_SN: TEST_DEVICE_1_ID},
    parent_clusters={},
    online=True,
    serial_number=TEST_DEVICE_1_SN,
    manufacturer="Test manufacturer",
    model="Test model",
    hardware_version="1.0",
    software_version="echo_test_software_version",
    entity_id="11111111-2222-3333-4444-555555555555",
    endpoint_id="G1234567890123456789012345678A",
    sensors={
        "dnd": AmazonDeviceSensor(
            name="dnd",
            value=False,
            error=False,
            error_msg=None,
            error_type=None,
            scale=None,
        ),
        "temperature": AmazonDeviceSensor(
            name="temperature",
            value="22.5",
            error=False,
            error_msg=None,
            error_type=None,
            scale="CELSIUS",
        ),
    },
    notifications_supported=True,
    notifications={
        NOTIFICATION_ALARM: AmazonSchedule(
            type=NOTIFICATION_ALARM,
            status="ON",
            label="Morning Alarm",
            next_occurrence=datetime(2023, 10, 1, 7, 0, 0, tzinfo=UTC),
        ),
        NOTIFICATION_REMINDER: AmazonSchedule(
            type=NOTIFICATION_REMINDER,
            status="ON",
            label="Take out the trash",
            next_occurrence=None,
        ),
        NOTIFICATION_TIMER: AmazonSchedule(
            type=NOTIFICATION_TIMER,
            status="OFF",
            label="",
            next_occurrence=None,
        ),
    },
    media_player_supported=True,
    communication_settings={
        "announcements": "ON",
        "communications": "ON",
        "dropin": "All",
    },
    voice_control_supported=True,
)

TEST_DEVICE_2_SN = "echo_test_2_serial_number"
TEST_DEVICE_2 = AmazonDevice(
    account_name="Echo Test 2",
    capabilities=["AUDIO_PLAYER", "MICROPHONE", "ALEXA_DEVICE_REBOOT"],
    device_family="mine",
    device_type="echo",
    household_device=True,
    device_owner_customer_id="amazon_ower_id",
    device_cluster_members={TEST_DEVICE_2_SN: "echo_test_2_device_id"},
    parent_clusters={},
    online=True,
    serial_number=TEST_DEVICE_2_SN,
    manufacturer="Test manufacturer 2",
    model="Test model 2",
    hardware_version="2.0",
    software_version="echo_test_2_software_version",
    entity_id="11111111-2222-3333-4444-555555555555",
    endpoint_id="G1234567890123456789012345678A",
    sensors={
        "temperature": AmazonDeviceSensor(
            name="temperature",
            value="22.5",
            error=False,
            error_msg=None,
            error_type=None,
            scale="CELSIUS",
        )
    },
    notifications_supported=False,
    notifications={},
    media_player_supported=False,
    communication_settings={},
    voice_control_supported=True,
)

TEST_DEVICE_AQM_SN = "aqm_test_serial_number"
TEST_DEVICE_AQM = AmazonDevice(
    account_name="Air Quality Monitor Test",
    # Air Quality Monitors are discovered via a separate GraphQL endpoint and
    # never expose voice, media or notification capabilities.
    capabilities=[],
    device_family="AIR_QUALITY_MONITOR",
    device_type=DEVICE_TYPE_AQM,
    household_device=False,
    device_owner_customer_id="amazon_ower_id",
    device_cluster_members={TEST_DEVICE_AQM_SN: DEVICE_TYPE_AQM},
    parent_clusters=[],
    online=True,
    serial_number=TEST_DEVICE_AQM_SN,
    manufacturer="Amazon",
    model="Air Quality Monitor",
    hardware_version=None,
    software_version="aqm_test_software_version",
    entity_id="66666666-7777-8888-9999-000000000000",
    endpoint_id="G1234567890123456789012345678C",
    sensors={
        "Humidity": AmazonDeviceSensor(
            name="Humidity",
            value="45",
            error=False,
            error_msg=None,
            error_type=None,
            scale="%",
        ),
        "VOC": AmazonDeviceSensor(
            name="VOC",
            value="120",
            error=False,
            error_msg=None,
            error_type=None,
            scale=None,
        ),
        "PM25": AmazonDeviceSensor(
            name="PM25",
            value="8",
            error=False,
            error_msg=None,
            error_type=None,
            scale="MicroGramsPerCubicMeter",
        ),
        "PM10": AmazonDeviceSensor(
            name="PM10",
            value="12",
            error=False,
            error_msg=None,
            error_type=None,
            scale="MicroGramsPerCubicMeter",
        ),
        "CO": AmazonDeviceSensor(
            name="CO",
            value="0.5",
            error=False,
            error_msg=None,
            error_type=None,
            scale="ppm",
        ),
        "Air Quality": AmazonDeviceSensor(
            name="Air Quality",
            value="42",
            error=False,
            error_msg=None,
            error_type=None,
            scale=None,
        ),
    },
    notifications_supported=False,
    notifications={},
    media_player_supported=False,
    communication_settings={},
    voice_control_supported=False,
)

TEST_VOCAL_RECORD_INITIAL = AmazonVocalRecord(
    timestamp=1000,
    history_type="WAKE_WORD_UTTERANCE",
    intent="PlayMusicIntent",
    title="Play some music",
    sub_title="Echo Test",
    person_first_name="John",
    person_type="CHILD",
)

TEST_VOCAL_RECORD_EVENT = AmazonVocalRecord(
    timestamp=1234567890,
    history_type="WAKE_WORD_UTTERANCE",
    intent="PlayMusicIntent",
    title="Play some music",
    sub_title="Echo Test",
    person_first_name="Jane",
    person_type="ADULT",
)
