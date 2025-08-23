"""Tests for the modbus config flow."""

from unittest.mock import patch

import pytest

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
    assert result


async def test_full_user_flow(hass: HomeAssistant) -> None:
    """Test the full user configuration flow."""
    result = await hass.config_entries.flow.async_init(
        MODBUS_DOMAIN, context={"source": SOURCE_USER}
    )

    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "user"

    with patch(
        "homeassistant.components.modbus.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={},
        )

    assert result.get("type") is FlowResultType.CREATE_ENTRY
    assert result.get("title") == "modbus_integration"
    assert result.get("data") == {}
    assert result.get("options") == {}
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize("source", [SOURCE_USER, SOURCE_IMPORT])
async def test_multiple_instances_allowed(
    hass: HomeAssistant,
    source: str,
) -> None:
    """Test we abort if already setup."""
    mock_config_entry = MockConfigEntry(domain=MODBUS_DOMAIN)

    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        MODBUS_DOMAIN, context={"source": source}
    )

    assert result.get("type") is FlowResultType.FORM


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


async def test_reconfigure_flow(
    hass: HomeAssistant,
) -> None:
    """Test the reconfigure configuration flow."""
    mock_config_entry = MockConfigEntry(domain=MODBUS_DOMAIN)
    mock_config_entry.add_to_hass(hass)
    result = await mock_config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
