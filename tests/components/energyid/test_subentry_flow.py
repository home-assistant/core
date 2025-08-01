"""Tests for the EnergyID options flow (subentry flow)."""

import datetime as dt
from unittest.mock import AsyncMock, MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.energyid.const import (
    CONF_ENERGYID_KEY,
    CONF_HA_ENTITY_ID,
    DATA_CLIENT,
    DOMAIN,
)
from homeassistant.components.energyid.subentry_flow import (
    _create_mapping_option,
    _get_suggested_entities,
    _send_initial_state,
    _suggest_energyid_key,
)
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry


async def test_get_suggested_entities_with_state_handling(hass: HomeAssistant) -> None:
    """Test _get_suggested_entities filtering based on properties and state."""
    ent_reg = er.async_get(hass)
    mock_entry_data = [
        {
            "entity_id": "sensor.sensor_total_increasing",
            "domain": "sensor",
            "platform": "test",
            "capabilities": {"state_class": SensorStateClass.TOTAL_INCREASING},
            "device_class": None,
            "original_device_class": None,
            "state": STATE_UNKNOWN,
        },
        {
            "entity_id": "sensor.sensor_power",
            "domain": "sensor",
            "platform": "test",
            "capabilities": {},
            "device_class": SensorDeviceClass.POWER,
            "original_device_class": SensorDeviceClass.POWER,
            "state": "123.4",
        },
        {
            "entity_id": "sensor.sensor_numeric_only",
            "domain": "sensor",
            "platform": "test",
            "capabilities": {},
            "device_class": None,
            "original_device_class": None,
            "state": "50",
        },
        {
            "entity_id": "sensor.sensor_non_numeric",
            "domain": "sensor",
            "platform": "test",
            "capabilities": {},
            "device_class": SensorDeviceClass.TEMPERATURE,
            "original_device_class": SensorDeviceClass.TEMPERATURE,
            "state": "cloudy",
        },
        {
            "entity_id": "sensor.sensor_mapped",
            "domain": "sensor",
            "platform": "test",
            "capabilities": {},
            "device_class": None,
            "original_device_class": None,
            "state": "10",
        },
        {
            "entity_id": "sensor.energyid_status_sensor",
            "domain": "sensor",
            "platform": DOMAIN,
            "capabilities": {},
            "device_class": None,
            "original_device_class": None,
            "state": "1",
        },
        {
            "entity_id": "light.kitchen",
            "domain": "light",
            "platform": "test",
            "capabilities": {},
            "device_class": None,
            "original_device_class": None,
            "state": "on",
        },
    ]

    mock_registry_entries = {}
    for data in mock_entry_data:
        hass.states.async_set(data["entity_id"], data["state"])
        entry_mock = MagicMock()
        entry_mock.entity_id = data["entity_id"]
        entry_mock.domain = data["domain"]
        entry_mock.platform = data["platform"]
        entry_mock.capabilities = data["capabilities"]
        entry_mock.device_class = data["device_class"]
        entry_mock.original_device_class = data["original_device_class"]
        mock_registry_entries[data["entity_id"]] = entry_mock

    current_mappings = {
        "sensor.sensor_mapped": {
            "ha_entity_id": "sensor.sensor_mapped",
            "energyid_key": "el",
        }
    }

    with patch.object(
        ent_reg.entities, "values", return_value=mock_registry_entries.values()
    ):
        suggested = _get_suggested_entities(hass, current_mappings)

    assert "sensor.sensor_total_increasing" in suggested
    assert "sensor.sensor_power" in suggested
    assert "sensor.sensor_numeric_only" in suggested
    assert "sensor.sensor_non_numeric" not in suggested
    assert "sensor.sensor_mapped" not in suggested
    assert "sensor.energyid_status_sensor" not in suggested
    assert "light.kitchen" not in suggested
    assert sorted(suggested) == sorted(
        [
            "sensor.sensor_total_increasing",
            "sensor.sensor_power",
            "sensor.sensor_numeric_only",
        ]
    )


@pytest.mark.parametrize(
    ("entity_id", "expected_key"),
    [
        ("sensor.total_energy_consumption", "el"),
        ("sensor.solar_production_total", "pv"),
        ("sensor.gas_meter", "gas"),
        ("sensor.main_power", "pwr"),
        ("sensor.battery_soc", "bat-soc"),
        ("sensor.ev_battery_level", "bat-soc"),
        ("sensor.water_usage", "dw"),
        ("sensor.living_room_temperature", "temp"),
        ("sensor.wind_speed", ""),
        (None, ""),
        ("", ""),
    ],
)
def test_suggest_energyid_key(entity_id: str | None, expected_key: str) -> None:
    """Test suggesting EnergyID keys based on entity IDs."""
    assert _suggest_energyid_key(entity_id) == expected_key


