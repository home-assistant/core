"""Provider and consumer fixtures independent of transport and device libraries."""

from collections.abc import Awaitable, Callable, Generator
from types import SimpleNamespace
from unittest.mock import Mock, patch

from lorawan_connection import DeviceDescriptor, Unsubscribe
from lorawan_connection.mock import MockConnection
import pytest

from homeassistant.components.lorawan import DeviceManager, async_register_connection
from homeassistant.config_entries import ConfigEntry, ConfigFlow
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.setup import async_setup_component

from .helpers import ExampleCoordinator, ExampleDevices, ExampleSensor

from tests.common import (
    MockConfigEntry,
    MockModule,
    mock_config_flow,
    mock_integration,
    mock_platform,
)


@pytest.fixture
def mock_connection() -> MockConnection:
    """Use the published in-memory connection."""
    return MockConnection()


@pytest.fixture(autouse=True)
def example_integrations(
    hass: HomeAssistant, mock_connection: MockConnection
) -> Generator[None]:
    """Exercise real config-entry/entity lifecycle with synthetic integrations."""

    async def setup_provider(hass: HomeAssistant, entry: ConfigEntry) -> bool:
        entry.async_on_unload(
            await async_register_connection(hass, entry, connection=mock_connection)
        )
        return True

    async def unload_provider(hass: HomeAssistant, entry: ConfigEntry) -> bool:
        return True

    async def setup_vendor(hass: HomeAssistant, entry: ConfigEntry) -> bool:
        manager = entry.runtime_data = DeviceManager(
            hass,
            entry,
            create_collection=ExampleDevices,
            create_coordinator=ExampleCoordinator,
        )
        entry.async_on_unload(manager.close)
        await manager.async_setup()
        await hass.config_entries.async_forward_entry_setups(entry, [Platform.SENSOR])
        return True

    async def unload_vendor(hass: HomeAssistant, entry: ConfigEntry) -> bool:
        return await hass.config_entries.async_unload_platforms(
            entry, [Platform.SENSOR]
        )

    async def setup_sensor(
        hass: HomeAssistant,
        entry: ConfigEntry,
        async_add_entities: AddConfigEntryEntitiesCallback,
    ) -> None:
        @callback
        def added(coordinator: ExampleCoordinator) -> None:
            async_add_entities(
                ExampleSensor(coordinator, key) for key in ("temperature", "humidity")
            )

        entry.async_on_unload(entry.runtime_data.subscribe_coordinator_added(added))

    mock_integration(
        hass,
        MockModule(
            "test_provider",
            dependencies=["lorawan"],
            async_setup_entry=setup_provider,
            async_unload_entry=unload_provider,
        ),
    )
    mock_integration(
        hass,
        MockModule(
            "test_vendor",
            dependencies=["lorawan"],
            async_setup_entry=setup_vendor,
            async_unload_entry=unload_vendor,
        ),
    )
    mock_platform(
        hass,
        "test_vendor.sensor",
        SimpleNamespace(async_setup_entry=setup_sensor, PARALLEL_UPDATES=0),
    )
    mock_platform(hass, "test_vendor.config_flow", Mock())
    mock_platform(hass, "test_provider.config_flow", Mock())
    with (
        mock_config_flow("test_vendor", ConfigFlow),
        mock_config_flow("test_provider", ConfigFlow),
        patch(
            "homeassistant.components.lorawan.async_get_lorawan",
            return_value={"test_vendor": [("example", 123), ("other_stack", "vendor")]},
        ),
        patch(
            "homeassistant.components.lorawan.connection.discovery_flow.async_create_flow"
        ),
    ):
        yield


@pytest.fixture
def provider_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Represent a provider without a server integration."""
    entry = MockConfigEntry(domain="test_provider", entry_id="network")
    entry.add_to_hass(hass)
    return entry


type RegisterBackend = Callable[
    [str, list[DeviceDescriptor]], Awaitable[tuple[MockConnection, Unsubscribe]]
]


@pytest.fixture
def registered_backend(hass: HomeAssistant) -> Generator[RegisterBackend]:
    """Register independently controlled connections."""
    cleanups: list[Unsubscribe] = []

    async def register(
        entry_id: str, descriptors: list[DeviceDescriptor]
    ) -> tuple[MockConnection, Unsubscribe]:
        assert await async_setup_component(hass, "lorawan", {})
        entry = hass.config_entries.async_get_entry(entry_id)
        if entry is None:
            entry = MockConfigEntry(domain="test_provider", entry_id=entry_id)
            entry.add_to_hass(hass)
        backend = MockConnection(descriptors)
        unsubscribe = await async_register_connection(hass, entry, connection=backend)
        cleanups.append(unsubscribe)
        return backend, unsubscribe

    yield register
    for unsubscribe in cleanups:
        unsubscribe()
