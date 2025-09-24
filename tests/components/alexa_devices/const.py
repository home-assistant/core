"""Alexa Devices tests const."""

from aioamazondevices.api import AmazonDevice, AmazonDeviceSensor

TEST_CODE = "023123"
TEST_PASSWORD = "fake_password"
TEST_USERNAME = "fake_email@gmail.com"

TEST_DEVICE_1_SN = "echo_test_serial_number"
TEST_DEVICE_1_ID = "echo_test_device_id"
TEST_DEVICE_1 = AmazonDevice(
    account_name="Echo Test",
    capabilities=["AUDIO_PLAYER", "MICROPHONE"],
    device_family="mine",
    device_type="echo",
    device_owner_customer_id="amazon_ower_id",
    device_cluster_members=[TEST_DEVICE_1_SN],
    online=True,
    serial_number=TEST_DEVICE_1_SN,
    software_version="echo_test_software_version",
    entity_id="11111111-2222-3333-4444-555555555555",
    endpoint_id="G1234567890123456789012345678A",
    sensors={
        "dnd": AmazonDeviceSensor(name="dnd", value=False, error=False, scale=None),
        "temperature": AmazonDeviceSensor(
            name="temperature", value="22.5", error=False, scale="CELSIUS"
        ),
    },
)

TEST_DEVICE_2_SN = "echo_test_2_serial_number"
TEST_DEVICE_2_ID = "echo_test_2_device_id"
TEST_DEVICE_2 = AmazonDevice(
    account_name="Echo Test 2",
    capabilities=["AUDIO_PLAYER", "MICROPHONE"],
    device_family="mine",
    device_type="echo",
    device_owner_customer_id="amazon_ower_id",
    device_cluster_members=[TEST_DEVICE_2_SN],
    online=True,
    serial_number=TEST_DEVICE_2_SN,
    software_version="echo_test_2_software_version",
    entity_id="11111111-2222-3333-4444-555555555555",
    endpoint_id="G1234567890123456789012345678A",
    sensors={
        "temperature": AmazonDeviceSensor(
            name="temperature", value="22.5", error=False, scale="CELSIUS"
        )
    },
)

TEST_DEVICE_2_SN = "echo_test_2_serial_number"
TEST_DEVICE_2_ID = "echo_test_2_device_id"
TEST_DEVICE_2 = AmazonDevice(
    account_name="Echo Test 2",
    capabilities=["AUDIO_PLAYER", "MICROPHONE"],
    device_family="mine",
    device_type="echo",
    device_owner_customer_id="amazon_ower_id",
    device_cluster_members=[TEST_DEVICE_2_SN],
    online=True,
    serial_number=TEST_DEVICE_2_SN,
    software_version="echo_test_2_software_version",
    do_not_disturb=False,
    response_style=None,
    bluetooth_state=True,
    entity_id="11111111-2222-3333-4444-555555555555",
    appliance_id="G1234567890123456789012345678A",
    sensors={
        "temperature": AmazonDeviceSensor(
            name="temperature", value="22.5", scale="CELSIUS"
        )
    },
)
