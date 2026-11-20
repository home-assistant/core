"""Test the Yardian config flow."""

from unittest.mock import AsyncMock

import pytest
from pytest_homeassistant.common import MockConfigEntry
from pyyardian import NetworkException, NotAuthorizedException

from homeassistant.components.yardian.const import DOMAIN, PRODUCT_NAME
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.aiohttp_client import async_get_clientsession

pytestmark = pytest.mark.usefixtures("mock_setup_entry", "mock_yardian_client")


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"host": "fake_host", "access_token": "fake_token"},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == PRODUCT_NAME
    assert result["data"] == {
        "host": "fake_host",
        "access_token": "fake_token",
        "name": "fake_name",
        "yid": "fake_yid",
    }
    assert result["result"].unique_id == "fake_yid"


async def test_already_configured(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yardian_client: AsyncMock,
) -> None:
    """Reject a second setup for the same controller at a different host."""
    mock_config_entry.add_to_hass(hass)
    mock_yardian_client.fetch_device_info.return_value = {
        "yid": mock_config_entry.unique_id
    }

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "yardian.example", CONF_ACCESS_TOKEN: "fake_token"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert hass.config_entries.async_entries(DOMAIN) == [mock_config_entry]


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (NotAuthorizedException, "invalid_auth"),
        (NetworkException, "cannot_connect"),
        (TimeoutError, "cannot_connect"),
        (Exception, "unknown"),
    ],
)
async def test_form_errors(
    hass: HomeAssistant,
    mock_yardian_client: AsyncMock,
    exception: type[Exception],
    error: str,
) -> None:
    """Test we handle errors and recover."""
    mock_yardian_client.fetch_device_info.side_effect = exception

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"host": "fake_host", "access_token": "fake_token"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    mock_yardian_client.fetch_device_info.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"host": "fake_host", "access_token": "fake_token"},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.parametrize("token", ["replacement_token", "abc"])
async def test_reauth(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yardian_client: AsyncMock,
    mock_yardian_client_create: AsyncMock,
    mock_setup_entry: AsyncMock,
    token: str,
) -> None:
    """Test reauthentication updates only the token and reloads the same entry."""
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry, title="My garden", options={"test_option": True}
    )
    original_data = dict(mock_config_entry.data)
    mock_yardian_client.fetch_device_info.return_value = {"yid": "yid123"}
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    mock_setup_entry.reset_mock()

    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert not result["errors"]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_ACCESS_TOKEN: token}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert hass.config_entries.async_entries(DOMAIN) == [mock_config_entry]
    assert mock_config_entry.unique_id == "yid123"
    assert mock_config_entry.title == "My garden"
    assert mock_config_entry.options == {"test_option": True}
    assert mock_config_entry.data == original_data | {CONF_ACCESS_TOKEN: token}
    mock_yardian_client_create.assert_awaited_once_with(
        async_get_clientsession(hass),
        original_data[CONF_HOST],
        token=token,
    )
    mock_yardian_client.fetch_device_info.assert_awaited_once()
    mock_setup_entry.assert_awaited_once_with(hass, mock_config_entry)


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        pytest.param(NotAuthorizedException, "invalid_auth", id="auth"),
        pytest.param(NetworkException, "cannot_connect", id="network"),
        pytest.param(TimeoutError, "cannot_connect", id="timeout"),
        pytest.param(Exception, "unknown", id="unexpected"),
    ],
)
@pytest.mark.parametrize("method", ["create", "fetch_device_info"])
async def test_reauth_errors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_yardian_client: AsyncMock,
    mock_yardian_client_create: AsyncMock,
    mock_setup_entry: AsyncMock,
    exception: type[Exception],
    error: str,
    method: str,
) -> None:
    """Test reauthentication errors preserve credentials and allow recovery."""
    mock_config_entry.add_to_hass(hass)
    original_data = dict(mock_config_entry.data)
    failing_method = {
        "create": mock_yardian_client_create,
        "fetch_device_info": mock_yardian_client.fetch_device_info,
    }[method]
    failing_method.side_effect = exception
    result = await mock_config_entry.start_reauth_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_ACCESS_TOKEN: "replacement_token"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == {"base": error}
    assert mock_config_entry.data == original_data
    mock_setup_entry.assert_not_awaited()

    failing_method.side_effect = None
    mock_yardian_client.fetch_device_info.return_value = {"yid": "yid123"}
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_ACCESS_TOKEN: "replacement_token"}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data == original_data | {
        CONF_ACCESS_TOKEN: "replacement_token"
    }
    mock_setup_entry.assert_awaited_once_with(hass, mock_config_entry)


async def test_reauth_wrong_device(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test reauthentication cannot replace the existing Yardian device."""
    mock_config_entry.add_to_hass(hass)
    original_data = dict(mock_config_entry.data)
    result = await mock_config_entry.start_reauth_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_ACCESS_TOKEN: "replacement_token"}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unique_id_mismatch"
    assert mock_config_entry.unique_id == "yid123"
    assert mock_config_entry.data == original_data
    assert hass.config_entries.async_entries(DOMAIN) == [mock_config_entry]
    mock_setup_entry.assert_not_awaited()
