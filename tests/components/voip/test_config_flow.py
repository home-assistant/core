"""Test VoIP config flow."""
from unittest.mock import Mock, patch

from homeassistant import config_entries
from homeassistant.components import voip
from homeassistant.const import CONF_IP_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_form_user(hass: HomeAssistant) -> None:
    """Test user form config flow."""

    result = await hass.config_entries.flow.async_init(
        voip.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert not result["errors"]

    with patch(
        "homeassistant.components.voip.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_IP_ADDRESS: "127.0.0.1"},
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_IP_ADDRESS: "127.0.0.1"}
    assert len(mock_setup_entry.mock_calls) == 1


async def test_invalid_ip(hass: HomeAssistant) -> None:
    """Test user form config flow with invalid ip address."""

    result = await hass.config_entries.flow.async_init(
        voip.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert not result["errors"]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_IP_ADDRESS: "not an ip address"},
    )
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {CONF_IP_ADDRESS: "invalid_ip_address"}


async def test_unload_entry(hass: HomeAssistant) -> None:
    """Test removing VoIP closes transport."""
    entry = MockConfigEntry(
        domain=voip.DOMAIN,
        data={
            CONF_IP_ADDRESS: "127.0.0.1",
        },
    )
    entry.add_to_hass(hass)
    transport = Mock(spec=["close"])

    with patch(
        "homeassistant.components.voip._create_sip_server",
        return_value=transport,
    ):
        assert await voip.async_setup_entry(hass, entry)
        assert await voip.async_unload_entry(hass, entry)
        assert len(transport.close.mock_calls) == 1
