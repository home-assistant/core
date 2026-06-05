"""Fixtures for KEBA P40 tests."""

from collections.abc import Generator
import json
from typing import Any
from unittest.mock import AsyncMock, patch

from keba_kecontact_p40 import LoadManagement, Wallbox
import pytest

from homeassistant.components.keba_p40.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT

from tests.common import MockConfigEntry, load_fixture


@pytest.fixture
def mock_wallbox() -> Wallbox:
    """Return a parsed Wallbox from the fixture."""
    data: dict[str, Any] = json.loads(load_fixture("wallbox.json", DOMAIN))
    return Wallbox.from_api(data)


@pytest.fixture
def mock_load_management() -> LoadManagement:
    """Return parsed load management from the fixture."""
    data: dict[str, Any] = json.loads(load_fixture("lmgmt.json", DOMAIN))
    return LoadManagement.from_api(data)


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mocked config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Garage",
        unique_id="21900042",
        data={
            CONF_HOST: "1.2.3.4",
            CONF_PORT: 8443,
            CONF_PASSWORD: "hunter2",
        },
    )


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.keba_p40.async_setup_entry", return_value=True
    ) as mock_setup:
        yield mock_setup


@pytest.fixture
def mock_client(
    mock_wallbox: Wallbox, mock_load_management: LoadManagement
) -> Generator[AsyncMock]:
    """Mock the KebaP40Client used by both the config flow and setup."""
    with (
        patch(
            "homeassistant.components.keba_p40.config_flow.KebaP40Client",
            autospec=True,
        ) as client_class,
        patch(
            "homeassistant.components.keba_p40.KebaP40Client",
            new=client_class,
        ),
    ):
        client = client_class.return_value
        client.login = AsyncMock(return_value=None)
        client.get_wallboxes = AsyncMock(return_value=[mock_wallbox])
        client.get_wallbox = AsyncMock(return_value=mock_wallbox)
        client.get_load_management = AsyncMock(return_value=mock_load_management)
        client.start_charging = AsyncMock()
        client.stop_charging = AsyncMock()
        client.set_phases = AsyncMock()
        client.set_availability = AsyncMock()
        client.lock = AsyncMock()
        client.unlock = AsyncMock()
        client.set_max_current = AsyncMock()
        yield client
