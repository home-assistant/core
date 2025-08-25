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


async def test_duplicate_reconfigure_entry(
    hass: HomeAssistant,
    mock_niko_home_control_connection: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reconfigure to other existing entry."""
    mock_config_entry.add_to_hass(hass)
    another_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Niko Home Control",
        data={CONF_HOST: "192.168.0.124"},
        entry_id="01JFN93M7KRA38V5AMPCJ2JYYB",
    )
    another_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "192.168.0.124"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


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
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"


async def test_reconfigure_cannot_connect(
    hass: HomeAssistant,
    mock_niko_home_control_connection: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reconfiguration with connection error."""
    mock_config_entry.add_to_hass(hass)

    mock_niko_home_control_connection.connect.side_effect = Exception("cannot_connect")

    result = await mock_config_entry.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "192.168.0.122"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    mock_niko_home_control_connection.connect.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "192.168.0.122"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
