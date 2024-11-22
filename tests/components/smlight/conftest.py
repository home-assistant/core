"""Common fixtures for the SMLIGHT Zigbee tests."""

from collections.abc import AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock, patch

from pysmlight.sse import sseClient
from pysmlight.web import CmdWrapper, Firmware, Info, Sensors
import pytest

from homeassistant.components.smlight import PLATFORMS
from homeassistant.components.smlight.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant

from tests.common import (
    MockConfigEntry,
    load_json_array_fixture,
    load_json_object_fixture,
)

MOCK_HOST = "slzb-06.local"
MOCK_USERNAME = "test-user"
MOCK_PASSWORD = "test-pass"


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: MOCK_HOST,
            CONF_USERNAME: MOCK_USERNAME,
            CONF_PASSWORD: MOCK_PASSWORD,
        },
        unique_id="aa:bb:cc:dd:ee:ff",
    )


@pytest.fixture
def mock_config_entry_host() -> MockConfigEntry:
    """Return the default mocked config entry, no credentials."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: MOCK_HOST,
        },
        unique_id="aa:bb:cc:dd:ee:ff",
    )


@pytest.fixture
def platforms() -> list[Platform]:
    """Platforms, which should be loaded during the test."""
    return PLATFORMS


@pytest.fixture(autouse=True)
async def mock_patch_platforms(platforms: list[str]) -> AsyncGenerator[None]:
    """Fixture to set up platforms for tests."""
    with patch(f"homeassistant.components.{DOMAIN}.PLATFORMS", platforms):
        yield


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.smlight.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_smlight_client(request: pytest.FixtureRequest) -> Generator[MagicMock]:
    """Mock the SMLIGHT API client."""
    with (
        patch("homeassistant.components.smlight.Api2", autospec=True) as smlight_mock,
        patch("homeassistant.components.smlight.config_flow.Api2", new=smlight_mock),
    ):
        api = smlight_mock.return_value
        api.host = MOCK_HOST
        api.get_info.return_value = Info.from_dict(
            load_json_object_fixture("info.json", DOMAIN)
        )
        api.get_sensors.return_value = Sensors.from_dict(
            load_json_object_fixture("sensors.json", DOMAIN)
        )

        def get_firmware_side_effect(*args, **kwargs) -> list[Firmware]:
            """Return the firmware version."""
            fw_list = []
            if kwargs.get("mode") == "zigbee":
                fw_list = load_json_array_fixture("zb_firmware.json", DOMAIN)
            else:
                fw_list = load_json_array_fixture("esp_firmware.json", DOMAIN)

            return [Firmware.from_dict(fw) for fw in fw_list]

        api.get_firmware_version.side_effect = get_firmware_side_effect

        api.check_auth_needed.return_value = False
        api.authenticate.return_value = True

        api.cmds = AsyncMock(spec_set=CmdWrapper)
        api.set_toggle = AsyncMock()
        api.sse = MagicMock(spec_set=sseClient)

        yield api


async def setup_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> MockConfigEntry:
    """Set up the integration."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    return mock_config_entry
