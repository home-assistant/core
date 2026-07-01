"""Test the NeoPool config flow."""

import importlib
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.neopool.const import DEFAULT_UNIT_ID, DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import MOCK_HOST, MOCK_PORT, MOCK_SERIAL

from tests.common import MockConfigEntry

USER_INPUT = {
    CONF_HOST: MOCK_HOST,
    CONF_PORT: MOCK_PORT,
    "unit_id": DEFAULT_UNIT_ID,
    "modbus_framer": "tcp",
}


async def test_user_flow(
    hass: HomeAssistant,
    mock_neopool_client: MagicMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test a happy-path config flow creates the entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert not result["errors"]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == MOCK_HOST
    assert result["data"][CONF_HOST] == MOCK_HOST
    assert result["data"][CONF_PORT] == MOCK_PORT
    assert result["result"].unique_id == MOCK_SERIAL
    assert mock_setup_entry.call_count == 1


@pytest.mark.parametrize(
    ("exc", "error_key"),
    [
        (
            "homeassistant.components.neopool.config_flow.NeoPoolConnectionError",
            "cannot_connect",
        ),
        (
            "homeassistant.components.neopool.config_flow.NeoPoolTimeoutError",
            "cannot_connect",
        ),
        (
            "homeassistant.components.neopool.config_flow.NeoPoolModbusError",
            "cannot_read_modbus",
        ),
    ],
)
async def test_user_flow_probe_errors_recover(
    hass: HomeAssistant,
    mock_neopool_client: MagicMock,
    mock_setup_entry: AsyncMock,
    exc: str,
    error_key: str,
) -> None:
    """Probe errors surface as form errors, and the flow recovers on retry."""
    exc_cls = _resolve(exc)

    with patch(
        "homeassistant.components.neopool.config_flow.async_probe_serial",
        new=AsyncMock(side_effect=exc_cls("boom")),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], USER_INPUT
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_HOST: error_key}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_flow_already_configured(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_neopool_client: MagicMock,
) -> None:
    """Test config flow aborts when the same device is already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


def _resolve(dotted: str) -> type[Exception]:
    """Import an exception class from a dotted path."""
    module_name, _, attr = dotted.rpartition(".")
    module = importlib.import_module(module_name)
    return getattr(module, attr)
