"""Tests for the eGauge config flow."""

from unittest.mock import AsyncMock, MagicMock, patch

from egauge_async.exceptions import (
    EgaugeAuthenticationError,
    EgaugeException,
    EgaugePermissionError,
)
from egauge_async.json.models import RegisterInfo, RegisterType
from httpx2 import ConnectError
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.egauge.const import CONF_INVERT_REGISTERS, DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


async def test_user_flow(hass: HomeAssistant) -> None:
    """Test the full happy path user flow from start to finish."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_HOST: "192.168.1.100",
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "secret",
            CONF_SSL: True,
            CONF_VERIFY_SSL: False,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "egauge-home"
    assert result["data"] == {
        CONF_HOST: "192.168.1.100",
        CONF_USERNAME: "admin",
        CONF_PASSWORD: "secret",
        CONF_SSL: True,
        CONF_VERIFY_SSL: False,
    }
    assert result["result"].unique_id == "ABC123456"


@pytest.mark.parametrize(
    ("side_effect", "expected_error"),
    [
        (EgaugeAuthenticationError, "invalid_auth"),
        (EgaugePermissionError, "missing_permission"),
        (ConnectError("Connection error"), "cannot_connect"),
        (Exception("Unexpected error"), "unknown"),
    ],
)
async def test_user_flow_errors(
    hass: HomeAssistant,
    mock_egauge_client: MagicMock,
    side_effect: Exception,
    expected_error: str,
) -> None:
    """Test user flow with various errors."""
    mock_egauge_client.get_device_serial_number.side_effect = side_effect

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_HOST: "192.168.1.100",
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "wrong",
            CONF_SSL: True,
            CONF_VERIFY_SSL: False,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": expected_error}

    # Test recovery after error
    mock_egauge_client.get_device_serial_number.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_HOST: "192.168.1.100",
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "secret",
            CONF_SSL: True,
            CONF_VERIFY_SSL: False,
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "egauge-home"
    assert result["data"] == {
        CONF_HOST: "192.168.1.100",
        CONF_USERNAME: "admin",
        CONF_PASSWORD: "secret",
        CONF_SSL: True,
        CONF_VERIFY_SSL: False,
    }
    assert result["result"].unique_id == "ABC123456"


async def test_user_flow_already_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test configuration flow aborts when device is already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_HOST: "http://192.168.1.200",
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "secret",
            CONF_SSL: True,
            CONF_VERIFY_SSL: False,
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reauth_flow(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_egauge_client: MagicMock,
) -> None:
    """Test the reauthentication flow."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_PASSWORD: "new-secret"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data == {
        CONF_HOST: "http://192.168.1.100",
        CONF_USERNAME: "admin",
        CONF_PASSWORD: "new-secret",
        CONF_SSL: True,
        CONF_VERIFY_SSL: False,
    }


