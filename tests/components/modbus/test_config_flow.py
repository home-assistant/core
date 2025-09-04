"""Tests for the modbus config flow."""

from homeassistant.components.modbus.const import MODBUS_DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_user_flow(hass: HomeAssistant) -> None:
    """Test the full user configuration flow."""
    result = await hass.config_entries.flow.async_init(
        MODBUS_DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.ABORT


async def test_reconfigure_flow(
    hass: HomeAssistant,
) -> None:
    """Test the reconfigure configuration flow."""
    mock_config_entry = MockConfigEntry(domain=MODBUS_DOMAIN)
    mock_config_entry.add_to_hass(hass)
    result = await mock_config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.ABORT


async def test_import_flow(
    hass: HomeAssistant,
) -> None:
    """Test the import configuration flow."""
    result = await hass.config_entries.flow.async_init(
        MODBUS_DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={},
    )

    assert result.get("type") is FlowResultType.CREATE_ENTRY
    assert result.get("title") == "modbus_integration"
    assert result.get("data") == {}
    assert result.get("options") == {}
