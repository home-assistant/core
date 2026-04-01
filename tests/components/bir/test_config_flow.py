"""Tests for the BIR config flow."""

from unittest.mock import AsyncMock, patch

from pybirno import BirAuthenticationError, BirConnectionError
import pytest

from homeassistant.components.bir.const import CONF_ADDRESS, CONF_PROPERTY_ID, DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


async def test_full_user_flow(
    hass: HomeAssistant,
    mock_address_search: AsyncMock,
) -> None:
    """Test the full user flow from search to address selection."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    with patch(
        "homeassistant.components.bir.config_flow.BirClient.authenticate",
        new_callable=AsyncMock,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"address_search": "Testveien"},
        )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "select_address"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"selected_address": "12345"},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Testveien 1, Bergen"
    assert result["data"] == {
        CONF_PROPERTY_ID: "12345",
        CONF_ADDRESS: "Testveien 1, Bergen",
    }


async def test_search_too_short(hass: HomeAssistant) -> None:
    """Test error when search query is too short."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"address_search": "Te"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "search_too_short"}


async def test_no_addresses_found(
    hass: HomeAssistant,
    mock_address_search: AsyncMock,
) -> None:
    """Test error when no addresses match the search."""
    mock_address_search.return_value = []

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"address_search": "Nonexistent Street"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "no_addresses_found"}


async def test_search_connection_error(
    hass: HomeAssistant,
    mock_address_search: AsyncMock,
) -> None:
    """Test error when address search fails."""
    mock_address_search.side_effect = BirConnectionError("Connection failed")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"address_search": "Testveien"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "cannot_connect"}


async def test_address_validation_error(
    hass: HomeAssistant,
    mock_address_search: AsyncMock,
) -> None:
    """Test error when address validation fails during selection."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"address_search": "Testveien"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "select_address"

    with patch(
        "homeassistant.components.bir.config_flow.BirClient.authenticate",
        new_callable=AsyncMock,
        side_effect=BirAuthenticationError("API error"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"selected_address": "12345"},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "select_address"
    assert result["errors"] == {"base": "cannot_connect"}


@pytest.mark.usefixtures("mock_address_search")
async def test_already_configured(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test aborting if address is already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"address_search": "Testveien"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "select_address"

    with patch(
        "homeassistant.components.bir.config_flow.BirClient.authenticate",
        new_callable=AsyncMock,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"selected_address": "12345"},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
