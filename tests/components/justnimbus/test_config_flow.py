"""Test the JustNimbus config flow."""
from unittest.mock import patch

from justnimbus.exceptions import InvalidClientID, JustNimbusError
import pytest

from homeassistant import config_entries
from homeassistant.components.justnimbus.const import DOMAIN
from homeassistant.const import CONF_CLIENT_ID
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] is None

    await _set_up_justnimbus(hass=hass, flow_id=result["flow_id"])


@pytest.mark.parametrize(
    "side_effect,errors",
    (
        (
            InvalidClientID(client_id="test_id"),
            {"base": "invalid_auth"},
        ),
        (
            JustNimbusError,
            {"base": "cannot_connect"},
        ),
        (
            RuntimeError,
            {"base": "unknown"},
        ),
    ),
)
async def test_form_errors(
    hass: HomeAssistant,
    side_effect: JustNimbusError,
    errors: dict,
) -> None:
    """Test we handle errors."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "justnimbus.JustNimbusClient.get_data",
        side_effect=side_effect,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            flow_id=result["flow_id"],
            user_input={
                CONF_CLIENT_ID: "test_id",
            },
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == errors

    await _set_up_justnimbus(hass=hass, flow_id=result["flow_id"])


async def test_abort_already_configured(hass: HomeAssistant) -> None:
    """Test we abort when the device is already configured."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="JustNimbus",
        data={CONF_CLIENT_ID: "test_id"},
        unique_id="test_id",
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result.get("type") == FlowResultType.FORM
    assert result.get("errors") is None
    assert "flow_id" in result

    result2 = await hass.config_entries.flow.async_configure(
        flow_id=result["flow_id"],
        user_input={
            CONF_CLIENT_ID: "test_id",
        },
    )

    assert result2.get("type") == FlowResultType.ABORT
    assert result2.get("reason") == "already_configured"


async def _set_up_justnimbus(hass: HomeAssistant, flow_id: str) -> None:
    """Reusable successful setup of JustNimbus sensor."""
    with patch("justnimbus.JustNimbusClient.get_data"), patch(
        "homeassistant.components.justnimbus.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            flow_id=flow_id,
            user_input={
                CONF_CLIENT_ID: "test_id",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "JustNimbus"
    assert result2["data"] == {
        CONF_CLIENT_ID: "test_id",
    }
    assert len(mock_setup_entry.mock_calls) == 1
