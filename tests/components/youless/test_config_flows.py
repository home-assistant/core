"""Test the youless config flow."""
from unittest.mock import patch
from urllib.error import HTTPError

import pytest

from homeassistant import config_entries
from homeassistant.components.youless import DOMAIN
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.data_entry_flow import RESULT_TYPE_CREATE_ENTRY, RESULT_TYPE_FORM

MOCK_CONFIG = {CONF_HOST: "172.0.0.1", CONF_NAME: "Test setup"}


@pytest.fixture(autouse=True)
def mock_dummy_tcp_server():
    """Mock a YouLess device."""

    class Dummy:
        async def start_server(self):
            raise HTTPError

        async def close_server(self):
            pass

    server = Dummy()
    with patch(
        "homeassistant.components.youless.config_flow.YoulessAPI", return_value=server
    ):
        yield server


async def test_full_flow(hass, aiohttp_client, aioclient_mock, current_request):
    """Check setup."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] == {}
    assert result["step_id"] == config_entries.SOURCE_USER

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=MOCK_CONFIG,
    )
    assert result2["type"] == RESULT_TYPE_CREATE_ENTRY
