"""Test the Opentherm Gateway config flow."""
from unittest.mock import patch

from pyotgw.vars import OTGW, OTGW_ABOUT
from serial import SerialException

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.opentherm_gw.const import (
    CONF_FLOOR_TEMP,
    CONF_PRECISION,
    CONF_READ_PRECISION,
    CONF_SET_PRECISION,
    CONF_TEMPORARY_OVRD_MODE,
    DOMAIN,
)
from homeassistant.const import (
    CONF_DEVICE,
    CONF_ID,
    CONF_NAME,
    PRECISION_HALVES,
    PRECISION_TENTHS,
)
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

MINIMAL_STATUS = {OTGW: {OTGW_ABOUT: "OpenTherm Gateway 4.2.5"}}


async def test_form_user(hass: HomeAssistant) -> None:
    """Test we get the form."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.opentherm_gw.async_setup",
        return_value=True,
    ) as mock_setup, patch(
        "homeassistant.components.opentherm_gw.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry, patch(
        "pyotgw.OpenThermGateway.connect", return_value=MINIMAL_STATUS
    ) as mock_pyotgw_connect, patch(
        "pyotgw.OpenThermGateway.disconnect", return_value=None
    ) as mock_pyotgw_disconnect, patch(
        "pyotgw.status.StatusManager._process_updates", return_value=None
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_NAME: "Test Entry 1", CONF_DEVICE: "/dev/ttyUSB0"}
        )
        await hass.async_block_till_done()

    assert result2["type"] == "create_entry"
    assert result2["title"] == "Test Entry 1"
    assert result2["data"] == {
        CONF_NAME: "Test Entry 1",
        CONF_DEVICE: "/dev/ttyUSB0",
        CONF_ID: "test_entry_1",
    }
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1
    assert len(mock_pyotgw_connect.mock_calls) == 1
    assert len(mock_pyotgw_disconnect.mock_calls) == 1


async def test_form_import(hass: HomeAssistant) -> None:
    """Test import from existing config."""

    with patch(
        "homeassistant.components.opentherm_gw.async_setup",
        return_value=True,
    ) as mock_setup, patch(
        "homeassistant.components.opentherm_gw.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry, patch(
        "pyotgw.OpenThermGateway.connect", return_value=MINIMAL_STATUS
    ) as mock_pyotgw_connect, patch(
        "pyotgw.OpenThermGateway.disconnect", return_value=None
    ) as mock_pyotgw_disconnect, patch(
        "pyotgw.status.StatusManager._process_updates", return_value=None
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={CONF_ID: "legacy_gateway", CONF_DEVICE: "/dev/ttyUSB1"},
        )

    assert result["type"] == "create_entry"
    assert result["title"] == "legacy_gateway"
    assert result["data"] == {
        CONF_NAME: "legacy_gateway",
        CONF_DEVICE: "/dev/ttyUSB1",
        CONF_ID: "legacy_gateway",
    }
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1
    assert len(mock_pyotgw_connect.mock_calls) == 1
    assert len(mock_pyotgw_disconnect.mock_calls) == 1


async def test_form_duplicate_entries(hass: HomeAssistant) -> None:
    """Test duplicate device or id errors."""
    flow1 = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    flow2 = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    flow3 = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.opentherm_gw.async_setup",
        return_value=True,
    ) as mock_setup, patch(
        "homeassistant.components.opentherm_gw.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry, patch(
        "pyotgw.OpenThermGateway.connect", return_value=MINIMAL_STATUS
    ) as mock_pyotgw_connect, patch(
        "pyotgw.OpenThermGateway.disconnect", return_value=None
    ) as mock_pyotgw_disconnect, patch(
        "pyotgw.status.StatusManager._process_updates", return_value=None
    ):
        result1 = await hass.config_entries.flow.async_configure(
            flow1["flow_id"], {CONF_NAME: "Test Entry 1", CONF_DEVICE: "/dev/ttyUSB0"}
        )
        result2 = await hass.config_entries.flow.async_configure(
            flow2["flow_id"], {CONF_NAME: "Test Entry 1", CONF_DEVICE: "/dev/ttyUSB1"}
        )
        result3 = await hass.config_entries.flow.async_configure(
            flow3["flow_id"], {CONF_NAME: "Test Entry 2", CONF_DEVICE: "/dev/ttyUSB0"}
        )
    assert result1["type"] == "create_entry"
    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "id_exists"}
    assert result3["type"] == "form"
    assert result3["errors"] == {"base": "already_configured"}
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1
    assert len(mock_pyotgw_connect.mock_calls) == 1
    assert len(mock_pyotgw_disconnect.mock_calls) == 1


async def test_form_connection_timeout(hass: HomeAssistant) -> None:
    """Test we handle connection timeout."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "pyotgw.OpenThermGateway.connect", side_effect=(TimeoutError)
    ) as mock_connect, patch(
        "pyotgw.status.StatusManager._process_updates", return_value=None
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_NAME: "Test Entry 1", CONF_DEVICE: "socket://192.0.2.254:1234"},
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "timeout_connect"}
    assert len(mock_connect.mock_calls) == 1


