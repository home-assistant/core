"""Tests for the diagnostics data provided by the Overkiz integration."""

from unittest.mock import AsyncMock, patch

from syrupy.assertion import SnapshotAssertion

from homeassistant.components.overkiz.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from tests.common import MockConfigEntry, async_load_json_object_fixture
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
    diagnostic_data = await async_load_json_object_fixture(
        hass, "setup_tahoma_switch.json", DOMAIN
    )

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
    diagnostic_data = await async_load_json_object_fixture(
        hass, "setup_tahoma_switch.json", DOMAIN
    )

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


async def test_device_diagnostics_execution_history_subsystem(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    init_integration: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test execution history matching ignores subsystem suffix."""

    diagnostic_data = await async_load_json_object_fixture(
        hass, "setup_tahoma_switch.json", DOMAIN
    )

    device = device_registry.async_get_device(
        identifiers={(DOMAIN, "rts://****-****-6867/16756006")}
    )
    assert device is not None

    class _FakeCommand:
        def __init__(self, device_url: str) -> None:
            self.device_url = device_url

    class _FakeExecution:
        def __init__(self, name: str, device_urls: list[str]) -> None:
            self.name = name
            self.commands = [_FakeCommand(device_url) for device_url in device_urls]

        def __repr__(self) -> str:
            return f"Execution({self.name})"

    execution_history = [
        _FakeExecution("matching", ["rts://****-****-6867/16756006#2"]),
        _FakeExecution("other", ["rts://****-****-6867/other_device"]),
    ]

    with patch.multiple(
        "pyoverkiz.client.OverkizClient",
        get_diagnostic_data=AsyncMock(return_value=diagnostic_data),
        get_execution_history=AsyncMock(return_value=execution_history),
    ):
        diagnostics = await get_diagnostics_for_device(
            hass, hass_client, init_integration, device
        )

    assert diagnostics["execution_history"] == ["Execution(matching)"]
