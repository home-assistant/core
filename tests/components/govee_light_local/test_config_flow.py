"""Test Govee light local config flow."""
from unittest.mock import AsyncMock, patch

from govee_local_api import GoveeDevice

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.govee_light_local.const import DOMAIN
from homeassistant.core import HomeAssistant

from .conftest import DEFAULT_CAPABILITEIS


async def test_creating_entry_has_no_devices(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_govee_api: AsyncMock
) -> None:
    """Test setting up Govee with no devices."""

    mock_govee_api.devices = []

    with patch(
        "homeassistant.components.govee_light_local.config_flow.GoveeController",
        return_value=mock_govee_api,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        # Confirmation form
        assert result["type"] == data_entry_flow.FlowResultType.FORM

        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        assert result["type"] == data_entry_flow.FlowResultType.ABORT

        await hass.async_block_till_done()

        mock_govee_api.start.assert_awaited_once()
        mock_setup_entry.assert_not_called()


async def test_creating_entry_has_with_devices(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_govee_api: AsyncMock,
) -> None:
    """Test setting up Govee with devices."""

    mock_govee_api.devices = [
        GoveeDevice(
            controller=mock_govee_api,
            ip="192.168.1.100",
            fingerprint="asdawdqwdqwd1",
            sku="H615A",
            capabilities=DEFAULT_CAPABILITEIS,
        )
    ]

    with patch(
        "homeassistant.components.govee_light_local.config_flow.GoveeController",
        return_value=mock_govee_api,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        # Confirmation form
        assert result["type"] == data_entry_flow.FlowResultType.FORM

        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY

        await hass.async_block_till_done()

        mock_govee_api.start.assert_awaited_once()
        mock_setup_entry.assert_awaited_once()
