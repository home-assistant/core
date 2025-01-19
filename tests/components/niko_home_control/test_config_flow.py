"""Test niko_home_control config flow."""

from unittest.mock import AsyncMock, patch

from homeassistant.components.niko_home_control.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_full_flow(
    hass: HomeAssistant,
    mock_niko_home_control_connection: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test the full flow."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "192.168.0.123"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Niko Home Control"
    assert result["data"] == {CONF_HOST: "192.168.0.123"}

    assert len(mock_setup_entry.mock_calls) == 1


async def test_cannot_connect(hass: HomeAssistant) -> None:
    """Test the cannot connect error."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.niko_home_control.config_flow.NHCController.connect",
        side_effect=Exception,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "192.168.0.123"},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    with patch(
        "homeassistant.components.niko_home_control.config_flow.NHCController.connect",
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "192.168.0.123"},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_duplicate_entry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test uniqueness."""

    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "192.168.0.123"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_import_flow(
    hass: HomeAssistant,
    mock_niko_home_control_connection: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test the import flow."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data={CONF_HOST: "192.168.0.123"}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Niko Home Control"
    assert result["data"] == {CONF_HOST: "192.168.0.123"}

    assert len(mock_setup_entry.mock_calls) == 1


async def test_import_cannot_connect(hass: HomeAssistant) -> None:
    """Test the cannot connect error."""

    with patch(
        "homeassistant.components.niko_home_control.config_flow.NHCController.connect",
        side_effect=Exception,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data={CONF_HOST: "192.168.0.123"}
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_duplicate_import_entry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test uniqueness."""

    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data={CONF_HOST: "192.168.0.123"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_duplicate_reconfigure_entry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test uniqueness."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "192.168.0.123"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reconfigure_setup(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test the reconfigure flow."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert set(result["data_schema"].schema) == {CONF_HOST}


async def test_reconfigure(
    hass: HomeAssistant,
    mock_niko_home_control_connection: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the reconfigure flow."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert set(result["data_schema"].schema) == {CONF_HOST}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "192.168.0.122"},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].entry_id != mock_config_entry.entry_id


async def test_reconfigure_cannot_connect(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test the cannot connect error."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reconfigure_flow(hass)
    with patch(
        "homeassistant.components.niko_home_control.config_flow.NHCController.connect",
        side_effect=Exception,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "192.168.0.122"},
        )
    assert result["errors"] == {"base": "cannot_connect"}


async def test_reconfigure_update_reload_and_abort(
    hass: HomeAssistant,
    mock_niko_home_control_connection: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the reconfigure flow with update, reload, and abort."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert set(result["data_schema"].schema) == {CONF_HOST}
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "192.168.0.122"},
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY


async def test_async_step_reconfigure_success(
    hass: HomeAssistant,
    mock_niko_home_control_connection: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test successful reconfiguration."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.niko_home_control.config_flow.NikoHomeControlConfigFlow.async_update_reload_and_abort",
        return_value={"type": FlowResultType.ABORT, "reason": "reconfigured"},
    ):
        result = await mock_config_entry.start_reconfigure_flow(hass)

        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {}

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "192.168.0.122"},
        )

        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["result"].entry_id != mock_config_entry.entry_id


async def test_async_step_reconfigure_cannot_connect(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reconfiguration with connection error."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.niko_home_control.config_flow.test_connection",
        return_value="cannot_connect",
    ):
        result = await mock_config_entry.start_reconfigure_flow(hass)

        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {}

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "192.168.0.122"},
        )

        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"base": "cannot_connect"}
