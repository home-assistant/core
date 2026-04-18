"""Test the Russound RIO config flow."""

from ipaddress import ip_address
from unittest.mock import AsyncMock

from homeassistant.components.russound_rio.const import DOMAIN, TYPE_SERIAL, TYPE_TCP
from homeassistant.config_entries import SOURCE_USER, SOURCE_ZEROCONF, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_TYPE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .const import (
    MOCK_RECONFIGURATION_SERIAL_ENTRY_DATA,
    MOCK_RECONFIGURATION_SERIAL_STEP_INPUT,
    MOCK_RECONFIGURATION_TCP_ENTRY_DATA,
    MOCK_RECONFIGURATION_TCP_STEP_INPUT,
    MOCK_SERIAL_CONFIG,
    MOCK_SERIAL_STEP_INPUT,
    MOCK_TCP_CONFIG,
    MOCK_TCP_STEP_INPUT,
    MODEL,
)

from tests.common import MockConfigEntry

ZEROCONF_DISCOVERY = ZeroconfServiceInfo(
    ip_address=ip_address("192.168.20.17"),
    ip_addresses=[ip_address("192.168.20.17")],
    hostname="controller1.local.",
    name="controller1._stream-magic._tcp.local.",
    port=9621,
    type="_rio._tcp.local.",
    properties={
        "txtvers": "0",
        "productType": "2",
        "productId": "59",
        "version": "07.04.00",
        "buildDate": "Jul 8 2019",
        "localName": "0",
    },
)


async def test_user_flow_tcp_creates_entry(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_russound_client: AsyncMock
) -> None:
    """Test TCP user flow creates an entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_TYPE: TYPE_TCP},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "tcp"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        MOCK_TCP_STEP_INPUT,
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == MODEL
    assert result["data"] == MOCK_TCP_CONFIG
    assert len(mock_setup_entry.mock_calls) == 1
    assert result["result"].unique_id == "00:11:22:33:44:55"


async def test_tcp_flow_cannot_connect_then_recovers(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_russound_client: AsyncMock
) -> None:
    """Test TCP flow handles cannot connect and recovers."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_TYPE: TYPE_TCP},
    )
    assert result["step_id"] == "tcp"

    mock_russound_client.connect.side_effect = TimeoutError

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        MOCK_TCP_STEP_INPUT,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "tcp"
    assert result["errors"] == {"base": "cannot_connect"}

    mock_russound_client.connect.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        MOCK_TCP_STEP_INPUT,
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == MOCK_TCP_CONFIG
    assert len(mock_setup_entry.mock_calls) == 1


