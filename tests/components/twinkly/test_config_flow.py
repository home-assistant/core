"""Tests for the config_flow of the twinly component."""

from unittest.mock import AsyncMock

import pytest

from homeassistant.components import dhcp
from homeassistant.components.twinkly.const import DOMAIN
from homeassistant.config_entries import SOURCE_DHCP, SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_ID, CONF_MODEL, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .const import TEST_MAC, TEST_MODEL, TEST_NAME

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("mock_twinkly_client", "mock_setup_entry")
async def test_full_flow(hass: HomeAssistant) -> None:
    """Test the full flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "192.168.0.123"},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_NAME
    assert result["data"] == {
        CONF_HOST: "192.168.0.123",
        CONF_ID: "00000000-0000-0000-0000-000000000000",
        CONF_NAME: TEST_NAME,
        CONF_MODEL: TEST_MODEL,
    }
    assert result["result"].unique_id == TEST_MAC


@pytest.mark.usefixtures("mock_setup_entry")
async def test_exceptions(hass: HomeAssistant, mock_twinkly_client: AsyncMock) -> None:
    """Test the failure when raising exceptions."""
    mock_twinkly_client.get_details.side_effect = TimeoutError
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "192.168.0.123"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {CONF_HOST: "cannot_connect"}

    mock_twinkly_client.get_details.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "192.168.0.123"},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("mock_twinkly_client", "mock_setup_entry")
async def test_already_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test the device is already configured."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "192.168.0.123"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("mock_twinkly_client", "mock_setup_entry")
async def test_dhcp_full_flow(hass: HomeAssistant) -> None:
    """Test DHCP discovery flow can confirm right away."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_DHCP},
        data=dhcp.DhcpServiceInfo(
            hostname="Twinkly_XYZ",
            ip="1.2.3.4",
            macaddress="002d133baabb",
        ),
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery_confirm"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_NAME
    assert result["data"] == {
        CONF_HOST: "1.2.3.4",
        CONF_ID: "00000000-0000-0000-0000-000000000000",
        CONF_NAME: TEST_NAME,
        CONF_MODEL: TEST_MODEL,
    }
    assert result["result"].unique_id == TEST_MAC


@pytest.mark.usefixtures("mock_twinkly_client")
async def test_dhcp_already_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test DHCP discovery flow aborts if entry already setup."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_DHCP},
        data=dhcp.DhcpServiceInfo(
            hostname="Twinkly_XYZ",
            ip="1.2.3.4",
            macaddress="002d133baabb",
        ),
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"

    assert mock_config_entry.data[CONF_HOST] == "1.2.3.4"


@pytest.mark.usefixtures("mock_twinkly_client", "mock_setup_entry")
async def test_user_flow_works_discovery(hass: HomeAssistant) -> None:
    """Test user flow can continue after discovery happened."""
    await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_DHCP},
        data=dhcp.DhcpServiceInfo(
            hostname="Twinkly_XYZ",
            ip="1.2.3.4",
            macaddress="002d133baabb",
        ),
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert len(hass.config_entries.flow.async_progress(DOMAIN)) == 2
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "10.0.0.131"},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY

    # Verify the discovery flow was aborted
    assert not hass.config_entries.flow.async_progress(DOMAIN)
