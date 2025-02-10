"""Test the Enigma2 config flow."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

from openwebif.api import OpenWebIfDevice, OpenWebIfServiceEvent, OpenWebIfStatus
import pytest

from homeassistant.components.enigma2.const import (
    CONF_DEEP_STANDBY,
    CONF_SOURCE_BOUQUET,
    CONF_USE_CHANNEL_ICON,
    DEFAULT_DEEP_STANDBY,
    DEFAULT_PORT,
    DEFAULT_SSL,
    DEFAULT_VERIFY_SSL,
    DOMAIN,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)

from tests.common import MockConfigEntry, load_json_object_fixture

MAC_ADDRESS = "12:34:56:78:90:ab"

TEST_REQUIRED = {
    CONF_HOST: "1.1.1.1",
    CONF_PORT: DEFAULT_PORT,
    CONF_SSL: DEFAULT_SSL,
    CONF_VERIFY_SSL: DEFAULT_VERIFY_SSL,
}

TEST_FULL = {
    CONF_HOST: "1.1.1.1",
    CONF_PORT: DEFAULT_PORT,
    CONF_SSL: DEFAULT_SSL,
    CONF_USERNAME: "root",
    CONF_PASSWORD: "password",
    CONF_VERIFY_SSL: DEFAULT_VERIFY_SSL,
}

EXPECTED_OPTIONS = {
    CONF_DEEP_STANDBY: DEFAULT_DEEP_STANDBY,
    CONF_SOURCE_BOUQUET: "Favourites",
    CONF_USE_CHANNEL_ICON: False,
}


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        domain=DOMAIN, data=TEST_REQUIRED, unique_id="12:34:56:78:90:ab"
    )


@pytest.fixture
def openwebif_device_mock() -> Generator[AsyncMock]:
    """Mock a OpenWebIf device."""

    with (
        patch(
            "homeassistant.components.enigma2.coordinator.OpenWebIfDevice",
            spec=OpenWebIfDevice,
        ) as openwebif_device_mock,
        patch(
            "homeassistant.components.enigma2.config_flow.OpenWebIfDevice",
            new=openwebif_device_mock,
        ),
    ):
        device = openwebif_device_mock.return_value
        device.status = OpenWebIfStatus(currservice=OpenWebIfServiceEvent())
        device.turn_off_to_deep = False
        device.sources = {"Test": "1"}
        device.source_list = list(device.sources.keys())
        device.picon_url = "file:///"
        device.get_about.return_value = load_json_object_fixture(
            "device_about.json", DOMAIN
        )
        device.get_status_info.return_value = load_json_object_fixture(
            "device_statusinfo_on.json", DOMAIN
        )
        device.get_all_bouquets.return_value = {
            "bouquets": [
                [
                    '1:7:1:0:0:0:0:0:0:0:FROM BOUQUET "userbouquet.favourites.tv" ORDER BY bouquet',
                    "Favourites (TV)",
                ]
            ]
        }
        yield device
