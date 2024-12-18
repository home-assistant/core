"""Fixtures for the Peblar integration tests."""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import MagicMock, patch

from peblar.models import PeblarSystemInformation
import pytest

from homeassistant.components.peblar.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PASSWORD

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
    with patch(
        "homeassistant.components.peblar.config_flow.Peblar", autospec=True
    ) as peblar_mock:
        peblar = peblar_mock.return_value
        peblar.system_information.return_value = PeblarSystemInformation.from_json(
            load_fixture("system_information.json", DOMAIN)
        )
        yield peblar
