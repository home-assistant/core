"""Test the youless config flow."""
from unittest.mock import MagicMock, patch
from urllib.error import URLError

from homeassistant.components.youless import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


def _get_mock_youless_api(initialize=None):
    mock_youless = MagicMock()
    if isinstance(initialize, Exception):
        type(mock_youless).initialize = MagicMock(side_effect=initialize)
    else:
        type(mock_youless).initialize = MagicMock(return_value=initialize)

    type(mock_youless).mac_address = None
    return mock_youless


async def test_full_flow(hass: HomeAssistant) -> None:
    """Check setup."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result.get("type") == FlowResultType.FORM
    assert result.get("errors") == {}
    assert result.get("step_id") == SOURCE_USER

    mock_youless = _get_mock_youless_api(
        initialize={"homes": [{"id": 1, "name": "myhome"}]}
    )
    with patch(
        "homeassistant.components.youless.config_flow.YoulessAPI",
        return_value=mock_youless,
    ) as mocked_youless:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"host": "localhost"},
        )

    assert result2.get("type") == FlowResultType.CREATE_ENTRY
    assert result2.get("title") == "localhost"
    assert len(mocked_youless.mock_calls) == 1


async def test_not_found(hass: HomeAssistant) -> None:
    """Check setup."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result.get("type") == FlowResultType.FORM
    assert result.get("errors") == {}
    assert result.get("step_id") == SOURCE_USER

    mock_youless = _get_mock_youless_api(initialize=URLError(""))
    with patch(
        "homeassistant.components.youless.config_flow.YoulessAPI",
        return_value=mock_youless,
    ) as mocked_youless:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"host": "localhost"},
        )

    assert result2.get("type") == FlowResultType.FORM
    assert len(mocked_youless.mock_calls) == 1