async def test_form_connection_error(hass: HomeAssistant) -> None:
    """Test we handle serial connection error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "pyotgw.OpenThermGateway.connect", side_effect=(SerialException)
    ) as mock_connect, patch(
        "pyotgw.status.StatusManager._process_updates", return_value=None
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_NAME: "Test Entry 1", CONF_DEVICE: "/dev/ttyUSB0"}
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "cannot_connect"}
    assert len(mock_connect.mock_calls) == 1


async def test_options_migration(hass: HomeAssistant) -> None:
    """Test migration of precision option after update."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Mock Gateway",
        data={
            CONF_NAME: "Test Entry 1",
            CONF_DEVICE: "/dev/ttyUSB0",
            CONF_ID: "test_entry_1",
        },
        options={
            CONF_FLOOR_TEMP: True,
            CONF_PRECISION: PRECISION_TENTHS,
        },
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.opentherm_gw.OpenThermGatewayDevice.connect_and_subscribe",
        return_value=True,
    ), patch(
        "homeassistant.components.opentherm_gw.async_setup",
        return_value=True,
    ), patch(
        "pyotgw.status.StatusManager._process_updates",
        return_value=None,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        result = await hass.config_entries.options.async_init(
            entry.entry_id, context={"source": config_entries.SOURCE_USER}, data=None
        )

        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "init"

        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={},
        )

        assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
        assert result["data"][CONF_READ_PRECISION] == PRECISION_TENTHS
        assert result["data"][CONF_SET_PRECISION] == PRECISION_TENTHS
        assert result["data"][CONF_FLOOR_TEMP] is True


async def test_options_form(hass: HomeAssistant) -> None:
    """Test the options form."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Mock Gateway",
        data={
            CONF_NAME: "Mock Gateway",
            CONF_DEVICE: "/dev/null",
            CONF_ID: "mock_gateway",
        },
        options={},
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.opentherm_gw.async_setup", return_value=True
    ), patch(
        "homeassistant.components.opentherm_gw.async_setup_entry", return_value=True
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(
        entry.entry_id, context={"source": "test"}, data=None
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_FLOOR_TEMP: True,
            CONF_READ_PRECISION: PRECISION_HALVES,
            CONF_SET_PRECISION: PRECISION_HALVES,
            CONF_TEMPORARY_OVRD_MODE: True,
        },
    )

    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_READ_PRECISION] == PRECISION_HALVES
    assert result["data"][CONF_SET_PRECISION] == PRECISION_HALVES
    assert result["data"][CONF_TEMPORARY_OVRD_MODE] is True
    assert result["data"][CONF_FLOOR_TEMP] is True

    result = await hass.config_entries.options.async_init(
        entry.entry_id, context={"source": "test"}, data=None
    )

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={CONF_READ_PRECISION: 0}
    )

    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_READ_PRECISION] == 0.0
    assert result["data"][CONF_SET_PRECISION] == PRECISION_HALVES
    assert result["data"][CONF_TEMPORARY_OVRD_MODE] is True
    assert result["data"][CONF_FLOOR_TEMP] is True

    result = await hass.config_entries.options.async_init(
        entry.entry_id, context={"source": "test"}, data=None
    )

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_FLOOR_TEMP: False,
            CONF_READ_PRECISION: PRECISION_TENTHS,
            CONF_SET_PRECISION: PRECISION_HALVES,
            CONF_TEMPORARY_OVRD_MODE: False,
        },
    )

    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_READ_PRECISION] == PRECISION_TENTHS
    assert result["data"][CONF_SET_PRECISION] == PRECISION_HALVES
    assert result["data"][CONF_TEMPORARY_OVRD_MODE] is False
    assert result["data"][CONF_FLOOR_TEMP] is False
