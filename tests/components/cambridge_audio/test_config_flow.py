"""Tests for the Cambridge Audio config flow."""

from ipaddress import ip_address
from unittest.mock import AsyncMock

from aiostreammagic import StreamMagicError

from homeassistant.components.cambridge_audio.const import DOMAIN
from homeassistant.components.zeroconf import ZeroconfServiceInfo
from homeassistant.config_entries import SOURCE_USER, SOURCE_ZEROCONF
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

ZEROCONF_DISCOVERY = ZeroconfServiceInfo(
    ip_address=ip_address("192.168.20.218"),
    ip_addresses=[ip_address("192.168.20.218")],
    hostname="cambridge_CXNv2.local.",
    name="cambridge_CXNv2._stream-magic._tcp.local.",
    port=80,
    type="_stream-magic._tcp.local.",
    properties={
        "serial": "0020c2d8",
        "hcv": "3764",
        "software": "v022-a-151+a",
        "model": "CXNv2",
        "udn": "02680b5c-1320-4d54-9f7c-3cfe915ad4c3",
    },
)


async def test_full_flow(
    hass: HomeAssistant,
    mock_stream_magic_client: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test full flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "192.168.20.218"},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Cambridge Audio CXNv2"
    assert result["data"] == {
        CONF_HOST: "192.168.20.218",
    }
    assert result["result"].unique_id == "0020c2d8"


async def test_flow_errors(
    hass: HomeAssistant,
    mock_stream_magic_client: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test flow errors."""
    mock_stream_magic_client.connect.side_effect = StreamMagicError

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "192.168.20.218"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    mock_stream_magic_client.connect.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "192.168.20.218"},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_duplicate(
    hass: HomeAssistant,
    mock_stream_magic_client: AsyncMock,
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
        {CONF_HOST: "192.168.20.218"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_zeroconf_flow(
    hass: HomeAssistant,
    mock_stream_magic_client: AsyncMock,
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
    assert result["title"] == "Cambridge Audio CXNv2"
    assert result["data"] == {
        CONF_HOST: "192.168.20.218",
    }
    assert result["result"].unique_id == "0020c2d8"


async def test_zeroconf_flow_errors(
    hass: HomeAssistant,
    mock_stream_magic_client: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test zeroconf flow."""
    mock_stream_magic_client.connect.side_effect = StreamMagicError
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=ZEROCONF_DISCOVERY,
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"

    mock_stream_magic_client.connect.side_effect = None

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
    assert result["title"] == "Cambridge Audio CXNv2"
    assert result["data"] == {
        CONF_HOST: "192.168.20.218",
    }
    assert result["result"].unique_id == "0020c2d8"


async def test_zeroconf_duplicate(
    hass: HomeAssistant,
    mock_stream_magic_client: AsyncMock,
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
