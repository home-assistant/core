"""Test the Aurora ABB PowerOne Solar PV config flow."""

from unittest.mock import MagicMock, patch

from serial.tools import list_ports_common

from homeassistant import config_entries
from homeassistant.components.aurora_abb_powerone.aurora_client import (
    AuroraClientError,
    AuroraInverterIdentifier,
)
from homeassistant.components.aurora_abb_powerone.const import (
    CONF_INVERTER_SERIAL_ADDRESS,
    CONF_SERIAL_COMPORT,
    CONF_TCP_HOST,
    CONF_TCP_PORT,
    CONF_TRANSPORT,
    DOMAIN,
    TCP_PORT_DEFAULT,
    TRANSPORT_SERIAL,
    TRANSPORT_TCP,
)
from homeassistant.const import ATTR_SERIAL_NUMBER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import MOCK_INVERTER_DATA
from .const import MOCK_FIRMWARE, MOCK_MODEL, MOCK_SERIAL_NUMBER

from tests.common import MockConfigEntry

MOCK_IDENTIFIER = AuroraInverterIdentifier(
    serial_number=MOCK_SERIAL_NUMBER,
    model=MOCK_MODEL,
    firmware=MOCK_FIRMWARE,
)

FAKE_COMPORTS = [list_ports_common.ListPortInfo("/dev/ttyUSB7")]


def _mock_aurora_client_setup() -> MagicMock:
    """Return a mock AuroraClient instance for setup (no real connections)."""
    mock_client = MagicMock()
    mock_client.try_connect_and_fetch_data.return_value = MOCK_INVERTER_DATA
    return mock_client


async def test_serial_flow_success(hass: HomeAssistant) -> None:
    """Test a complete successful serial setup flow."""
    mock_setup_client = _mock_aurora_client_setup()
    with (
        patch(
            "serial.tools.list_ports.comports",
            return_value=FAKE_COMPORTS,
        ),
        patch(
            "homeassistant.components.aurora_abb_powerone.config_flow.validate_and_connect_serial",
            return_value=MOCK_IDENTIFIER,
        ),
        patch(
            "homeassistant.components.aurora_abb_powerone.AuroraClient.from_serial",
            return_value=mock_setup_client,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "choose_transport"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_TRANSPORT: TRANSPORT_SERIAL},
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "configure_serial"
        assert result["errors"] == {}

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_SERIAL_COMPORT: "/dev/ttyUSB7", CONF_INVERTER_SERIAL_ADDRESS: 3},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_TRANSPORT: TRANSPORT_SERIAL,
        CONF_INVERTER_SERIAL_ADDRESS: 3,
        CONF_SERIAL_COMPORT: "/dev/ttyUSB7",
        ATTR_SERIAL_NUMBER: MOCK_SERIAL_NUMBER,
        "model": MOCK_MODEL,
        "firmware": MOCK_FIRMWARE,
    }


async def test_tcp_flow_success(hass: HomeAssistant) -> None:
    """Test a complete successful TCP setup flow."""
    mock_setup_client = _mock_aurora_client_setup()
    with (
        patch(
            "homeassistant.components.aurora_abb_powerone.config_flow.validate_and_connect_tcp",
            return_value=MOCK_IDENTIFIER,
        ),
        patch(
            "homeassistant.components.aurora_abb_powerone.AuroraClient.from_tcp",
            return_value=mock_setup_client,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "choose_transport"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_TRANSPORT: TRANSPORT_TCP},
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "configure_tcp"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_TCP_HOST: "127.0.0.1",
                CONF_TCP_PORT: TCP_PORT_DEFAULT,
                CONF_INVERTER_SERIAL_ADDRESS: 3,
            },
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_TRANSPORT: TRANSPORT_TCP,
        CONF_INVERTER_SERIAL_ADDRESS: 3,
        CONF_TCP_HOST: "127.0.0.1",
        CONF_TCP_PORT: TCP_PORT_DEFAULT,
        ATTR_SERIAL_NUMBER: MOCK_SERIAL_NUMBER,
        "model": MOCK_MODEL,
        "firmware": MOCK_FIRMWARE,
    }


async def test_serial_flow_no_comports(hass: HomeAssistant) -> None:
    """Test that flow aborts when no serial ports are available."""
    with patch(
        "serial.tools.list_ports.comports",
        return_value=[],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "choose_transport"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_TRANSPORT: TRANSPORT_SERIAL},
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_serial_ports"