async def test_tcp_flow_duplicate_aborts(
    hass: HomeAssistant,
    mock_russound_client: AsyncMock,
    mock_setup_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test duplicate TCP flow aborts."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_TYPE: TYPE_TCP},
    )
    assert result["step_id"] == "tcp"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        MOCK_TCP_STEP_INPUT,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_zeroconf_flow(
    hass: HomeAssistant,
    mock_russound_client: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test zeroconf flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=ZEROCONF_DISCOVERY,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "MCA-C5"
    assert result["data"] == {
        CONF_TYPE: TYPE_TCP,
        CONF_HOST: "192.168.20.17",
        CONF_PORT: 9621,
    }
    assert result["result"].unique_id == "00:11:22:33:44:55"


async def test_zeroconf_flow_errors(
    hass: HomeAssistant,
    mock_russound_client: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test zeroconf flow errors."""
    mock_russound_client.connect.side_effect = TimeoutError

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=ZEROCONF_DISCOVERY,
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"

    mock_russound_client.connect.side_effect = None

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=ZEROCONF_DISCOVERY,
    )
    assert result["step_id"] == "discovery_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_TYPE: TYPE_TCP,
        CONF_HOST: "192.168.20.17",
        CONF_PORT: 9621,
    }


async def test_zeroconf_duplicate(
    hass: HomeAssistant,
    mock_russound_client: AsyncMock,
    mock_setup_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test zeroconf duplicate."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=ZEROCONF_DISCOVERY,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_zeroconf_duplicate_different_ip(
    hass: HomeAssistant,
    mock_russound_client: AsyncMock,
    mock_setup_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test zeroconf duplicate with IP update."""
    mock_config_entry.add_to_hass(hass)

    zeroconf_discovery_different_ip = ZeroconfServiceInfo(
        ip_address=ip_address("192.168.20.18"),
        ip_addresses=[ip_address("192.168.20.18")],
        hostname="controller1.local.",
        name="controller1._stream-magic._tcp.local.",
        port=9621,
        type="_rio._tcp.local.",
        properties={
            "txtvers": "0",
            "productType": "2",
            "productId": "59",
            "version": "07.04.00",
            "buildDate": "Jul 8 2019",
            "localName": "0",
        },
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=zeroconf_discovery_different_ip,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"

    entry = hass.config_entries.async_get_entry(mock_config_entry.entry_id)
    assert entry
    assert entry.data == {
        CONF_TYPE: TYPE_TCP,
        CONF_HOST: "192.168.20.18",
        CONF_PORT: 9621,
    }


async def test_user_flow_after_zeroconf_started(
    hass: HomeAssistant,
    mock_russound_client: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test user flow after zeroconf started."""
    await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=ZEROCONF_DISCOVERY,
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert len(hass.config_entries.flow.async_progress(DOMAIN)) == 2
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_TYPE: TYPE_TCP},
    )
    assert result["step_id"] == "tcp"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        MOCK_TCP_STEP_INPUT,
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert not hass.config_entries.flow.async_progress(DOMAIN)


async def _start_reconfigure_flow(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> ConfigFlowResult:
    """Initialize reconfigure flow."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    return result


async def test_reconfigure_tcp_flow(
    hass: HomeAssistant,
    mock_russound_client: AsyncMock,
    mock_setup_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test TCP reconfigure flow."""
    result = await _start_reconfigure_flow(hass, mock_config_entry)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_TYPE: TYPE_TCP},
    )
    assert result["step_id"] == "tcp"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        MOCK_RECONFIGURATION_TCP_STEP_INPUT,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"

    entry = hass.config_entries.async_get_entry(mock_config_entry.entry_id)
    assert entry
    assert entry.data == MOCK_RECONFIGURATION_TCP_ENTRY_DATA


async def test_reconfigure_unique_id_mismatch(
    hass: HomeAssistant,
    mock_russound_client: AsyncMock,
    mock_setup_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Ensure reconfigure flow aborts when the device changes."""
    mock_russound_client.controllers[1].mac_address = "different_mac"

    result = await _start_reconfigure_flow(hass, mock_config_entry)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_TYPE: TYPE_TCP},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "tcp"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        MOCK_RECONFIGURATION_TCP_STEP_INPUT,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "wrong_device"


async def test_user_flow_serial_creates_entry(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_russound_client: AsyncMock,
) -> None:
    """Test serial user flow creates an entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_TYPE: TYPE_SERIAL},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "serial"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        MOCK_SERIAL_STEP_INPUT,
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == MODEL
    assert result["data"] == MOCK_SERIAL_CONFIG
    assert len(mock_setup_entry.mock_calls) == 1
    assert result["result"].unique_id == "00:11:22:33:44:55"


async def test_serial_flow_cannot_connect_then_recovers(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_russound_client: AsyncMock,
) -> None:
    """Test serial flow handles cannot connect and recovers."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_TYPE: TYPE_SERIAL},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "serial"

    mock_russound_client.connect.side_effect = TimeoutError

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        MOCK_SERIAL_STEP_INPUT,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "serial"
    assert result["errors"] == {"base": "cannot_connect"}

    mock_russound_client.connect.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        MOCK_SERIAL_STEP_INPUT,
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == MODEL
    assert result["data"] == MOCK_SERIAL_CONFIG
    assert len(mock_setup_entry.mock_calls) == 1


async def test_serial_flow_duplicate_aborts(
    hass: HomeAssistant,
    mock_russound_client: AsyncMock,
    mock_setup_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test duplicate serial flow aborts."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_TYPE: TYPE_SERIAL},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "serial"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        MOCK_SERIAL_STEP_INPUT,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reconfigure_serial_flow(
    hass: HomeAssistant,
    mock_russound_client: AsyncMock,
    mock_setup_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test serial reconfigure flow."""
    result = await _start_reconfigure_flow(hass, mock_config_entry)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_TYPE: TYPE_SERIAL},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "serial"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        MOCK_RECONFIGURATION_SERIAL_STEP_INPUT,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"

    entry = hass.config_entries.async_get_entry(mock_config_entry.entry_id)
    assert entry
    assert entry.data == MOCK_RECONFIGURATION_SERIAL_ENTRY_DATA


async def test_reconfigure_serial_unique_id_mismatch(
    hass: HomeAssistant,
    mock_russound_client: AsyncMock,
    mock_setup_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Ensure serial reconfigure aborts when device changes."""
    mock_russound_client.controllers[1].mac_address = "different_mac"

    result = await _start_reconfigure_flow(hass, mock_config_entry)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_TYPE: TYPE_SERIAL},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "serial"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        MOCK_RECONFIGURATION_SERIAL_STEP_INPUT,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "wrong_device"
