"""Fixtures for Palazzetti integration tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

from pypalazzetti.temperature import TemperatureDefinition, TemperatureDescriptionKey
import pytest

from homeassistant.components.palazzetti.const import DOMAIN
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.palazzetti.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title="palazzetti",
        domain=DOMAIN,
        data={CONF_HOST: "127.0.0.1"},
        unique_id="11:22:33:44:55:66",
    )


@pytest.fixture
def mock_palazzetti_client() -> Generator[AsyncMock]:
    """Return a mocked PalazzettiClient."""
    with (
        patch(
            "homeassistant.components.palazzetti.coordinator.PalazzettiClient",
            autospec=True,
        ) as client,
        patch(
            "homeassistant.components.palazzetti.config_flow.PalazzettiClient",
            new=client,
        ),
    ):
        mock_client = client.return_value
        mock_client.mac = "11:22:33:44:55:66"
        mock_client.name = "Stove"
        mock_client.sw_version = "0.0.0"
        mock_client.hw_version = "1.1.1"
        mock_client.to_dict.return_value = {
            "host": "XXXXXXXXXX",
            "connected": True,
            "properties": {},
            "attributes": {},
        }
        mock_client.fan_speed_min = 1
        mock_client.fan_speed_max = 5
        mock_client.has_fan_silent = True
        mock_client.has_fan_high = True
        mock_client.has_fan_auto = True
        mock_client.has_on_off_switch = True
        mock_client.has_pellet_level = False
        mock_client.connected = True
        mock_client.status = 6
        mock_client.is_heating = True
        mock_client.room_temperature = 18
        mock_client.T1 = 21.5
        mock_client.T2 = 25.1
        mock_client.T3 = 45
        mock_client.T4 = 0
        mock_client.T5 = 0
        mock_client.target_temperature = 21
        mock_client.target_temperature_min = 5
        mock_client.target_temperature_max = 50
        mock_client.pellet_quantity = 1248
        mock_client.pellet_level = 0
        mock_client.has_second_fan = True
        mock_client.has_second_fan = False
        mock_client.fan_speed = 3
        mock_client.current_fan_speed.return_value = 3
        mock_client.min_fan_speed.return_value = 0
        mock_client.max_fan_speed.return_value = 5
        mock_client.connect.return_value = True
        mock_client.update_state.return_value = True
        mock_client.set_on.return_value = True
        mock_client.set_target_temperature.return_value = True
        mock_client.set_fan_speed.return_value = True
        mock_client.set_fan_silent.return_value = True
        mock_client.set_fan_high.return_value = True
        mock_client.set_fan_auto.return_value = True
        mock_client.set_power_mode.return_value = True
        mock_client.power_mode = 3
        mock_client.list_temperatures.return_value = [
            TemperatureDefinition(
                description_key=TemperatureDescriptionKey.ROOM_TEMP,
                state_property="T1",
            ),
            TemperatureDefinition(
                description_key=TemperatureDescriptionKey.RETURN_WATER_TEMP,
                state_property="T4",
            ),
            TemperatureDefinition(
                description_key=TemperatureDescriptionKey.TANK_WATER_TEMP,
                state_property="T5",
            ),
            TemperatureDefinition(
                description_key=TemperatureDescriptionKey.WOOD_COMBUSTION_TEMP,
                state_property="T3",
            ),
            TemperatureDefinition(
                description_key=TemperatureDescriptionKey.AIR_OUTLET_TEMP,
                state_property="T2",
            ),
            TemperatureDefinition(
                description_key=TemperatureDescriptionKey.T1_HYDRO_TEMP,
                state_property="T1",
            ),
            TemperatureDefinition(
                description_key=TemperatureDescriptionKey.T2_HYDRO_TEMP,
                state_property="T2",
            ),
        ]
        yield mock_client


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_palazzetti_client: MagicMock,
) -> MockConfigEntry:
    """Set up the Palazzetti integration for testing."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    return mock_config_entry
