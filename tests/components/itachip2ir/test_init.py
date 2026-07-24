"""Tests for itachip2ir integration setup and unload."""

# pylint: disable=home-assistant-tests-direct-async-setup,home-assistant-tests-direct-async-setup-entry

from typing import cast
from unittest.mock import AsyncMock, MagicMock

from pyitach import ItachConnectionError, ItachError
import pytest

from homeassistant.components.itachip2ir import (
    ItachRuntimeData,
    async_reload_entry,
    async_setup,
    async_setup_entry,
    async_unload_entry,
)
from homeassistant.components.itachip2ir.const import DISCOVERY, DOMAIN
from homeassistant.const import EVENT_HOMEASSISTANT_STOP, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from tests.common import MockConfigEntry

HOST = "192.168.1.211"
PORT = 4998
UNIQUE_ID = "GlobalCache_000C1E123456"


class FakeDiscovery:
    """Fake discovery listener."""

    instances: list[FakeDiscovery] = []

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize fake discovery listener."""
        self.hass = hass
        self.async_start = AsyncMock()
        self.async_stop = AsyncMock()
        FakeDiscovery.instances.append(self)


class FakeClient:
    """Fake iTach client."""

    instances: list[FakeClient] = []

    def __init__(
        self,
        host: str,
        port: int,
        *,
        ir_module: int = 1,
        ir_ports: int = 3,
        connector_modes: dict[int, str] | None = None,
        module_error: Exception | None = None,
        modes_error: Exception | None = None,
    ) -> None:
        """Initialize fake iTach client."""
        self.host = host
        self.port = port
        self.ir_module = ir_module
        self.ir_ports = ir_ports
        self.connector_modes = (
            {1: "IR", 2: "SENSOR", 3: "IR_BLASTER"}
            if connector_modes is None
            else connector_modes
        )
        self.module_error = module_error
        self.modes_error = modes_error
        self.close = AsyncMock()
        FakeClient.instances.append(self)

    async def async_get_ir_module(self) -> tuple[int, int]:
        """Return fake IR module information."""
        if self.module_error is not None:
            raise self.module_error
        return self.ir_module, self.ir_ports

    async def async_get_ir_connector_modes(
        self,
        module: int,
        ports: int,
    ) -> dict[int, str]:
        """Return fake IR connector modes."""
        if self.modes_error is not None:
            raise self.modes_error
        return self.connector_modes


def _make_entry(
    *,
    data: dict | None = None,
    options: dict | None = None,
    unique_id: str | None = UNIQUE_ID,
) -> MockConfigEntry:
    """Create a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=unique_id,
        data=data or {"host": HOST, "port": PORT},
        options=options or {},
        title="iTach IP2IR",
    )


@pytest.fixture(autouse=True)
def reset_fakes() -> None:
    """Reset fake instance tracking."""
    FakeDiscovery.instances.clear()
    FakeClient.instances.clear()


