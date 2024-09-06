"""Test the WatchYourLAN config flow."""

from unittest.mock import AsyncMock, patch

from homeassistant import config_entries
from homeassistant.components.watchyourlan.config_flow import CannotConnect
from homeassistant.components.watchyourlan.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_SSL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


async def test_form(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test we get the form and create entry with valid data."""
    # Initiate the flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # Check that the form is shown with no errors initially
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}

    # Patch the API call to simulate valid response
    with patch(
        "homeassistant.components.watchyourlan.config_flow.WatchYourLANClient.get_all_hosts",
        new_callable=AsyncMock,
        return_value={"title": "WatchYourLAN", "url": "http://127.0.0.1:8840"},
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "127.0.0.1",
                CONF_PORT: 8840,
                CONF_SSL: False,
            },
        )
        await hass.async_block_till_done()

    # Ensure that the config entry is created with correct values
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "WatchYourLAN"
    assert result["data"] == {
        "url": "http://127.0.0.1:8840",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_cannot_connect(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # Simulate CannotConnect error during validation
    with patch(
        "homeassistant.components.watchyourlan.config_flow.WatchYourLANClient.get_all_hosts",
        new_callable=AsyncMock,
        side_effect=CannotConnect,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "127.0.0.1",
                CONF_PORT: 8840,
                CONF_SSL: False,
            },
        )

    # Ensure the form shows the cannot_connect error
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    # Simulate a valid entry after resolving connection issue
    with patch(
        "homeassistant.components.watchyourlan.config_flow.WatchYourLANClient.get_all_hosts",
        new_callable=AsyncMock,
        return_value={"title": "WatchYourLAN", "url": "http://127.0.0.1:8840"},
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "127.0.0.1",
                CONF_PORT: 8840,
                CONF_SSL: False,
            },
        )
        await hass.async_block_till_done()

    # Ensure the entry is created after retrying
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "WatchYourLAN"
    assert result["data"] == {
        "url": "http://127.0.0.1:8840",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_invalid_host(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test we handle an invalid host during the setup."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # Simulate an invalid hostname or connection issue
    with patch(
        "homeassistant.components.watchyourlan.config_flow.WatchYourLANClient.get_all_hosts",
        new_callable=AsyncMock,
        side_effect=CannotConnect,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "invalid-host",
                CONF_PORT: 8840,
                CONF_SSL: False,
            },
        )

    # Ensure the form shows the cannot_connect error
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}
