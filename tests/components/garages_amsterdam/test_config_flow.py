"""Test the Garages Amsterdam config flow."""
from http import HTTPStatus
from unittest.mock import patch

from aiohttp import ClientResponseError
import pytest

from homeassistant import config_entries
from homeassistant.components.garages_amsterdam.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


async def test_full_flow(hass: HomeAssistant) -> None:
    """Test we get the form."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result.get("type") == FlowResultType.FORM

    with patch(
        "homeassistant.components.garages_amsterdam.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"garage_name": "IJDok"},
        )
        await hass.async_block_till_done()

    assert result2.get("type") == FlowResultType.CREATE_ENTRY
    assert result2.get("title") == "IJDok"
    assert "result" in result2
    assert result2["result"].unique_id == "IJDok"
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("side_effect", "reason"),
    [
        (RuntimeError, "unknown"),
        (
            ClientResponseError(None, None, status=HTTPStatus.INTERNAL_SERVER_ERROR),
            "cannot_connect",
        ),
    ],
)
async def test_error_handling(
    side_effect: Exception, reason: str, hass: HomeAssistant
) -> None:
    """Test we get the form."""

    with patch(
        "homeassistant.components.garages_amsterdam.config_flow.ODPAmsterdam.all_garages",
        side_effect=side_effect,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
    assert result.get("type") == FlowResultType.ABORT
    assert result.get("reason") == reason