async def test_async_setup_starts_discovery_once(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test async_setup starts discovery and does not start it twice."""
    hass.data["itachip2ir_disable_discovery"] = False

    monkeypatch.setattr(
        "homeassistant.components.itachip2ir.ItachDiscovery",
        FakeDiscovery,
    )

    assert await async_setup(hass, {})
    assert await async_setup(hass, {})

    assert len(FakeDiscovery.instances) == 1
    FakeDiscovery.instances[0].async_start.assert_awaited_once()
    assert hass.data[DOMAIN][DISCOVERY] is FakeDiscovery.instances[0]


async def test_async_setup_does_not_start_discovery_when_disabled(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test async_setup does not start discovery when disabled for tests."""
    hass.data["itachip2ir_disable_discovery"] = True

    monkeypatch.setattr(
        "homeassistant.components.itachip2ir.ItachDiscovery",
        FakeDiscovery,
    )

    assert await async_setup(hass, {})

    assert FakeDiscovery.instances == []
    assert DISCOVERY not in hass.data[DOMAIN]


async def test_discovery_stops_on_home_assistant_stop(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test discovery listener is stopped on Home Assistant shutdown."""
    hass.data["itachip2ir_disable_discovery"] = False

    monkeypatch.setattr(
        "homeassistant.components.itachip2ir.ItachDiscovery",
        FakeDiscovery,
    )

    assert await async_setup(hass, {})

    discovery = FakeDiscovery.instances[0]

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()

    discovery.async_stop.assert_awaited_once()
    assert DISCOVERY not in hass.data[DOMAIN]


async def test_async_setup_entry_success_creates_runtime_data(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test successful config entry setup creates runtime data."""
    entry = _make_entry()
    entry.add_to_hass(hass)

    monkeypatch.setattr(
        "homeassistant.components.itachip2ir.ItachDiscovery",
        FakeDiscovery,
    )
    monkeypatch.setattr(
        "homeassistant.components.itachip2ir.ItachClient",
        FakeClient,
    )

    forward_setups = AsyncMock(return_value=True)
    monkeypatch.setattr(
        hass.config_entries,
        "async_forward_entry_setups",
        forward_setups,
    )

    assert await async_setup_entry(hass, entry)

    assert isinstance(entry.runtime_data, ItachRuntimeData)
    assert entry.runtime_data.host == HOST
    assert entry.runtime_data.port == PORT
    assert entry.runtime_data.device_id == UNIQUE_ID
    assert entry.runtime_data.ir_module == 1
    assert entry.runtime_data.ir_ports == 3
    assert entry.runtime_data.ir_enabled_ports == [1, 3]
    assert entry.runtime_data.ir_connector_modes == {
        "1": "IR",
        "2": "SENSOR",
        "3": "IR_BLASTER",
    }
    assert cast(object, entry.runtime_data.client) is FakeClient.instances[0]

    forward_setups.assert_awaited_once_with(entry, ["infrared"])


async def test_async_setup_entry_uses_options_host_and_port(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test setup uses host and port from options when present."""
    entry = _make_entry(
        data={"host": "192.168.1.100", "port": 4998},
        options={"host": HOST, "port": 5998},
    )
    entry.add_to_hass(hass)

    monkeypatch.setattr(
        "homeassistant.components.itachip2ir.ItachDiscovery",
        FakeDiscovery,
    )
    monkeypatch.setattr(
        "homeassistant.components.itachip2ir.ItachClient",
        FakeClient,
    )
    monkeypatch.setattr(
        hass.config_entries,
        "async_forward_entry_setups",
        AsyncMock(return_value=True),
    )

    assert await async_setup_entry(hass, entry)

    assert entry.runtime_data.host == HOST
    assert entry.runtime_data.port == 5998
    assert FakeClient.instances[0].host == HOST
    assert FakeClient.instances[0].port == 5998


async def test_async_setup_entry_connection_error_raises_not_ready_and_closes(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test connection failure raises ConfigEntryNotReady and closes client."""
    entry = _make_entry()
    entry.add_to_hass(hass)

    class ConnectionErrorClient(FakeClient):
        def __init__(self, host: str, port: int) -> None:
            super().__init__(
                host,
                port,
                module_error=ItachConnectionError("cannot connect"),
            )

    monkeypatch.setattr(
        "homeassistant.components.itachip2ir.ItachDiscovery",
        FakeDiscovery,
    )
    monkeypatch.setattr(
        "homeassistant.components.itachip2ir.ItachClient",
        ConnectionErrorClient,
    )

    with pytest.raises(ConfigEntryNotReady, match="cannot_connect"):
        await async_setup_entry(hass, entry)

    FakeClient.instances[0].close.assert_awaited_once()


async def test_async_setup_entry_ir_validation_error_raises_not_ready_and_closes(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test IR validation failure raises ConfigEntryNotReady and closes client."""
    entry = _make_entry()
    entry.add_to_hass(hass)

    class ValidationErrorClient(FakeClient):
        def __init__(self, host: str, port: int) -> None:
            super().__init__(
                host,
                port,
                modes_error=ItachError("bad get_IR response"),
            )

    monkeypatch.setattr(
        "homeassistant.components.itachip2ir.ItachDiscovery",
        FakeDiscovery,
    )
    monkeypatch.setattr(
        "homeassistant.components.itachip2ir.ItachClient",
        ValidationErrorClient,
    )

    with pytest.raises(
        ConfigEntryNotReady,
        match="invalid_config",
    ):
        await async_setup_entry(hass, entry)

    FakeClient.instances[0].close.assert_awaited_once()


async def test_async_setup_entry_get_ir_fallback_exposes_all_ports(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test setup falls back to all ports when get_IR returns no modes."""
    entry = _make_entry()
    entry.add_to_hass(hass)

    class FallbackClient(FakeClient):
        def __init__(self, host: str, port: int) -> None:
            super().__init__(
                host,
                port,
                ir_module=1,
                ir_ports=3,
                connector_modes={},
            )

    monkeypatch.setattr(
        "homeassistant.components.itachip2ir.ItachDiscovery",
        FakeDiscovery,
    )
    monkeypatch.setattr(
        "homeassistant.components.itachip2ir.ItachClient",
        FallbackClient,
    )
    monkeypatch.setattr(
        hass.config_entries,
        "async_forward_entry_setups",
        AsyncMock(return_value=True),
    )

    assert await async_setup_entry(hass, entry)

    assert entry.runtime_data.ir_enabled_ports == [1, 2, 3]
    assert entry.runtime_data.ir_connector_modes == {
        "1": "UNKNOWN",
        "2": "UNKNOWN",
        "3": "UNKNOWN",
    }


async def test_async_setup_entry_no_output_ports_raises_not_ready_and_closes(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test setup fails when get_IR returns modes but none are IR outputs."""
    entry = _make_entry()
    entry.add_to_hass(hass)

    class NoOutputPortsClient(FakeClient):
        def __init__(self, host: str, port: int) -> None:
            super().__init__(
                host,
                port,
                ir_module=1,
                ir_ports=3,
                connector_modes={1: "SENSOR", 2: "SENSOR", 3: "SENSOR"},
            )

    monkeypatch.setattr(
        "homeassistant.components.itachip2ir.ItachDiscovery",
        FakeDiscovery,
    )
    monkeypatch.setattr(
        "homeassistant.components.itachip2ir.ItachClient",
        NoOutputPortsClient,
    )

    with pytest.raises(
        ConfigEntryNotReady,
        match="no_ir_ports",
    ):
        await async_setup_entry(hass, entry)

    FakeClient.instances[0].close.assert_awaited_once()


async def test_async_setup_entry_missing_unique_id_raises(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test setup fails if the config entry has no unique ID."""
    entry = _make_entry(unique_id=None)
    entry.add_to_hass(hass)

    monkeypatch.setattr(
        "homeassistant.components.itachip2ir.ItachDiscovery",
        FakeDiscovery,
    )

    with pytest.raises(ValueError, match="missing a unique_id"):
        await async_setup_entry(hass, entry)


async def test_async_unload_entry_closes_client_and_keeps_discovery(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test unload closes client but does not stop discovery."""
    entry = _make_entry()
    entry.runtime_data = MagicMock()
    entry.runtime_data.client.close = AsyncMock()

    discovery = FakeDiscovery(hass)
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][DISCOVERY] = discovery

    unload_platforms = AsyncMock(return_value=True)
    monkeypatch.setattr(
        hass.config_entries,
        "async_unload_platforms",
        unload_platforms,
    )

    assert await async_unload_entry(hass, entry)

    unload_platforms.assert_awaited_once_with(
        entry,
        [Platform.INFRARED],
    )
    entry.runtime_data.client.close.assert_awaited_once()
    discovery.async_stop.assert_not_awaited()
    assert hass.data[DOMAIN][DISCOVERY] is discovery


async def test_async_unload_entry_does_not_close_client_if_platform_unload_fails(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test client is not closed when platform unload fails."""
    entry = _make_entry()
    entry.runtime_data = MagicMock()
    entry.runtime_data.client.close = AsyncMock()

    monkeypatch.setattr(
        hass.config_entries,
        "async_unload_platforms",
        AsyncMock(return_value=False),
    )

    assert not await async_unload_entry(hass, entry)

    entry.runtime_data.client.close.assert_not_awaited()


async def test_async_reload_entry_reloads_config_entry(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test reload delegates to the config entry manager."""
    entry = _make_entry()
    async_reload = AsyncMock()

    monkeypatch.setattr(hass.config_entries, "async_reload", async_reload)

    await async_reload_entry(hass, entry)

    async_reload.assert_awaited_once_with(entry.entry_id)


async def test_async_setup_entry_starts_discovery_when_enabled(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test setup entry starts discovery when discovery is enabled."""
    hass.data["itachip2ir_disable_discovery"] = False
    entry = _make_entry()
    entry.add_to_hass(hass)

    monkeypatch.setattr(
        "homeassistant.components.itachip2ir.ItachDiscovery",
        FakeDiscovery,
    )
    monkeypatch.setattr(
        "homeassistant.components.itachip2ir.ItachClient",
        FakeClient,
    )

    forward_setups = AsyncMock(return_value=True)
    monkeypatch.setattr(
        hass.config_entries,
        "async_forward_entry_setups",
        forward_setups,
    )

    assert await async_setup_entry(hass, entry)

    assert len(FakeDiscovery.instances) == 1
    FakeDiscovery.instances[0].async_start.assert_awaited_once()
    assert hass.data[DOMAIN][DISCOVERY] is FakeDiscovery.instances[0]
    forward_setups.assert_awaited_once_with(entry, ["infrared"])
