"""Fixtures for the Peblar integration tests."""

from __future__ import annotations

from collections.abc import Generator
from contextlib import nullcontext
from unittest.mock import MagicMock, patch

from peblar import (
    PeblarEVInterface,
    PeblarMeter,
    PeblarSystem,
    PeblarSystemInformation,
    PeblarUserConfiguration,
    PeblarVersions,
)
import pytest

from homeassistant.components.peblar.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PASSWORD
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, load_fixture


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title="Peblar",
        domain=DOMAIN,
        data={
            CONF_HOST: "127.0.0.127",
            CONF_PASSWORD: "OMGSPIDERS",
        },
        unique_id="23-45-A4O-MOF",
    )


@pytest.fixture
def mock_setup_entry() -> Generator[None]:
    """Mock setting up a config entry."""
    with patch("homeassistant.components.peblar.async_setup_entry", return_value=True):
        yield


@pytest.fixture
def mock_peblar() -> Generator[MagicMock]:
    """Return a mocked Peblar client."""
    with (
        patch("homeassistant.components.peblar.Peblar", autospec=True) as peblar_mock,
        patch("homeassistant.components.peblar.config_flow.Peblar", new=peblar_mock),
    ):
        peblar = peblar_mock.return_value
        peblar.available_versions.return_value = PeblarVersions.from_json(
            load_fixture("available_versions.json", DOMAIN)
        )
        peblar.current_versions.return_value = PeblarVersions.from_json(
            load_fixture("current_versions.json", DOMAIN)
        )
        peblar.user_configuration.return_value = PeblarUserConfiguration.from_json(
            load_fixture("user_configuration.json", DOMAIN)
        )
        peblar.system_information.return_value = PeblarSystemInformation.from_json(
            load_fixture("system_information.json", DOMAIN)
        )

        api = peblar.rest_api.return_value
        api.ev_interface.return_value = PeblarEVInterface.from_json(
            load_fixture("ev_interface.json", DOMAIN)
        )
        api.meter.return_value = PeblarMeter.from_json(
            load_fixture("meter.json", DOMAIN)
        )
        api.system.return_value = PeblarSystem.from_json(
            load_fixture("system.json", DOMAIN)
        )

        yield peblar


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_peblar: MagicMock,
    request: pytest.FixtureRequest,
) -> MockConfigEntry:
    """Set up the Peblar integration for testing."""
    mock_config_entry.add_to_hass(hass)

    context = nullcontext()
    if platform := getattr(request, "param", None):
        context = patch("homeassistant.components.peblar.PLATFORMS", [platform])

    with context:
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    return mock_config_entry
