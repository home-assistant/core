"""Tests for the Epion config flow."""
from unittest.mock import MagicMock, patch

from epion import EpionAuthenticationError, EpionConnectionError
import pytest

from homeassistant import config_entries
from homeassistant.components.epion.const import DOMAIN
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry, load_json_object_fixture

API_KEY = "test-key-123"


async def test_user_flow(hass: HomeAssistant, mock_epion_api_one_device) -> None:
    """Test we can handle a regular successflow setup flow."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.epion.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_KEY: API_KEY},
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Epion integration"
    assert result["data"] == {
        CONF_API_KEY: API_KEY,
    }
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (EpionAuthenticationError("Invalid auth"), "invalid_auth"),
        (EpionConnectionError("Timeout error"), "cannot_connect"),
    ],
)
async def test_form_exceptions(
    hass: HomeAssistant, exception: Exception, error: str
) -> None:
    """Test we can handle Form exceptions."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_epion_api = _get_mock_epion_api(get_current=exception)
    with patch(
        "homeassistant.components.epion.config_flow.Epion",
        return_value=mock_epion_api,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_KEY: API_KEY},
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": error}

    # Test a retry to recover, upon failure
    mock_epion_api = _get_mock_epion_api(
        get_current=load_epion_api_get_current_fixture()
    )

    with patch(
        "homeassistant.components.epion.config_flow.Epion",
        return_value=mock_epion_api,
    ), patch(
        "homeassistant.components.epion.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_KEY: API_KEY},
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Epion integration"
    assert result["data"] == {
        CONF_API_KEY: API_KEY,
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_duplicate_entry(hass: HomeAssistant, mock_epion_api_one_device) -> None:
    """Test duplicate setup handling."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_API_KEY: API_KEY,
        },
        unique_id="account-dupe-123",
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.epion.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_KEY: API_KEY},
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert mock_setup_entry.call_count == 0


@pytest.fixture
def mock_epion_api_one_device():
    """Build a fixture for the Epion API that connects successfully and returns one device."""
    current_one_device_data = load_epion_api_get_current_fixture()
    mock_epion_api = _get_mock_epion_api(get_current=current_one_device_data)
    with patch(
        "homeassistant.components.epion.config_flow.Epion",
        return_value=mock_epion_api,
    ) as mock_epion_api:
        yield mock_epion_api


def load_epion_api_get_current_fixture(
    fixture: str = "epion/get_current_one_device.json",
):
    """Load an Epion API get_current response structure."""
    return load_json_object_fixture(fixture)


def _get_mock_epion_api(get_current=None) -> MagicMock:
    """Get a mock Epion API client."""
    mock_epion_api = MagicMock()
    if isinstance(get_current, Exception):
        type(mock_epion_api).get_current = MagicMock(side_effect=get_current)
    else:
        type(mock_epion_api).get_current = MagicMock(return_value=get_current)
    return mock_epion_api
