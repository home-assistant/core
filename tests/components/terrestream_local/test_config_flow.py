"""Test physical pairing and duplicate prevention."""

from unittest.mock import AsyncMock, patch

import pytest
from terrestream_local.errors import AuthenticationError, ClientError

from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import CREDENTIALS, UUID

from tests.common import MockConfigEntry


async def test_user_form(hass: HomeAssistant) -> None:
    """Show a pairing form without contacting the sensor."""
    result = await hass.config_entries.flow.async_init(
        "terrestream_local", context={"source": "user"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}


async def test_pairing(hass: HomeAssistant) -> None:
    """Persist authenticated identity and preserve leading zeros."""
    with (
        patch(
            "homeassistant.components.terrestream_local.config_flow.pair_device",
            return_value=(CREDENTIALS, AsyncMock()),
        ) as pair,
        patch(
            "homeassistant.components.terrestream_local.async_setup_entry",
            return_value=True,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            "terrestream_local",
            context={"source": "user"},
            data={"host": "sensor.local", "code": "00123456"},
        )
        await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == UUID
    assert result["data"]["credentials"]["fingerprint"] == CREDENTIALS.fingerprint
    assert pair.call_args.args[2] == "00123456"


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        pytest.param(AuthenticationError("invalid"), "invalid_auth", id="wrong-code"),
        pytest.param(ClientError("offline"), "cannot_connect", id="offline"),
        pytest.param(ValueError("host"), "cannot_connect", id="invalid-address"),
    ],
)
async def test_pairing_error(
    hass: HomeAssistant, error: Exception, expected: str
) -> None:
    """Keep pairing failures recoverable in the form."""
    with patch(
        "homeassistant.components.terrestream_local.config_flow.pair_device",
        side_effect=error,
    ):
        result = await hass.config_entries.flow.async_init(
            "terrestream_local",
            context={"source": "user"},
            data={"host": "sensor.local", "code": "00123456"},
        )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected}


async def test_duplicate(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Do not create two entries for the same authenticated UUID."""
    with patch(
        "homeassistant.components.terrestream_local.config_flow.pair_device",
        return_value=(CREDENTIALS, AsyncMock()),
    ):
        result = await hass.config_entries.flow.async_init(
            "terrestream_local",
            context={"source": "user"},
            data={"host": "sensor.local", "code": "00123456"},
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
