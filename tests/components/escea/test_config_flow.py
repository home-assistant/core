"""Tests for Escea."""

from collections.abc import Callable, Coroutine
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant import config_entries
from homeassistant.components.escea.const import DOMAIN, ESCEA_FIREPLACE
from homeassistant.components.escea.discovery import DiscoveryServiceListener
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


@pytest.fixture(name="mock_discovery_service")
def mock_discovery_service_fixture() -> AsyncMock:
    """Mock discovery service."""
    discovery_service = AsyncMock()
    discovery_service.controllers = {}
    return discovery_service


@pytest.fixture(name="mock_controller")
def mock_controller_fixture() -> MagicMock:
    """Mock controller."""
    return MagicMock()


def _mock_start_discovery(
    discovery_service: MagicMock, controller: MagicMock
) -> Callable[[], Coroutine[None, None, None]]:
    """Mock start discovery service."""

    async def do_discovered() -> None:
        """Call the listener callback."""
        listener: DiscoveryServiceListener = discovery_service.call_args[0][0]
        listener.controller_discovered(controller)

    return do_discovered


async def test_not_found(
    hass: HomeAssistant, mock_discovery_service: MagicMock
) -> None:
    """Test not finding any Escea controllers."""

    with (
        patch(
            "homeassistant.components.escea.discovery.pescea_discovery_service"
        ) as discovery_service,
        patch("homeassistant.components.escea.config_flow.TIMEOUT_DISCOVERY", 0),
    ):
        discovery_service.return_value = mock_discovery_service

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        # Confirmation form
        assert result["type"] is FlowResultType.FORM

        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"
    assert discovery_service.return_value.close.call_count == 1


async def test_found(
    hass: HomeAssistant, mock_controller: MagicMock, mock_discovery_service: AsyncMock
) -> None:
    """Test finding an Escea controller."""
    mock_discovery_service.controllers["test-uid"] = mock_controller

    with (
        patch(
            "homeassistant.components.escea.async_setup_entry",
            return_value=True,
        ) as mock_setup,
        patch(
            "homeassistant.components.escea.discovery.pescea_discovery_service"
        ) as discovery_service,
    ):
        discovery_service.return_value = mock_discovery_service
        mock_discovery_service.start_discovery.side_effect = _mock_start_discovery(
            discovery_service, mock_controller
        )

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        # Confirmation form
        assert result["type"] is FlowResultType.FORM

        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert mock_setup.call_count == 1


async def test_single_instance_allowed(hass: HomeAssistant) -> None:
    """Test single instance allowed."""
    config_entry = MockConfigEntry(domain=DOMAIN, title=ESCEA_FIREPLACE)
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.escea.discovery.pescea_discovery_service"
    ) as discovery_service:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"
    assert discovery_service.call_count == 0
