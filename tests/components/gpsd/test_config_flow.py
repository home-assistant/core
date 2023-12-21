"""Test the GPSD config flow."""
from unittest.mock import AsyncMock, patch

from gps3.agps3threaded import GPSD_PORT as DEFAULT_PORT

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.gpsd import config_flow
from homeassistant.components.gpsd.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

HOST = "gpsd.local"


async def test_form(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}

    with patch("socket.socket") as mock_socket:
        mock_connect = mock_socket.return_value.connect
        mock_connect.return_value = None

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: HOST,
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == f"GPS {HOST}"
    assert result2["data"] == {
        CONF_HOST: HOST,
        CONF_PORT: DEFAULT_PORT,
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_connection_error(hass: HomeAssistant) -> None:
    """Test connection to host error."""
    with patch("socket.socket") as mock_socket:
        mock_connect = mock_socket.return_value.connect
        mock_connect.side_effect = OSError

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={CONF_HOST: "nonexistent.local", CONF_PORT: 1234},
        )

        assert result["type"] == "form"
        assert result["step_id"] == "user"
        assert result["errors"] == {"base": "cannot_connect"}


async def test_import(hass: HomeAssistant) -> None:
    """Test import step."""
    with patch("homeassistant.components.gpsd.config_flow.socket") as mock_socket:
        mock_connect = mock_socket.return_value.connect
        mock_connect.return_value = None

        flow = config_flow.GPSDConfigFlow()
        flow.hass = hass

        result = await flow.async_step_import(
            {CONF_HOST: HOST, CONF_PORT: 1234, CONF_NAME: "MyGPS"}
        )
        assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
        assert result["title"] == "MyGPS"
        assert result["data"] == {
            CONF_HOST: HOST,
            CONF_NAME: "MyGPS",
            CONF_PORT: 1234,
        }
