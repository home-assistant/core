"""Test the Anthem A/V Receivers config flow."""
from unittest.mock import AsyncMock, patch

from anthemav.device_error import DeviceError

from homeassistant.components.anthemav.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_form_with_valid_connection(
    hass: HomeAssistant, mock_connection_create: AsyncMock, mock_anthemav: AsyncMock
) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] is None

    with patch(
        "homeassistant.components.anthemav.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.1.1.1",
                "port": 14999,
            },
        )

        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Anthem AV"
    assert result2["data"] == {
        "host": "1.1.1.1",
        "port": 14999,
        "mac": "00:00:00:00:00:01",
        "model": "MRX 520",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_device_info_error(hass: HomeAssistant) -> None:
    """Test we handle DeviceError from library."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with patch(
        "anthemav.Connection.create",
        side_effect=DeviceError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.1.1.1",
                "port": 14999,
            },
        )

        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_receive_deviceinfo"}


async def test_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with patch(
        "anthemav.Connection.create",
        side_effect=OSError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.1.1.1",
                "port": 14999,
            },
        )

        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_device_already_configured(
    hass: HomeAssistant,
    mock_connection_create: AsyncMock,
    mock_anthemav: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test we import existing configuration."""
    config = {
        "host": "1.1.1.1",
        "port": 14999,
    }

    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=config
    )

    assert result.get("type") == FlowResultType.ABORT
    assert result.get("reason") == "already_configured"
