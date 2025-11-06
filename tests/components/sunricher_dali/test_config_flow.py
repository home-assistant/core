"""Test the Sunricher DALI config flow."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from PySrDaliGateway.exceptions import DaliGatewayError

from homeassistant.components.sunricher_dali.config_flow import OptionsFlowHandler
from homeassistant.components.sunricher_dali.const import CONF_SERIAL_NUMBER, DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_discovery_flow_success(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_discovery: MagicMock,
    mock_gateway: MagicMock,
) -> None:
    """Test a successful discovery flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "user"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "select_gateway"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"selected_gateway": mock_gateway.gw_sn},
    )

    assert result.get("type") is FlowResultType.CREATE_ENTRY
    assert result.get("title") == mock_gateway.name
    assert result.get("data") == {
        CONF_SERIAL_NUMBER: mock_gateway.gw_sn,
        CONF_HOST: mock_gateway.gw_ip,
        CONF_PORT: mock_gateway.port,
        CONF_NAME: mock_gateway.name,
        CONF_USERNAME: mock_gateway.username,
        CONF_PASSWORD: mock_gateway.passwd,
    }
    result_entry = result.get("result")
    assert result_entry is not None
    assert result_entry.unique_id == mock_gateway.gw_sn
    mock_setup_entry.assert_called_once()
    mock_gateway.connect.assert_awaited_once()
    mock_gateway.disconnect.assert_awaited_once()


async def test_discovery_no_gateways_found(
    hass: HomeAssistant,
    mock_discovery: MagicMock,
    mock_gateway: MagicMock,
) -> None:
    """Test discovery step when no gateways are found."""
    mock_discovery.discover_gateways.return_value = []

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "select_gateway"
    errors = result.get("errors")
    assert errors is not None
    assert errors["base"] == "no_devices_found"

    mock_discovery.discover_gateways.return_value = [mock_gateway]
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "select_gateway"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"selected_gateway": mock_gateway.gw_sn},
    )

    assert result.get("type") is FlowResultType.CREATE_ENTRY


async def test_discovery_gateway_error(
    hass: HomeAssistant,
    mock_discovery: MagicMock,
    mock_gateway: MagicMock,
) -> None:
    """Test discovery error handling when gateway search fails."""
    mock_discovery.discover_gateways.side_effect = DaliGatewayError("failure")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "select_gateway"
    errors = result.get("errors")
    assert errors is not None
    assert errors["base"] == "discovery_failed"

    mock_discovery.discover_gateways.side_effect = None
    mock_discovery.discover_gateways.return_value = [mock_gateway]
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "select_gateway"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"selected_gateway": mock_gateway.gw_sn},
    )

    assert result.get("type") is FlowResultType.CREATE_ENTRY


async def test_discovery_connection_failure(
    hass: HomeAssistant,
    mock_discovery: MagicMock,
    mock_gateway: MagicMock,
) -> None:
    """Test connection failure when validating the selected gateway."""
    mock_gateway.connect.side_effect = DaliGatewayError("failure")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "select_gateway"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"selected_gateway": mock_gateway.gw_sn},
    )

    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "select_gateway"
    errors = result.get("errors")
    assert errors is not None
    assert errors["base"] == "cannot_connect"
    mock_gateway.connect.assert_awaited_once()
    mock_gateway.disconnect.assert_not_awaited()

    mock_gateway.connect.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"selected_gateway": mock_gateway.gw_sn},
    )

    assert result.get("type") is FlowResultType.CREATE_ENTRY


async def test_discovery_duplicate_filtered(
    hass: HomeAssistant,
    mock_discovery: MagicMock,
    mock_config_entry: MockConfigEntry,
    mock_gateway: MagicMock,
) -> None:
    """Test that already configured gateways are filtered out."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "select_gateway"
    errors = result.get("errors")
    assert errors is not None
    assert errors["base"] == "no_devices_found"

    await hass.config_entries.async_remove(mock_config_entry.entry_id)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "select_gateway"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"selected_gateway": mock_gateway.gw_sn},
    )

    assert result.get("type") is FlowResultType.CREATE_ENTRY


async def test_discovery_unique_id_already_configured(
    hass: HomeAssistant,
    mock_discovery: MagicMock,
    mock_config_entry: MockConfigEntry,
    mock_gateway: MagicMock,
) -> None:
    """Test duplicate protection when the entry appears during the flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"selected_gateway": mock_gateway.gw_sn},
    )

    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "already_configured"


