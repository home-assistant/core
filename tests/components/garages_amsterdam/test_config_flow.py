"""Test the Garages Amsterdam config flow."""
from unittest.mock import patch

from aiohttp import ClientResponseError
import pytest

from homeassistant import config_entries, setup
from homeassistant.components.garages_amsterdam.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import (
    RESULT_TYPE_ABORT,
    RESULT_TYPE_CREATE_ENTRY,
    RESULT_TYPE_FORM,
)


async def test_full_flow(hass: HomeAssistant) -> None:
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result.get("type") == RESULT_TYPE_FORM
    assert "flow_id" in result

    with patch(
        "homeassistant.components.garages_amsterdam.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"garage_name": "IJDok"},
        )
        await hass.async_block_till_done()

    assert result2.get("type") == RESULT_TYPE_CREATE_ENTRY
    assert result2.get("title") == "IJDok"
    assert "result" in result2
    assert result2["result"].unique_id == "IJDok"
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    "side_effect,reason",
    [
        (RuntimeError, "unknown"),
        (ClientResponseError(None, None, status=500), "cannot_connect"),
    ],
)
async def test_error_handling(
    side_effect: Exception, reason: str, hass: HomeAssistant
) -> None:
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})

    with patch(
        "homeassistant.components.garages_amsterdam.config_flow.garages_amsterdam.get_garages",
        side_effect=side_effect,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
    assert result.get("type") == RESULT_TYPE_ABORT
    assert result.get("reason") == reason
