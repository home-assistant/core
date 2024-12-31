"""Test the Russound RIO config flow."""

from ipaddress import ip_address
from unittest.mock import AsyncMock

from homeassistant.components.russound_rio.const import DOMAIN
from homeassistant.components.zeroconf import ZeroconfServiceInfo
from homeassistant.config_entries import SOURCE_USER, SOURCE_ZEROCONF, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .const import MOCK_CONFIG, MOCK_RECONFIGURATION_CONFIG, MODEL

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


async def test_form(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_russound_client: AsyncMock
) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        MOCK_CONFIG,
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == MODEL
    assert result["data"] == MOCK_CONFIG
    assert len(mock_setup_entry.mock_calls) == 1
    assert result["result"].unique_id == "00:11:22:33:44:55"


async def test_form_cannot_connect(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_russound_client: AsyncMock
) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    mock_russound_client.connect.side_effect = TimeoutError
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        MOCK_CONFIG,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    # Recover with correct information
    mock_russound_client.connect.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        MOCK_CONFIG,
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == MODEL
    assert result["data"] == MOCK_CONFIG
    assert len(mock_setup_entry.mock_calls) == 1


async def test_duplicate(
    hass: HomeAssistant,
    mock_russound_client: AsyncMock,
    mock_setup_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test duplicate flow."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        MOCK_CONFIG,
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
        CONF_HOST: "192.168.20.17",
        CONF_PORT: 9621,
    }
    assert result["result"].unique_id == "00:11:22:33:44:55"


async def test_zeroconf_flow_errors(
    hass: HomeAssistant,
    mock_russound_client: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test zeroconf flow."""
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
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "MCA-C5"
    assert result["data"] == {
        CONF_HOST: "192.168.20.17",
        CONF_PORT: 9621,
    }
    assert result["result"].unique_id == "00:11:22:33:44:55"


async def test_zeroconf_duplicate(
    hass: HomeAssistant,
    mock_russound_client: AsyncMock,
    mock_setup_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test duplicate flow."""
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
    """Test duplicate flow with different IP."""
    mock_config_entry.add_to_hass(hass)

    ZEROCONF_DISCOVERY_DIFFERENT_IP = ZeroconfServiceInfo(
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
        data=ZEROCONF_DISCOVERY_DIFFERENT_IP,
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"

    entry = hass.config_entries.async_get_entry(mock_config_entry.entry_id)
    assert entry
    assert entry.data == {
        CONF_HOST: "192.168.20.18",
        CONF_PORT: 9621,
    }


async def test_user_flow_works_discovery(
    hass: HomeAssistant,
    mock_russound_client: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test user flow can continue after discovery happened."""
    await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=ZEROCONF_DISCOVERY,
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert len(hass.config_entries.flow.async_progress(DOMAIN)) == 2
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        MOCK_CONFIG,
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY

    assert not hass.config_entries.flow.async_progress(DOMAIN)


async def _start_reconfigure_flow(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> ConfigFlowResult:
    """Initialize a reconfigure flow."""
    mock_config_entry.add_to_hass(hass)

    reconfigure_result = await mock_config_entry.start_reconfigure_flow(hass)

    assert reconfigure_result["type"] is FlowResultType.FORM
    assert reconfigure_result["step_id"] == "reconfigure"

    return reconfigure_result


async def test_reconfigure_flow(
    hass: HomeAssistant,
    mock_russound_client: AsyncMock,
    mock_setup_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reconfigure flow."""

    reconfigure_result = await _start_reconfigure_flow(hass, mock_config_entry)

    result = await hass.config_entries.flow.async_configure(
        reconfigure_result["flow_id"],
        MOCK_RECONFIGURATION_CONFIG,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"

    entry = hass.config_entries.async_get_entry(mock_config_entry.entry_id)
    assert entry
    assert entry.data == {
        CONF_HOST: "192.168.20.70",
        CONF_PORT: 9622,
    }


async def test_reconfigure_unique_id_mismatch(
    hass: HomeAssistant,
    mock_russound_client: AsyncMock,
    mock_setup_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Ensure reconfigure flow aborts when the bride changes."""
    mock_russound_client.controllers[1].mac_address = "different_mac"

    reconfigure_result = await _start_reconfigure_flow(hass, mock_config_entry)

    result = await hass.config_entries.flow.async_configure(
        reconfigure_result["flow_id"],
        MOCK_RECONFIGURATION_CONFIG,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "wrong_device"
