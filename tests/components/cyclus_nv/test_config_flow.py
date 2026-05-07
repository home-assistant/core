"""Tests for the Cyclus NV config flow."""

from unittest.mock import AsyncMock, MagicMock

from cyclus.exceptions import CyclusError
import pytest

from homeassistant.components.cyclus_nv.const import (
    CONF_BAG_ID,
    CONF_HOUSE_NUMBER,
    CONF_ZIPCODE,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


@pytest.mark.usefixtures("mock_cyclus_client")
async def test_full_user_flow(hass: HomeAssistant) -> None:
    """Test registering an integration and finishing flow works."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_ZIPCODE: "1234AB",
            CONF_HOUSE_NUMBER: "1",
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY

    config_entry = result["result"]
    assert config_entry.unique_id == "0123456789abcdef"
    assert config_entry.data == {
        CONF_ZIPCODE: "1234AB",
        CONF_HOUSE_NUMBER: "1",
        CONF_BAG_ID: "0123456789abcdef",
    }
    assert not config_entry.options


async def test_cannot_connect(
    hass: HomeAssistant,
    mock_cyclus_client: MagicMock,
) -> None:
    """Test we show user form on connection error."""
    mock_cyclus_client.get_bag_id = AsyncMock(side_effect=CyclusError)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={
            CONF_ZIPCODE: "1234AB",
            CONF_HOUSE_NUMBER: "1",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "cannot_connect"}

    # Recover from error
    mock_cyclus_client.get_bag_id = AsyncMock(return_value="0123456789abcdef")

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_ZIPCODE: "1234AB",
            CONF_HOUSE_NUMBER: "1",
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY

    config_entry = result["result"]
    assert config_entry.unique_id == "0123456789abcdef"
    assert config_entry.data == {
        CONF_ZIPCODE: "1234AB",
        CONF_HOUSE_NUMBER: "1",
        CONF_BAG_ID: "0123456789abcdef",
    }


@pytest.mark.usefixtures("mock_cyclus_client")
async def test_address_already_set_up(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test we abort if address has already been set up."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={
            CONF_ZIPCODE: "1234AB",
            CONF_HOUSE_NUMBER: "1",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
