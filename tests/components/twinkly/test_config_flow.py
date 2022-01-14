"""Tests for the config_flow of the twinly component."""
from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.components import dhcp
from homeassistant.components.twinkly.const import (
    DOMAIN as TWINKLY_DOMAIN,
    ENTRY_DATA_HOST,
    ENTRY_DATA_ID,
    ENTRY_DATA_MODEL,
    ENTRY_DATA_NAME,
)

from . import TEST_MODEL, ClientMock

from tests.common import MockConfigEntry


async def test_invalid_host(hass):
    """Test the failure when invalid host provided."""
    client = ClientMock()
    client.is_offline = True
    with patch(
        "homeassistant.components.twinkly.config_flow.Twinkly", return_value=client
    ):
        result = await hass.config_entries.flow.async_init(
            TWINKLY_DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] == "form"
        assert result["step_id"] == "user"
        assert result["errors"] == {}
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {ENTRY_DATA_HOST: "dummy"},
        )

    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["errors"] == {ENTRY_DATA_HOST: "cannot_connect"}


async def test_success_flow(hass):
    """Test that an entity is created when the flow completes."""
    client = ClientMock()
    with patch(
        "homeassistant.components.twinkly.config_flow.Twinkly", return_value=client
    ), patch("homeassistant.components.twinkly.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_init(
            TWINKLY_DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        assert result["type"] == "form"
        assert result["step_id"] == "user"
        assert result["errors"] == {}

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {ENTRY_DATA_HOST: "dummy"},
        )

    assert result["type"] == "create_entry"
    assert result["title"] == client.id
    assert result["data"] == {
        ENTRY_DATA_HOST: "dummy",
        ENTRY_DATA_ID: client.id,
        ENTRY_DATA_NAME: client.id,
        ENTRY_DATA_MODEL: TEST_MODEL,
    }


async def test_dhcp_can_confirm(hass):
    """Test DHCP discovery flow can confirm right away."""
    client = ClientMock()
    with patch(
        "homeassistant.components.twinkly.config_flow.Twinkly", return_value=client
    ):
        result = await hass.config_entries.flow.async_init(
            TWINKLY_DOMAIN,
            context={"source": config_entries.SOURCE_DHCP},
            data=dhcp.DhcpServiceInfo(
                hostname="Twinkly_XYZ",
                ip="1.2.3.4",
                macaddress="aa:bb:cc:dd:ee:ff",
            ),
        )
        await hass.async_block_till_done()

    assert result["type"] == "form"
    assert result["step_id"] == "discovery_confirm"


async def test_dhcp_success(hass):
    """Test DHCP discovery flow success."""
    client = ClientMock()
    with patch(
        "homeassistant.components.twinkly.config_flow.Twinkly", return_value=client
    ), patch("homeassistant.components.twinkly.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_init(
            TWINKLY_DOMAIN,
            context={"source": config_entries.SOURCE_DHCP},
            data=dhcp.DhcpServiceInfo(
                hostname="Twinkly_XYZ",
                ip="1.2.3.4",
                macaddress="aa:bb:cc:dd:ee:ff",
            ),
        )
        await hass.async_block_till_done()

        assert result["type"] == "form"
        assert result["step_id"] == "discovery_confirm"

        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] == "create_entry"
    assert result["title"] == client.id
    assert result["data"] == {
        ENTRY_DATA_HOST: "1.2.3.4",
        ENTRY_DATA_ID: client.id,
        ENTRY_DATA_NAME: client.id,
        ENTRY_DATA_MODEL: TEST_MODEL,
    }


async def test_dhcp_already_exists(hass):
    """Test DHCP discovery flow that fails to connect."""
    client = ClientMock()

    entry = MockConfigEntry(
        domain=TWINKLY_DOMAIN,
        data={
            ENTRY_DATA_HOST: "1.2.3.4",
            ENTRY_DATA_ID: client.id,
            ENTRY_DATA_NAME: client.id,
            ENTRY_DATA_MODEL: TEST_MODEL,
        },
        unique_id=client.id,
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.twinkly.config_flow.Twinkly", return_value=client
    ):
        result = await hass.config_entries.flow.async_init(
            TWINKLY_DOMAIN,
            context={"source": config_entries.SOURCE_DHCP},
            data=dhcp.DhcpServiceInfo(
                hostname="Twinkly_XYZ",
                ip="1.2.3.4",
                macaddress="aa:bb:cc:dd:ee:ff",
            ),
        )
        await hass.async_block_till_done()

    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"
