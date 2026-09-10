"""Test the De Dietrich config flow."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from unittest.mock import _patch, patch

from modbus_connection import ModbusConnectionError, ModbusTcpParams, ModbusTimeoutError
from modbus_connection.mock import MockModbusConnection, MockModbusUnit
import pytest

from homeassistant import config_entries
from homeassistant.components.de_dietrich.const import DOMAIN
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import MOCK_USER_INPUT, seed_boiler

from tests.common import MockConfigEntry


def _patch_temporary_unit(connection: MockModbusConnection) -> _patch:
    """Stand in for async_get_temporary_unit, handing out a unit on connection."""

    @asynccontextmanager
    async def _get_temporary_unit(
        hass: HomeAssistant, params: ModbusTcpParams, unit_id: int
    ) -> AsyncIterator[MockModbusUnit]:
        yield connection.for_unit(unit_id)

    return patch(
        "homeassistant.components.de_dietrich.config_flow.async_get_temporary_unit",
        side_effect=_get_temporary_unit,
    )


async def test_user_step_shows_form(hass: HomeAssistant) -> None:
    """Test the initial form renders with no errors before any input."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}


@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_step_success(hass: HomeAssistant) -> None:
    """Test the flow detects the base layout and stores connection settings."""
    mock_conn = MockModbusConnection()
    unit = mock_conn.for_unit(10)
    seed_boiler(unit)

    with _patch_temporary_unit(mock_conn):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data=MOCK_USER_INPUT,
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "De Dietrich"
    assert result["data"] == MOCK_USER_INPUT


async def test_user_step_rejects_unknown_device(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test the flow rejects an unknown device type."""
    mock_conn = MockModbusConnection()
    seed_boiler(mock_conn.for_unit(10), 999)

    with _patch_temporary_unit(mock_conn):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data=MOCK_USER_INPUT,
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unsupported_device"}
    assert "raw_type_code=999" in caplog.text
    assert (
        "probe outcomes: ['success', 'success', 'success', 'unsupported'" in caplog.text
    )


@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_step_detects_isystem(
    hass: HomeAssistant,
) -> None:
    """Test iSystem detection survives a failed base-layout probe."""
    mock_conn = MockModbusConnection()
    unit = mock_conn.for_unit(10)
    seed_boiler(unit)
    unit.fail_read(3, ModbusTimeoutError("base probe timeout"))
    unit.fail_read(600, None)
    unit.fail_read(679, None)
    unit.holding.update({600: 100, 679: 12, 680: 30, 681: 2, 682: 10, 683: 9, 684: 25})

    with _patch_temporary_unit(mock_conn):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data=MOCK_USER_INPUT,
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == MOCK_USER_INPUT


@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_step_cannot_connect(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test the user step reports cannot_connect on a dead link, then recovers."""
    mock_conn = MockModbusConnection()
    mock_conn.for_unit(10).fail_requests(ModbusConnectionError("stuck"))

    with _patch_temporary_unit(mock_conn):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data=MOCK_USER_INPUT,
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "cannot_connect"}
    assert result["description_placeholders"] == {
        "error": "Could not identify the Diematic register layout"
    }
    assert "probe outcomes: ['error'" in caplog.text

    working_conn = MockModbusConnection()
    seed_boiler(working_conn.for_unit(10))

    with _patch_temporary_unit(working_conn):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], MOCK_USER_INPUT
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_step_identity_read_fails(hass: HomeAssistant) -> None:
    """Test cannot_connect when neither identity block can be read."""
    mock_conn = MockModbusConnection()
    unit = mock_conn.for_unit(10)
    unit.fail_read(457, ModbusTimeoutError("no identity"))
    unit.fail_read(600, ModbusTimeoutError("no iSystem identity"))
    unit.fail_read(679, ModbusTimeoutError("no iSystem clock"))

    with _patch_temporary_unit(mock_conn):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data=MOCK_USER_INPUT,
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "cannot_connect"}


@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_step_unknown_error(hass: HomeAssistant) -> None:
    """Test unexpected errors are logged and shown as unknown."""
    with patch(
        "homeassistant.components.de_dietrich.config_flow._async_detect",
        side_effect=Exception("boom"),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data=MOCK_USER_INPUT,
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "unknown"}


@pytest.mark.parametrize(
    "host",
    [
        pytest.param("boiler.local", id="same_connection"),
        pytest.param("BOILER.LOCAL", id="host_case"),
    ],
)
async def test_user_step_already_configured(hass: HomeAssistant, host: str) -> None:
    """Test duplicates are rejected without connecting to the boiler."""
    entry = MockConfigEntry(
        domain=DOMAIN, data={**MOCK_USER_INPUT, CONF_HOST: "boiler.local"}
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.de_dietrich.config_flow.async_get_temporary_unit",
        side_effect=ModbusConnectionError("offline"),
    ) as mock_get_unit:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={**MOCK_USER_INPUT, CONF_HOST: host},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    mock_get_unit.assert_not_called()
