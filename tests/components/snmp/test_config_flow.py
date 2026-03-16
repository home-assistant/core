"""Tests for the SNMP config flow."""

from unittest.mock import patch

from pysnmp.proto.rfc1902 import OctetString

from homeassistant import config_entries
from homeassistant.components.snmp.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_user_flow_success(hass: HomeAssistant) -> None:
    """Test successful user setup flow."""
    # 1. Initialize the config flow in 'user' mode.
    # This simulates a user going to Settings -> Integrations -> Add Integration -> SNMP.
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    # We expect to see a FORM (the text boxes for host, community, etc.).
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    # 2. Simulate user filling the form and clicking 'Submit'.
    # We MOCK the network calls so we don't actually need a real SNMP device.
    with (
        patch(
            # Mocking the GET command to return a dummy value
            "homeassistant.components.snmp.config_flow.get_cmd",
            return_value=(None, None, None, [[OctetString("98F")]]),
        ),
        patch(
            # Mocking the transport creation (which checks IP validity)
            "homeassistant.components.snmp.config_flow.UdpTransportTarget.create",
            return_value="mock_target",
        ),
        patch(
            # Mocking the setup_entry because we only want to test the flow logic here
            "homeassistant.components.snmp.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "192.168.1.1",
                "baseoid": "1.3.6.1.4.1.2021.10.1.3.1",
                "community": "public",
            },
        )
        await hass.async_block_till_done()

    # 3. Verify the result is a success.
    # We expect a CREATE_ENTRY type, and the data should contain all the defaults we set.
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "192.168.1.1"
    assert result["data"] == {
        "host": "192.168.1.1",
        "baseoid": "1.3.6.1.4.1.2021.10.1.3.1",
        "community": "public",
        "port": 161,
        "version": "1",
        "auth_protocol": "none",
        "priv_protocol": "none",
    }
    # Ensure Home Assistant actually called the setup function for this new entry.
    assert len(mock_setup_entry.mock_calls) == 1


async def test_user_flow_cannot_connect(hass: HomeAssistant) -> None:
    """Test user setup flow failure - cannot connect."""
    # Start the flow.
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # Mock the GET command to return a 'Timeout' error.
    with (
        patch(
            "homeassistant.components.snmp.config_flow.get_cmd",
            return_value=("Timeout", None, None, None),
        ),
        patch(
            "homeassistant.components.snmp.config_flow.UdpTransportTarget.create",
            return_value="mock_target",
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "192.168.1.1",
                "baseoid": "1.3.6.1.4.1.2021.10.1.3.1",
            },
        )

    # Verify the flow shows the FORM again but with an error message.
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_import_flow_success(hass: HomeAssistant) -> None:
    """Test successful YAML import flow."""
    # YAML configuration doesn't usually require validation during boot to keep startup fast.
    # We test that the SOURCE_IMPORT data is correctly turned into a config entry.
    with patch(
        "homeassistant.components.snmp.async_setup_entry", return_value=True
    ) as mock_setup:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={
                "host": "192.168.1.1",
                "baseoid": "1.3.6.1.4.1.2021.10.1.3.1",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        "host": "192.168.1.1",
        "baseoid": "1.3.6.1.4.1.2021.10.1.3.1",
    }
    assert len(mock_setup.mock_calls) == 1


async def test_import_flow_already_configured(hass: HomeAssistant) -> None:
    """Test YAML import flow aborts if already configured."""
    MockConfigEntry(
        domain=DOMAIN,
        data={
            "host": "192.168.1.1",
            "baseoid": "1.3.6.1.4.1.2021.10.1.3.1",
        },
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data={
            "host": "192.168.1.1",
            "baseoid": "1.3.6.1.4.1.2021.10.1.3.1",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
