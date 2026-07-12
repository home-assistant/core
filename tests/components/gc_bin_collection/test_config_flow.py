"""Tests for the Gold Coast Bin Collection config flow."""

from unittest.mock import MagicMock, patch

from gcbinspy.gcbinspy import AddressException
import pytest
import requests

from homeassistant.components.gc_bin_collection.const import CONF_PROPERTY_ID, DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import MOCK_ADDRESS, MOCK_PROPERTY_ID


@pytest.fixture
def mock_gcbinspy_flow():
    """Return a mock GoldCoastBins client for config flow."""
    with patch(
        "homeassistant.components.gc_bin_collection.config_flow.GoldCoastBins"
    ) as mock_class:
        client = MagicMock()
        client.property_id.return_value = MOCK_PROPERTY_ID
        mock_class.return_value = client
        # Also patch coordinator so config entry setup doesn't fail
        with patch(
            "homeassistant.components.gc_bin_collection.coordinator.GoldCoastBins"
        ) as coord_mock:
            coord_client = MagicMock()
            coord_client.next_landfill.return_value = __import__("datetime").date(
                2026, 6, 9
            )
            coord_client.next_recycling.return_value = __import__("datetime").date(
                2026, 6, 16
            )
            coord_client.next_organics.return_value = __import__("datetime").date(
                2026, 6, 9
            )
            coord_mock.return_value = coord_client
            yield mock_class, client


async def test_form_success(hass: HomeAssistant, mock_gcbinspy_flow) -> None:
    """Test successful user config flow."""
    _mock_class, _mock_client = mock_gcbinspy_flow

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert not result["errors"]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_ADDRESS: MOCK_ADDRESS},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == MOCK_ADDRESS
    assert result["data"] == {
        CONF_ADDRESS: MOCK_ADDRESS,
        CONF_PROPERTY_ID: MOCK_PROPERTY_ID,
    }


async def test_form_address_not_found(hass: HomeAssistant) -> None:
    """Test config flow when address cannot be resolved to a property."""
    with patch(
        "homeassistant.components.gc_bin_collection.config_flow.GoldCoastBins",
        side_effect=AddressException("No property found"),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_ADDRESS: "Unknown Address QLD 9999"},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "address_not_found"}


async def test_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test config flow when API is unreachable."""
    with patch(
        "homeassistant.components.gc_bin_collection.config_flow.GoldCoastBins",
        side_effect=requests.exceptions.ConnectionError,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_ADDRESS: MOCK_ADDRESS},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_form_timeout(hass: HomeAssistant) -> None:
    """Test config flow when API times out."""
    with patch(
        "homeassistant.components.gc_bin_collection.config_flow.GoldCoastBins",
        side_effect=requests.exceptions.Timeout,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_ADDRESS: MOCK_ADDRESS},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_form_unknown_error(hass: HomeAssistant) -> None:
    """Test config flow on unexpected exception."""
    with patch(
        "homeassistant.components.gc_bin_collection.config_flow.GoldCoastBins",
        side_effect=Exception("Unexpected"),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_ADDRESS: MOCK_ADDRESS},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}


async def test_duplicate_entry(hass: HomeAssistant, mock_gcbinspy_flow) -> None:
    """Test config flow aborts on duplicate property ID."""
    _mock_class, _mock_client = mock_gcbinspy_flow

    # First entry
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_ADDRESS: MOCK_ADDRESS},
    )

    # Second entry with same address (same property ID)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_ADDRESS: MOCK_ADDRESS},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
