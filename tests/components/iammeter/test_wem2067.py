"""WEM2067 parsing, entity selection, optional NET discovery and lifecycle."""

from datetime import timedelta

from freezegun.api import FrozenDateTimeFactory
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker

from homeassistant.components.iammeter.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER, ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_PORT, STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

A = [230.0, 1.0, 230.0, 11.0, 1.0, 50.0, 0.91]
B = [240.0, 2.0, 480.0, 22.0, 2.0, 49.0, 0.92]
NET = [235.0, 0.0, 710.0, 44.0, 4.0, 49.5, 0.94]
SERIAL = "test-meter-2067"
ENDPOINT = "http://192.0.2.1:80/monitorjson"


def mock_readings(
    aioclient_mock: AiohttpClientMocker,
    rows: list[list[float]],
    endpoint: str = ENDPOINT,
) -> None:
    """Serve a complete raw two-channel payload through the real library."""
    aioclient_mock.clear_requests()
    aioclient_mock.get(
        endpoint,
        json={
            "method": "5-test",
            "SN": SERIAL,
            "mac": "00:00:00:00:00:01",
            "Datas": rows,  # codespell:ignore datas
        },
    )


def make_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Register a dual-channel meter with the standard polling interval."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Dual-channel meter",
        unique_id=SERIAL,
        data={CONF_HOST: "192.0.2.1", CONF_PORT: 80},
    )
    entry.add_to_hass(hass)
    return entry


async def test_setup_without_net(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Expose the two physical channels, preserving energy semantics and IDs."""
    mock_readings(aioclient_mock, [A, B])
    entry = make_entry(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED
    entities = er.async_entries_for_config_entry(entity_registry, entry.entry_id)
    assert len(entities) == 14
    assert not any(entity.unique_id.endswith(("_C", "_Net")) for entity in entities)
    power_a = entity_registry.async_get_entity_id(
        Platform.SENSOR, DOMAIN, f"{SERIAL}_Power_A"
    )
    power_b = entity_registry.async_get_entity_id(
        Platform.SENSOR, DOMAIN, f"{SERIAL}_Power_B"
    )
    assert hass.states.get(power_a).state == "230.0"
    assert hass.states.get(power_b).state == "480.0"
    assert hass.states.get(power_b).attributes["unit_of_measurement"] == "W"
    energy = entity_registry.async_get_entity_id(
        Platform.SENSOR, DOMAIN, f"{SERIAL}_ImportEnergy_B"
    )
    assert hass.states.get(energy).state == "22.0"
    assert hass.states.get(energy).attributes["unit_of_measurement"] == "kWh"
    assert hass.states.get(energy).attributes["state_class"] == "total_increasing"
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, SERIAL), entry.entry_id
    )
    assert device.model == "WEM2067"


async def test_setup_with_net(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    entity_registry: er.EntityRegistry,
) -> None:
    """Treat the third row as NET and retain the existing NET measurement keys."""
    mock_readings(aioclient_mock, [A, B, NET])
    entry = make_entry(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    entities = er.async_entries_for_config_entry(entity_registry, entry.entry_id)
    assert len(entities) == 20
    assert not any(entity.unique_id.endswith("_C") for entity in entities)
    net_power = entity_registry.async_get_entity_id(
        Platform.SENSOR, DOMAIN, f"{SERIAL}_Power_Net"
    )
    net_energy = entity_registry.async_get_entity_id(
        Platform.SENSOR, DOMAIN, f"{SERIAL}_ImportEnergy_Net"
    )
    net_pf = entity_registry.async_get_entity_id(
        Platform.SENSOR, DOMAIN, f"{SERIAL}_PF_Net"
    )
    entity_registry.async_update_entity(net_power, disabled_by=None)
    entity_registry.async_update_entity(net_energy, disabled_by=None)
    entity_registry.async_update_entity(net_pf, disabled_by=None)
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get(net_power).state == "710.0"
    assert hass.states.get(net_power).attributes["friendly_name"].endswith("Net power")
    assert hass.states.get(net_energy).state == "44.0"
    assert hass.states.get(net_energy).attributes["state_class"] == "total_increasing"
    assert hass.states.get(net_pf).state == "0.94"
    assert "unit_of_measurement" not in hass.states.get(net_pf).attributes


async def test_net_discovery_loss_and_recovery(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Discover NET once, then mark it unavailable without disrupting A/B."""
    mock_readings(aioclient_mock, [A, B])
    entry = make_entry(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert (
        entity_registry.async_get_entity_id(
            Platform.SENSOR, DOMAIN, f"{SERIAL}_Power_Net"
        )
        is None
    )
    mock_readings(aioclient_mock, [A, B, NET])
    freezer.tick(timedelta(seconds=31))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    net_power = entity_registry.async_get_entity_id(
        Platform.SENSOR, DOMAIN, f"{SERIAL}_Power_Net"
    )
    assert net_power is not None
    entity_registry.async_update_entity(net_power, disabled_by=None)
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get(net_power).state == "710.0"
    mock_readings(aioclient_mock, [A, B])
    freezer.tick(timedelta(seconds=31))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert hass.states.get(net_power).state == STATE_UNAVAILABLE
    power_b = entity_registry.async_get_entity_id(
        Platform.SENSOR, DOMAIN, f"{SERIAL}_Power_B"
    )
    assert hass.states.get(power_b).state == "480.0"
    mock_readings(aioclient_mock, [A, B, NET])
    freezer.tick(timedelta(seconds=31))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert hass.states.get(net_power).state == "710.0"
    assert len(er.async_entries_for_config_entry(entity_registry, entry.entry_id)) == 20


async def test_unload_removes_discovery_listener(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Unloading stops polling even with the optional-discovery listener."""
    mock_readings(aioclient_mock, [A, B])
    entry = make_entry(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED
    calls = aioclient_mock.call_count
    freezer.tick(timedelta(minutes=2))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert aioclient_mock.call_count == calls


async def test_user_flow_with_dual_channel_payload(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    entity_registry: er.EntityRegistry,
) -> None:
    """Accept WEM2067 through the full configuration and setup path."""
    mock_readings(aioclient_mock, [A, B], "https://meter.example/WEM2067/monitorjson")
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "https://meter.example/WEM2067/", CONF_PORT: 80}
    )
    await hass.async_block_till_done()
    assert result["type"] == "create_entry"
    entry = result["result"]
    assert entry.unique_id == SERIAL
    assert entry.runtime_data.data["Model"] == "WEM2067"
    assert len(er.async_entries_for_config_entry(entity_registry, entry.entry_id)) == 14
