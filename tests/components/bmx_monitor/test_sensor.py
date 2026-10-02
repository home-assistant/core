"""Test BM2 sensor conversion, registration and entity properties."""

from datetime import timedelta
from time import monotonic
from unittest.mock import MagicMock, patch

from bmx_ble import BM2Generation, BM2Protocol, BM2Reading
from freezegun.api import FrozenDateTimeFactory
import pytest
from sensor_state_data import DeviceKey, SensorUpdate

from homeassistant.components.bluetooth.passive_update_processor import (
    PassiveBluetoothEntityKey,
)
from homeassistant.components.bmx_monitor import sensor
from homeassistant.components.bmx_monitor.const import (
    CONF_BATTERY_TYPE,
    CONF_RATE_LIMIT_MODE,
    DOMAIN,
)
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from tests.common import MockConfigEntry, async_fire_time_changed
from tests.components.bluetooth import (
    async_setup_with_default_adapter,
    generate_advertisement_data,
    generate_ble_device,
    inject_advertisement_with_time_and_source_connectable,
)

ADDRESS = "AA:BB:CC:DD:EE:FF"


@pytest.mark.parametrize("key", list(sensor.SENSOR_DESCRIPTIONS))
def test_update_conversion(key: str) -> None:
    """Map each supported reading to its HA description and entity key."""
    device_key = DeviceKey(key, ADDRESS)
    bluetooth_key = PassiveBluetoothEntityKey(key, ADDRESS)
    update = MagicMock(spec=SensorUpdate)
    device_info = MagicMock()
    update.devices = {ADDRESS: device_info}
    update.entity_descriptions = {device_key: MagicMock()}
    update.entity_values = {device_key: MagicMock(native_value=42)}
    converted_info = {"name": "BM2"}
    with patch.object(
        sensor, "sensor_device_info_to_hass_device_info", return_value=converted_info
    ) as convert:
        result = sensor.sensor_update_to_bluetooth_data_update(update)
    convert.assert_called_once_with(device_info)
    assert result.devices == {ADDRESS: converted_info}
    assert result.entity_descriptions == {
        bluetooth_key: sensor.SENSOR_DESCRIPTIONS[key]
    }
    assert result.entity_data == {bluetooth_key: 42}
    assert result.entity_names == {}


def test_empty_update() -> None:
    """An update with no readings creates no phantom entities."""
    update = MagicMock(spec=SensorUpdate)
    update.devices = {}
    update.entity_descriptions = {}
    update.entity_values = {}
    result = sensor.sensor_update_to_bluetooth_data_update(update)
    assert result.devices == {}
    assert result.entity_descriptions == {}
    assert result.entity_data == {}


@pytest.mark.usefixtures("mock_bluetooth", "entity_registry_enabled_by_default")
@pytest.mark.parametrize("connectable", [False, True])
async def test_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
    connectable: bool,
) -> None:
    """Advertisements create and update sensors through the real BLE processors."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=ADDRESS,
        options={CONF_BATTERY_TYPE: "Lead-acid", CONF_RATE_LIMIT_MODE: "never"},
    )
    entry.add_to_hass(hass)
    await async_setup_with_default_adapter(hass)
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    await hass.async_block_till_done(wait_background_tasks=True)

    device = generate_ble_device(ADDRESS, "Battery Monitor")
    advertisement = generate_advertisement_data(
        local_name="Battery Monitor",
        manufacturer_data={27928: bytes.fromhex("95185a633bc8fafdea8897c7c435")},
        rssi=-60,
    )
    inject_advertisement_with_time_and_source_connectable(
        hass, device, advertisement, monotonic(), "test-proxy", connectable
    )
    await hass.async_block_till_done(wait_background_tasks=True)
    assert not hass.states.async_all("sensor")

    with patch.object(
        BM2Protocol,
        "async_poll",
        side_effect=[
            BM2Reading(
                12.5,
                67,
                2 if connectable else None,
                "active" if connectable else "advertisement",
            ),
            BM2Reading(
                14.5,
                80,
                4 if connectable else None,
                "active" if connectable else "advertisement",
            ),
        ],
    ) as poll:
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)
        poll.assert_awaited_once()
        assert (poll.call_args.args[1] is not None) is connectable

        expected = {
            "battery_voltage": "12.5",
            "battery_percent": "90",
            "battery_status": "normal",
            "battery_chemistry": "Lead-acid",
            "bm2_generation": str(BM2Generation.ENHANCED),
            "signal_strength": "-60",
        }
        entity_ids = {}
        for key, value in expected.items():
            entity_id = entity_registry.async_get_entity_id(
                "sensor", DOMAIN, f"{ADDRESS}-{key}"
            )
            assert entity_id is not None
            entity_ids[key] = entity_id
            state = hass.states.get(entity_id)
            assert state is not None
            assert state.state == value
        assert (
            len(er.async_entries_for_config_entry(entity_registry, entry.entry_id)) == 6
        )

        # The real coordinator debounces polls even when rate limiting is disabled.
        freezer.tick(timedelta(seconds=11))
        async_fire_time_changed(hass, dt_util.utcnow())
        await hass.async_block_till_done(wait_background_tasks=True)
        advertisement = generate_advertisement_data(
            local_name="Battery Monitor",
            manufacturer_data={28183: bytes.fromhex("ef5156042924d1202023336420b7")},
            rssi=-65,
        )
        inject_advertisement_with_time_and_source_connectable(
            hass, device, advertisement, monotonic(), "test-proxy", connectable
        )
        await hass.async_block_till_done(wait_background_tasks=True)
        assert poll.await_count == 2
        expected |= {
            "battery_voltage": "14.5",
            "battery_percent": "100",
            "battery_status": "charging",
            "signal_strength": "-65",
        }
        for key, value in expected.items():
            state = hass.states.get(entity_ids[key])
            assert state is not None
            assert state.state == value
        assert (
            len(er.async_entries_for_config_entry(entity_registry, entry.entry_id)) == 6
        )

        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)
        for entity_id in entity_ids.values():
            state = hass.states.get(entity_id)
            assert state is not None
            assert state.state == "unavailable"


@pytest.mark.parametrize("value", [12.5, 67, "charging", None])
def test_native_value(value: float | str | None) -> None:
    """The entity exposes its processor's latest value, including missing data."""
    entity = MagicMock()
    entity.entity_key = PassiveBluetoothEntityKey("battery_voltage", ADDRESS)
    entity.processor.entity_data = {entity.entity_key: value}
    assert sensor.BMxBluetoothSensorEntity.native_value.fget(entity) == value


@pytest.mark.parametrize("available", [True, False])
def test_availability(available: bool) -> None:
    """Unavailable processors expose assumed rather than live sensor states."""
    entity = MagicMock()
    entity.processor.available = available
    assert sensor.BMxBluetoothSensorEntity.available.fget(entity) is available
    assert sensor.BMxBluetoothSensorEntity.assumed_state.fget(entity) is not available
