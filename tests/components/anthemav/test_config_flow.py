"""Test the Anthem A/V Receivers config flow."""
import asyncio
from unittest.mock import AsyncMock, patch

from homeassistant import config_entries
from homeassistant.components.anthemav.const import DOMAIN, EMPTY_MAC, UNKNOWN_MODEL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import RESULT_TYPE_CREATE_ENTRY, RESULT_TYPE_FORM


async def test_form_with_valid_connection(
    hass: HomeAssistant, mock_connection_create: AsyncMock, mock_anthemav: AsyncMock
) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_FORM
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
                "name": "Anthem Av",
            },
        )

        await hass.async_block_till_done()

    assert result2["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result2["data"] == {
        "host": "1.1.1.1",
        "port": 14999,
        "name": "Anthem Av",
        "mac": "00:00:00:00:00:01",
        "model": "MRX 520",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_timeout_device_info(hass: HomeAssistant) -> None:
    """Test we handle tineout error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "anthemav.Connection.create",
        side_effect=asyncio.TimeoutError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.1.1.1",
                "port": 14999,
                "name": "Anthem Av",
            },
        )

        await hass.async_block_till_done()

    assert result2["type"] == RESULT_TYPE_FORM
    assert result2["errors"] == {"base": "cannot_receive_deviceinfo"}


async def test_form_invalid_macaddress(
    hass: HomeAssistant, mock_connection_create: AsyncMock, mock_anthemav: AsyncMock
) -> None:
    """Test we handle when receiving invalid mac address."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] is None

    mock_anthemav.protocol.macaddress = EMPTY_MAC

    with patch(
        "homeassistant.components.anthemav.async_setup_entry",
        return_value=True,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.1.1.1",
                "port": 14999,
                "name": "Anthem Av",
            },
        )

        await hass.async_block_till_done()

    assert result2["type"] == RESULT_TYPE_FORM
    assert result2["errors"] == {"base": "cannot_receive_deviceinfo"}


async def test_form_invalid_model(
    hass: HomeAssistant, mock_connection_create: AsyncMock, mock_anthemav: AsyncMock
) -> None:
    """Test we handle when receiving and invalid AVR model."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] is None

    mock_anthemav.protocol.model = UNKNOWN_MODEL

    with patch(
        "homeassistant.components.anthemav.async_setup_entry",
        return_value=True,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.1.1.1",
                "port": 14999,
                "name": "Anthem Av",
            },
        )

        await hass.async_block_till_done()

    assert result2["type"] == RESULT_TYPE_FORM
    assert result2["errors"] == {"base": "cannot_receive_deviceinfo"}


async def test_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
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
                "name": "Anthem Av",
            },
        )

        await hass.async_block_till_done()

    assert result2["type"] == RESULT_TYPE_FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_unknown_error(hass: HomeAssistant) -> None:
    """Test we handle any errors."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "anthemav.Connection.create",
        side_effect=Exception,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.1.1.1",
                "port": 14999,
                "name": "Anthem Av",
            },
        )

        await hass.async_block_till_done()

    assert result2["type"] == RESULT_TYPE_FORM
    assert result2["errors"] == {"base": "unknown"}


async def test_import_configuration(
    hass: HomeAssistant, mock_connection_create: AsyncMock, mock_anthemav: AsyncMock
) -> None:
    """Test we import existing configuration."""
    config = {
        "host": "1.1.1.1",
        "port": 14999,
        "name": "Anthem Av",
    }
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_IMPORT}, data=config
    )

    assert result["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result["data"] == {
        "host": "1.1.1.1",
        "port": 14999,
        "name": "Anthem Av",
        "mac": "00:00:00:00:00:01",
        "model": "MRX 520",
    }