async def test_serial_flow_invalid_serial_port(hass: HomeAssistant) -> None:
    """Test serial flow handles invalid serial port error."""
    with patch(
        "serial.tools.list_ports.comports",
        return_value=FAKE_COMPORTS,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_TRANSPORT: TRANSPORT_SERIAL},
        )

        with patch(
            "homeassistant.components.aurora_abb_powerone.config_flow.validate_and_connect_serial",
            side_effect=OSError(19, "No such device"),
        ):
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                {CONF_SERIAL_COMPORT: "/dev/ttyUSB7", CONF_INVERTER_SERIAL_ADDRESS: 3},
            )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_serial_port"}


async def test_serial_flow_cannot_open_port(hass: HomeAssistant) -> None:
    """Test serial flow handles cannot open port error."""
    with patch(
        "serial.tools.list_ports.comports",
        return_value=FAKE_COMPORTS,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_TRANSPORT: TRANSPORT_SERIAL},
        )

        with patch(
            "homeassistant.components.aurora_abb_powerone.config_flow.validate_and_connect_serial",
            side_effect=AuroraClientError("could not open port /dev/ttyUSB7"),
        ):
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                {CONF_SERIAL_COMPORT: "/dev/ttyUSB7", CONF_INVERTER_SERIAL_ADDRESS: 3},
            )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_open_serial_port"}


async def test_serial_flow_cannot_connect(hass: HomeAssistant) -> None:
    """Test serial flow handles generic connection error and can recover."""
    mock_setup_client = _mock_aurora_client_setup()
    with patch(
        "serial.tools.list_ports.comports",
        return_value=FAKE_COMPORTS,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_TRANSPORT: TRANSPORT_SERIAL},
        )

        with patch(
            "homeassistant.components.aurora_abb_powerone.config_flow.validate_and_connect_serial",
            side_effect=AuroraClientError("No response after 10 seconds"),
        ):
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                {CONF_SERIAL_COMPORT: "/dev/ttyUSB7", CONF_INVERTER_SERIAL_ADDRESS: 3},
            )
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"base": "cannot_connect"}

        # Verify the flow can recover and succeed after error
        with (
            patch(
                "homeassistant.components.aurora_abb_powerone.config_flow.validate_and_connect_serial",
                return_value=MOCK_IDENTIFIER,
            ),
            patch(
                "homeassistant.components.aurora_abb_powerone.AuroraClient.from_serial",
                return_value=mock_setup_client,
            ),
        ):
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                {CONF_SERIAL_COMPORT: "/dev/ttyUSB7", CONF_INVERTER_SERIAL_ADDRESS: 3},
            )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_tcp_flow_cannot_connect(hass: HomeAssistant) -> None:
    """Test TCP flow handles connection error and can recover."""
    mock_setup_client = _mock_aurora_client_setup()
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_TRANSPORT: TRANSPORT_TCP},
    )

    with patch(
        "homeassistant.components.aurora_abb_powerone.config_flow.validate_and_connect_tcp",
        side_effect=AuroraClientError("Connection refused"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_TCP_HOST: "127.0.0.1",
                CONF_TCP_PORT: TCP_PORT_DEFAULT,
                CONF_INVERTER_SERIAL_ADDRESS: 3,
            },
        )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    # Verify the flow can recover and succeed after error
    with (
        patch(
            "homeassistant.components.aurora_abb_powerone.config_flow.validate_and_connect_tcp",
            return_value=MOCK_IDENTIFIER,
        ),
        patch(
            "homeassistant.components.aurora_abb_powerone.AuroraClient.from_tcp",
            return_value=mock_setup_client,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_TCP_HOST: "127.0.0.1",
                CONF_TCP_PORT: TCP_PORT_DEFAULT,
                CONF_INVERTER_SERIAL_ADDRESS: 3,
            },
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_flow_already_configured(hass: HomeAssistant) -> None:
    """Test that flow aborts if the device is already configured."""
    existing_entry = MockConfigEntry(
        domain=DOMAIN,
        data={},
        unique_id=MOCK_SERIAL_NUMBER,
    )
    existing_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_TRANSPORT: TRANSPORT_TCP},
    )

    with patch(
        "homeassistant.components.aurora_abb_powerone.config_flow.validate_and_connect_tcp",
        return_value=MOCK_IDENTIFIER,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_TCP_HOST: "127.0.0.1",
                CONF_TCP_PORT: TCP_PORT_DEFAULT,
                CONF_INVERTER_SERIAL_ADDRESS: 3,
            },
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reconfigure_serial_success(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test successful reconfiguration with serial transport."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "serial.tools.list_ports.comports",
        return_value=FAKE_COMPORTS,
    ):
        result = await mock_config_entry.start_reconfigure_flow(hass)
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "choose_transport"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_TRANSPORT: TRANSPORT_SERIAL},
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "configure_serial"

        mock_setup_client = _mock_aurora_client_setup()
        with (
            patch(
                "homeassistant.components.aurora_abb_powerone.config_flow.validate_and_connect_serial",
                return_value=MOCK_IDENTIFIER,
            ),
            patch(
                "homeassistant.components.aurora_abb_powerone.AuroraClient.from_serial",
                return_value=mock_setup_client,
            ),
        ):
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                {CONF_SERIAL_COMPORT: "/dev/ttyUSB7", CONF_INVERTER_SERIAL_ADDRESS: 3},
            )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data[CONF_TRANSPORT] == TRANSPORT_SERIAL


