"""Test the Firmata config flow."""
from unittest.mock import patch

from pymata_express.pymata_express_serial import serial

from homeassistant import config_entries
from homeassistant.components.firmata.const import CONF_SERIAL_PORT, DOMAIN
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant


async def test_import_cannot_connect_pymata(hass: HomeAssistant) -> None:
    """Test we fail with an invalid board."""

    with patch(
        "homeassistant.components.firmata.board.PymataExpress.start_aio",
        side_effect=RuntimeError,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={CONF_SERIAL_PORT: "/dev/nonExistent"},
        )

        assert result["type"] == "abort"
        assert result["reason"] == "cannot_connect"


async def test_import_cannot_connect_serial(hass: HomeAssistant) -> None:
    """Test we fail with an invalid board."""

    with patch(
        "homeassistant.components.firmata.board.PymataExpress.start_aio",
        side_effect=serial.serialutil.SerialException,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={CONF_SERIAL_PORT: "/dev/nonExistent"},
        )

        assert result["type"] == "abort"
        assert result["reason"] == "cannot_connect"


async def test_import_cannot_connect_serial_timeout(hass: HomeAssistant) -> None:
    """Test we fail with an invalid board."""

    with patch(
        "homeassistant.components.firmata.board.PymataExpress.start_aio",
        side_effect=serial.serialutil.SerialTimeoutException,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={CONF_SERIAL_PORT: "/dev/nonExistent"},
        )

        assert result["type"] == "abort"
        assert result["reason"] == "cannot_connect"


async def test_import(hass: HomeAssistant) -> None:
    """Test we create an entry from config."""

    with patch(
        "homeassistant.components.firmata.board.PymataExpress", autospec=True
    ), patch(
        "homeassistant.components.firmata.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.firmata.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={CONF_SERIAL_PORT: "/dev/nonExistent"},
        )

        assert result["type"] == "create_entry"
        assert result["title"] == "serial-/dev/nonExistent"
        assert result["data"] == {
            CONF_NAME: "serial-/dev/nonExistent",
            CONF_SERIAL_PORT: "/dev/nonExistent",
        }
        await hass.async_block_till_done()
        assert len(mock_setup.mock_calls) == 1
        assert len(mock_setup_entry.mock_calls) == 1
