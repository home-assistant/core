"""Test the flume config flow."""

from http import HTTPStatus
from unittest.mock import patch

import pytest
import requests.exceptions
from requests_mock.mocker import Mocker

from homeassistant import config_entries
from homeassistant.components.flume.const import DOMAIN
from homeassistant.const import (
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    CONF_PASSWORD,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import DEVICE_LIST, DEVICE_LIST_URL

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("access_token", "device_list")
async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form and can setup from user input."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with (
        patch(
            "homeassistant.components.flume.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "test-password",
                CONF_CLIENT_ID: "client_id",
                CONF_CLIENT_SECRET: "client_secret",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "test-username"
    assert result2["data"] == {
        CONF_USERNAME: "test-username",
        CONF_PASSWORD: "test-password",
        CONF_CLIENT_ID: "client_id",
        CONF_CLIENT_SECRET: "client_secret",
    }
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.usefixtures("access_token")
async def test_form_invalid_auth(hass: HomeAssistant, requests_mock: Mocker) -> None:
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    requests_mock.register_uri(
        "GET",
        DEVICE_LIST_URL,
        status_code=HTTPStatus.UNAUTHORIZED,
        json={"message": "Failure"},
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: "test-username",
            CONF_PASSWORD: "test-password",
            CONF_CLIENT_ID: "client_id",
            CONF_CLIENT_SECRET: "client_secret",
        },
    )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"password": "invalid_auth"}


@pytest.mark.usefixtures("access_token", "device_list_timeout")
async def test_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: "test-username",
            CONF_PASSWORD: "test-password",
            CONF_CLIENT_ID: "client_id",
            CONF_CLIENT_SECRET: "client_secret",
        },
    )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


@pytest.mark.parametrize(  # Remove when translations fixed
    "ignore_translations",
    ["component.flume.config.abort.reauth_successful"],
)
@pytest.mark.usefixtures("access_token")
async def test_reauth(hass: HomeAssistant, requests_mock: Mocker) -> None:
    """Test we can reauth."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_USERNAME: "test@test.org",
            CONF_CLIENT_ID: "client_id",
            CONF_CLIENT_SECRET: "client_secret",
        },
        unique_id="test@test.org",
    )
    entry.add_to_hass(hass)

    result = await entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_PASSWORD: "test-password",
        },
    )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"password": "invalid_auth"}

    requests_mock.register_uri(
        "GET",
        DEVICE_LIST_URL,
        exc=requests.exceptions.ConnectTimeout,
    )

    with (
        patch(
            "homeassistant.components.flume.config_flow.os.path.exists",
            return_value=True,
        ),
        patch("homeassistant.components.flume.config_flow.os.unlink") as mock_unlink,
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {
                CONF_PASSWORD: "test-password",
            },
        )
        # The existing token file was removed
        assert len(mock_unlink.mock_calls) == 1

    assert result3["type"] is FlowResultType.FORM
    assert result3["errors"] == {"base": "cannot_connect"}

    requests_mock.register_uri(
        "GET",
        DEVICE_LIST_URL,
        status_code=HTTPStatus.OK,
        json={
            "data": DEVICE_LIST,
        },
    )

    with (
        patch(
            "homeassistant.components.flume.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result4 = await hass.config_entries.flow.async_configure(
            result3["flow_id"],
            {
                CONF_PASSWORD: "test-password",
            },
        )

    assert mock_setup_entry.called
    assert result4["type"] is FlowResultType.ABORT
    assert result4["reason"] == "reauth_successful"


@pytest.mark.usefixtures("access_token")
async def test_form_no_devices(hass: HomeAssistant, requests_mock: Mocker) -> None:
    """Test a device list response that contains no values will raise an error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    requests_mock.register_uri(
        "GET",
        DEVICE_LIST_URL,
        status_code=HTTPStatus.OK,
        json={"data": []},
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: "test-username",
            CONF_PASSWORD: "test-password",
            CONF_CLIENT_ID: "client_id",
            CONF_CLIENT_SECRET: "client_secret",
        },
    )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}