def test_create_mapping_option() -> None:
    """Test creating mapping option labels."""
    option = _create_mapping_option("sensor.my_power_sensor", {"energyid_key": "pwr"})
    assert option["label"] == "my_power_sensor → pwr (Grid offtake power (kW))"
    option_custom = _create_mapping_option(
        "sensor.custom", {"energyid_key": "custom_key"}
    )
    assert option_custom["label"] == "custom → custom_key"


async def test_send_initial_state_errors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test errors during initial state sending."""
    mock_config_entry.add_to_hass(hass)
    entity_id = "sensor.test_state_error"

    hass.data.pop(DOMAIN, None)
    with pytest.raises(
        ValueError,
        match=f"Integration data not found for entry {mock_config_entry.entry_id}",
    ):
        await _send_initial_state(hass, entity_id, "key1", mock_config_entry)

    hass.data[DOMAIN] = {}
    hass.data[DOMAIN][mock_config_entry.entry_id] = {"dummy_key": "dummy_value"}

    with pytest.raises(
        ValueError,
        match=f"Webhook client not found for entry {mock_config_entry.entry_id}",
    ):
        await _send_initial_state(hass, entity_id, "key1", mock_config_entry)

    mock_client = MagicMock()
    hass.data[DOMAIN][mock_config_entry.entry_id][DATA_CLIENT] = mock_client
    hass.states.async_set(entity_id, "not_a_number")
    await _send_initial_state(hass, entity_id, "key2", mock_config_entry)
    assert "Cannot convert" in caplog.text
    mock_client.update_sensor.assert_not_called()

    mock_client.reset_mock()
    caplog.clear()
    hass.states.async_set(entity_id, STATE_UNAVAILABLE)
    await _send_initial_state(hass, entity_id, "key3", mock_config_entry)
    assert f"Current state is {STATE_UNAVAILABLE}" in caplog.text
    mock_client.update_sensor.assert_not_called()


async def test_send_initial_state_with_valid_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test sending initial state successfully."""
    now = dt.datetime(2023, 1, 1, 12, 0, 0, tzinfo=dt.UTC)
    freezer.move_to(now)
    mock_config_entry.add_to_hass(hass)
    entity_id = "sensor.test_valid_state"
    energyid_key = "el_test"
    state_value = "123.45"

    mock_client = AsyncMock()
    hass.data.setdefault(DOMAIN, {})[mock_config_entry.entry_id] = {
        DATA_CLIENT: mock_client
    }
    hass.states.async_set(entity_id, state_value, {"last_updated": now})

    await _send_initial_state(hass, entity_id, energyid_key, mock_config_entry)

    mock_client.update_sensor.assert_called_once_with(
        energyid_key, float(state_value), now
    )


@pytest.mark.usefixtures("mock_webhook_client")
async def test_add_mapping_with_exceptions(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test exception handling during initial state send."""
    mock_config_entry.add_to_hass(hass)
    entity_id = "sensor.exception_test"
    hass.states.async_set(entity_id, "10")

    mock_client = MagicMock()
    error_message = "Client error during initial send"
    mock_client.update_sensor = AsyncMock(side_effect=ValueError(error_message))

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][mock_config_entry.entry_id] = {DATA_CLIENT: mock_client}

    result_init = await hass.config_entries.options.async_init(
        mock_config_entry.entry_id
    )

    flow_id = result_init["flow_id"]

    result_add = await hass.config_entries.options.async_configure(
        flow_id, user_input={"next_step": "add_mapping"}
    )

    add_flow_id = result_add["flow_id"]

    with patch(
        "homeassistant.components.energyid.subentry_flow._get_suggested_entities",
        return_value=[entity_id],
    ):
        await hass.config_entries.options.async_configure(
            add_flow_id,
            user_input={
                CONF_HA_ENTITY_ID: entity_id,
                CONF_ENERGYID_KEY: "exception_key",
            },
        )

    await hass.async_block_till_done()

    assert mock_client.update_sensor.call_count == 1
    assert error_message in caplog.text
