"""Common fixtures and mocks for myplink tests."""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.myuplink.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, load_json_value_fixture


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title="MyUplink Setup",
        domain=DOMAIN,
        data={},
    )


@pytest.fixture
def mock_myuplink(request: pytest.FixtureRequest) -> Generator[None, MagicMock, None]:
    """Return a mocked myuplink client."""

    with patch(
        "homeassistant.components.myuplink.MyUplinkAPI", autospec=True
    ) as myuplink_mock:
        myuplink = myuplink_mock.return_value
        myuplink.async_get_systems_json.return_value = load_json_value_fixture(
            "systems.json", DOMAIN
        )
        myuplink.async_get_device_json.return_value = load_json_value_fixture(
            "device.json", DOMAIN
        )
        myuplink.async_get_device_points_json.return_value = load_json_value_fixture(
            "device_points_nibe_f730.json", DOMAIN
        )

        yield myuplink


@pytest.fixture
async def init_integration(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_myuplink: MagicMock
) -> MockConfigEntry:
    """Set up the myuplink integration for testing."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.helpers.config_entry_oauth2_flow.async_get_config_entry_implementation"
    ):
        assert await async_setup_component(hass, "myuplink", {})
        await hass.async_block_till_done()

    return mock_config_entry
