"""Test setup of zeversolar local integration."""
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
from zeversolarlocal.api import SolarData, ZeverError, ZeverTimeout

from homeassistant.components.zeversolar.const import (
    COORDINATOR,
    DOMAIN,
    ZEVER_INVERTER_ID,
)
from homeassistant.const import CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt

from tests.common import MockConfigEntry, async_fire_time_changed

INVERTER_ID = "abcd"


@pytest.fixture
async def zever_entry(hass):
    """Mock zever entry added to hass."""
    entry_data = {
        CONF_URL: "http://1.1.1.1/home.cgi",
        ZEVER_INVERTER_ID: INVERTER_ID,
        "title": "Zeversolar invertor.",
    }
    mock_entry = MockConfigEntry(domain=DOMAIN, unique_id="1234", data=entry_data)

    mock_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.zeversolar.config_flow.api.solardata",
        return_value=SolarData(daily_energy=1, current_power=2),
    ):
        await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()

    return mock_entry


def get_daily_energy(hass: HomeAssistant) -> str:
    """Return state of daily total generated energy.

    helper function.
    """
    total_energy_name = f"sensor.total_generated_energy_{INVERTER_ID}"
    generated_energy = hass.states.get(total_energy_name)
    return generated_energy.state


def get_current_power(hass: HomeAssistant) -> str:
    """Return the state of current solar power production.

    helper function.
    """
    power_production_name = f"sensor.current_solar_power_production_{INVERTER_ID}"
    current_power = hass.states.get(power_production_name)
    return current_power.state


async def test_setup(hass: HomeAssistant, zever_entry: MockConfigEntry):
    """Test a successful setup."""

    registry = er.async_get(hass)

    total_energy_name = f"sensor.total_generated_energy_{INVERTER_ID}"
    total_energy_entity = registry.async_get(total_energy_name)
    assert total_energy_entity
    assert INVERTER_ID in total_energy_entity.unique_id
    generated_energy = hass.states.get(total_energy_name)
    assert generated_energy.state == "1"

    power_production_name = f"sensor.current_solar_power_production_{INVERTER_ID}"
    current_power_entity = registry.async_get(power_production_name)
    assert current_power_entity
    assert INVERTER_ID in total_energy_entity.unique_id
    current_power = hass.states.get(power_production_name)
    assert current_power.state == "2"


class dummy_date_time:
    """A dummy datetime."""

    def __init__(self) -> None:
        """Init."""
        self._current = datetime.now()

    def now(self, *args, **kwargs):
        """Now in the future."""
        return datetime.now() + timedelta(hours=60)


async def test_24hr_error(hass: HomeAssistant, zever_entry: MockConfigEntry):
    """Test a successful setup."""

    data = hass.data[DOMAIN][zever_entry.entry_id]
    coordinator = data[COORDINATOR]

    with patch(
        "homeassistant.components.zeversolar.api.solardata",
        return_value=SolarData(daily_energy=2, current_power=3),
    ):
        # await coordinator.async_refresh()
        async_fire_time_changed(hass, dt.now() + timedelta(seconds=20))
        await hass.async_block_till_done()

        assert get_current_power(hass) == "3"
        assert get_daily_energy(hass) == "2"

    with patch(
        "homeassistant.components.zeversolar.api.solardata", side_effect=ZeverError
    ):
        # An error which should be swallowed. Nothing serious.
        # await coordinator.async_refresh()
        async_fire_time_changed(hass, dt.now() + timedelta(seconds=20))
        await hass.async_block_till_done()

        assert get_current_power(hass) == "3"
        assert get_daily_energy(hass) == "2"

    with patch(
        "homeassistant.components.zeversolar.api.solardata", side_effect=ZeverTimeout
    ):
        # await coordinator.async_refresh()
        async_fire_time_changed(hass, dt.now() + timedelta(seconds=20))

        await hass.async_block_till_done()

        assert get_current_power(hass) == "0"
        assert get_daily_energy(hass) == "2"

    with patch(
        "homeassistant.components.zeversolar.api.solardata", side_effect=ZeverTimeout
    ):
        async_fire_time_changed(hass, dt.now() + timedelta(seconds=20))
        await hass.async_block_till_done()

        assert get_current_power(hass) == "0"
        assert get_daily_energy(hass) == "2"

    with patch(
        "homeassistant.components.zeversolar.api.solardata", side_effect=ZeverTimeout
    ), patch(
        "homeassistant.components.zeversolar.dt.now",
        return_value=dt.now() + timedelta(hours=27),
    ):
        async_fire_time_changed(hass, dt.now() + timedelta(seconds=20))
        await hass.async_block_till_done()

        assert get_current_power(hass) == "unavailable"
        assert coordinator.last_exception is not None


async def test_new_day(hass: HomeAssistant, zever_entry: MockConfigEntry):
    """Test return values when a new day has arrived."""

    with patch(
        "homeassistant.components.zeversolar.api.solardata", side_effect=ZeverTimeout
    ):
        async_fire_time_changed(hass, dt.now() + timedelta(seconds=20))
        await hass.async_block_till_done()

        assert get_current_power(hass) == "0"
        assert get_daily_energy(hass) == "1"

    with patch(
        "homeassistant.components.zeversolar.api.solardata", side_effect=ZeverTimeout
    ), patch(
        "homeassistant.components.zeversolar.dt.now",
        return_value=dt.now() + timedelta(hours=24),
    ):
        async_fire_time_changed(hass, dt.now() + timedelta(seconds=20))
        await hass.async_block_till_done()

        assert get_current_power(hass) == "0"
        assert get_daily_energy(hass) == "0"
