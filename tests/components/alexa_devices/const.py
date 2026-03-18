"""Alexa Devices tests const."""

from aioamazondevices.api import AmazonDevice, AmazonDeviceSensor

TEST_CODE = "023123"
TEST_PASSWORD = "fake_password"
TEST_SERIAL_NUMBER = "echo_test_serial_number"
TEST_USERNAME = "fake_email@gmail.com"

TEST_DEVICE_ID = "echo_test_device_id"

TEST_DEVICE = AmazonDevice(
    account_name="Echo Test",
    capabilities=["AUDIO_PLAYER", "MICROPHONE"],
    device_family="mine",
    device_type="echo",
    device_owner_customer_id="amazon_ower_id",
    device_cluster_members=[TEST_SERIAL_NUMBER],
    online=True,
    serial_number=TEST_SERIAL_NUMBER,
    software_version="echo_test_software_version",
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
