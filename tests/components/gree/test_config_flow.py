"""Tests for the Gree Integration."""

import asyncio
from unittest.mock import AsyncMock, patch

from greeclimate.discovery import Discovery
import pytest

from homeassistant import config_entries
from homeassistant.components.gree.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .common import FakeDiscovery

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


@patch("homeassistant.components.gree.config_flow.DISCOVERY_TIMEOUT", 0)
async def test_creating_entry_sets_up_climate(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test setting up Gree creates the climate components."""
    with patch(
        "homeassistant.components.gree.config_flow.Discovery",
        return_value=FakeDiscovery(),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        # Confirmation form
        assert result["type"] is FlowResultType.FORM

        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        assert result["type"] is FlowResultType.CREATE_ENTRY

        await hass.async_block_till_done()

        assert len(mock_setup_entry.mock_calls) == 1


@patch("homeassistant.components.gree.config_flow.DISCOVERY_TIMEOUT", 0)
async def test_creating_entry_has_no_devices(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test setting up Gree creates the climate components."""
    with patch(
        "homeassistant.components.gree.config_flow.Discovery",
        return_value=FakeDiscovery(),
    ) as discovery:
        discovery.return_value.mock_devices = []

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        # Confirmation form
        assert result["type"] is FlowResultType.FORM

        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        assert result["type"] is FlowResultType.ABORT

        await hass.async_block_till_done()

        assert len(mock_setup_entry.mock_calls) == 0


@pytest.mark.usefixtures("socket_enabled")
async def test_cancelled_discovery_releases_socket(hass: HomeAssistant) -> None:
    """Test cancelling setup releases the discovery socket."""
    discovery = Discovery()
    transport, _ = await hass.loop.create_datagram_endpoint(
        lambda: discovery, local_addr=("127.0.0.1", 0)
    )
    socket = transport.get_extra_info("socket")
    try:
        with (
            patch(
                "homeassistant.components.gree.config_flow.Discovery",
                return_value=discovery,
            ),
            patch.object(discovery, "scan", side_effect=asyncio.CancelledError),
        ):
            result = await hass.config_entries.flow.async_init(
                DOMAIN, context={"source": config_entries.SOURCE_USER}
            )
            with pytest.raises(asyncio.CancelledError):
                await hass.config_entries.flow.async_configure(result["flow_id"], {})

        await asyncio.sleep(0)
        assert socket.fileno() == -1
    finally:
        transport.close()
        await asyncio.sleep(0)
