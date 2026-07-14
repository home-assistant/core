"""Test the MELCloud Home integration init behavior."""

import asyncio
from unittest.mock import AsyncMock

from aiomelcloudhome import UnitStateDelta, UserContext
from aiomelcloudhome.exceptions import (
    MelCloudHomeAuthenticationError,
    MelCloudHomeConnectionError,
    MelCloudHomeTimeoutError,
    MelCloudHomeWebSocketError,
)
from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.climate import ATTR_CURRENT_TEMPERATURE, HVACMode
from homeassistant.components.melcloud_home.const import DOMAIN
from homeassistant.components.melcloud_home.coordinator import UPDATE_INTERVAL
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_TEMPERATURE, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import setup_integration

from tests.common import (
    MockConfigEntry,
    async_fire_time_changed,
    async_load_json_object_fixture,
)

ATA_ENTITY_ID = "climate.living_room_ac"
ATW_ZONE1_ENTITY_ID = "climate.heat_pump_zone_1"


@pytest.mark.usefixtures("mock_melcloud_client")
async def test_entry_setup_unload(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test integration setup and unload."""
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    ("exception", "setup_state"),
    [
        (MelCloudHomeAuthenticationError("bad creds"), ConfigEntryState.SETUP_ERROR),
        (MelCloudHomeConnectionError("cannot connect"), ConfigEntryState.SETUP_RETRY),
        (MelCloudHomeTimeoutError("timeout"), ConfigEntryState.SETUP_RETRY),
    ],
)
async def test_entry_setup_retry_on_update_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_melcloud_client: AsyncMock,
    exception: Exception,
    setup_state: ConfigEntryState,
) -> None:
    """Test setup retries when initial coordinator refresh fails."""
    mock_melcloud_client.get_context.side_effect = exception

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is setup_state


async def test_new_ata_unit_callback(
    hass: HomeAssistant,
    mock_melcloud_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that new ATA units discovered on coordinator refresh create climate entities."""
    fixture = await async_load_json_object_fixture(hass, "context.json", DOMAIN)
    mock_melcloud_client.get_context.return_value = UserContext.model_validate(
        {
            **fixture,
            "buildings": [
                {**building, "airToAirUnits": []} for building in fixture["buildings"]
            ],
        }
    )
    await setup_integration(hass, mock_config_entry)
    ata_entities = [
        entity
        for entity in er.async_entries_for_config_entry(
            entity_registry, mock_config_entry.entry_id
        )
        if "living_room" in entity.entity_id
    ]
    assert not ata_entities

    mock_melcloud_client.get_context.return_value = UserContext.model_validate(fixture)
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    ata_entities = [
        entity
        for entity in er.async_entries_for_config_entry(
            entity_registry, mock_config_entry.entry_id
        )
        if "living_room" in entity.entity_id
    ]
    assert ata_entities


async def test_stale_devices_removed(
    hass: HomeAssistant,
    mock_melcloud_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that devices are removed when units disappear from the account."""
    fixture = await async_load_json_object_fixture(hass, "context.json", DOMAIN)
    await setup_integration(hass, mock_config_entry)

    assert device_registry.async_get_device(identifiers={(DOMAIN, "ata-unit-uuid-1")})
    assert device_registry.async_get_device(identifiers={(DOMAIN, "atw-unit-uuid-1")})

    # Poof, now they're gone
    mock_melcloud_client.get_context.return_value = UserContext.model_validate(
        {
            **fixture,
            "buildings": [
                {**building, "airToAirUnits": [], "airToWaterUnits": []}
                for building in fixture["buildings"]
            ],
        }
    )
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (
        device_registry.async_get_device(identifiers={(DOMAIN, "ata-unit-uuid-1")})
        is None
    )
    assert (
        device_registry.async_get_device(identifiers={(DOMAIN, "atw-unit-uuid-1")})
        is None
    )


async def test_new_atw_unit_callback(
    hass: HomeAssistant,
    mock_melcloud_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that new ATW units discovered on coordinator refresh create climate entities."""
    fixture = await async_load_json_object_fixture(hass, "context.json", DOMAIN)
    mock_melcloud_client.get_context.return_value = UserContext.model_validate(
        {
            **fixture,
            "buildings": [
                {**building, "airToWaterUnits": []} for building in fixture["buildings"]
            ],
        }
    )
    await setup_integration(hass, mock_config_entry)
    atw_entities = [
        entity
        for entity in er.async_entries_for_config_entry(
            entity_registry, mock_config_entry.entry_id
        )
        if "heat_pump" in entity.entity_id
    ]
    assert not atw_entities

    mock_melcloud_client.get_context.return_value = UserContext.model_validate(fixture)
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    atw_entities = [
        entity
        for entity in er.async_entries_for_config_entry(
            entity_registry, mock_config_entry.entry_id
        )
        if "heat_pump" in entity.entity_id
    ]
    assert atw_entities


async def test_websocket_delta_updates_ata_state(
    hass: HomeAssistant,
    mock_melcloud_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    websocket_updates: asyncio.Queue[UnitStateDelta | Exception],
) -> None:
    """Test a websocket delta updates ATA state without triggering a poll."""
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(ATA_ENTITY_ID)
    assert state.state == HVACMode.HEAT

    websocket_updates.put_nowait(
        UnitStateDelta(
            unit_id="ata-unit-uuid-1",
            unit_type="ata",
            changes={"Power": False, "SetTemperature": 25.0},
        )
    )
    await websocket_updates.join()

    state = hass.states.get(ATA_ENTITY_ID)
    assert state.state == HVACMode.OFF
    assert state.attributes[ATTR_TEMPERATURE] == 25.0
    assert mock_melcloud_client.get_context.call_count == 1


@pytest.mark.usefixtures("mock_melcloud_client")
async def test_websocket_delta_updates_atw_zone_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    websocket_updates: asyncio.Queue[UnitStateDelta | Exception],
) -> None:
    """Test a websocket delta updates ATW zone state."""
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(ATW_ZONE1_ENTITY_ID)
    assert state.attributes[ATTR_CURRENT_TEMPERATURE] == 20.0
    assert state.attributes[ATTR_TEMPERATURE] == 21.0

    websocket_updates.put_nowait(
        UnitStateDelta(
            unit_id="atw-unit-uuid-1",
            unit_type="atw",
            changes={"RoomTemperatureZone1": 21.5, "SetTemperatureZone1": 22.0},
        )
    )
    await websocket_updates.join()

    state = hass.states.get(ATW_ZONE1_ENTITY_ID)
    assert state.attributes[ATTR_CURRENT_TEMPERATURE] == 21.5
    assert state.attributes[ATTR_TEMPERATURE] == 22.0


@pytest.mark.parametrize(
    "delta",
    [
        pytest.param(
            UnitStateDelta(
                unit_id="unknown-unit", unit_type="ata", changes={"Power": False}
            ),
            id="unknown_unit_id",
        ),
        pytest.param(
            UnitStateDelta(
                unit_id="ata-unit-uuid-1",
                unit_type="unknown",
                changes={"Power": False},
            ),
            id="unknown_unit_type",
        ),
        pytest.param(
            UnitStateDelta(
                unit_id="ata-unit-uuid-1",
                unit_type="ata",
                changes={"OperationMode": None},
            ),
            id="all_none_changes",
        ),
        pytest.param(
            UnitStateDelta(
                unit_id="ata-unit-uuid-1",
                unit_type="ata",
                changes={"SomethingNew": "value"},
            ),
            id="unknown_setting_name",
        ),
    ],
)
@pytest.mark.usefixtures("mock_melcloud_client")
async def test_websocket_delta_ignored(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    websocket_updates: asyncio.Queue[UnitStateDelta | Exception],
    delta: UnitStateDelta,
) -> None:
    """Test deltas that must not change entity state."""
    await setup_integration(hass, mock_config_entry)

    before = hass.states.get(ATA_ENTITY_ID)

    websocket_updates.put_nowait(delta)
    await websocket_updates.join()

    after = hass.states.get(ATA_ENTITY_ID)
    assert after.state == before.state
    assert after.attributes == before.attributes
    assert after.last_updated == before.last_updated


@pytest.mark.usefixtures("mock_melcloud_client")
async def test_websocket_delta_skips_none_values(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    websocket_updates: asyncio.Queue[UnitStateDelta | Exception],
) -> None:
    """Test None change values are skipped while others are applied."""
    await setup_integration(hass, mock_config_entry)

    websocket_updates.put_nowait(
        UnitStateDelta(
            unit_id="ata-unit-uuid-1",
            unit_type="ata",
            changes={"OperationMode": None, "SetTemperature": 25.0},
        )
    )
    await websocket_updates.join()

    state = hass.states.get(ATA_ENTITY_ID)
    assert state.state == HVACMode.HEAT
    assert state.attributes[ATTR_TEMPERATURE] == 25.0


async def test_websocket_error_falls_back_to_polling(
    hass: HomeAssistant,
    mock_melcloud_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    websocket_updates: asyncio.Queue[UnitStateDelta | Exception],
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a websocket failure keeps entities updating through polling."""
    await setup_integration(hass, mock_config_entry)

    websocket_updates.put_nowait(MelCloudHomeWebSocketError("boom"))
    await hass.async_block_till_done()

    assert "Live updates are unavailable" in caplog.text

    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert mock_melcloud_client.get_context.call_count == 2
    state = hass.states.get(ATA_ENTITY_ID)
    assert state.state != STATE_UNAVAILABLE


@pytest.mark.usefixtures("mock_melcloud_client")
async def test_websocket_closed_on_unload(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_websocket: AsyncMock,
) -> None:
    """Test the websocket is closed when the entry is unloaded."""
    await setup_integration(hass, mock_config_entry)

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    mock_websocket.close.assert_awaited_once()
