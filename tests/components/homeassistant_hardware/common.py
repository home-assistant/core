"""Common test constants for homeassistant_hardware tests."""

from ha_silabs_firmware_client import FirmwareManifest, FirmwareMetadata
from yarl import URL

from homeassistant.util import dt as dt_util

TEST_DOMAIN = "test"
TEST_FIRMWARE_RELEASES_URL = "https://example.org/firmware"
TEST_MANIFEST = FirmwareManifest(
    url=URL("https://example.org/firmware"),
    html_url=URL("https://example.org/release_notes"),
    created_at=dt_util.utcnow(),
    firmwares=(
        FirmwareMetadata(
            filename="skyconnect_zigbee_ncp_test.gbl",
            checksum="aaa",
            size=123,
            release_notes="Some release notes go here",
            metadata={
                "baudrate": 115200,
                "ezsp_version": "7.4.4.0",
                "fw_type": "zigbee_ncp",
                "fw_variant": None,
                "metadata_version": 2,
                "sdk_version": "4.4.4",
            },
            url=URL("https://example.org/firmwares/skyconnect_zigbee_ncp_test.gbl"),
        ),
    ),
)
