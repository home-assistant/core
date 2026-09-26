"""Tests for the Profalux Neosol config flow."""

from unittest.mock import AsyncMock, MagicMock

from pyneosol import DongleNotFoundError, NotADongleError, TransportError
import pytest

from homeassistant.components.neosol.const import DOMAIN
from homeassistant.config_entries import SOURCE_USB, SOURCE_USER
from homeassistant.const import CONF_DEVICE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.usb import UsbServiceInfo

from . import MOCK_PORT, MOCK_SERIAL

from tests.common import MockConfigEntry

USB_DISCOVERY_INFO = UsbServiceInfo(
    device=MOCK_PORT,
    vid="10C4",
    pid="0003",
    serial_number="ABCDEF01",
    manufacturer="PROFALUX",
    description="KEELOQ USB Device",
)

# The probe fails either when opening the port, or when reading the identification.
PROBE_FAILURES = [
    pytest.param(
        "open", DongleNotFoundError("no such port"), "cannot_connect", id="no-port"
    ),
    pytest.param("open", TransportError("port busy"), "cannot_connect", id="port-busy"),
    pytest.param(
        "info", NotADongleError("no marker"), "not_a_dongle", id="not-a-dongle"
    ),
    pytest.param("info", RuntimeError("boom"), "unknown", id="unexpected"),
]

OTHER_PORT = "/dev/ttyACM1"
OTHER_SERIAL = "0099FFFF"

# A dongle counts as configured when an entry uses its port, or its serial number on
# another port. Only the latter needs a probe to be told apart.
ALREADY_CONFIGURED = [
    pytest.param(MOCK_PORT, OTHER_SERIAL, 0, id="same-port"),
    pytest.param(OTHER_PORT, MOCK_SERIAL, 1, id="same-dongle"),
]


def _fail_probe(
    mock_dongle_class: MagicMock, failing_call: str, exception: Exception
) -> None:
    """Make the probe fail, and clear the failure so the next attempt succeeds."""
    target = (
        mock_dongle_class.open
        if failing_call == "open"
        else mock_dongle_class.open.return_value.info
    )
    target.side_effect = exception


def _recover_probe(mock_dongle_class: MagicMock) -> None:
    """Undo what _fail_probe set up."""
    mock_dongle_class.open.side_effect = None
    mock_dongle_class.open.return_value.info.side_effect = None


async def test_user_flow(
    hass: HomeAssistant, mock_dongle: MagicMock, mock_setup_entry: AsyncMock
) -> None:
    """Test configuring a dongle by picking its serial port."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_DEVICE: MOCK_PORT}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Profalux Neosol"
    assert result["data"] == {CONF_DEVICE: MOCK_PORT}
    assert result["result"].unique_id == MOCK_SERIAL
    # The config entry setup owns the port, so the flow must not keep it open.
    mock_dongle.close.assert_awaited_once()
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.usefixtures("mock_setup_entry")
@pytest.mark.parametrize(("failing_call", "exception", "error"), PROBE_FAILURES)
async def test_user_flow_errors(
    hass: HomeAssistant,
    mock_dongle_class: MagicMock,
    failing_call: str,
    exception: Exception,
    error: str,
) -> None:
    """Test the user flow reports probe failures and recovers afterwards."""
    _fail_probe(mock_dongle_class, failing_call, exception)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_DEVICE: MOCK_PORT}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    _recover_probe(mock_dongle_class)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_DEVICE: MOCK_PORT}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("mock_setup_entry")
@pytest.mark.parametrize(
    "exception",
    [
        pytest.param(NotADongleError("no marker"), id="not-a-dongle"),
        pytest.param(RuntimeError("boom"), id="unexpected"),
    ],
)
async def test_port_released_when_identification_fails(
    hass: HomeAssistant, mock_dongle: MagicMock, exception: Exception
) -> None:
    """Test the probe closes the port whatever makes the identification fail."""
    mock_dongle.info.side_effect = exception

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_DEVICE: MOCK_PORT}
    )

    mock_dongle.close.assert_awaited_once()


@pytest.mark.parametrize(("entry_port", "entry_serial", "probes"), ALREADY_CONFIGURED)
async def test_user_flow_already_configured(
    hass: HomeAssistant,
    mock_dongle_class: MagicMock,
    entry_port: str,
    entry_serial: str,
    probes: int,
) -> None:
    """Test the user flow refuses a dongle that is already configured."""
    MockConfigEntry(
        domain=DOMAIN, data={CONF_DEVICE: entry_port}, unique_id=entry_serial
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_DEVICE: MOCK_PORT}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    # A port already in use is refused before the probe talks over it.
    assert mock_dongle_class.open.call_count == probes


@pytest.mark.parametrize(("entry_port", "entry_serial", "probes"), ALREADY_CONFIGURED)
async def test_usb_discovery_already_configured(
    hass: HomeAssistant,
    mock_dongle_class: MagicMock,
    entry_port: str,
    entry_serial: str,
    probes: int,
) -> None:
    """Test discovery aborts on a dongle that is already configured."""
    MockConfigEntry(
        domain=DOMAIN, data={CONF_DEVICE: entry_port}, unique_id=entry_serial
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USB}, data=USB_DISCOVERY_INFO
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert mock_dongle_class.open.call_count == probes


@pytest.mark.usefixtures("mock_dongle")
async def test_second_dongle(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test another dongle can be configured next to an existing one."""
    MockConfigEntry(
        domain=DOMAIN, data={CONF_DEVICE: OTHER_PORT}, unique_id=OTHER_SERIAL
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_DEVICE: MOCK_PORT}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == MOCK_SERIAL


@pytest.mark.usefixtures("mock_dongle")
async def test_usb_discovery_flow(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test a dongle plugged in is discovered and confirmed."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USB}, data=USB_DISCOVERY_INFO
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "usb_confirm"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_DEVICE: MOCK_PORT}
    assert result["result"].unique_id == MOCK_SERIAL
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(("failing_call", "exception", "reason"), PROBE_FAILURES)
async def test_usb_discovery_probe_failure(
    hass: HomeAssistant,
    mock_dongle_class: MagicMock,
    failing_call: str,
    exception: Exception,
    reason: str,
) -> None:
    """Test discovery aborts when the plugged device is not a usable dongle."""
    _fail_probe(mock_dongle_class, failing_call, exception)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USB}, data=USB_DISCOVERY_INFO
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == reason
