"""Common fixtures for the Ubiquiti airOS tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

from airos.airos8 import AirOSData
import pytest

from homeassistant.components.airos.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME

from tests.common import MockConfigEntry, load_json_object_fixture


@pytest.fixture
def ap_fixture():
    """Load fixture data for AP mode."""
    json_data = load_json_object_fixture("ap-ptp.json", DOMAIN)
    return AirOSData.from_dict(json_data)


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.airos.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_airos_client(
    request: pytest.FixtureRequest, ap_fixture: AirOSData
) -> Generator[AsyncMock]:
    """Fixture to mock the AirOS API client."""
    mock_airos = AsyncMock()
    mock_airos.status.return_value = ap_fixture

    if hasattr(request, "param"):
        mock_airos.login.side_effect = request.param
    else:
        mock_airos.login.return_value = True

    with (
        patch(
            "homeassistant.components.airos.config_flow.AirOS", return_value=mock_airos
        ),
        patch(
            "homeassistant.components.airos.coordinator.AirOS", return_value=mock_airos
        ),
        patch("homeassistant.components.airos.AirOS", return_value=mock_airos),
    ):
        yield mock_airos


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
        unique_id="device0123",
    )
