"""Common fixtures for the INDI Allsky tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.indi_allsky.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_SSL, CONF_VERIFY_SSL

from tests.common import MockConfigEntry


@pytest.fixture(autouse=True)
def mock_system_random() -> Generator[None]:
    """Mock random.SystemRandom.getrandbits to produce deterministic camera access tokens."""
    with patch("random.SystemRandom.getrandbits", return_value=123123123123):
        yield


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.indi_allsky.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_indi_allsky_client() -> Generator[AsyncMock]:
    """Mock the third-party aioindiallsky client globally across coordinator and config flow."""
    with (
        patch(
            "homeassistant.components.indi_allsky.coordinator.IndiAllSkyClient",
            autospec=True,
        ) as mock_client,
        patch(
            "homeassistant.components.indi_allsky.config_flow.IndiAllSkyClient",
            new=mock_client,
        ),
    ):
        client_instance = mock_client.return_value
        client_instance.fetch_image = AsyncMock(return_value=b"fake_jpeg_data")
        yield client_instance


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Fixture to cleanly create an INDI Allsky configuration entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="INDI Allsky",
        data={
            CONF_HOST: "127.0.0.1",
            CONF_PORT: 443,
            CONF_SSL: True,
            CONF_VERIFY_SSL: True,
        },
        entry_id="1234567890abcdef1234567890abcdef",
    )
