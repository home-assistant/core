"""Test the Airthings sensors."""

from unittest.mock import AsyncMock, patch

from airthings import AirthingsDevice

from homeassistant.components.airthings import DOMAIN
from homeassistant.core import HomeAssistant

from . import TEST_DATA

from tests.common import MockConfigEntry


async def init_with_device(hass: HomeAssistant, device: AirthingsDevice) -> None:
    """Set up the Airthings integration in Home Assistant with a single device."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        data=TEST_DATA,
    )

    mock_airthings = AsyncMock()
    mock_airthings.update_devices.return_value = {device.device_id: device}

    with (
        patch(
            "airthings.get_token",
            return_value="test_token",
        ),
        patch(
            "homeassistant.components.airthings.Airthings",
            return_value=mock_airthings,
        ),
    ):
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()


async def assert_device(
    hass: HomeAssistant,
    sensors: dict[str, float],
    states: dict[str, str | None],
) -> None:
    """Test Airthings device states against sensor values."""

    device = AirthingsDevice(
        device_id="1234567890",
        name="Bedroom",
        sensors=sensors,
        # Unused attributes
        is_active=True,
        device_type="...",
        product_name="...",
        location_name="...",
    )
    await init_with_device(hass, device)

    for entity_id_suffix, expected_state_value in states.items():
        entity_id = "sensor.bedroom_" + entity_id_suffix
        if expected_state_value is None:
            assert hass.states.get(entity_id) is None
        else:
            entity_state = hass.states.get(entity_id)
            assert (
                entity_state.state if entity_state else None
            ) == expected_state_value


async def test_view_plus_sensors(hass: HomeAssistant) -> None:
    """Test View Plus device sensors."""

    await assert_device(
        hass=hass,
        sensors={
            "battery": 1.1,
            "co2": 2.2,
            "humidity": 3.3,
            "pm1": 4.4,
            "pm25": 5.5,
            "pressure": 6.6,
            "radonShortTermAvg": 7.7,
            "temp": 8.8,
            "voc": 9.9,
        },
        states={
            "battery": "1.1",
            "carbon_dioxide": "2.2",
            "humidity": "3.3",
            "pm1": "4.4",
            "pm2_5": "5.5",
            "atmospheric_pressure": "6.6",
            "radon": "7.7",
            "temperature": "8.8",
            "volatile_organic_compounds_parts": "9.9",
            "illuminance": None,
        },
    )


async def test_wave_enhance_sensors(hass: HomeAssistant) -> None:
    """Test Wave Enhance device sensors."""

    await assert_device(
        hass=hass,
        sensors={
            "battery": 1.1,
            "co2": 2.2,
            "humidity": 3.3,
            "lux": 4.4,
            "pressure": 5.5,
            "sla": 6.6,
            "temp": 7.7,
            "voc": 8.8,
        },
        states={
            "battery": "1.1",
            "carbon_dioxide": "2.2",
            "humidity": "3.3",
            "illuminance": "4.4",
            "atmospheric_pressure": "5.5",
            # sla with 6.6 not supported yet
            "temperature": "7.7",
            "volatile_organic_compounds_parts": "8.8",
            "pm1": None,
            "pm2_5": None,
        },
    )


async def test_wave_plus_sensors(hass: HomeAssistant) -> None:
    """Test Wave Plus device sensors."""

    await assert_device(
        hass=hass,
        sensors={
            "battery": 1.1,
            "co2": 2.2,
            "humidity": 3.3,
            "pressure": 4.4,
            "radonShortTermAvg": 5.5,
            "temp": 6.6,
            "voc": 7.7,
        },
        states={
            "battery": "1.1",
            "carbon_dioxide": "2.2",
            "humidity": "3.3",
            "atmospheric_pressure": "4.4",
            "radon": "5.5",
            "temperature": "6.6",
            "volatile_organic_compounds_parts": "7.7",
            "pm1": None,
            "pm2_5": None,
            "illuminance": None,
        },
    )
