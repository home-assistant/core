"""Fixtures for the Fumis integration tests."""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import MagicMock, patch

from fumis import FumisInfo
import pytest

from homeassistant.components.fumis.const import DOMAIN
from homeassistant.const import CONF_MAC, CONF_PIN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, load_fixture


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title="Clou Duo",
        domain=DOMAIN,
        data={
            CONF_MAC: "AABBCCDDEEFF",
            CONF_PIN: "1234",
        },
        unique_id="aa:bb:cc:dd:ee:ff",
    )


@pytest.fixture
def mock_setup_entry() -> Generator[None]:
    """Mock setting up a config entry."""
    with patch("homeassistant.components.fumis.async_setup_entry", return_value=True):
        yield


@pytest.fixture
def mock_fumis() -> Generator[MagicMock]:
    """Return a mocked Fumis client."""
    with (
        patch(
            "homeassistant.components.fumis.coordinator.Fumis",
            autospec=True,
        ) as fumis_mock,
        patch(
            "homeassistant.components.fumis.config_flow.Fumis",
            new=fumis_mock,
        ),
    ):
        fumis = fumis_mock.return_value
        fumis.update_info.return_value = FumisInfo.from_json(
            load_fixture("info.json", DOMAIN)
        )
        yield fumis


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_fumis: MagicMock,
) -> MockConfigEntry:
    """Set up the Fumis integration for testing."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    return mock_config_entry
