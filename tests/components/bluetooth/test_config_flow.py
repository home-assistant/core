"""Test the bluetooth config flow."""

from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.components.bluetooth.const import DOMAIN
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_async_step_user(hass):
    """Test setting up manually."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data={},
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "enable_bluetooth"
    with patch(
        "homeassistant.components.bluetooth.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )
    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Bluetooth"
    assert result2["data"] == {}
    assert len(mock_setup_entry.mock_calls) == 1


async def test_async_step_user_only_allows_one(hass):
    """Test setting up manually with an existing entry."""
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data={},
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_async_step_integration_discovery(hass):
    """Test setting up from integration discovery."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_INTEGRATION_DISCOVERY},
        data={},
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "enable_bluetooth"
    with patch(
        "homeassistant.components.bluetooth.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )
    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Bluetooth"
    assert result2["data"] == {}
    assert len(mock_setup_entry.mock_calls) == 1


async def test_async_step_integration_discovery_during_onboarding(hass):
    """Test setting up from integration discovery during onboarding."""

    with patch(
        "homeassistant.components.bluetooth.async_setup_entry", return_value=True
    ) as mock_setup_entry, patch(
        "homeassistant.components.onboarding.async_is_onboarded",
        return_value=False,
    ) as mock_onboarding:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_INTEGRATION_DISCOVERY},
            data={},
        )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Bluetooth"
    assert result["data"] == {}
    assert len(mock_setup_entry.mock_calls) == 1
    assert len(mock_onboarding.mock_calls) == 1


async def test_async_step_integration_discovery_already_exists(hass):
    """Test setting up from integration discovery when an entry already exists."""
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_INTEGRATION_DISCOVERY},
        data={},
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_async_step_import(hass):
    """Test setting up from integration discovery."""
    with patch(
        "homeassistant.components.bluetooth.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={},
        )
        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["title"] == "Bluetooth"
        assert result["data"] == {}
    assert len(mock_setup_entry.mock_calls) == 1


async def test_async_step_import_already_exists(hass):
    """Test setting up from yaml when an entry already exists."""
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data={},
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"
