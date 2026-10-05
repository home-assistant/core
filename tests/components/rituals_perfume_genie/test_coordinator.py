"""Tests for the polling of the Rituals Perfume Genie integration."""

from datetime import timedelta
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from ritualsgenie import RitualsGenieConnectionError, Sensor

from homeassistant.components.rituals_perfume_genie.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_ON, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .common import (
    init_integration,
    mock_client,
    mock_config_entry,
    mock_diffuser,
    mock_diffuser_v1_battery_cartridge,
    mock_diffuser_v2_no_battery_no_cartridge,
)

from tests.common import async_fire_time_changed


async def _tick(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, delta: timedelta
) -> None:
    """Move the clock forward and let the coordinators update."""
    freezer.tick(delta)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


async def test_one_request_for_all_diffusers(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test the state of all diffusers is fetched in a single request."""
    config_entry = mock_config_entry(unique_id="id_123_single_request")
    client = await init_integration(
        hass,
        config_entry,
        [
            mock_diffuser_v1_battery_cartridge(),
            mock_diffuser_v2_no_battery_no_cartridge(),
        ],
    )
    assert client.hubs.call_count == 1

    await _tick(hass, freezer, timedelta(minutes=5))

    assert client.hubs.call_count == 2
    client.hub.assert_not_called()


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensors_update_hourly(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test the sensors are fetched once an hour, not with every hub update."""
    config_entry = mock_config_entry(unique_id="id_123_sensors_hourly")
    diffuser = mock_diffuser_v1_battery_cartridge()
    client = await init_integration(hass, config_entry, [diffuser])
    assert client.sensors.call_count == 1

    await _tick(hass, freezer, timedelta(minutes=55))
    assert client.sensors.call_count == 1

    diffuser.wifi_percentage = 25
    await _tick(hass, freezer, timedelta(minutes=5))

    assert client.sensors.call_count == 2
    state = hass.states.get("sensor.genie_wi_fi_signal")
    assert state
    assert state.state == "25"


async def test_fill_updates_daily(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test the fill level is fetched once a day."""
    config_entry = mock_config_entry(unique_id="id_123_fill_daily")
    diffuser = mock_diffuser_v1_battery_cartridge()
    client = await init_integration(hass, config_entry, [diffuser])
    assert client.sensor.call_count == 1

    diffuser.fill = "50-60%"
    await _tick(hass, freezer, timedelta(hours=23))

    assert client.sensor.call_count == 1
    state = hass.states.get("sensor.genie_fill")
    assert state
    assert state.state == "90-100%"

    await _tick(hass, freezer, timedelta(hours=1))

    assert client.sensor.call_count == 2
    state = hass.states.get("sensor.genie_fill")
    assert state
    assert state.state == "50-60%"


async def test_fill_updates_on_cartridge_change(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test the fill level is fetched right away when the cartridge changes."""
    config_entry = mock_config_entry(unique_id="id_123_fill_cartridge")
    diffuser = mock_diffuser_v1_battery_cartridge()
    client = await init_integration(hass, config_entry, [diffuser])
    assert client.sensor.call_count == 1

    diffuser.has_cartridge = False
    diffuser.fill = "Not available"
    await _tick(hass, freezer, timedelta(hours=1))

    assert client.sensor.call_count == 2
    state = hass.states.get("sensor.genie_fill")
    assert state
    assert state.state == "Not available"


async def test_sensors_failure_does_not_block_setup(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test failing sensors don't block the setup, or the other entities."""
    config_entry = mock_config_entry(unique_id="id_123_sensors_failure")
    config_entry.add_to_hass(hass)
    client = mock_client([mock_diffuser_v1_battery_cartridge()])
    sensors = client.sensors.side_effect
    client.sensors.side_effect = RitualsGenieConnectionError

    with patch(
        "homeassistant.components.rituals_perfume_genie.RitualsGenie",
        return_value=client,
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    state = hass.states.get("switch.genie")
    assert state
    assert state.state == STATE_ON

    state = hass.states.get("sensor.genie_perfume")
    assert state
    assert state.state == STATE_UNAVAILABLE

    client.sensors.side_effect = sensors
    await _tick(hass, freezer, timedelta(hours=1))

    state = hass.states.get("sensor.genie_perfume")
    assert state
    assert state.state == "Ritual of Sakura"


async def test_diffuser_removed_from_account(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test the entities of a diffuser that is no longer on the account."""
    config_entry = mock_config_entry(unique_id="id_123_diffuser_removed")
    client = await init_integration(hass, config_entry, [mock_diffuser("lot123")])

    client.hubs.side_effect = list
    await _tick(hass, freezer, timedelta(hours=1))

    for entity_id in ("switch.genie", "sensor.genie_perfume"):
        state = hass.states.get(entity_id)
        assert state
        assert state.state == STATE_UNAVAILABLE


async def test_disabled_sensors_not_fetched(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test the sensors of disabled entities are not fetched."""
    config_entry = mock_config_entry(unique_id="id_123_disabled_sensors")
    client = await init_integration(
        hass, config_entry, [mock_diffuser_v1_battery_cartridge()]
    )

    entry = entity_registry.async_get("sensor.genie_wi_fi_signal")
    assert entry
    assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION

    assert client.sensors.call_args.kwargs["only"] == {
        Sensor.BATTERY,
        Sensor.PERFUME,
    }


async def test_perfume_fetched_for_fill(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test the perfume is fetched for the fill level, even when disabled."""
    config_entry = mock_config_entry(unique_id="id_123_perfume_for_fill")
    config_entry.add_to_hass(hass)
    diffuser = mock_diffuser_v1_battery_cartridge()

    for key in ("battery_percentage", "charging", "perfume"):
        entity_registry.async_get_or_create(
            "binary_sensor" if key == "charging" else "sensor",
            DOMAIN,
            f"{diffuser.hublot}-{key}",
            config_entry=config_entry,
            disabled_by=er.RegistryEntryDisabler.USER,
        )

    client = await init_integration(hass, config_entry, [diffuser])

    assert client.sensors.call_args.kwargs["only"] == {Sensor.PERFUME}
    assert client.sensor.call_count == 1

    state = hass.states.get("sensor.genie_fill")
    assert state
    assert state.state == "90-100%"
