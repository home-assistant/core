"""Tests for the Tank Utility config flow."""

from unittest.mock import MagicMock

import pytest
from pytest_homeassistant.common import MockConfigEntry
import requests

from homeassistant.components.tank_utility.const import DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.const import CONF_DEVICES, CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import MOCK_DEVICE_ID, TEST_EMAIL, TEST_PASSWORD


def _mock_http_error(status_code: int) -> requests.exceptions.HTTPError:
    """Create a mock HTTPError with a response."""
    response = requests.Response()
    response.status_code = status_code
    return requests.exceptions.HTTPError(response=response)


@pytest.mark.usefixtures("mock_get_devices", "mock_setup_entry")
async def test_user_flow_success(
    hass: HomeAssistant,
    mock_get_token: MagicMock,
) -> None:
    """Test successful user configuration flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_EMAIL: " Test@Example.com ",
            CONF_PASSWORD: TEST_PASSWORD,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_EMAIL
    assert result["data"] == {
        CONF_EMAIL: TEST_EMAIL,
        CONF_PASSWORD: TEST_PASSWORD,
        CONF_DEVICES: [MOCK_DEVICE_ID],
    }
    mock_get_token.assert_called_once_with(TEST_EMAIL, TEST_PASSWORD, force=True)


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        pytest.param(
            _mock_http_error(requests.codes.unauthorized),
            "invalid_auth",
            id="invalid_auth",
        ),
        pytest.param(
            requests.exceptions.ConnectTimeout(),
            "cannot_connect",
            id="connect_timeout",
        ),
        pytest.param(
            _mock_http_error(requests.codes.internal_server_error),
            "cannot_connect",
            id="http_500",
        ),
        pytest.param(
            RuntimeError("Unexpected API response"),
            "unknown",
            id="unknown",
        ),
    ],
)
@pytest.mark.usefixtures("mock_get_devices", "mock_setup_entry")
async def test_user_flow_errors(
    hass: HomeAssistant,
    mock_get_token: MagicMock,
    exception: Exception,
    error: str,
) -> None:
    """Test user flow error handling and recovery."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    mock_get_token.side_effect = exception
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_EMAIL: TEST_EMAIL,
            CONF_PASSWORD: TEST_PASSWORD,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": error}

    mock_get_token.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_EMAIL: TEST_EMAIL,
            CONF_PASSWORD: TEST_PASSWORD,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_EMAIL


@pytest.mark.usefixtures("mock_get_token", "mock_get_devices", "mock_setup_entry")
async def test_user_flow_already_configured(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test user flow aborts when email is already configured."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_EMAIL: TEST_EMAIL,
            CONF_PASSWORD: TEST_PASSWORD,
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_import_flow_success(
    hass: HomeAssistant,
    mock_get_token: MagicMock,
) -> None:
    """Test YAML import flow creates config entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={
            CONF_EMAIL: " test@example.com ",
            CONF_PASSWORD: TEST_PASSWORD,
            CONF_DEVICES: [MOCK_DEVICE_ID],
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_EMAIL
    assert result["data"] == {
        CONF_EMAIL: TEST_EMAIL,
        CONF_PASSWORD: TEST_PASSWORD,
        CONF_DEVICES: [MOCK_DEVICE_ID],
    }
    mock_get_token.assert_called_once_with(TEST_EMAIL, TEST_PASSWORD, force=True)


@pytest.mark.usefixtures("mock_get_token", "mock_setup_entry")
async def test_import_flow_already_configured(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test YAML import flow aborts if already configured."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={
            CONF_EMAIL: TEST_EMAIL,
            CONF_PASSWORD: TEST_PASSWORD,
            CONF_DEVICES: [MOCK_DEVICE_ID],
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    ("exception", "reason"),
    [
        pytest.param(
            _mock_http_error(requests.codes.unauthorized),
            "invalid_auth",
            id="invalid_auth",
        ),
        pytest.param(
            requests.exceptions.ConnectTimeout(),
            "cannot_connect",
            id="cannot_connect",
        ),
        pytest.param(
            RuntimeError("Explosion"),
            "unknown",
            id="unknown",
        ),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_import_flow_errors(
    hass: HomeAssistant,
    mock_get_token: MagicMock,
    exception: Exception,
    reason: str,
) -> None:
    """Test YAML import flow aborts with expected reason on failure."""
    mock_get_token.side_effect = exception

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={
            CONF_EMAIL: TEST_EMAIL,
            CONF_PASSWORD: TEST_PASSWORD,
            CONF_DEVICES: [MOCK_DEVICE_ID],
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == reason
