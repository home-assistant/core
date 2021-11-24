"""Tests for the Fronius integration."""
from homeassistant.components.fronius.const import DOMAIN
from homeassistant.const import CONF_HOST
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt

from tests.common import MockConfigEntry, async_fire_time_changed, load_fixture
from tests.test_util.aiohttp import AiohttpClientMocker

MOCK_HOST = "http://fronius"
MOCK_UID = "123.4567890"  # has to match mocked logger unique_id


async def setup_fronius_integration(hass):
    """Create the Fronius integration."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=MOCK_UID,
        data={
            CONF_HOST: MOCK_HOST,
            "is_logger": True,
        },
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


def mock_responses(
    aioclient_mock: AiohttpClientMocker,
    host: str = MOCK_HOST,
    night: bool = False,
) -> None:
    """Mock responses for Fronius Symo inverter with meter."""
    aioclient_mock.clear_requests()
    _day_or_night = "night" if night else "day"

    aioclient_mock.get(
        f"{host}/solar_api/GetAPIVersion.cgi",
        text=load_fixture("symo/GetAPIVersion.json", "fronius"),
    )
    aioclient_mock.get(
        f"{host}/solar_api/v1/GetInverterRealtimeData.cgi?Scope=Device&"
        "DeviceId=1&DataCollection=CommonInverterData",
        text=load_fixture(
            f"symo/GetInverterRealtimeDate_Device_1_{_day_or_night}.json", "fronius"
        ),
    )
    aioclient_mock.get(
        f"{host}/solar_api/v1/GetInverterInfo.cgi",
        text=load_fixture("symo/GetInverterInfo.json", "fronius"),
    )
    aioclient_mock.get(
        f"{host}/solar_api/v1/GetLoggerInfo.cgi",
        text=load_fixture("symo/GetLoggerInfo.json", "fronius"),
    )
    aioclient_mock.get(
        f"{host}/solar_api/v1/GetMeterRealtimeData.cgi?Scope=Device&DeviceId=0",
        text=load_fixture("symo/GetMeterRealtimeData_Device_0.json", "fronius"),
    )
    aioclient_mock.get(
        f"{host}/solar_api/v1/GetMeterRealtimeData.cgi?Scope=System",
        text=load_fixture("symo/GetMeterRealtimeData_System.json", "fronius"),
    )
    aioclient_mock.get(
        f"{host}/solar_api/v1/GetPowerFlowRealtimeData.fcgi",
        text=load_fixture(
            f"symo/GetPowerFlowRealtimeData_{_day_or_night}.json", "fronius"
        ),
    )
    aioclient_mock.get(
        f"{host}/solar_api/v1/GetStorageRealtimeData.cgi?Scope=System",
        text=load_fixture("symo/GetStorageRealtimeData_System.json", "fronius"),
    )


async def enable_all_entities(hass, config_entry_id, time_till_next_update):
    """Enable all entities for a config entry and fast forward time to receive data."""
    registry = er.async_get(hass)
    entities = er.async_entries_for_config_entry(registry, config_entry_id)
    for entry in [
        entry for entry in entities if entry.disabled_by == er.DISABLED_INTEGRATION
    ]:
        registry.async_update_entity(entry.entity_id, **{"disabled_by": None})
    await hass.async_block_till_done()
    async_fire_time_changed(hass, dt.utcnow() + time_till_next_update)
    await hass.async_block_till_done()