@pytest.mark.parametrize(
    ("side_effect", "expected_error"),
    [
        pytest.param(EgaugeAuthenticationError, "invalid_auth", id="invalid_auth"),
        pytest.param(
            EgaugePermissionError, "missing_permission", id="missing_permission"
        ),
        pytest.param(
            ConnectError("Connection error"), "cannot_connect", id="cannot_connect"
        ),
        pytest.param(Exception, "unknown", id="unknown"),
    ],
)
async def test_reauth_flow_errors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_egauge_client: MagicMock,
    side_effect: type[Exception] | Exception,
    expected_error: str,
) -> None:
    """Test reauthentication flow errors and recovery."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)

    mock_egauge_client.get_device_serial_number.side_effect = side_effect
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_PASSWORD: "wrong"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == {"base": expected_error}

    mock_egauge_client.get_device_serial_number.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_PASSWORD: "new-secret"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data[CONF_PASSWORD] == "new-secret"


async def test_reauth_flow_unique_id_mismatch(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_egauge_client: MagicMock,
) -> None:
    """Test reauthentication aborts when connected to a different device."""
    mock_config_entry.add_to_hass(hass)
    mock_egauge_client.get_device_serial_number.return_value = "XYZ987654"

    result = await mock_config_entry.start_reauth_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_PASSWORD: "new-secret"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unique_id_mismatch"
    assert mock_config_entry.data[CONF_PASSWORD] == "secret"


async def test_options_flow_selects_inverted_registers(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    init_integration: MockConfigEntry,
) -> None:
    """Test that the options flow stores the registers to invert."""
    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_INVERT_REGISTERS: ["Grid"]},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert mock_config_entry.options[CONF_INVERT_REGISTERS] == ["Grid"]


async def test_options_flow_aborts_when_not_loaded(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the options flow aborts when the entry has no runtime data yet."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "not_loaded"


async def test_options_flow_offers_only_power_registers(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    init_integration: MockConfigEntry,
) -> None:
    """Test the picker only offers registers whose reading can be inverted."""
    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    select = result["data_schema"].schema[CONF_INVERT_REGISTERS]
    assert select.config["options"] == ["Grid", "Solar"]


async def test_options_flow_ignores_a_register_no_longer_present(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    init_integration: MockConfigEntry,
) -> None:
    """Test a stored register absent from the device is dropped, not re-saved."""
    hass.config_entries.async_update_entry(
        mock_config_entry,
        options={CONF_INVERT_REGISTERS: ["Gone"]},
    )

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    select = result["data_schema"].schema[CONF_INVERT_REGISTERS]
    assert "Gone" not in select.config["options"]

    # Submit without overriding: the saved value is the form's own default.
    # If the stale name were not filtered out of that default, it would be
    # either rejected by the selector or saved here.
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert mock_config_entry.options[CONF_INVERT_REGISTERS] == []


async def test_options_flow_does_not_reuse_the_coordinator_client(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_egauge_client: MagicMock,
    init_integration: MockConfigEntry,
) -> None:
    """Test the picker read does not go through the coordinator's client.

    EgaugeJsonClient memoises its first register list, so a read through the
    coordinator's instance returns the setup-time snapshot. Breaking that
    instance must not break the dialog.
    """
    mock_egauge_client.get_register_info.side_effect = RuntimeError(
        "coordinator client reused"
    )
    flow_client = MagicMock()
    flow_client.get_register_info = AsyncMock(
        return_value={
            "Grid": RegisterInfo(name="Grid", type=RegisterType.POWER, idx=0, did=None)
        }
    )

    with patch(
        "homeassistant.components.egauge.config_flow.EgaugeJsonClient",
        return_value=flow_client,
    ):
        result = await hass.config_entries.options.async_init(
            mock_config_entry.entry_id
        )

    assert result["type"] is FlowResultType.FORM
    select = result["data_schema"].schema[CONF_INVERT_REGISTERS]
    assert select.config["options"] == ["Grid"]


async def test_options_flow_does_not_offer_a_register_without_a_sensor(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_egauge_client: MagicMock,
    init_integration: MockConfigEntry,
) -> None:
    """Test a register added after setup is not offered.

    Sensors are built once from the setup snapshot, so inverting a register
    that arrived later would change nothing until the entry reloads.
    """
    mock_egauge_client.get_register_info.return_value = {
        "Grid": RegisterInfo(name="Grid", type=RegisterType.POWER, idx=0, did=None),
        "Solar": RegisterInfo(name="Solar", type=RegisterType.POWER, idx=1, did=None),
        "Main": RegisterInfo(name="Main", type=RegisterType.POWER, idx=9, did=None),
    }

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    select = result["data_schema"].schema[CONF_INVERT_REGISTERS]
    # Main is on the device but setup built no sensor for it.
    assert select.config["options"] == ["Grid", "Solar"]


@pytest.mark.parametrize(
    ("side_effect", "reason"),
    [
        pytest.param(EgaugeAuthenticationError, "invalid_auth", id="invalid_auth"),
        pytest.param(
            EgaugePermissionError, "missing_permission", id="missing_permission"
        ),
        pytest.param(EgaugeException, "cannot_fetch_registers", id="egauge_error"),
        pytest.param(
            ConnectError("unreachable"), "cannot_fetch_registers", id="cannot_connect"
        ),
    ],
)
async def test_options_flow_aborts_when_the_refresh_fails(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_egauge_client: MagicMock,
    init_integration: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
    side_effect: type[Exception] | Exception,
    reason: str,
) -> None:
    """Test a failed register read aborts with its cause, not cached registers.

    These are expected outcomes the abort message explains, so nothing is
    logged as an exception.
    """
    mock_egauge_client.get_register_info.side_effect = side_effect

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == reason
    assert "Traceback" not in caplog.text


async def test_options_flow_aborts_unknown_on_an_unexpected_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_egauge_client: MagicMock,
    init_integration: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test an unexpected failure is logged and reported, not swallowed."""
    mock_egauge_client.get_register_info.side_effect = ValueError("boom")

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unknown"
    assert "Unexpected exception reading eGauge registers" in caplog.text
