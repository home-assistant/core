"""Tests for the EOL Tracker config flow."""

from __future__ import annotations

from unittest.mock import patch

from aiohttp import ClientError
import pytest

from homeassistant.components.eol_tracker import DOMAIN
from homeassistant.components.eol_tracker.config_flow import CONF_DEVICE, CONF_NAME
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


MOCK_PRODUCTS = [
    {"label": "python", "name": "Python"},
    {"label": "nodejs", "name": "Node.js"},
]

PYTHON_LATEST_URI = "https://endoflife.date/api/v1/products/python/releases/latest"


async def test_user_step_shows_form(hass: HomeAssistant) -> None:
    """Test the user step shows the form."""
    with patch(
        "homeassistant.components.eol_tracker.config_flow.EOLClient.fetch_all_products",
        return_value=MOCK_PRODUCTS,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}


async def test_user_step_cannot_connect(hass: HomeAssistant) -> None:
    """Test we show an error when the API cannot be reached."""
    with patch(
        "homeassistant.components.eol_tracker.config_flow.EOLClient.fetch_all_products",
        side_effect=ClientError,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "cannot_connect"}


async def test_user_step_no_products(hass: HomeAssistant) -> None:
    """Test we show an error when no products are returned."""
    with patch(
        "homeassistant.components.eol_tracker.config_flow.EOLClient.fetch_all_products",
        return_value=[],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "no_products"}


async def test_user_step_invalid_device(hass: HomeAssistant) -> None:
    """Test selecting an invalid product shows a form error."""
    with patch(
        "homeassistant.components.eol_tracker.config_flow.EOLClient.fetch_all_products",
        return_value=MOCK_PRODUCTS,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_DEVICE: "invalid"},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_device"}


async def test_user_step_creates_entry_with_default_name(hass: HomeAssistant) -> None:
    """Test selecting a product creates an entry named after the product."""
    with patch(
        "homeassistant.components.eol_tracker.config_flow.EOLClient.fetch_all_products",
        return_value=MOCK_PRODUCTS,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_DEVICE: "python"},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Python"
    assert result["data"] == {
        CONF_DEVICE: PYTHON_LATEST_URI,
        CONF_NAME: "",
    }


async def test_user_step_creates_entry_with_custom_name(hass: HomeAssistant) -> None:
    """Test selecting a product with a custom name creates an entry."""
    with patch(
        "homeassistant.components.eol_tracker.config_flow.EOLClient.fetch_all_products",
        return_value=MOCK_PRODUCTS,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_DEVICE: "python", CONF_NAME: "My Python"},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "My Python"
    assert result["data"] == {
        CONF_DEVICE: PYTHON_LATEST_URI,
        CONF_NAME: "My Python",
    }


async def test_user_step_aborts_if_already_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test we abort when the selected product is already configured."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.eol_tracker.config_flow.EOLClient.fetch_all_products",
        return_value=MOCK_PRODUCTS,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_DEVICE: "python"},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
