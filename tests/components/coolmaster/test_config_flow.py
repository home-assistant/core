"""Test the Coolmaster config flow."""
from unittest.mock import patch

from homeassistant import config_entries, setup
from homeassistant.components.coolmaster.const import DOMAIN, AVAILABLE_MODES

# from homeassistant.components.coolmaster.config_flow import validate_connection

from tests.common import mock_coro


def _flow_data():
    options = {"host": "1.1.1.1"}
    for mode in AVAILABLE_MODES:
        options[mode] = True
    return options


async def test_form(hass):
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] is None

    with patch(
        "homeassistant.components.coolmaster.config_flow.validate_connection",
        return_value=mock_coro(True),
    ), patch(
        "homeassistant.components.coolmaster.async_setup", return_value=mock_coro(True)
    ) as mock_setup, patch(
        "homeassistant.components.coolmaster.async_setup_entry",
        return_value=mock_coro(True),
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], _flow_data()
        )

    assert result2["type"] == "create_entry"
    assert result2["title"] == "1.1.1.1"
    assert result2["data"] == {
        "host": "1.1.1.1",
        "port": 10102,
        "supported_modes": AVAILABLE_MODES,
    }
    await hass.async_block_till_done()
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_timeout(hass):
    """Test we handle a connection timeout."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.coolmaster.config_flow.validate_connection",
        side_effect=TimeoutError(),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], _flow_data()
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "connection_error"}


async def test_form_connection_refused(hass):
    """Test we handle a connection error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.coolmaster.config_flow.validate_connection",
        side_effect=ConnectionRefusedError(),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], _flow_data()
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "connection_error"}


async def test_form_no_units(hass):
    """Test we handle no units found."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.coolmaster.config_flow.validate_connection",
        return_value=mock_coro(False),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], _flow_data()
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "no_units"}
