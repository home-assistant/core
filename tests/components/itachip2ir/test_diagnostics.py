"""Tests for iTach IP2IR diagnostics."""

from typing import cast
from unittest.mock import AsyncMock

from pyitach import ItachClient

from homeassistant.components.itachip2ir import ItachRuntimeData
from homeassistant.components.itachip2ir.const import DOMAIN
from homeassistant.components.itachip2ir.diagnostics import (
    _extract_client,
    async_get_config_entry_diagnostics,
)
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

HOST = "192.168.1.211"
PORT = 4998
UNIQUE_ID = "GlobalCache_000C1E123456"


class FakeClient:
    """Fake iTach client for diagnostics tests."""

    def __init__(
        self,
        *,
        version: str = "710-1000-23",
        version_error: Exception | None = None,
    ) -> None:
        """Initialize fake client."""
        self.version = version
        self.version_error = version_error
        self.async_get_version = AsyncMock(side_effect=self._async_get_version)

    async def _async_get_version(self, module: int) -> str:
        """Return fake firmware version."""
        if self.version_error is not None:
            raise self.version_error

        return self.version


class RuntimeWithInvalidClient:
    """Runtime wrapper with an invalid client object."""

    client = object()


def _make_entry(
    *,
    client: FakeClient | None = None,
    data: dict | None = None,
    options: dict | None = None,
) -> MockConfigEntry:
    """Create a mock config entry with runtime data."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=UNIQUE_ID,
        data=data
        or {
            "host": HOST,
            "port": PORT,
            "ir_module": 1,
            "ir_ports": 3,
            "ir_enabled_ports": [1, 3],
            "ir_connector_modes": {
                "1": "IR",
                "2": "SENSOR",
                "3": "IR_BLASTER",
            },
        },
        options=options or {},
        title="iTach IP2IR",
    )

    entry.runtime_data = ItachRuntimeData(
        host=HOST,
        port=PORT,
        device_id=UNIQUE_ID,
        ir_module=1,
        ir_ports=3,
        ir_enabled_ports=[1, 3],
        ir_connector_modes={
            "1": "IR",
            "2": "SENSOR",
            "3": "IR_BLASTER",
        },
        client=cast(ItachClient, client or FakeClient()),
    )

    return entry


def test_extract_client_returns_none_for_invalid_client() -> None:
    """Test invalid runtime client is ignored."""
    assert _extract_client(RuntimeWithInvalidClient()) is None


async def test_diagnostics_returns_redacted_entry_and_device_data(
    hass: HomeAssistant,
) -> None:
    """Test diagnostics returns useful redacted entry and device data."""
    client = FakeClient(version="710-1000-23")
    entry = _make_entry(client=client)
    entry.add_to_hass(hass)

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)

    assert diagnostics == {
        "entry": {
            "title": "iTach IP2IR",
            "domain": DOMAIN,
            "data": {
                "host": HOST,
                "port": PORT,
                "ir_module": 1,
                "ir_ports": 3,
                "ir_enabled_ports": [1, 3],
                "ir_connector_modes": {
                    "1": "IR",
                    "2": "SENSOR",
                    "3": "IR_BLASTER",
                },
            },
            "options": {},
            "unique_id": "**REDACTED**",
        },
        "device": {
            "host": HOST,
            "port": PORT,
            "device_id": "**REDACTED**",
            "ir_module": 1,
            "ir_ports": 3,
            "ir_enabled_ports": [1, 3],
            "ir_connector_modes": {
                "1": "IR",
                "2": "SENSOR",
                "3": "IR_BLASTER",
            },
            "firmware_version": "710-1000-23",
            "firmware_error": None,
        },
    }

    client.async_get_version.assert_awaited_once_with(1)


async def test_diagnostics_redacts_nested_sensitive_values(hass: HomeAssistant) -> None:
    """Test diagnostics redacts sensitive fields in nested data and options."""
    entry = _make_entry(
        data={
            "host": HOST,
            "port": PORT,
            "device_id": UNIQUE_ID,
            "uuid": UNIQUE_ID,
            "unique_id": UNIQUE_ID,
        },
        options={
            "device_id": UNIQUE_ID,
            "uuid": UNIQUE_ID,
            "unique_id": UNIQUE_ID,
        },
    )
    entry.add_to_hass(hass)

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)

    assert diagnostics["entry"]["unique_id"] == "**REDACTED**"
    assert diagnostics["device"]["device_id"] == "**REDACTED**"

    assert diagnostics["entry"]["data"]["device_id"] == "**REDACTED**"
    assert diagnostics["entry"]["data"]["uuid"] == "**REDACTED**"
    assert diagnostics["entry"]["data"]["unique_id"] == "**REDACTED**"

    assert diagnostics["entry"]["options"]["device_id"] == "**REDACTED**"
    assert diagnostics["entry"]["options"]["uuid"] == "**REDACTED**"
    assert diagnostics["entry"]["options"]["unique_id"] == "**REDACTED**"


async def test_diagnostics_handles_firmware_version_error(hass: HomeAssistant) -> None:
    """Test diagnostics handles firmware lookup failures safely."""
    client = FakeClient(version_error=RuntimeError("device offline"))
    entry = _make_entry(client=client)
    entry.add_to_hass(hass)

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)

    assert diagnostics["device"]["firmware_version"] is None
    assert diagnostics["device"]["firmware_error"] == "device offline"
    assert diagnostics["device"]["device_id"] == "**REDACTED**"

    client.async_get_version.assert_awaited_once_with(1)


async def test_diagnostics_includes_options_host_and_port(hass: HomeAssistant) -> None:
    """Test diagnostics includes current options."""
    entry = _make_entry(
        options={
            "host": "192.168.1.250",
            "port": 5998,
        },
    )
    entry.add_to_hass(hass)

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)

    assert diagnostics["entry"]["options"] == {
        "host": "192.168.1.250",
        "port": 5998,
    }


async def test_diagnostics_handles_missing_runtime_data(hass: HomeAssistant) -> None:
    """Test diagnostics fall back to config entry data without runtime data."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=UNIQUE_ID,
        data={
            "host": HOST,
            "port": PORT,
            "ir_module": 1,
            "ir_ports": 3,
            "ir_enabled_ports": [1, 3],
            "ir_connector_modes": {"1": "IR", "3": "IR_BLASTER"},
        },
        options={},
        title="iTach IP2IR",
    )
    entry.add_to_hass(hass)

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)

    assert diagnostics["device"] == {
        "host": HOST,
        "port": PORT,
        "device_id": "**REDACTED**",
        "ir_module": 1,
        "ir_ports": 3,
        "ir_enabled_ports": [1, 3],
        "ir_connector_modes": {"1": "IR", "3": "IR_BLASTER"},
        "firmware_version": None,
        "firmware_error": None,
    }


async def test_diagnostics_accepts_runtime_data_client_directly(
    hass: HomeAssistant,
) -> None:
    """Test diagnostics supports tests or callers storing the client directly."""
    client = FakeClient(version="710-2000-99")
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=UNIQUE_ID,
        data={"host": HOST, "port": PORT, "ir_module": 2},
        options={},
        title="iTach IP2IR",
    )
    entry.runtime_data = client
    entry.add_to_hass(hass)

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)

    assert diagnostics["device"]["firmware_version"] == "710-2000-99"
    client.async_get_version.assert_awaited_once_with(2)
