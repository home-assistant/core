"""Common test constants for homeassistant_hardware tests."""

from ha_silabs_firmware_client import ChangelogEntry, FirmwareManifest, FirmwareMetadata
from yarl import URL

from homeassistant.util import dt as dt_util

TEST_DOMAIN = "test"
TEST_FIRMWARE_RELEASES_URL = "https://example.org/firmware"
TEST_ZIGBEE_CHANGELOG = (
    ChangelogEntry(
        version="7.4.4.0",
        summary="Some release notes go here",
        notes="- Detailed notes for 7.4.4.0",
    ),
    ChangelogEntry(version="7.3.2.0", summary="Summary for 7.3.2.0", notes=None),
    ChangelogEntry(version="7.3.1.0", summary="Summary for 7.3.1.0", notes=None),
)
TEST_OPENTHREAD_CHANGELOG = (
    ChangelogEntry(
        version="SL-OPENTHREAD/2.4.4.0_GitHub-7074a43e4",
        summary="Summary for 2.4.4.0",
        notes=None,
    ),
    ChangelogEntry(
        version="SL-OPENTHREAD/2.4.2.0_GitHub-a9a2ca8c5",
        summary="Summary for 2.4.2.0",
        notes=None,
    ),
    ChangelogEntry(
        version="SL-OPENTHREAD/2.4.0.0_GitHub-91fa1f455",
        summary="Summary for 2.4.0.0",
        notes=None,
    ),
)
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
            version="7.4.4.0",
            changelog=TEST_ZIGBEE_CHANGELOG,
        ),
        FirmwareMetadata(
            filename="skyconnect_openthread_rcp_test.gbl",
            checksum="bbb",
            size=456,
            release_notes="Summary for 2.4.4.0",
            metadata={
                "baudrate": 460800,
                "fw_type": "openthread_rcp",
                "fw_variant": None,
                "metadata_version": 2,
                "ot_rcp_version": "SL-OPENTHREAD/2.4.4.0_GitHub-7074a43e4",
                "sdk_version": "4.4.4",
            },
            url=URL("https://example.org/firmwares/skyconnect_openthread_rcp_test.gbl"),
            version="SL-OPENTHREAD/2.4.4.0_GitHub-7074a43e4",
            changelog=TEST_OPENTHREAD_CHANGELOG,
        ),
    ),
    changelogs={
        "zigbee_ncp": TEST_ZIGBEE_CHANGELOG,
        "openthread_rcp": TEST_OPENTHREAD_CHANGELOG,
    },
)