async def test_options_flow_init(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test options flow init step."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_options_flow_refresh_not_found(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_discovery: MagicMock,
) -> None:
    """Test gateway not found during refresh."""
    mock_config_entry.add_to_hass(hass)
    mock_discovery.discover_gateways.return_value = []

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={"refresh": True}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "refresh"
    assert result["errors"]["base"] == "gateway_not_found"


async def test_options_flow_refresh_exception(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_discovery: MagicMock,
) -> None:
    """Test refresh with exception."""
    mock_config_entry.add_to_hass(hass)
    mock_discovery.discover_gateways.side_effect = Exception

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={"refresh": True}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "refresh"
    assert result["errors"]["base"] == "cannot_connect"


async def test_options_flow_refresh_success(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_discovery: MagicMock,
    mock_gateway: MagicMock,
) -> None:
    """Test successful gateway refresh with full flow."""

    mock_config_entry.add_to_hass(hass)
    mock_gateway.gw_ip = "192.168.1.101"

    with (
        patch("homeassistant.helpers.device_registry.async_get") as mock_dr,
        patch("homeassistant.helpers.entity_registry.async_get") as mock_er,
        patch.object(hass.config_entries, "async_unload") as mock_unload,
        patch.object(hass.config_entries, "async_setup") as mock_setup,
    ):
        mock_dr.return_value.async_entries_for_config_entry.return_value = []
        mock_er.return_value.async_entries_for_config_entry.return_value = []
        mock_unload.return_value = True
        mock_setup.return_value = True

        result = await hass.config_entries.options.async_init(
            mock_config_entry.entry_id
        )
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input={"refresh": True}
        )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "refresh_result"
        assert mock_config_entry.data[CONF_HOST] == "192.168.1.101"

        result = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input={}
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_options_flow_refresh_reload_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_discovery: MagicMock,
    mock_gateway: MagicMock,
) -> None:
    """Test refresh when reload fails."""

    mock_config_entry.add_to_hass(hass)

    with (
        patch("homeassistant.helpers.device_registry.async_get") as mock_dr,
        patch("homeassistant.helpers.entity_registry.async_get") as mock_er,
        patch.object(hass.config_entries, "async_unload") as mock_unload,
        patch.object(hass.config_entries, "async_setup") as mock_setup,
    ):
        mock_dr.return_value.async_entries_for_config_entry.return_value = []
        mock_er.return_value.async_entries_for_config_entry.return_value = []
        mock_unload.return_value = True
        mock_setup.return_value = False

        result = await hass.config_entries.options.async_init(
            mock_config_entry.entry_id
        )
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input={"refresh": True}
        )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "refresh"
        assert result["errors"]["base"] == "cannot_connect"


async def test_options_flow_refresh_with_runtime_data(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_discovery: MagicMock,
    mock_gateway: MagicMock,
) -> None:
    """Test refresh when config entry has runtime_data."""

    mock_config_entry.add_to_hass(hass)
    mock_config_entry.runtime_data = SimpleNamespace(gateway=mock_gateway)

    with (
        patch("homeassistant.helpers.device_registry.async_get") as mock_dr,
        patch("homeassistant.helpers.entity_registry.async_get") as mock_er,
        patch.object(hass.config_entries, "async_unload") as mock_unload,
        patch.object(hass.config_entries, "async_setup") as mock_setup,
    ):
        mock_dr.return_value.async_entries_for_config_entry.return_value = []
        mock_er.return_value.async_entries_for_config_entry.return_value = []
        mock_unload.return_value = True
        mock_setup.return_value = True

        result = await hass.config_entries.options.async_init(
            mock_config_entry.entry_id
        )
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input={"refresh": True}
        )

        assert result["type"] is FlowResultType.FORM
        mock_gateway.disconnect.assert_awaited_once()


