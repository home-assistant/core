"""Tests for Vanderbilt SPC component."""
# from unittest.mock import Mock, PropertyMock, patch
import pytest

from homeassistant import config_entries
from homeassistant.components.spc import DOMAIN, CONF_API_URL, CONF_WS_URL
from homeassistant.data_entry_flow import (
    RESULT_TYPE_CREATE_ENTRY,
    RESULT_TYPE_FORM,
)

from tests.async_mock import AsyncMock, patch


@pytest.fixture
def mock_client():
    """Mock API client."""
    with patch("homeassistant.components.spc.config_flow.SpcWebGateway") as client:

        def mock_constructor(loop, session, api_url, ws_url, async_callback=None):
            """Fake the client constructor."""
            client.api_url = api_url
            client.ws_url = ws_url
            client.async_callback = async_callback
            return client

        client.side_effect = mock_constructor
        client.async_load_parameters = AsyncMock()
        client.info = {"sn": "123", "variant": "4100", "version": "3.5"}

        yield client


def _create_test_config():
    return {CONF_API_URL: "http://localhost/", CONF_WS_URL: "ws://localhost/"}


async def test_setup_integration(hass, mock_client):
    """Test that the integration can be set up."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}, data=None
    )

    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "user"},
        data=_create_test_config(),
    )

    assert result["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result["data"] == _create_test_config()
    assert result["title"] == "SPC 4100"

    assert mock_client.async_load_parameters.await_count == 1
    assert mock_client.api_url == "http://localhost/"
    assert mock_client.ws_url == "ws://localhost/"


async def test_invalid_user_input(hass, mock_client):
    """Test that the integration can be set up."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}, data=None
    )

    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "user"},
        data={CONF_API_URL: "xxx", CONF_WS_URL: "ws://localhost/"},
    )

    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"]["base"] == "invalid_url"
