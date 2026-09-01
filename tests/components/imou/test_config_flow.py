"""Tests for the Imou config flow."""

from unittest.mock import AsyncMock

from pyimouapi.exceptions import (
    ConnectFailedException,
    ImouException,
    InvalidAppIdOrSecretException,
    RequestFailedException,
)
import pytest

from homeassistant.components.imou.const import (
    CONF_API_URL,
    CONF_APP_ID,
    CONF_APP_SECRET,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_DHCP, SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo

from .const import TEST_APP_ID, TEST_APP_SECRET, USER_INPUT

from tests.common import MockConfigEntry

DHCP_DISCOVERY = DhcpServiceInfo(
    ip="127.0.0.1",
    hostname="imou",
    macaddress="1c4d895f7a29",
)

NEW_APP_SECRET = "new_app_secret"


async def test_user_flow_success(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_imou_openapi_client: AsyncMock,
) -> None:
    """Test successful user flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=USER_INPUT,
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Imou"
    assert result["data"] == USER_INPUT
    assert result["result"].unique_id == USER_INPUT[CONF_APP_ID]
    assert len(mock_setup_entry.mock_calls) == 1


async def test_user_flow_duplicate_entry(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_imou_openapi_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test duplicate entry is aborted."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=USER_INPUT,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    ("side_effect", "expected_error"),
    [
        (ConnectFailedException("fail"), "cannot_connect"),
        (RequestFailedException("fail"), "cannot_connect"),
        (InvalidAppIdOrSecretException("fail"), "invalid_auth"),
        (ImouException("fail"), "unknown"),
    ],
)
async def test_user_flow_exception_then_recover(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_imou_openapi_client: AsyncMock,
    side_effect: Exception,
    expected_error: str,
) -> None:
    """Errors map to stable keys; clearing the failure allows completing the flow."""
    mock_imou_openapi_client.async_get_token.side_effect = side_effect

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=USER_INPUT,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert "errors" in result
    assert result["errors"]["base"] == expected_error

    mock_imou_openapi_client.async_get_token.reset_mock(side_effect=True)

    recover = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=USER_INPUT,
    )

    assert recover["type"] is FlowResultType.CREATE_ENTRY
    assert recover["title"] == "Imou"
    assert recover["data"] == USER_INPUT
    assert recover["result"].unique_id == USER_INPUT[CONF_APP_ID]
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize("region", ["sg", "eu", "na", "cn"])
async def test_user_flow_success_per_region(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_imou_openapi_client: AsyncMock,
    region: str,
) -> None:
    """Each supported API region can complete the config flow."""
    user_input = {
        CONF_APP_ID: f"{TEST_APP_ID}_{region}",
        CONF_APP_SECRET: TEST_APP_SECRET,
        CONF_API_URL: region,
    }

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=user_input,
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Imou"
    assert result["data"] == user_input
    assert result["result"].unique_id == user_input[CONF_APP_ID]


async def test_dhcp_discovery_success(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_imou_openapi_client: AsyncMock,
) -> None:
    """DHCP discovery opens the existing user login form and creates an entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_DHCP},
        data=DHCP_DISCOVERY,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=USER_INPUT,
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Imou"
    assert result["data"] == USER_INPUT
    assert result["result"].unique_id == USER_INPUT[CONF_APP_ID]
    assert len(mock_setup_entry.mock_calls) == 1


async def test_dhcp_discovery_aborts_when_already_configured(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Any existing Imou entry suppresses further DHCP discovery."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_DHCP},
        data=DHCP_DISCOVERY,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_dhcp_discovery_aborts_when_user_flow_in_progress(
    hass: HomeAssistant,
) -> None:
    """DHCP discovery does not sit beside an unfinished manual setup."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_DHCP},
        data=DHCP_DISCOVERY,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_in_progress"


async def test_dhcp_discovery_invalid_auth(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_imou_openapi_client: AsyncMock,
) -> None:
    """Bad credentials stay on the user step, then recover to CREATE_ENTRY."""
    mock_imou_openapi_client.async_get_token.side_effect = (
        InvalidAppIdOrSecretException("fail")
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_DHCP},
        data=DHCP_DISCOVERY,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=USER_INPUT,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"]["base"] == "invalid_auth"

    mock_imou_openapi_client.async_get_token.reset_mock(side_effect=True)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=USER_INPUT,
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Imou"
    assert result["data"] == USER_INPUT
    assert result["result"].unique_id == USER_INPUT[CONF_APP_ID]
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.usefixtures("mock_setup_entry")
async def test_reauth_flow_success(
    hass: HomeAssistant,
    mock_imou_openapi_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Reauth updates the App secret and reloads the entry."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_APP_SECRET: NEW_APP_SECRET},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data[CONF_APP_SECRET] == NEW_APP_SECRET
    mock_imou_openapi_client.async_close.assert_awaited_once()


@pytest.mark.parametrize(
    ("side_effect", "expected_error"),
    [
        (ConnectFailedException("fail"), "cannot_connect"),
        (RequestFailedException("fail"), "cannot_connect"),
        (InvalidAppIdOrSecretException("fail"), "invalid_auth"),
        (ImouException("fail"), "unknown"),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_reauth_flow_exception_then_recover(
    hass: HomeAssistant,
    mock_imou_openapi_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    side_effect: Exception,
    expected_error: str,
) -> None:
    """Errors map to stable keys; clearing the failure allows completing reauth."""
    mock_config_entry.add_to_hass(hass)
    mock_imou_openapi_client.async_get_token.side_effect = side_effect

    result = await mock_config_entry.start_reauth_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_APP_SECRET: NEW_APP_SECRET},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"]["base"] == expected_error

    mock_imou_openapi_client.async_get_token.reset_mock(side_effect=True)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_APP_SECRET: NEW_APP_SECRET},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data[CONF_APP_SECRET] == NEW_APP_SECRET
    assert mock_imou_openapi_client.async_close.await_count == 2


@pytest.mark.usefixtures("mock_setup_entry")
async def test_reauth_unique_id_mismatch(
    hass: HomeAssistant,
    mock_imou_openapi_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Reauth aborts when the unique ID does not match the existing entry."""
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(mock_config_entry, unique_id="other-app-id")

    result = await mock_config_entry.start_reauth_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_APP_SECRET: NEW_APP_SECRET},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unique_id_mismatch"
