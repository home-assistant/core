"""Test the Bryant Evolution config flow."""

from unittest.mock import DEFAULT, AsyncMock, patch

from homeassistant import config_entries
from homeassistant.components.bryant_evolution.const import (
    CONF_SYSTEM_ID,
    CONF_ZONE_ID,
    DOMAIN,
)
from homeassistant.const import CONF_FILENAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


async def test_form_success(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with (
        patch(
            "evolutionhttp.BryantEvolutionLocalClient.get_client", return_value=DEFAULT
        ) as mock_factory,
    ):
        mock_client = mock_factory.return_value
        mock_client.read_current_temperature.return_value = 72
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_FILENAME: "test_form_success",
                CONF_SYSTEM_ID: 1,
                CONF_ZONE_ID: 2,
            },
        )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "System 1 Zone 2"
    assert result["data"] == {
        CONF_FILENAME: "test_form_success",
        CONF_SYSTEM_ID: 1,
        CONF_ZONE_ID: 2,
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_cannot_connect(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with (
        patch(
            "evolutionhttp.BryantEvolutionLocalClient.get_client", return_value=DEFAULT
        ) as mock_factory,
    ):
        mock_client = mock_factory.return_value
        mock_client.read_current_temperature.return_value = None
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_FILENAME: "test_form_cannot_connect",
                CONF_SYSTEM_ID: 1,
                CONF_ZONE_ID: 2,
            },
        )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    # Make sure the config flow tests finish with either an
    # FlowResultType.CREATE_ENTRY or FlowResultType.ABORT so
    # we can show the config flow is able to recover from an error.

    with (
        patch(
            "evolutionhttp.BryantEvolutionLocalClient.get_client", return_value=DEFAULT
        ) as mock_factory,
    ):
        mock_client = mock_factory.return_value
        mock_client.read_current_temperature.return_value = 72
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_FILENAME: "some-serial",
                CONF_SYSTEM_ID: 1,
                CONF_ZONE_ID: 2,
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "System 1 Zone 2"
    assert result["data"] == {
        CONF_FILENAME: "some-serial",
        CONF_SYSTEM_ID: 1,
        CONF_ZONE_ID: 2,
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_cannot_connect_bad_file(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test we handle cannot connect error from a missing file."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            # This file does not exist.
            CONF_FILENAME: "test_form_cannot_connect_bad_file",
            CONF_SYSTEM_ID: 1,
            CONF_ZONE_ID: 2,
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}
