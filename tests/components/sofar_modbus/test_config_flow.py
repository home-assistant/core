"""Test the Sofar Inverter Modbus config flow."""

from unittest.mock import AsyncMock, patch

from modbus_connection import ModbusConnectionError
from modbus_connection.mock import MockModbusConnection
import pytest

from homeassistant import config_entries
from homeassistant.components.sofar_modbus.config_flow import (
    SofarUnrecognizedError,
    _async_probe,
)
from homeassistant.components.sofar_modbus.const import (
    CONF_MODBUS_ADDR,
    CONF_READ_EPS,
    DEFAULT_NAME,
    DOMAIN,
)
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import MOCK_MODEL, MOCK_SERIAL, MOCK_USER_INPUT, seed_pv_inverter

from tests.common import MockConfigEntry


async def test_form_user_step(hass: HomeAssistant) -> None:
    """Test the initial user form is displayed with defaults."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}


async def test_user_step_success(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test successful user flow creating a config entry."""
    with patch(
        "homeassistant.components.sofar_modbus.config_flow._async_probe",
        return_value=(MOCK_SERIAL, MOCK_MODEL),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data=MOCK_USER_INPUT,
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == MOCK_MODEL
    assert result["data"] == MOCK_USER_INPUT
    assert result["result"].unique_id == MOCK_SERIAL
    assert len(mock_setup_entry.mock_calls) == 1


async def test_user_step_success_without_model(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test successful flow falls back to the default title when model is None."""
    with patch(
        "homeassistant.components.sofar_modbus.config_flow._async_probe",
        return_value=(MOCK_SERIAL, None),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data=MOCK_USER_INPUT,
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == DEFAULT_NAME
    assert result["data"] == MOCK_USER_INPUT


async def test_user_step_cannot_connect(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test cannot_connect error when the Modbus connection fails, and recovery."""
    with patch(
        "homeassistant.components.sofar_modbus.config_flow._async_probe",
        side_effect=ModbusConnectionError("Connection timed out"),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data=MOCK_USER_INPUT,
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "cannot_connect"}

    with patch(
        "homeassistant.components.sofar_modbus.config_flow._async_probe",
        return_value=(MOCK_SERIAL, MOCK_MODEL),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], MOCK_USER_INPUT
        )

    assert result2["type"] is FlowResultType.CREATE_ENTRY


async def test_user_step_unrecognized_inverter(hass: HomeAssistant) -> None:
    """Test unrecognized_inverter error when the serial matches no known model."""
    with patch(
        "homeassistant.components.sofar_modbus.config_flow._async_probe",
        side_effect=SofarUnrecognizedError("UNKNOWN_SERIAL"),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data=MOCK_USER_INPUT,
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "unrecognized_inverter"}


async def test_user_step_already_configured(hass: HomeAssistant) -> None:
    """Test aborting when the inverter is already configured."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id=MOCK_SERIAL, data=MOCK_USER_INPUT)
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.sofar_modbus.config_flow._async_probe",
        return_value=(MOCK_SERIAL, MOCK_MODEL),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data=MOCK_USER_INPUT,
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_async_probe_real_mock_connection() -> None:
    """Test _async_probe directly against a real MockModbusConnection."""
    mock_conn = MockModbusConnection()
    unit = mock_conn.for_unit(1)
    seed_pv_inverter(unit)

    with patch(
        "homeassistant.components.sofar_modbus.config_flow.build_connection",
        return_value=mock_conn,
    ):
        serial, model = await _async_probe(MOCK_USER_INPUT)

    assert serial == MOCK_SERIAL
    assert model == MOCK_MODEL


async def test_async_probe_unrecognized_serial() -> None:
    """Test _async_probe raises SofarUnrecognizedError on an unseeded/unknown serial."""
    mock_conn = MockModbusConnection()
    mock_conn.for_unit(1)  # unseeded registers -> zeroes

    with (
        patch(
            "homeassistant.components.sofar_modbus.config_flow.build_connection",
            return_value=mock_conn,
        ),
        pytest.raises(SofarUnrecognizedError),
    ):
        await _async_probe(MOCK_USER_INPUT)


async def test_reconfigure_flow_form_and_success(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test the reconfigure flow displays a form and successfully updates the config entry."""
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id=MOCK_SERIAL, data=MOCK_USER_INPUT, title=MOCK_MODEL
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "entry_id": entry.entry_id,
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert result["errors"] == {}

    new_input = {
        CONF_HOST: "192.168.1.222",
        CONF_PORT: 5020,
        CONF_MODBUS_ADDR: 2,
        CONF_READ_EPS: True,
    }
    with patch(
        "homeassistant.components.sofar_modbus.config_flow._async_probe",
        return_value=(MOCK_SERIAL, MOCK_MODEL),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=new_input
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data[CONF_HOST] == "192.168.1.222"
    assert entry.data[CONF_PORT] == 5020
    assert entry.data[CONF_MODBUS_ADDR] == 2
    assert entry.data[CONF_READ_EPS] is True


async def test_reconfigure_flow_cannot_connect(hass: HomeAssistant) -> None:
    """Test reconfigure flow error handling when the Modbus connection fails."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id=MOCK_SERIAL, data=MOCK_USER_INPUT)
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "entry_id": entry.entry_id,
        },
    )

    with patch(
        "homeassistant.components.sofar_modbus.config_flow._async_probe",
        side_effect=ModbusConnectionError("Connection timed out"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_HOST: "10.0.0.1"}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert result["errors"] == {"base": "cannot_connect"}


async def test_reconfigure_flow_unrecognized_inverter(hass: HomeAssistant) -> None:
    """Test reconfigure flow error handling when the inverter serial is unrecognized."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id=MOCK_SERIAL, data=MOCK_USER_INPUT)
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "entry_id": entry.entry_id,
        },
    )

    with patch(
        "homeassistant.components.sofar_modbus.config_flow._async_probe",
        side_effect=SofarUnrecognizedError("UNKNOWN"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_HOST: "192.168.1.100"}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert result["errors"] == {"base": "unrecognized_inverter"}


async def test_reconfigure_flow_different_serial_aborts(hass: HomeAssistant) -> None:
    """Test reconfigure flow aborts when the new host connects to a different inverter."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id=MOCK_SERIAL, data=MOCK_USER_INPUT)
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "entry_id": entry.entry_id,
        },
    )

    with patch(
        "homeassistant.components.sofar_modbus.config_flow._async_probe",
        return_value=("DIFFERENT_SERIAL_123", "HYD-6000-EP"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_HOST: "192.168.1.199"}
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "different_serial"
