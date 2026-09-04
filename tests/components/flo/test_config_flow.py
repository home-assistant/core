"""Test the flo config flow."""

from http import HTTPStatus
import json
from unittest.mock import AsyncMock, patch

from aioflo.api import SSO_TOKEN_URL
from aioflo.errors import RequestError
import pytest

from homeassistant import config_entries
from homeassistant.components.flo import async_get_flo_api
from homeassistant.components.flo.const import CONF_USE_SSO, DOMAIN
from homeassistant.const import CONTENT_TYPE_JSON
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .common import TEST_PASSWORD, TEST_USER_ID

from tests.test_util.aiohttp import AiohttpClientMocker


@pytest.mark.usefixtures("aioclient_mock_fixture")
async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.flo.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"username": TEST_USER_ID, "password": TEST_PASSWORD}
        )

        assert result2["type"] is FlowResultType.CREATE_ENTRY
        assert result2["title"] == TEST_USER_ID
        assert result2["data"] == {"username": TEST_USER_ID, "password": TEST_PASSWORD}
        await hass.async_block_till_done()
        assert len(mock_setup_entry.mock_calls) == 1


async def test_form_cannot_connect(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test we handle cannot connect error when legacy and SSO both fail."""
    aioclient_mock.post(
        "https://api.meetflo.com/api/v1/users/auth",
        status=HTTPStatus.BAD_REQUEST,
    )
    aioclient_mock.post(
        SSO_TOKEN_URL,
        status=HTTPStatus.BAD_REQUEST,
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"username": "test-username", "password": "test-password"}
    )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_sso_after_legacy_failure(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test config flow falls back to Moen SSO when legacy auth fails."""
    aioclient_mock.post(
        "https://api.meetflo.com/api/v1/users/auth",
        status=HTTPStatus.BAD_REQUEST,
    )
    aioclient_mock.post(
        SSO_TOKEN_URL,
        text=json.dumps(
            {
                "token": {
                    "access_token": "sso-access-token",
                    "refresh_token": "sso-refresh-token",
                    "token_type": "Bearer",
                    "expires_in": 3600,
                }
            }
        ),
        headers={"Content-Type": CONTENT_TYPE_JSON},
        status=HTTPStatus.OK,
    )
    aioclient_mock.get(
        "https://api-gw.meetflo.com/api/v2/users/me",
        text=json.dumps({"id": TEST_USER_ID, "email": "email@address.com"}),
        headers={"Content-Type": CONTENT_TYPE_JSON},
        status=HTTPStatus.OK,
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.flo.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"username": TEST_USER_ID, "password": TEST_PASSWORD}
        )

        assert result2["type"] is FlowResultType.CREATE_ENTRY
        assert result2["data"] == {
            "username": TEST_USER_ID,
            "password": TEST_PASSWORD,
            CONF_USE_SSO: True,
        }
        await hass.async_block_till_done()
        assert len(mock_setup_entry.mock_calls) == 1


async def test_async_get_flo_api_falls_back_to_sso(hass: HomeAssistant) -> None:
    """Test legacy RequestError triggers a SSO retry."""
    client = object()

    with patch(
        "homeassistant.components.flo.async_get_api",
        new_callable=AsyncMock,
        side_effect=[RequestError("legacy failed"), client],
    ) as mock_get_api:
        api, used_sso = await async_get_flo_api(hass, TEST_USER_ID, TEST_PASSWORD)

    assert api is client
    assert used_sso is True
    assert mock_get_api.await_count == 2
    assert mock_get_api.await_args_list[0].kwargs["use_sso"] is False
    assert mock_get_api.await_args_list[1].kwargs["use_sso"] is True


async def test_async_get_flo_api_uses_stored_sso(hass: HomeAssistant) -> None:
    """Test a stored SSO flag skips the legacy attempt."""
    client = object()

    with patch(
        "homeassistant.components.flo.async_get_api",
        new_callable=AsyncMock,
        return_value=client,
    ) as mock_get_api:
        api, used_sso = await async_get_flo_api(
            hass, TEST_USER_ID, TEST_PASSWORD, use_sso=True
        )

    assert api is client
    assert used_sso is True
    assert mock_get_api.await_count == 1
    assert mock_get_api.await_args.kwargs["use_sso"] is True
