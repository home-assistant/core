"""Tests for the diagnostics data provided by the Overkiz integration."""

from unittest.mock import AsyncMock, patch

from syrupy import SnapshotAssertion

from homeassistant.components.overkiz.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from tests.common import MockConfigEntry, load_json_object_fixture
from tests.components.diagnostics import (
    get_diagnostics_for_config_entry,
    get_diagnostics_for_device,
)
from tests.typing import ClientSessionGenerator


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    init_integration: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics."""
    diagnostic_data = load_json_object_fixture("overkiz/setup_tahoma_switch.json")

    with patch.multiple(
        "pyoverkiz.client.OverkizClient",
        get_diagnostic_data=AsyncMock(return_value=diagnostic_data),
        get_execution_history=AsyncMock(return_value=[]),
    ):
        assert (
            await get_diagnostics_for_config_entry(hass, hass_client, init_integration)
            == snapshot
        )


async def test_device_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    init_integration: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test device diagnostics."""
    diagnostic_data = load_json_object_fixture("overkiz/setup_tahoma_switch.json")

    device = device_registry.async_get_device(
        identifiers={(DOMAIN, "rts://****-****-6867/16756006")}
    )
    assert device is not None

    with patch.multiple(
        "pyoverkiz.client.OverkizClient",
        get_diagnostic_data=AsyncMock(return_value=diagnostic_data),
        get_execution_history=AsyncMock(return_value=[]),
    ):
        assert (
            await get_diagnostics_for_device(
                hass, hass_client, init_integration, device
            )
            == snapshot
        )
