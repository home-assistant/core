"""Provide common fixtures."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

from matter_server.client.models.node import MatterNode
from matter_server.common.const import SCHEMA_VERSION
from matter_server.common.models import ServerInfoMessage
import pytest

from homeassistant.core import HomeAssistant

from .common import setup_integration_with_node_fixture

from tests.common import MockConfigEntry

MOCK_FABRIC_ID = 12341234
MOCK_COMPR_FABRIC_ID = 1234


@pytest.fixture(name="matter_client")
async def matter_client_fixture() -> AsyncGenerator[MagicMock]:
    """Fixture for a Matter client."""
    with patch(
        "homeassistant.components.matter.MatterClient", autospec=True
    ) as client_class:
        client = client_class.return_value

        async def connect() -> None:
            """Mock connect."""
            await asyncio.sleep(0)

        async def listen(init_ready: asyncio.Event | None) -> None:
            """Mock listen."""
            if init_ready is not None:
                init_ready.set()
            listen_block = asyncio.Event()
            await listen_block.wait()
            pytest.fail("Listen was not cancelled!")

        client.connect = AsyncMock(side_effect=connect)
        client.start_listening = AsyncMock(side_effect=listen)
        client.server_info = ServerInfoMessage(
            fabric_id=MOCK_FABRIC_ID,
            compressed_fabric_id=MOCK_COMPR_FABRIC_ID,
            schema_version=1,
            sdk_version="2022.11.1",
            wifi_credentials_set=True,
            thread_credentials_set=True,
            min_supported_schema_version=SCHEMA_VERSION,
            bluetooth_enabled=False,
        )

        yield client


@pytest.fixture(name="integration")
async def integration_fixture(
    hass: HomeAssistant, matter_client: MagicMock
) -> MockConfigEntry:
    """Set up the Matter integration."""
    entry = MockConfigEntry(domain="matter", data={"url": "ws://localhost:5580/ws"})
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    return entry


@pytest.fixture(
    params=[
        "door_lock",
        "smoke_detector",
        "air_purifier",
        "eve_energy_plug_patched",
        "eve_energy_plug",
    ]
)
async def matter_devices(
    hass: HomeAssistant, matter_client: MagicMock, request: pytest.FixtureRequest
) -> MatterNode:
    """Fixture for a Matter device."""
    return await setup_integration_with_node_fixture(hass, request.param, matter_client)

@pytest.fixture
async def matter_node(hass: HomeAssistant, matter_client: MagicMock, fixture: str) -> MatterNode:
    """Fixture for a Matter node."""
    return await setup_integration_with_node_fixture(hass, fixture, matter_client)

@pytest.fixture(name="door_lock_node")
async def door_lock_fixture(
    hass: HomeAssistant, matter_client: MagicMock
) -> MatterNode:
    """Fixture for a door lock node."""
    return await setup_integration_with_node_fixture(hass, "door_lock", matter_client)


@pytest.fixture(name="smoke_detector_node")
async def smoke_detector_fixture(
    hass: HomeAssistant, matter_client: MagicMock
) -> MatterNode:
    """Fixture for a smoke detector node."""
    return await setup_integration_with_node_fixture(
        hass, "smoke_detector", matter_client
    )


@pytest.fixture(name="door_lock_with_unbolt_node")
async def door_lock_with_unbolt_fixture(
    hass: HomeAssistant, matter_client: MagicMock
) -> MatterNode:
    """Fixture for a door lock node with unbolt feature."""
    return await setup_integration_with_node_fixture(
        hass, "door_lock_with_unbolt", matter_client
    )


@pytest.fixture(name="eve_contact_sensor_node")
async def eve_contact_sensor_node_fixture(
    hass: HomeAssistant, matter_client: MagicMock
) -> MatterNode:
    """Fixture for a contact sensor node."""
    return await setup_integration_with_node_fixture(
        hass, "eve_contact_sensor", matter_client
    )


@pytest.fixture(name="flow_sensor_node")
async def flow_sensor_node_fixture(
    hass: HomeAssistant, matter_client: MagicMock
) -> MatterNode:
    """Fixture for a flow sensor node."""
    return await setup_integration_with_node_fixture(hass, "flow_sensor", matter_client)


@pytest.fixture(name="humidity_sensor_node")
async def humidity_sensor_node_fixture(
    hass: HomeAssistant, matter_client: MagicMock
) -> MatterNode:
    """Fixture for a humidity sensor node."""
    return await setup_integration_with_node_fixture(
        hass, "humidity_sensor", matter_client
    )


@pytest.fixture(name="light_sensor_node")
async def light_sensor_node_fixture(
    hass: HomeAssistant, matter_client: MagicMock
) -> MatterNode:
    """Fixture for a light sensor node."""
    return await setup_integration_with_node_fixture(
        hass, "light_sensor", matter_client
    )


@pytest.fixture(name="pressure_sensor_node")
async def pressure_sensor_node_fixture(
    hass: HomeAssistant, matter_client: MagicMock
) -> MatterNode:
    """Fixture for a pressure sensor node."""
    return await setup_integration_with_node_fixture(
        hass, "pressure_sensor", matter_client
    )


@pytest.fixture(name="temperature_sensor_node")
async def temperature_sensor_node_fixture(
    hass: HomeAssistant, matter_client: MagicMock
) -> MatterNode:
    """Fixture for a temperature sensor node."""
    return await setup_integration_with_node_fixture(
        hass, "temperature_sensor", matter_client
    )


@pytest.fixture(name="eve_energy_plug_node")
async def eve_energy_plug_node_fixture(
    hass: HomeAssistant, matter_client: MagicMock
) -> MatterNode:
    """Fixture for a Eve Energy Plug node."""
    return await setup_integration_with_node_fixture(
        hass, "eve_energy_plug", matter_client
    )


@pytest.fixture(name="eve_thermo_node")
async def eve_thermo_node_fixture(
    hass: HomeAssistant, matter_client: MagicMock
) -> MatterNode:
    """Fixture for a Eve Thermo node."""
    return await setup_integration_with_node_fixture(hass, "eve_thermo", matter_client)


@pytest.fixture(name="eve_energy_plug_patched_node")
async def eve_energy_plug_patched_node_fixture(
    hass: HomeAssistant, matter_client: MagicMock
) -> MatterNode:
    """Fixture for a Eve Energy Plug node (patched to include Matter 1.3 energy clusters)."""
    return await setup_integration_with_node_fixture(
        hass, "eve_energy_plug_patched", matter_client
    )


@pytest.fixture(name="eve_weather_sensor_node")
async def eve_weather_sensor_node_fixture(
    hass: HomeAssistant, matter_client: MagicMock
) -> MatterNode:
    """Fixture for a Eve Weather sensor node."""
    return await setup_integration_with_node_fixture(
        hass, "eve_weather_sensor", matter_client
    )


@pytest.fixture(name="air_quality_sensor_node")
async def air_quality_sensor_node_fixture(
    hass: HomeAssistant, matter_client: MagicMock
) -> MatterNode:
    """Fixture for an air quality sensor (LightFi AQ1) node."""
    return await setup_integration_with_node_fixture(
        hass, "air_quality_sensor", matter_client
    )


@pytest.fixture(name="air_purifier_node")
async def air_purifier_node_fixture(
    hass: HomeAssistant, matter_client: MagicMock
) -> MatterNode:
    """Fixture for an air purifier node."""
    return await setup_integration_with_node_fixture(
        hass, "air_purifier", matter_client
    )


@pytest.fixture(name="dishwasher_node")
async def dishwasher_node_fixture(
    hass: HomeAssistant, matter_client: MagicMock
) -> MatterNode:
    """Fixture for a dishwasher node."""
    return await setup_integration_with_node_fixture(
        hass, "silabs_dishwasher", matter_client
    )