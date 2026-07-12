"""Test the Harman Luxury config flow."""

from dataclasses import replace
from unittest.mock import AsyncMock

from aioharmanluxury import HarmanLuxuryError
import pytest

from homeassistant.components.harman_luxury.const import DOMAIN
from homeassistant.config_entries import SOURCE_SSDP, SOURCE_USER
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import DEVICE_INFO, SSDP_DISCOVERY, TEST_HOST, TEST_NAME, TEST_SERIAL

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("mock_client")
async def test_user_flow(hass: HomeAssistant) -> None:
    """Test the full user configuration flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: TEST_HOST}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_NAME
    assert result["data"] == {CONF_HOST: TEST_HOST}
    assert result["result"].unique_id == TEST_SERIAL


async def test_user_flow_cannot_connect(
    hass: HomeAssistant, mock_client: AsyncMock
) -> None:
    """Test the user flow recovers from a connection error."""
    mock_client.async_get_info.side_effect = HarmanLuxuryError

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: TEST_HOST}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    mock_client.async_get_info.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: TEST_HOST}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_flow_blank_serial(
    hass: HomeAssistant, mock_client: AsyncMock
) -> None:
    """Test the user flow recovers from a device that reports no serial."""
    mock_client.async_get_info.return_value = replace(DEVICE_INFO, serial="")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: TEST_HOST}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    mock_client.async_get_info.return_value = DEVICE_INFO
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: TEST_HOST}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("mock_client")
async def test_user_flow_already_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test aborting the user flow when the device is already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: TEST_HOST}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("mock_client")
async def test_ssdp_flow(hass: HomeAssistant) -> None:
    """Test the SSDP discovery flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_SSDP}, data=SSDP_DISCOVERY
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery_confirm"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_NAME
    assert result["data"] == {CONF_HOST: TEST_HOST}
    assert result["result"].unique_id == TEST_SERIAL


@pytest.mark.usefixtures("mock_client")
async def test_ssdp_flow_already_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test SSDP discovery aborts and updates the host when already configured."""
    mock_config_entry.add_to_hass(hass)

    discovery = replace(SSDP_DISCOVERY, ssdp_location="http://5.5.5.5:16500/desc.xml")
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_SSDP}, data=discovery
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    # The stale host is updated to the newly discovered one.
    assert mock_config_entry.data[CONF_HOST] == "5.5.5.5"


async def test_ssdp_flow_cannot_connect(
    hass: HomeAssistant, mock_client: AsyncMock
) -> None:
    """Test SSDP discovery aborts when the device cannot be reached."""
    mock_client.async_get_info.side_effect = HarmanLuxuryError

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_SSDP}, data=SSDP_DISCOVERY
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


@pytest.mark.usefixtures("mock_client")
async def test_ssdp_flow_missing_serial(hass: HomeAssistant) -> None:
    """Test SSDP discovery aborts when the advertisement lacks a serial."""
    discovery = replace(SSDP_DISCOVERY, upnp={})

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_SSDP}, data=discovery
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_ssdp_flow_serial_mismatch(
    hass: HomeAssistant, mock_client: AsyncMock
) -> None:
    """Test SSDP discovery aborts when the API serial differs from the advertised one."""
    mock_client.async_get_info.return_value = replace(DEVICE_INFO, serial="different")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_SSDP}, data=SSDP_DISCOVERY
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"
