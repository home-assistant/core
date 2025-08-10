"""Test the flo config flow."""

from http import HTTPStatus
import json
import time
from unittest.mock import patch

import pytest

from homeassistant import config_entries
from homeassistant.components.flo.const import DOMAIN
from homeassistant.const import CONTENT_TYPE_JSON
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .common import TEST_EMAIL_ADDRESS, TEST_PASSWORD, TEST_TOKEN, TEST_USER_ID

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
    """Test we handle cannot connect error."""
    now = round(time.time())
    # Mocks a failed login response for flo.
    aioclient_mock.post(
        "https://api.meetflo.com/api/v1/users/auth",
        json=json.dumps(
            {
                "token": TEST_TOKEN,
                "tokenPayload": {
                    "user": {"user_id": TEST_USER_ID, "email": TEST_EMAIL_ADDRESS},
                    "timestamp": now,
                },
                "tokenExpiration": 86400,
                "timeNow": now,
            }
        ),
        headers={"Content-Type": CONTENT_TYPE_JSON},
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
