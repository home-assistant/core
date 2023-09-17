"""Test the IntelliFire config flow."""

from unittest.mock import AsyncMock, patch

from homeassistant import config_entries
from homeassistant.components.weatherflow.const import DOMAIN
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_address_in_use(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_has_devices_error_address_in_use: AsyncMock,
) -> None:
    """Test the address in use error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["errors"] == {"base": "address_in_use"}


async def test_cannot_connect(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_has_devices_error_listener
) -> None:
    """Test cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["errors"] == {"base": "cannot_connect"}


async def test_abort_create(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_has_devices: AsyncMock
) -> None:
    """Test abort creation."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data=mock_config_entry.data,
    )
    assert result["type"] == FlowResultType.ABORT


async def test_single_instance(
    hass: HomeAssistant,
    mock_config_entry2: MockConfigEntry,
    mock_has_devices: AsyncMock,
) -> None:
    """Test more than one instance."""
    mock_config_entry2.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
    assert result["type"] == FlowResultType.ABORT


async def test_has_no_devices(
    hass: HomeAssistant, mock_has_no_devices: AsyncMock
) -> None:
    """Test a no device found."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "4.3.2.1"},
    )
    await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.ABORT


async def test_devices_with_mocks(
    hass: HomeAssistant, mock_start: AsyncMock, mock_stop: AsyncMock
) -> None:
    """Test getting user input."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
    await hass.async_block_till_done()
    assert result["type"] == FlowResultType.CREATE_ENTRY


async def test_devices_with_mocks_timeout(
    hass: HomeAssistant, mock_start_timeout: AsyncMock, mock_stop: AsyncMock
) -> None:
    """Test getting user input."""

    # with patch("pyweatherflowudp.client") as mock_listener:
    #     mock_client = MagicMock()
    #     mock_listener.return_value.__aenter__.return_value = mock_client

    #     # Setting up client.on to do nothing
    #     mock_client.on.side_effect = lambda event, callback: None
    with patch(
        "homeassistant.components.weatherflow.config_flow._async_has_devices"
    ) as mock_async_has_devices:
        # Set the wait_timeout parameter to 5 seconds
        mock_async_has_devices.wait_timeout = 1
        await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )
