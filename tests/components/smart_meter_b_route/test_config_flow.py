"""Test the Smart Meter B-route config flow."""

from collections.abc import Generator
from unittest.mock import AsyncMock, Mock, patch

from momonga import MomongaSkJoinFailure, MomongaSkScanFailure
import pytest
from serial.tools.list_ports_linux import SysFS

from homeassistant import config_entries
from homeassistant.components.smart_meter_b_route.const import DOMAIN, ENTRY_TITLE
from homeassistant.const import CONF_DEVICE, CONF_ID, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import user_input


@pytest.fixture
def mock_comports() -> Generator[Mock]:
    """Override comports."""
    with patch(
        "homeassistant.components.smart_meter_b_route.config_flow.comports",
        return_value=[SysFS("/dev/ttyUSB41"), SysFS("/dev/ttyUSB42")],
    ) as mock:
        yield mock


@pytest.fixture
def mock_serial(read_until_response=b"OK 00") -> Generator[Mock]:
    """Mock for Serial class."""

    class MockSerial:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def write(self, *args, **kwargs) -> None:
            pass

        def readline(self) -> bytes:
            return b""

        def read_until(self, *args, **kwargs) -> bytes:
            return read_until_response

        def flush(self) -> None:
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args, **kwargs) -> None:
            pass

    with patch(
        "homeassistant.components.smart_meter_b_route.config_flow.Serial", MockSerial
    ):
        yield MockSerial


@pytest.fixture
def mock_momonga(exception=None) -> Generator[Mock]:
    """Mock for Serial class."""

    class MockMomonga:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args, **kwargs) -> None:
            pass

    with patch(
        "homeassistant.components.smart_meter_b_route.config_flow.Momonga",
        MockMomonga,
    ):
        yield MockMomonga


async def test_form(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_comports: Mock,
    mock_serial: Mock,
    mock_momonga: Mock,
) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert not result["errors"]
    with (
        patch.object(
            mock_serial,
            "__init__",
        ) as mock_serial_init,
        patch.object(mock_momonga, "__init__") as mock_momonga_init,
    ):
        mock_serial_init.return_value = None
        mock_momonga_init.return_value = None
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input,
        )
        await hass.async_block_till_done()

        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["title"] == ENTRY_TITLE
        assert result["data"] == user_input
        mock_setup_entry.assert_called_once()
        mock_comports.assert_called_once()
        mock_serial_init.assert_called_once_with(user_input[CONF_DEVICE], 115200)
        mock_momonga_init.assert_called_once_with(
            dev=user_input[CONF_DEVICE],
            rbid=user_input[CONF_ID],
            pwd=user_input[CONF_PASSWORD],
        )


@pytest.mark.parametrize(
    ("error", "message"),
    [
        (MomongaSkJoinFailure, "invalid_auth"),
        (MomongaSkScanFailure, "cannot_connect"),
        (Exception, "unknown"),
    ],
)
async def test_form_errors(
    hass: HomeAssistant,
    error: Exception,
    message: str,
    mock_comports: Mock,
    mock_serial: Mock,
    mock_momonga: Mock,
) -> None:
    """Test we handle error."""
    result_init = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    with (
        patch.object(mock_serial, "__init__") as mock_serial_init,
        patch.object(mock_momonga, "__init__", side_effect=error) as mock_momonga_init,
    ):
        mock_serial_init.return_value = None
        result_configure = await hass.config_entries.flow.async_configure(
            result_init["flow_id"],
            user_input,
        )

        assert result_configure["type"] is FlowResultType.FORM
        assert result_configure["errors"] == {"base": message}
        await hass.async_block_till_done()
        mock_comports.assert_called()
        mock_serial_init.assert_called_once_with(user_input[CONF_DEVICE], 115200)
        mock_momonga_init.assert_called_once_with(
            dev=user_input[CONF_DEVICE],
            rbid=user_input[CONF_ID],
            pwd=user_input[CONF_PASSWORD],
        )

        hass.config_entries.flow.async_abort(result_init["flow_id"])
