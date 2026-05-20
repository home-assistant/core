"""Tests for Wibeee sensors."""

from __future__ import annotations

from unittest.mock import MagicMock

from homeassistant.components.wibeee.const import (
    CONF_MAC_ADDRESS,
    CONF_UPDATE_MODE,
    CONF_WIBEEE_ID,
    DOMAIN,
    MODE_LOCAL_PUSH,
    MODE_POLLING,
)
from homeassistant.const import CONF_HOST, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant

from .conftest import MOCK_HOST, MOCK_MAC, MOCK_WIBEEE_ID

from tests.common import MockConfigEntry


async def test_sensors_created(
    hass: HomeAssistant, loaded_entry: MockConfigEntry
) -> None:
    """Test that sensor entities are created."""
    states = hass.states.async_all("sensor")
    # Should have sensors for the discovered phases
    entity_ids = {state.entity_id for state in states}
    assert "sensor.wibeee_2233_active_power" in entity_ids
    assert "sensor.wibeee_2233_l1_active_power" in entity_ids


async def test_sensor_state_class(
    hass: HomeAssistant, loaded_entry: MockConfigEntry
) -> None:
    """Test sensor has correct state class."""
    state = hass.states.get("sensor.wibeee_2233_active_power")
    assert state.attributes.get("state_class") == "measurement"


async def test_sensor_no_data(
    hass: HomeAssistant, loaded_entry: MockConfigEntry
) -> None:
    """Test sensor handles missing data."""
    # Wipe coordinator data
    runtime = loaded_entry.runtime_data
    coordinator = runtime.coordinator
    coordinator.async_set_updated_data(None)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.wibeee_2233_active_power")
    assert state.state == STATE_UNAVAILABLE


async def test_sensor_invalid_value(
    hass: HomeAssistant, loaded_entry: MockConfigEntry
) -> None:
    """Test sensor handles non-numeric values."""
    runtime = loaded_entry.runtime_data
    coordinator = runtime.coordinator

    # Inject non-numeric data
    invalid_data = {
        "fase4": {
            "p_activa": "not_a_number",
        }
    }
    coordinator.async_set_updated_data(invalid_data)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.wibeee_2233_active_power")
    assert state.state == STATE_UNAVAILABLE


async def test_sensors_push_mode_filters_polling_only_keys(
    hass: HomeAssistant, mock_wibeee_api: MagicMock
) -> None:
    """Push mode must skip sensors whose keys cannot be refreshed via push."""
    # Initial fetch reports a polling-only metric (angle) plus a push-refreshable
    # one (p_activa). In push mode, only the latter should produce an entity.
    mock_wibeee_api.async_fetch_sensors_data.return_value = {
        "fase4": {"p_activa": "120", "angle": "33"},
    }

    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=MOCK_MAC,
        title="Wibeee 2233",
        data={
            CONF_HOST: MOCK_HOST,
            CONF_MAC_ADDRESS: MOCK_MAC,
            CONF_WIBEEE_ID: MOCK_WIBEEE_ID,
        },
        options={CONF_UPDATE_MODE: MODE_LOCAL_PUSH},
        version=2,
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.wibeee_2233_active_power") is not None
    # angle is not push-refreshable, so the entity must not exist in push mode
    assert hass.states.get("sensor.wibeee_2233_angle") is None


async def test_sensors_polling_mode_keeps_all_keys(
    hass: HomeAssistant, mock_wibeee_api: MagicMock
) -> None:
    """Polling mode keeps all sensors, including polling-only metrics."""
    mock_wibeee_api.async_fetch_sensors_data.return_value = {
        "fase4": {"p_activa": "120", "angle": "33"},
    }

    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=MOCK_MAC,
        title="Wibeee 2233",
        data={
            CONF_HOST: MOCK_HOST,
            CONF_MAC_ADDRESS: MOCK_MAC,
            CONF_WIBEEE_ID: MOCK_WIBEEE_ID,
        },
        options={CONF_UPDATE_MODE: MODE_POLLING},
        version=2,
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Both should exist; angle is disabled-by-default so check the entity registry
    from homeassistant.helpers import entity_registry as er  # noqa: PLC0415

    registry = er.async_get(hass)
    assert registry.async_get(f"sensor.wibeee_{MOCK_MAC[-4:]}_active_power") is not None
    assert registry.async_get(f"sensor.wibeee_{MOCK_MAC[-4:]}_angle") is not None


