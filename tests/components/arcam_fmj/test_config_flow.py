"""Tests for the Arcam FMJ config flow module."""

from collections.abc import Generator
from dataclasses import replace
from unittest.mock import AsyncMock, MagicMock, patch

from arcam.fmj.client import ConnectionFailed
import pytest

from homeassistant.components.arcam_fmj.const import DOMAIN
from homeassistant.config_entries import SOURCE_SSDP, SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_SOURCE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.ssdp import (
    ATTR_UPNP_DEVICE_TYPE,
    ATTR_UPNP_FRIENDLY_NAME,
    ATTR_UPNP_MANUFACTURER,
    ATTR_UPNP_MODEL_NAME,
    ATTR_UPNP_MODEL_NUMBER,
    ATTR_UPNP_SERIAL,
    ATTR_UPNP_UDN,
    SsdpServiceInfo,
)

from .conftest import (
    MOCK_CONFIG_ENTRY,
    MOCK_HOST,
    MOCK_NAME,
    MOCK_PORT,
    MOCK_UDN,
    MOCK_UUID,
)

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker

MOCK_UPNP_DEVICE = f"""
<root xmlns="urn:schemas-upnp-org:device-1-0">
  <device>
    <UDN>{MOCK_UDN}</UDN>
  </device>
</root>
"""

MOCK_UPNP_LOCATION = f"http://{MOCK_HOST}:8080/dd.xml"

MOCK_DISCOVER = SsdpServiceInfo(
    ssdp_usn="mock_usn",
    ssdp_st="mock_st",
    ssdp_location=f"http://{MOCK_HOST}:8080/dd.xml",
    upnp={
        ATTR_UPNP_MANUFACTURER: "ARCAM",
        ATTR_UPNP_MODEL_NAME: " ",
        ATTR_UPNP_MODEL_NUMBER: "AVR450, AVR750",
        ATTR_UPNP_FRIENDLY_NAME: f"Arcam media client {MOCK_UUID}",
        ATTR_UPNP_SERIAL: "12343",
        ATTR_UPNP_UDN: MOCK_UDN,
        ATTR_UPNP_DEVICE_TYPE: "urn:schemas-upnp-org:device:MediaRenderer:1",
    },
)


@pytest.fixture(name="dummy_client", autouse=True)
def dummy_client_fixture() -> Generator[MagicMock]:
    """Mock out the real client."""
    with patch("homeassistant.components.arcam_fmj.config_flow.Client") as client:
        client.return_value.start.side_effect = AsyncMock(return_value=None)
        client.return_value.stop.side_effect = AsyncMock(return_value=None)
        yield client.return_value


async def test_ssdp(hass: HomeAssistant) -> None:
    """Test a ssdp import flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_SSDP},
        data=MOCK_DISCOVER,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirm"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"Arcam FMJ ({MOCK_HOST})"
    assert result["data"] == MOCK_CONFIG_ENTRY


async def test_ssdp_abort(hass: HomeAssistant) -> None:
    """Test a ssdp import flow."""
    entry = MockConfigEntry(
        domain=DOMAIN, data=MOCK_CONFIG_ENTRY, title=MOCK_NAME, unique_id=MOCK_UUID
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_SSDP},
        data=MOCK_DISCOVER,
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_ssdp_unable_to_connect(
    hass: HomeAssistant, dummy_client: MagicMock
) -> None:
    """Test a ssdp import flow."""
    dummy_client.start.side_effect = AsyncMock(side_effect=ConnectionFailed)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_SSDP},
        data=MOCK_DISCOVER,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirm"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_ssdp_invalid_id(hass: HomeAssistant) -> None:
    """Test a ssdp with invalid  UDN."""
    discover = replace(
        MOCK_DISCOVER, upnp=MOCK_DISCOVER.upnp | {ATTR_UPNP_UDN: "invalid"}
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_SSDP},
        data=discover,
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_ssdp_update(hass: HomeAssistant) -> None:
    """Test a ssdp import flow."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "old_host", CONF_PORT: MOCK_PORT},
        title=MOCK_NAME,
        unique_id=MOCK_UUID,
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_SSDP},
        data=MOCK_DISCOVER,
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"

    assert entry.data[CONF_HOST] == MOCK_HOST


async def test_user(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    """Test a manual user configuration flow."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_USER},
        data=None,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    user_input = {
        CONF_HOST: MOCK_HOST,
        CONF_PORT: MOCK_PORT,
    }

    aioclient_mock.get(MOCK_UPNP_LOCATION, text=MOCK_UPNP_DEVICE)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"Arcam FMJ ({MOCK_HOST})"
    assert result["data"] == MOCK_CONFIG_ENTRY
    assert result["result"].unique_id == MOCK_UUID


async def test_invalid_ssdp(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test a a config flow where ssdp fails."""
    user_input = {
        CONF_HOST: MOCK_HOST,
        CONF_PORT: MOCK_PORT,
    }

    aioclient_mock.get(MOCK_UPNP_LOCATION, text="")
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_USER},
        data=user_input,
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"Arcam FMJ ({MOCK_HOST})"
    assert result["data"] == MOCK_CONFIG_ENTRY
    assert result["result"].unique_id is None


async def test_user_wrong(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test a manual user configuration flow with no ssdp response."""
    user_input = {
        CONF_HOST: MOCK_HOST,
        CONF_PORT: MOCK_PORT,
    }

    aioclient_mock.get(MOCK_UPNP_LOCATION, status=404)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_USER},
        data=user_input,
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"Arcam FMJ ({MOCK_HOST})"
    assert result["result"].unique_id is None
