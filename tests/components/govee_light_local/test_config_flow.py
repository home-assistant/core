"""Test Govee light local config flow."""

from errno import EADDRINUSE
from unittest.mock import AsyncMock, patch

from govee_local_api import GoveeDevice

from homeassistant import config_entries
from homeassistant.components.govee_light_local.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import DEFAULT_CAPABILITIES


def _get_devices(mock_govee_api: AsyncMock) -> list[GoveeDevice]:
    return [
        GoveeDevice(
            controller=mock_govee_api,
            ip="192.168.1.100",
            fingerprint="asdawdqwdqwd1",
            sku="H615A",
            capabilities=DEFAULT_CAPABILITIES,
        )
    ]


async def test_creating_entry_has_no_devices(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_govee_api: AsyncMock
) -> None:
    """Test setting up Govee with no devices."""

    mock_govee_api.devices = []

    with patch(
        "homeassistant.components.govee_light_local.config_flow.DISCOVERY_TIMEOUT",
        0,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        # Confirmation form
        assert result["type"] is FlowResultType.FORM

        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        assert result["type"] is FlowResultType.ABORT

        await hass.async_block_till_done()

        mock_govee_api.start.assert_awaited_once()
        mock_setup_entry.assert_not_called()


async def test_creating_entry_has_with_devices(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_govee_api: AsyncMock,
) -> None:
    """Test setting up Govee with devices."""

    mock_govee_api.devices = _get_devices(mock_govee_api)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # Confirmation form
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY

    await hass.async_block_till_done()

    mock_govee_api.start.assert_awaited_once()
    mock_setup_entry.assert_awaited_once()


async def test_creating_entry_errno(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_govee_api: AsyncMock,
) -> None:
    """Test setting up Govee with devices."""

    e = OSError()
    e.errno = EADDRINUSE
    mock_govee_api.start.side_effect = e
    mock_govee_api.devices = _get_devices(mock_govee_api)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # Confirmation form
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.ABORT

    await hass.async_block_till_done()

    assert mock_govee_api.start.call_count == 1
    mock_setup_entry.assert_not_awaited()
