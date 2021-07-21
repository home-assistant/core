"""Test the AirTouch 4 config flow."""
from unittest.mock import AsyncMock, patch

from airtouch4pyapi.airtouch import AirTouch, AirTouchAc, AirTouchGroup

from homeassistant import config_entries
from homeassistant.components.airtouch4.const import DOMAIN


async def test_form(hass):
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] is None
    mock_ac = AirTouchAc()
    mock_groups = AirTouchGroup()

    with patch(
        "homeassistant.components.airtouch4.config_flow.AirTouch.GetAcs",
        return_value=[mock_ac],
    ), patch(
        "homeassistant.components.airtouch4.config_flow.AirTouch.UpdateInfo",
        return_value=None,
    ), patch(
        "homeassistant.components.airtouch4.config_flow.AirTouch.GetGroups",
        return_value=[mock_groups],
    ), patch(
        "homeassistant.components.airtouch4.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"host": "0.0.0.1"}
        )
        await hass.async_block_till_done()

    assert result2["type"] == "create_entry"
    assert result2["title"] == "0.0.0.1"
    assert result2["data"] == {
        "host": "0.0.0.1",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_timeout(hass):
    """Test we handle a connection timeout."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    mock_airtouch = AirTouch("")
    mock_airtouch.UpdateInfo = AsyncMock()
    mock_airtouch.error = TimeoutError()
    with patch(
        "homeassistant.components.airtouch4.config_flow.AirTouch",
        return_value=mock_airtouch,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"host": "0.0.0.1"}
        )
        assert result2["type"] == "form"
        assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_library_error_message(hass):
    """Test we handle an unknown error message from the library."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    mock_airtouch = AirTouch("")
    mock_airtouch.UpdateInfo = AsyncMock()
    mock_airtouch.error = "example error message"
    with patch(
        "homeassistant.components.airtouch4.config_flow.AirTouch",
        return_value=mock_airtouch,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"host": "0.0.0.1"}
        )
        assert result2["type"] == "form"
        assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_connection_refused(hass):
    """Test we handle a connection error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    mock_airtouch = AirTouch("")
    mock_airtouch.UpdateInfo = AsyncMock()
    mock_airtouch.error = ConnectionRefusedError()
    with patch(
        "homeassistant.components.airtouch4.config_flow.AirTouch",
        return_value=mock_airtouch,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"host": "0.0.0.1"}
        )
        assert result2["type"] == "form"
        assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_no_units(hass):
    """Test we handle no units found."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_ac = AirTouchAc()
    with patch(
        "homeassistant.components.airtouch4.config_flow.AirTouch.GetAcs",
        return_value=[mock_ac],
    ), patch(
        "homeassistant.components.airtouch4.config_flow.AirTouch.UpdateInfo",
        return_value=None,
    ), patch(
        "homeassistant.components.airtouch4.config_flow.AirTouch.GetGroups",
        return_value=[],
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"host": "0.0.0.1"}
        )

        assert result2["type"] == "form"
        assert result2["errors"] == {"base": "no_units"}