async def test_reconfigure_tcp_success(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test successful reconfiguration switching to TCP transport."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reconfigure_flow(hass)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_TRANSPORT: TRANSPORT_TCP},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "configure_tcp"

    mock_setup_client = _mock_aurora_client_setup()
    with (
        patch(
            "homeassistant.components.aurora_abb_powerone.config_flow.validate_and_connect_tcp",
            return_value=MOCK_IDENTIFIER,
        ),
        patch(
            "homeassistant.components.aurora_abb_powerone.AuroraClient.from_tcp",
            return_value=mock_setup_client,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_TCP_HOST: "127.0.0.1",
                CONF_TCP_PORT: TCP_PORT_DEFAULT,
                CONF_INVERTER_SERIAL_ADDRESS: 3,
            },
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data[CONF_TRANSPORT] == TRANSPORT_TCP
    assert mock_config_entry.data[CONF_TCP_HOST] == "127.0.0.1"


async def test_reconfigure_unique_id_mismatch(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test reconfigure aborts when the inverter serial number doesn't match."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reconfigure_flow(hass)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_TRANSPORT: TRANSPORT_TCP},
    )

    different_identifier = AuroraInverterIdentifier(
        serial_number="DIFFERENT_SN",
        model=MOCK_MODEL,
        firmware=MOCK_FIRMWARE,
    )
    with patch(
        "homeassistant.components.aurora_abb_powerone.config_flow.validate_and_connect_tcp",
        return_value=different_identifier,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_TCP_HOST: "127.0.0.1",
                CONF_TCP_PORT: TCP_PORT_DEFAULT,
                CONF_INVERTER_SERIAL_ADDRESS: 3,
            },
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unique_id_mismatch"


async def test_serial_flow_other_os_error(hass: HomeAssistant) -> None:
    """Test serial flow handles non-errno-19 OS errors as cannot_connect."""
    with patch(
        "serial.tools.list_ports.comports",
        return_value=FAKE_COMPORTS,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_TRANSPORT: TRANSPORT_SERIAL},
        )

        with patch(
            "homeassistant.components.aurora_abb_powerone.config_flow.validate_and_connect_serial",
            side_effect=OSError(5, "Input/output error"),
        ):
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                {CONF_SERIAL_COMPORT: "/dev/ttyUSB7", CONF_INVERTER_SERIAL_ADDRESS: 3},
            )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_serial_flow_end_to_end_via_aurora_client(hass: HomeAssistant) -> None:
    """Test serial flow exercising validate_and_connect_serial with AuroraClient mocked."""
    mock_setup_client = _mock_aurora_client_setup()
    mock_setup_client.try_connect_and_fetch_identifier.return_value = MOCK_IDENTIFIER

    with (
        patch(
            "serial.tools.list_ports.comports",
            return_value=FAKE_COMPORTS,
        ),
        patch(
            "homeassistant.components.aurora_abb_powerone.aurora_client.AuroraClient.from_serial",
            return_value=mock_setup_client,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_TRANSPORT: TRANSPORT_SERIAL},
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_SERIAL_COMPORT: "/dev/ttyUSB7", CONF_INVERTER_SERIAL_ADDRESS: 3},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][ATTR_SERIAL_NUMBER] == MOCK_SERIAL_NUMBER


async def test_tcp_flow_end_to_end_via_aurora_client(hass: HomeAssistant) -> None:
    """Test TCP flow exercising validate_and_connect_tcp with AuroraClient mocked."""
    mock_setup_client = _mock_aurora_client_setup()
    mock_setup_client.try_connect_and_fetch_identifier.return_value = MOCK_IDENTIFIER

    with patch(
        "homeassistant.components.aurora_abb_powerone.aurora_client.AuroraClient.from_tcp",
        return_value=mock_setup_client,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_TRANSPORT: TRANSPORT_TCP},
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_TCP_HOST: "127.0.0.1",
                CONF_TCP_PORT: TCP_PORT_DEFAULT,
                CONF_INVERTER_SERIAL_ADDRESS: 3,
            },
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][ATTR_SERIAL_NUMBER] == MOCK_SERIAL_NUMBER
