"""Test the AirTouch 4 config flow."""
from unittest.mock import AsyncMock, Mock, patch

from airtouch4pyapi.airtouch import AirTouch, AirTouchAc, AirTouchGroup, AirTouchStatus

from homeassistant import config_entries
from homeassistant.components.airtouch4.const import DOMAIN
from homeassistant.core import HomeAssistant


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] is None
    mock_ac = AirTouchAc()
    mock_groups = AirTouchGroup()
    mock_airtouch = AirTouch("")
    mock_airtouch.UpdateInfo = AsyncMock()
    mock_airtouch.Status = AirTouchStatus.OK
    mock_airtouch.GetAcs = Mock(return_value=[mock_ac])
    mock_airtouch.GetGroups = Mock(return_value=[mock_groups])

    with patch(
        "homeassistant.components.airtouch4.config_flow.AirTouch",
        return_value=mock_airtouch,
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


async def test_form_timeout(hass: HomeAssistant) -> None:
    """Test we handle a connection timeout."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    mock_airtouch = AirTouch("")
    mock_airtouch.UpdateInfo = AsyncMock()
    mock_airtouch.status = AirTouchStatus.CONNECTION_INTERRUPTED
    with patch(
        "homeassistant.components.airtouch4.config_flow.AirTouch",
        return_value=mock_airtouch,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"host": "0.0.0.1"}
        )
        assert result2["type"] == "form"
        assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_library_error_message(hass: HomeAssistant) -> None:
    """Test we handle an unknown error message from the library."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    mock_airtouch = AirTouch("")
    mock_airtouch.UpdateInfo = AsyncMock()
    mock_airtouch.status = AirTouchStatus.ERROR
    with patch(
        "homeassistant.components.airtouch4.config_flow.AirTouch",
        return_value=mock_airtouch,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"host": "0.0.0.1"}
        )
        assert result2["type"] == "form"
        assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_connection_refused(hass: HomeAssistant) -> None:
    """Test we handle a connection error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    mock_airtouch = AirTouch("")
    mock_airtouch.UpdateInfo = AsyncMock()
    mock_airtouch.status = AirTouchStatus.NOT_CONNECTED
    with patch(
        "homeassistant.components.airtouch4.config_flow.AirTouch",
        return_value=mock_airtouch,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"host": "0.0.0.1"}
        )
        assert result2["type"] == "form"
        assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_no_units(hass: HomeAssistant) -> None:
    """Test we handle no units found."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    mock_ac = AirTouchAc()
    mock_airtouch = AirTouch("")
    mock_airtouch.UpdateInfo = AsyncMock()
    mock_airtouch.Status = AirTouchStatus.OK
    mock_airtouch.GetAcs = Mock(return_value=[mock_ac])
    mock_airtouch.GetGroups = Mock(return_value=[])

    with patch(
        "homeassistant.components.airtouch4.config_flow.AirTouch",
        return_value=mock_airtouch,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"host": "0.0.0.1"}
        )

        assert result2["type"] == "form"
        assert result2["errors"] == {"base": "no_units"}
