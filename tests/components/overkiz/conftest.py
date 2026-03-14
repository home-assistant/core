"""Configuration for overkiz tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, Mock, patch

import pytest

from homeassistant.components.overkiz.const import DOMAIN
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from . import DEFAULT_SETUP_FIXTURE, load_setup_fixture
from .test_config_flow import TEST_EMAIL, TEST_GATEWAY_ID, TEST_PASSWORD, TEST_SERVER

from tests.common import MockConfigEntry

MOCK_SETUP_RESPONSE = Mock(devices=[], gateways=[])


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title="Somfy TaHoma Switch",
        domain=DOMAIN,
        unique_id=TEST_GATEWAY_ID,
        data={"username": TEST_EMAIL, "password": TEST_PASSWORD, "hub": TEST_SERVER},
    )


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Mock setting up a config entry."""
    with patch(
        "homeassistant.components.overkiz.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def setup_overkiz_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
):
    """Return a helper to set up the Overkiz integration from a chosen fixture."""

    async def _setup(
        *,
        fixture: str = DEFAULT_SETUP_FIXTURE,
        platforms: list[Platform] | None = None,
    ) -> MockConfigEntry:
        mock_config_entry.add_to_hass(hass)

        setup_context = patch.multiple(
            "pyoverkiz.client.OverkizClient",
            login=AsyncMock(return_value=True),
            get_setup=AsyncMock(return_value=load_setup_fixture(fixture)),
            get_scenarios=AsyncMock(return_value=[]),
            fetch_events=AsyncMock(return_value=[]),
        )

        with setup_context:
            if platforms is None:
                await hass.config_entries.async_setup(mock_config_entry.entry_id)
            else:
                with patch("homeassistant.components.overkiz.PLATFORMS", platforms):
                    await hass.config_entries.async_setup(mock_config_entry.entry_id)

            await hass.async_block_till_done()

        return mock_config_entry

    return _setup


@pytest.fixture
async def init_integration(
    setup_overkiz_integration,
) -> MockConfigEntry:
    """Set up the Overkiz integration for testing."""
    return await setup_overkiz_integration()
