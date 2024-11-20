"""Common fixtures for the Roth Touchline SL tests."""

from collections.abc import Generator
from typing import NamedTuple
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.touchline_sl.const import DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

from tests.common import MockConfigEntry


class FakeModule(NamedTuple):
    """Fake Module used for unit testing only."""

    name: str
    id: str


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.touchline_sl.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_touchlinesl_client() -> Generator[AsyncMock]:
    """Mock a pytouchlinesl client."""
    with (
        patch(
            "homeassistant.components.touchline_sl.TouchlineSL",
            autospec=True,
        ) as mock_client,
        patch(
            "homeassistant.components.touchline_sl.config_flow.TouchlineSL",
            new=mock_client,
        ),
    ):
        client = mock_client.return_value
        client.user_id.return_value = 12345
        client.modules.return_value = [FakeModule(name="Foobar", id="deadbeef")]
        yield client


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock a config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="TouchlineSL",
        data={
            CONF_USERNAME: "test-username",
            CONF_PASSWORD: "test-password",
        },
        unique_id="12345",
    )
