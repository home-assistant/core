"""Tests for the Sun WEG sensor."""

from datetime import timedelta
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
from sunweg.api import APIHelper
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.sunweg.const import DOMAIN
from homeassistant.components.sunweg.coordinator import SCAN_INTERVAL
from homeassistant.core import HomeAssistant, dt_util
from homeassistant.setup import async_setup_component

from .common import SUNWEG_MOCK_ENTRY

from tests.common import async_fire_time_changed


async def test_sensor_total(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    freezer: FrozenDateTimeFactory,
    plant_fixture,
    plant_fixture_alternative,
) -> None:
    """Test sensor type total."""
    mock_entry = SUNWEG_MOCK_ENTRY
    mock_entry.add_to_hass(hass)

    with (
        patch.object(APIHelper, "authenticate", return_value=True),
        patch.object(APIHelper, "listPlants", return_value=[plant_fixture]),
        patch.object(APIHelper, "plant", return_value=plant_fixture),
        patch.object(APIHelper, "complete_inverter"),
    ):
        assert await async_setup_component(hass, DOMAIN, mock_entry.data)
        freezer.tick(SCAN_INTERVAL)
        async_fire_time_changed(hass, dt_util.now() + timedelta(minutes=20))
        await hass.async_block_till_done(wait_background_tasks=True)

        state = hass.states.get("sensor.plant_123_total_money_lifetime")
        assert state.state == snapshot
        assert state.attributes == snapshot

        state = hass.states.get("sensor.plant_123_total_energy_today")
        assert state.state == snapshot
        assert state.attributes == snapshot

        state = hass.states.get("sensor.plant_123_total_output_power")
        assert state.state == snapshot
        assert state.attributes == snapshot

        state = hass.states.get("sensor.plant_123_total_lifetime_energy_output")
        assert state.state == snapshot
        assert state.attributes == snapshot

        state = hass.states.get("sensor.plant_123_total_kwh_per_kwp")
        assert state.state == snapshot
        assert state.attributes == snapshot

        state = hass.states.get("sensor.plant_123_total_last_update")
        assert state.state == snapshot
        assert state.attributes == snapshot

        with patch.object(APIHelper, "plant", return_value=plant_fixture_alternative):
            freezer.tick(SCAN_INTERVAL)
            async_fire_time_changed(hass, dt_util.now() + timedelta(minutes=20))
            await hass.async_block_till_done(wait_background_tasks=True)

            state = hass.states.get("sensor.plant_123_total_last_update")
            assert state.state == snapshot
            assert state.attributes == snapshot


async def test_sensor_inverter(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    freezer: FrozenDateTimeFactory,
    plant_fixture,
) -> None:
    """Test sensor type inverter."""
    mock_entry = SUNWEG_MOCK_ENTRY
    mock_entry.add_to_hass(hass)

    with (
        patch.object(APIHelper, "authenticate", return_value=True),
        patch.object(APIHelper, "listPlants", return_value=[plant_fixture]),
        patch.object(APIHelper, "plant", return_value=plant_fixture),
        patch.object(APIHelper, "complete_inverter"),
    ):
        assert await async_setup_component(hass, DOMAIN, mock_entry.data)
        freezer.tick(SCAN_INTERVAL)
        async_fire_time_changed(hass, dt_util.now() + timedelta(minutes=20))
        await hass.async_block_till_done(wait_background_tasks=True)

        state = hass.states.get("sensor.inversor01_energy_today")
        assert state.state == snapshot
        assert state.attributes == snapshot

        state = hass.states.get("sensor.inversor01_lifetime_energy_output")
        assert state.state == snapshot
        assert state.attributes == snapshot

        state = hass.states.get("sensor.inversor01_ac_frequency")
        assert state.state == snapshot
        assert state.attributes == snapshot

        state = hass.states.get("sensor.inversor01_output_power")
        assert state.state == snapshot
        assert state.attributes == snapshot

        state = hass.states.get("sensor.inversor01_temperature")
        assert state.state == snapshot
        assert state.attributes == snapshot

        state = hass.states.get("sensor.inversor01_power_factor")
        assert state.state == snapshot
        assert state.attributes == snapshot


async def test_sensor_phase(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    freezer: FrozenDateTimeFactory,
    plant_fixture,
) -> None:
    """Test sensor type phase."""
    mock_entry = SUNWEG_MOCK_ENTRY
    mock_entry.add_to_hass(hass)

    with (
        patch.object(APIHelper, "authenticate", return_value=True),
        patch.object(APIHelper, "listPlants", return_value=[plant_fixture]),
        patch.object(APIHelper, "plant", return_value=plant_fixture),
        patch.object(APIHelper, "complete_inverter"),
    ):
        assert await async_setup_component(hass, DOMAIN, mock_entry.data)
        freezer.tick(SCAN_INTERVAL)
        async_fire_time_changed(hass, dt_util.now() + timedelta(minutes=20))
        await hass.async_block_till_done(wait_background_tasks=True)

        state = hass.states.get("sensor.inversor01_phasea_voltage")
        assert state.state == snapshot
        assert state.attributes == snapshot

        state = hass.states.get("sensor.inversor01_phasea_amperage")
        assert state.state == snapshot
        assert state.attributes == snapshot


async def test_sensor_string(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    freezer: FrozenDateTimeFactory,
    plant_fixture,
) -> None:
    """Test sensor type string."""
    mock_entry = SUNWEG_MOCK_ENTRY
    mock_entry.add_to_hass(hass)

    with (
        patch.object(APIHelper, "authenticate", return_value=True),
        patch.object(APIHelper, "listPlants", return_value=[plant_fixture]),
        patch.object(APIHelper, "plant", return_value=plant_fixture),
        patch.object(APIHelper, "complete_inverter"),
    ):
        assert await async_setup_component(hass, DOMAIN, mock_entry.data)
        freezer.tick(SCAN_INTERVAL)
        async_fire_time_changed(hass, dt_util.now() + timedelta(minutes=20))
        await hass.async_block_till_done(wait_background_tasks=True)

        state = hass.states.get("sensor.inversor01_str1_voltage")
        assert state.state == snapshot
        assert state.attributes == snapshot

        state = hass.states.get("sensor.inversor01_str1_amperage")
        assert state.state == snapshot
        assert state.attributes == snapshot
