"""AirGradient tests configuration."""

from collections.abc import Generator
from unittest.mock import patch

from airgradient import Measures
import pytest

from homeassistant.components.airgradient.const import DOMAIN
from homeassistant.const import CONF_HOST

from tests.common import MockConfigEntry, load_fixture
from tests.components.smhi.common import AsyncMock


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock, None, None]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.airgradient.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_airgradient_client() -> Generator[AsyncMock, None, None]:
    """Mock an AirGradient client."""
    with (
        patch(
            "homeassistant.components.airgradient.coordinator.AirGradientClient",
            autospec=True,
        ) as mock_client,
        patch(
            "homeassistant.components.airgradient.config_flow.AirGradientClient",
            new=mock_client,
        ),
    ):
        client = mock_client.return_value
        client.get_current_measures.return_value = Measures.from_json(
            load_fixture("current_measures.json", DOMAIN)
        )
        yield client


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock a config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Airgradient",
        data={CONF_HOST: "10.0.0.131"},
        unique_id="84fce612f5b8",
    )
