"""Test the youless config flow."""
from unittest.mock import MagicMock, patch
from urllib.error import URLError

from homeassistant import config_entries
from homeassistant.components.youless import DOMAIN
from homeassistant.data_entry_flow import RESULT_TYPE_FORM


def _get_mock_youless_api(initialize=None):
    mock_youless = MagicMock()
    if isinstance(initialize, Exception):
        type(mock_youless).initialize = MagicMock(side_effect=initialize)
    else:
        type(mock_youless).initialize = MagicMock(return_value=initialize)
    return mock_youless


async def test_full_flow(hass, aiohttp_client, aioclient_mock, current_request):
    """Check setup."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] == {}
    assert result["step_id"] == config_entries.SOURCE_USER

    mock_youless = _get_mock_youless_api(
        initialize={"homes": [{"id": 1, "name": "myhome"}]}
    )
    with patch(
        "homeassistant.components.youless.config_flow.YoulessAPI",
        return_value=mock_youless,
    ) as mock_setup:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"host": "localhost", "name": "YouLess Sensor"},
        )

    assert result2["type"] == "create_entry"
    assert result2["title"] == "YouLess Sensor"
    await hass.async_block_till_done()
    assert len(mock_setup.mock_calls) == 1


async def test_not_found(hass, aiohttp_client, aioclient_mock, current_request):
    """Check setup."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] == {}
    assert result["step_id"] == config_entries.SOURCE_USER

    mock_youless = _get_mock_youless_api(initialize=URLError(""))
    with patch(
        "homeassistant.components.youless.config_flow.YoulessAPI",
        return_value=mock_youless,
    ) as mock_setup:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"host": "localhost", "name": "YouLess Sensor"},
        )

    assert result2["type"] == "form"
    assert len(mock_setup.mock_calls) == 1
