"""Tests for the polling of the Rituals Perfume Genie integration."""

from datetime import timedelta
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import async_fire_time_changed
from ritualsgenie import RitualsGenieConnectionError, Sensor

from homeassistant.components.rituals_perfume_genie.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .common import (
    init_integration,
    mock_client,
    mock_config_entry,
    mock_diffuser,
    mock_diffuser_v1_battery_cartridge,
    mock_diffuser_v2_no_battery_no_cartridge,
)


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
    diffuser.fill_raw = "9000"
    await _tick(hass, freezer, timedelta(hours=23))

    assert client.sensor.call_count == 1
    state = hass.states.get("sensor.genie_fill")
    assert state
    assert state.state == "95"

    await _tick(hass, freezer, timedelta(hours=1))

    assert client.sensor.call_count == 2
    state = hass.states.get("sensor.genie_fill")
    assert state
    assert state.state == "55"


async def test_fill_updates_on_cartridge_change(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test the fill level is fetched right away when the cartridge changes."""
    config_entry = mock_config_entry(unique_id="id_123_fill_cartridge")
    diffuser = mock_diffuser_v1_battery_cartridge()
    client = await init_integration(hass, config_entry, [diffuser])
    assert client.sensor.call_count == 1

    diffuser.has_cartridge = False
    diffuser.fill = "No measurement available"
    diffuser.fill_raw = "-1"
    await _tick(hass, freezer, timedelta(hours=1))

    assert client.sensor.call_count == 2
    state = hass.states.get("sensor.genie_fill")
    assert state
    assert state.state == STATE_UNKNOWN


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
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a diffuser that left the account loses its device and entities."""
    config_entry = mock_config_entry(unique_id="id_123_diffuser_removed")
    client = await init_integration(hass, config_entry, [mock_diffuser("lot123")])
    assert device_registry.async_get_device_by_identifier(
        (DOMAIN, "lot123"), config_entry.entry_id
    )

    client.hubs.side_effect = list
    await _tick(hass, freezer, timedelta(minutes=5))

    assert "lot123" not in config_entry.runtime_data.sensors

    assert not device_registry.async_get_device_by_identifier(
        (DOMAIN, "lot123"), config_entry.entry_id
    )
    assert not er.async_entries_for_config_entry(entity_registry, config_entry.entry_id)
    assert hass.states.get("switch.genie") is None
    assert hass.states.get("sensor.genie_perfume") is None


async def test_diffuser_added_to_account(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test a diffuser added to the account gets its entities, without a reload."""
    config_entry = mock_config_entry(unique_id="id_123_diffuser_added")
    diffusers = [mock_diffuser_v1_battery_cartridge()]
    client = await init_integration(hass, config_entry, diffusers)
    assert hass.states.get("switch.genie_v2") is None

    diffusers.append(mock_diffuser_v2_no_battery_no_cartridge())
    await _tick(hass, freezer, timedelta(minutes=5))
    # The first update of its sensors waits a moment for all its entities.
    await _tick(hass, freezer, timedelta(seconds=1))

    state = hass.states.get("switch.genie_v2")
    assert state
    assert state.state == STATE_ON

    # The sensors of the new diffuser are there right away, not an hour later.
    state = hass.states.get("binary_sensor.genie_v2_cartridge")
    assert state
    assert state.state == STATE_OFF
    assert client.sensors.call_args.kwargs["only"] == {Sensor.PERFUME}

    # Nothing changes for the diffuser that was already there.
    state = hass.states.get("switch.genie")
    assert state
    assert state.state == STATE_ON


async def test_diffuser_returns_to_account(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a diffuser that returns to the account gets its entities back."""
    config_entry = mock_config_entry(unique_id="id_123_diffuser_returns")
    config_entry.add_to_hass(hass)

    # Enabled by the user while it was on the account: it comes back enabled.
    entity_registry.async_get_or_create(
        "sensor",
        DOMAIN,
        "lot123-wifi_percentage",
        config_entry=config_entry,
        suggested_object_id="genie_wi_fi_signal",
    )

    diffusers = [mock_diffuser("lot123")]
    client = await init_integration(hass, config_entry, diffusers)

    diffusers.clear()
    await _tick(hass, freezer, timedelta(minutes=5))
    assert hass.states.get("switch.genie") is None

    diffusers.append(mock_diffuser("lot123"))
    await _tick(hass, freezer, timedelta(minutes=5))
    # The first update of its sensors waits a moment for all its entities.
    await _tick(hass, freezer, timedelta(seconds=1))

    state = hass.states.get("switch.genie")
    assert state
    assert state.state == STATE_ON

    state = hass.states.get("sensor.genie_perfume")
    assert state
    assert state.state == "Ritual of Sakura"

    # The first update fetched what the returned entities need.
    state = hass.states.get("sensor.genie_wi_fi_signal")
    assert state
    assert state.state == "75"
    assert Sensor.WIFI in client.sensors.call_args.kwargs["only"]


async def test_stale_device_removed_on_setup(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Test a device left behind by a diffuser no longer on the account is removed."""
    config_entry = mock_config_entry(unique_id="id_123_stale_device")
    config_entry.add_to_hass(hass)
    device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id, identifiers={(DOMAIN, "lot999")}
    )

    await init_integration(hass, config_entry, [mock_diffuser("lot123")])

    assert not device_registry.async_get_device_by_identifier(
        (DOMAIN, "lot999"), config_entry.entry_id
    )
    assert device_registry.async_get_device_by_identifier(
        (DOMAIN, "lot123"), config_entry.entry_id
    )


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
    assert state.state == "95"


async def test_diffuser_offline_sensors_unavailable(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test sensors follow the diffuser state, without waiting for their update."""
    config_entry = mock_config_entry(unique_id="id_123_diffuser_offline")
    diffuser = mock_diffuser_v1_battery_cartridge()
    client = await init_integration(hass, config_entry, [diffuser])

    diffuser.available = False
    await _tick(hass, freezer, timedelta(minutes=5))

    assert client.sensors.call_count == 1
    for entity_id in ("sensor.genie_perfume", "binary_sensor.genie_charging"):
        state = hass.states.get(entity_id)
        assert state
        assert state.state == STATE_UNAVAILABLE


async def test_hubs_failure_sensors_unavailable(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test sensors become unavailable when the diffusers can't be fetched."""
    config_entry = mock_config_entry(unique_id="id_123_hubs_failure")
    client = await init_integration(
        hass, config_entry, [mock_diffuser_v1_battery_cartridge()]
    )

    client.hubs.side_effect = RitualsGenieConnectionError
    await _tick(hass, freezer, timedelta(minutes=5))

    assert client.sensors.call_count == 1
    for entity_id in ("sensor.genie_perfume", "binary_sensor.genie_charging"):
        state = hass.states.get(entity_id)
        assert state
        assert state.state == STATE_UNAVAILABLE


async def test_model_fetched_once(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test the model of each diffuser is fetched only once."""
    config_entry = mock_config_entry(unique_id="id_123_model_once")
    client = await init_integration(
        hass,
        config_entry,
        [
            mock_diffuser_v1_battery_cartridge(),
            mock_diffuser_v2_no_battery_no_cartridge(),
        ],
    )
    assert client.hublot.call_count == 2

    await _tick(hass, freezer, timedelta(minutes=5))
    await _tick(hass, freezer, timedelta(minutes=5))

    assert client.hublot.call_count == 2


async def test_model_failure(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test a failing model lookup keeps the known model, and is retried."""
    config_entry = mock_config_entry(unique_id="id_123_model_failure")
    config_entry.add_to_hass(hass)
    device = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, "lot123")},
        model="The Perfume Genie 2.0",
    )
    client = mock_client([mock_diffuser("lot123", model="Genie 3.0")])
    hardware = client.hublot.side_effect
    client.hublot.side_effect = RitualsGenieConnectionError

    with patch(
        "homeassistant.components.rituals_perfume_genie.RitualsGenie",
        return_value=client,
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED
    device = device_registry.async_get(device.id)
    assert device
    assert device.model == "The Perfume Genie 2.0"

    client.hublot.side_effect = hardware
    await _tick(hass, freezer, timedelta(minutes=5))

    device = device_registry.async_get(device.id)
    assert device
    assert device.model == "Genie 3.0"
