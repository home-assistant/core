"""Tests the config flow of EHEIM Digital."""

from unittest.mock import MagicMock

from homeassistant.components.eheimdigital.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_config_flow_new_device(
    hass: HomeAssistant, mock_async_zeroconf: MagicMock
) -> None:
    """Test config flow."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    # Confirmation form
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_config_flow_no_device(
    hass: HomeAssistant, mock_async_zeroconf: MagicMock
) -> None:
    """Test config flow without a found device."""

    mock_async_zeroconf.async_get_service_info.return_value = None

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"


async def test_already_configured(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_async_zeroconf: MagicMock,
) -> None:
    """Test flow aborts when already configured."""

    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"
