"""Tests for the eGauge config flow."""

from unittest.mock import MagicMock

from egauge_async.json.client import EgaugeAuthenticationError
from httpx import ConnectError
import pytest

from homeassistant.components.egauge.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


@pytest.fixture
def mock_setup_entry():
    """Mock setting up a config entry."""
    with pytest.mock.patch(
        "homeassistant.components.egauge.async_setup_entry", return_value=True
    ):
        yield


@pytest.mark.usefixtures("mock_egauge_client")
async def test_user_flow(hass: HomeAssistant) -> None:
    """Test the full happy path user flow from start to finish."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_HOST: "http://192.168.1.100",
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "secret",
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "eGauge"
    assert result["data"] == {
        CONF_HOST: "http://192.168.1.100",
        CONF_USERNAME: "admin",
        CONF_PASSWORD: "secret",
    }
    assert result["result"].unique_id == "ABC123456"


@pytest.mark.parametrize(
    ("side_effect", "expected_error"),
    [
        (EgaugeAuthenticationError, "invalid_auth"),
        (ConnectError, "cannot_connect"),
        (Exception, "unknown"),
    ],
)
async def test_user_flow_errors(
    hass: HomeAssistant,
    mock_egauge_client: MagicMock,
    side_effect: Exception,
    expected_error: str,
) -> None:
    """Test user flow with various errors."""
    mock_egauge_client.get_device_serial_number.side_effect = side_effect

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={
            CONF_HOST: "http://192.168.1.100",
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "wrong",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": expected_error}

    # Test recovery after error
    mock_egauge_client.get_device_serial_number.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_HOST: "http://192.168.1.100",
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "secret",
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("mock_egauge_client")
async def test_user_flow_already_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test configuration flow aborts when device is already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={
            CONF_HOST: "http://192.168.1.200",
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "secret",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("mock_egauge_client")
async def test_reauth_flow(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test reauthentication flow."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "newsecret",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data == {
        CONF_HOST: "http://192.168.1.100",
        CONF_USERNAME: "admin",
        CONF_PASSWORD: "newsecret",
    }


@pytest.mark.parametrize(
    ("side_effect", "expected_error"),
    [
        (EgaugeAuthenticationError, "invalid_auth"),
        (ConnectError, "cannot_connect"),
        (Exception, "unknown"),
    ],
)
async def test_reauth_flow_errors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_egauge_client: MagicMock,
    side_effect: Exception,
    expected_error: str,
) -> None:
    """Test reauthentication flow with errors."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)

    mock_egauge_client.get_device_serial_number.side_effect = side_effect

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "wrong",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == {"base": expected_error}