async def test_sensor_setup_no_data_returns_early(
    hass: HomeAssistant,
) -> None:
    """sensor.async_setup_entry must return early when coordinator has no data."""
    from homeassistant.components.wibeee.sensor import (  # noqa: PLC0415
        async_setup_entry,
    )

    coordinator = MagicMock()
    coordinator.data = None
    runtime = MagicMock()
    runtime.coordinator = coordinator
    runtime.device_info = MagicMock(mac_addr_short="2233", ip_addr=MOCK_HOST)
    entry = MagicMock()
    entry.runtime_data = runtime
    entry.options = {}

    added: list = []

    def _add(entities, update_before_add=False) -> None:
        added.extend(entities)

    await async_setup_entry(hass, entry, _add)
    assert added == []


async def test_sensor_setup_no_phases_returns_early(
    hass: HomeAssistant,
) -> None:
    """sensor.async_setup_entry must return early when no known phases found."""
    from homeassistant.components.wibeee.sensor import (  # noqa: PLC0415
        async_setup_entry,
    )

    coordinator = MagicMock()
    # Data with only unknown phase keys → discovered_phases stays empty.
    coordinator.data = {"unknown_phase": {"vrms": "230"}}
    runtime = MagicMock()
    runtime.coordinator = coordinator
    runtime.device_info = MagicMock(mac_addr_short="2233", ip_addr=MOCK_HOST)
    entry = MagicMock()
    entry.runtime_data = runtime
    entry.options = {}

    added: list = []

    def _add(entities, update_before_add=False) -> None:
        added.extend(entities)

    await async_setup_entry(hass, entry, _add)
    assert added == []


async def test_sensor_native_value_non_dict_data(
    hass: HomeAssistant, loaded_entry: MockConfigEntry
) -> None:
    """native_value returns None when coordinator.data is not a dict."""
    from homeassistant.components.wibeee.const import SENSOR_TYPES  # noqa: PLC0415
    from homeassistant.components.wibeee.sensor import WibeeeSensor  # noqa: PLC0415

    runtime = loaded_entry.runtime_data
    coordinator = runtime.coordinator
    sensor = WibeeeSensor(
        coordinator=coordinator,
        device_info=runtime.device_info,
        phase_key="fase4",
        description=SENSOR_TYPES["p_activa"],
    )

    coordinator.data = "not_a_dict"  # type: ignore[assignment]
    assert sensor.native_value is None


async def test_sensor_native_value_phase_not_dict(
    hass: HomeAssistant, loaded_entry: MockConfigEntry
) -> None:
    """native_value returns None when phase data is not a dict."""
    from homeassistant.components.wibeee.const import SENSOR_TYPES  # noqa: PLC0415
    from homeassistant.components.wibeee.sensor import WibeeeSensor  # noqa: PLC0415

    runtime = loaded_entry.runtime_data
    coordinator = runtime.coordinator
    sensor = WibeeeSensor(
        coordinator=coordinator,
        device_info=runtime.device_info,
        phase_key="fase4",
        description=SENSOR_TYPES["p_activa"],
    )

    coordinator.data = {"fase4": "garbage"}  # type: ignore[dict-item]
    assert sensor.native_value is None


async def test_sensor_native_value_missing_key(
    hass: HomeAssistant, loaded_entry: MockConfigEntry
) -> None:
    """native_value returns None when the sensor key is absent from phase."""
    from homeassistant.components.wibeee.const import SENSOR_TYPES  # noqa: PLC0415
    from homeassistant.components.wibeee.sensor import WibeeeSensor  # noqa: PLC0415

    runtime = loaded_entry.runtime_data
    coordinator = runtime.coordinator
    sensor = WibeeeSensor(
        coordinator=coordinator,
        device_info=runtime.device_info,
        phase_key="fase4",
        description=SENSOR_TYPES["p_activa"],
    )

    coordinator.data = {"fase4": {"vrms": "230.0"}}
    assert sensor.native_value is None


async def test_sensor_native_value_invalid_number(
    hass: HomeAssistant, loaded_entry: MockConfigEntry
) -> None:
    """native_value returns None when value can't be parsed as a float."""
    from homeassistant.components.wibeee.const import SENSOR_TYPES  # noqa: PLC0415
    from homeassistant.components.wibeee.sensor import WibeeeSensor  # noqa: PLC0415

    runtime = loaded_entry.runtime_data
    coordinator = runtime.coordinator
    sensor = WibeeeSensor(
        coordinator=coordinator,
        device_info=runtime.device_info,
        phase_key="fase4",
        description=SENSOR_TYPES["p_activa"],
    )

    coordinator.data = {"fase4": {"p_activa": "not_a_number"}}
    assert sensor.native_value is None