async def test_options_flow_refresh_with_devices(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_discovery: MagicMock,
    mock_gateway: MagicMock,
) -> None:
    """Test refresh with device and entity cleanup."""

    mock_config_entry.add_to_hass(hass)

    mock_device = MagicMock()
    mock_device.id = "device_123"
    mock_device.name = "Test Device"

    mock_entity = MagicMock()
    mock_entity.entity_id = "light.test"

    with (
        patch(
            "homeassistant.components.sunricher_dali.config_flow.dr.async_get"
        ) as mock_dr_get,
        patch(
            "homeassistant.components.sunricher_dali.config_flow.dr.async_entries_for_config_entry"
        ) as mock_dr_entries,
        patch(
            "homeassistant.components.sunricher_dali.config_flow.er.async_get"
        ) as mock_er_get,
        patch(
            "homeassistant.components.sunricher_dali.config_flow.er.async_entries_for_config_entry"
        ) as mock_er_entries,
        patch.object(hass.config_entries, "async_unload") as mock_unload,
        patch.object(hass.config_entries, "async_setup") as mock_setup,
    ):
        mock_device_reg = MagicMock()
        mock_dr_get.return_value = mock_device_reg
        mock_dr_entries.return_value = [mock_device]

        mock_entity_reg = MagicMock()
        mock_er_get.return_value = mock_entity_reg
        mock_er_entries.return_value = [mock_entity]

        mock_unload.return_value = True
        mock_setup.return_value = True

        result = await hass.config_entries.options.async_init(
            mock_config_entry.entry_id
        )
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input={"refresh": True}
        )

        assert result["type"] is FlowResultType.FORM
        mock_device_reg.async_remove_device.assert_called_once_with("device_123")
        mock_entity_reg.async_remove.assert_called_once_with("light.test")


async def test_options_flow_refresh_reload_exception(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_discovery: MagicMock,
    mock_gateway: MagicMock,
) -> None:
    """Test refresh when reload raises exception."""

    mock_config_entry.add_to_hass(hass)

    with (
        patch("homeassistant.helpers.device_registry.async_get") as mock_dr,
        patch("homeassistant.helpers.entity_registry.async_get") as mock_er,
        patch.object(hass.config_entries, "async_unload") as mock_unload,
    ):
        mock_dr.return_value.async_entries_for_config_entry.return_value = []
        mock_er.return_value.async_entries_for_config_entry.return_value = []
        mock_unload.side_effect = RuntimeError("Unload failed")

        result = await hass.config_entries.options.async_init(
            mock_config_entry.entry_id
        )
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input={"refresh": True}
        )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "refresh"
        assert result["errors"]["base"] == "cannot_connect"


async def test_options_flow_refresh_result_show_form(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_discovery: MagicMock,
    mock_gateway: MagicMock,
) -> None:
    """Test refresh_result step shows form when user_input is None."""

    mock_config_entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.sunricher_dali.config_flow.dr.async_get"
        ) as mock_dr_get,
        patch(
            "homeassistant.components.sunricher_dali.config_flow.dr.async_entries_for_config_entry"
        ) as mock_dr_entries,
        patch(
            "homeassistant.components.sunricher_dali.config_flow.er.async_get"
        ) as mock_er_get,
        patch(
            "homeassistant.components.sunricher_dali.config_flow.er.async_entries_for_config_entry"
        ) as mock_er_entries,
        patch.object(hass.config_entries, "async_unload") as mock_unload,
        patch.object(hass.config_entries, "async_setup") as mock_setup,
    ):
        mock_device_reg = MagicMock()
        mock_dr_get.return_value = mock_device_reg
        mock_dr_entries.return_value = []

        mock_entity_reg = MagicMock()
        mock_er_get.return_value = mock_entity_reg
        mock_er_entries.return_value = []

        mock_unload.return_value = True
        mock_setup.return_value = True

        result = await hass.config_entries.options.async_init(
            mock_config_entry.entry_id
        )
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input={"refresh": True}
        )

        # First time entering refresh_result, user_input is None (internally)
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "refresh_result"

        # Complete the flow
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input={}
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_options_flow_refresh_result_initial_display(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test refresh_result step initial display with user_input=None."""

    mock_config_entry.add_to_hass(hass)

    # Create options flow handler
    flow_handler = OptionsFlowHandler(mock_config_entry)
    flow_handler.hass = hass

    # Call async_step_refresh_result with None to hit line 189
    result = await flow_handler.async_step_refresh_result(user_input=None)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "refresh_result"
