"""Test the JustNimbus config flow."""
from unittest.mock import patch

from justnimbus.exceptions import InvalidClientID, JustNimbusError
import pytest

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.justnimbus.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import FIXTURE_OLD_USER_INPUT, FIXTURE_UNIQUE_ID, FIXTURE_USER_INPUT

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
    ("side_effect", "errors"),
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
            user_input=FIXTURE_USER_INPUT,
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == errors

    await _set_up_justnimbus(hass=hass, flow_id=result["flow_id"])


async def test_abort_already_configured(hass: HomeAssistant) -> None:
    """Test we abort when the device is already configured."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="JustNimbus",
        data=FIXTURE_USER_INPUT,
        unique_id=FIXTURE_UNIQUE_ID,
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result.get("type") == FlowResultType.FORM
    assert result.get("errors") is None

    result2 = await hass.config_entries.flow.async_configure(
        flow_id=result["flow_id"],
        user_input=FIXTURE_USER_INPUT,
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
            user_input=FIXTURE_USER_INPUT,
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "JustNimbus"
    assert result2["data"] == FIXTURE_USER_INPUT
    assert len(mock_setup_entry.mock_calls) == 1


async def test_reauth_flow(hass: HomeAssistant) -> None:
    """Test reauth works."""
    with patch(
        "homeassistant.components.justnimbus.config_flow.justnimbus.JustNimbusClient.get_data",
        return_value=False,
    ):
        mock_config = MockConfigEntry(
            domain=DOMAIN, unique_id=FIXTURE_UNIQUE_ID, data=FIXTURE_OLD_USER_INPUT
        )
        mock_config.add_to_hass(hass)

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={
                "source": config_entries.SOURCE_REAUTH,
                "entry_id": mock_config.entry_id,
            },
            data=FIXTURE_OLD_USER_INPUT,
        )

        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "user"

    with patch(
        "homeassistant.components.justnimbus.config_flow.justnimbus.JustNimbusClient.get_data",
        return_value=True,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            FIXTURE_USER_INPUT,
        )
        await hass.async_block_till_done()

        assert result2["type"] == data_entry_flow.FlowResultType.ABORT
        assert result2["reason"] == "reauth_successful"
        assert mock_config.data == FIXTURE_USER_INPUT
