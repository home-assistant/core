"""Provide common fixtures."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from typing import Any
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
        client.check_node_update = AsyncMock(return_value=None)
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
        "air_quality_sensor",
        "aqara_door_window_p2",
        "aqara_motion_p2",
        "aqara_presence_fp300",
        "aqara_sensor_w100",
        "aqara_thermostat_w500",
        "aqara_u200",
        "color_temperature_light",
        "ecovacs_deebot",
        "eberle_ute3000",
        "eufy_vacuum_omni_e28",
        "eve_contact_sensor",
        "eve_energy_20ecn4101",
        "eve_energy_plug",
        "eve_energy_plug_patched",
        "eve_shutter",
        "eve_thermo_v4",
        "eve_thermo_v5",
        "eve_weather_sensor",
        "extended_color_light",
        "haojai_switch",
        "heiman_motion_sensor_m1",
        "heiman_smoke_detector",
        "ikea_air_quality_monitor",
        "ikea_scroll_wheel",
        "inovelli_vtm30",
        "inovelli_vtm31",
        "longan_link_thermostat",
        "mock_air_purifier",
        "mock_battery_storage",
        "mock_cooktop",
        "mock_dimmable_light",
        "mock_dimmable_plugin_unit",
        "mock_door_lock",
        "mock_door_lock_with_unbolt",
        "mock_extractor_hood",
        "mock_fan",
        "mock_flow_sensor",
        "mock_generic_switch",
        "mock_generic_switch_multi",
        "mock_humidity_sensor",
        "mock_laundry_dryer",
        "mock_leak_sensor",
        "mock_light_sensor",
        "mock_lock",
        "mock_microwave_oven",
        "mock_mounted_dimmable_load_control_fixture",
        "mock_occupancy_sensor",
        "mock_on_off_plugin_unit",
        "mock_onoff_light",
        "mock_onoff_light_alt_name",
        "mock_onoff_light_no_name",
        "mock_oven",
        "mock_pressure_sensor",
        "mock_pump",
        "mock_room_airconditioner",
        "mock_solar_inverter",
        "mock_speaker",
        "mock_switch_unit",
        "mock_temperature_sensor",
        "mock_thermostat",
        "mock_valve",
        "mock_vacuum_cleaner",
        "mock_window_covering_full",
        "mock_window_covering_lift",
        "mock_window_covering_pa_lift",
        "mock_window_covering_pa_tilt",
        "mock_window_covering_tilt",
        "onoff_light_with_levelcontrol_present",
        "resideo_x2s_thermostat",
        "secuyou_smart_lock",
        "silabs_dishwasher",
        "silabs_evse_charging",
        "silabs_laundrywasher",
        "silabs_light_switch",
        "silabs_refrigerator",
        "silabs_water_heater",
        "switchbot_k11_plus",
        "tado_smart_radiator_thermostat_x",
        "yandex_smart_socket",
        "zemismart_mt25b",
    ]
)
async def matter_devices(
    hass: HomeAssistant, matter_client: MagicMock, request: pytest.FixtureRequest
) -> MatterNode:
    """Fixture for a Matter device."""
    return await setup_integration_with_node_fixture(hass, request.param, matter_client)


@pytest.fixture
def attributes() -> dict[str, Any]:
    """Return common attributes for all nodes."""
    return {}


@pytest.fixture
async def matter_node(
    hass: HomeAssistant,
    matter_client: MagicMock,
    node_fixture: str,
    attributes: dict[str, Any],
) -> MatterNode:
    """Fixture for a Matter node."""
    return await setup_integration_with_node_fixture(
        hass, node_fixture, matter_client, attributes
    )
