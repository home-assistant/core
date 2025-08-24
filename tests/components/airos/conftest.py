"""Common fixtures for the Ubiquiti airOS tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

from airos.airos8 import AirOS8Data
import pytest

from homeassistant.components.airos.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME

from tests.common import MockConfigEntry, load_json_object_fixture


@pytest.fixture
def ap_fixture():
    """Load fixture data for AP mode."""
    json_data = load_json_object_fixture("airos_loco5ac_ap-ptp.json", DOMAIN)
    return AirOS8Data.from_dict(json_data)


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.airos.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_airos_class() -> Generator[MagicMock]:
    """Fixture to mock the AirOS class itself."""
    with (
        patch("homeassistant.components.airos.AirOS", autospec=True) as mock_class,
        patch("homeassistant.components.airos.config_flow.AirOS", new=mock_class),
        patch("homeassistant.components.airos.coordinator.AirOS", new=mock_class),
    ):
        yield mock_class


@pytest.fixture
def mock_airos_client(
    request: pytest.FixtureRequest, ap_fixture: AirOS8Data
) -> Generator[AsyncMock]:
    """Fixture to mock the AirOS API client."""
    with (
        patch(
            "homeassistant.components.airos.config_flow.AirOS8", autospec=True
        ) as mock_airos,
        patch("homeassistant.components.airos.coordinator.AirOS8", new=mock_airos),
        patch("homeassistant.components.airos.AirOS8", new=mock_airos),
    ):
        client = mock_airos.return_value
        client.status.return_value = ap_fixture
        client.login.return_value = True
        yield client


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the AirOS mocked config entry."""
    return MockConfigEntry(
        title="NanoStation",
        domain=DOMAIN,
        data={
            CONF_HOST: "1.1.1.1",
            CONF_PASSWORD: "test-password",
            CONF_USERNAME: "ubnt",
        },
        unique_id="01:23:45:67:89:AB",
    )
