"""Test the IntelliFire config flow."""
from unittest.mock import AsyncMock, MagicMock

from homeassistant import config_entries
from homeassistant.components import dhcp
from homeassistant.components.intellifire.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import RESULT_TYPE_CREATE_ENTRY, RESULT_TYPE_FORM


async def test_form(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_intellifire_config_flow: MagicMock,
    mock_fireplace_finder: AsyncMock,
) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] == {}

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "host": "1.1.1.1",
        },
    )
    await hass.async_block_till_done()

    assert result2["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result2["title"] == "Fireplace"
    assert result2["data"] == {"host": "1.1.1.1"}

    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_cannot_connect(
    hass: HomeAssistant,
    mock_intellifire_config_flow: MagicMock,
    mock_fireplace_finder: AsyncMock,
) -> None:
    """Test we handle cannot connect error."""
    mock_intellifire_config_flow.poll.side_effect = ConnectionError

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "host": "1.1.1.1",
        },
    )

    assert result2["type"] == RESULT_TYPE_FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_dhcp_discovery_good(
    hass: HomeAssistant,
    mock_intellifire_config_flow: MagicMock,
    mock_fireplace_finder: AsyncMock,
) -> None:
    """Test successful DHCP Discovery."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_DHCP},
        data=dhcp.DhcpServiceInfo(
            ip="1.1.1.1",
            macaddress="AA:BB:CC:DD:EE:FF",
            hostname="zentrios-Test",
        ),
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "host": "1.1.1.1",
        },
    )

    assert result2["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result2["title"] == "Fireplace"
    assert result2["data"] == {"host": "1.1.1.1"}


async def test_dhcp_discovery_bad(
    hass: HomeAssistant,
    mock_intellifire_config_flow: MagicMock,
    mock_fireplace_finder: AsyncMock,
) -> None:
    """Test failed DHCP Discovery."""

    mock_intellifire_config_flow.poll.side_effect = ConnectionError

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_DHCP},
        data=dhcp.DhcpServiceInfo(
            ip="1.1.1.1",
            macaddress="AA:BB:CC:DD:EE:FF",
            hostname="zentrios-Evil",
        ),
    )

    print(result)
    print(result)
