"""Test BM2 sensor conversion, registration and entity properties."""

import asyncio
from collections.abc import AsyncGenerator
from datetime import timedelta
from time import monotonic
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from bleak.exc import BleakError
from bmx_ble import BM2Generation, BM2Protocol, BM2Reading
from bmx_ble.battery import Battery
from bmx_ble.protocol import BM2_AES_IV, BM2_AES_KEY
from Crypto.Cipher import AES
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed
from pytest_homeassistant.components.bluetooth import (
    async_setup_with_default_adapter,
    generate_advertisement_data,
    generate_ble_device,
    inject_advertisement_with_time_and_source_connectable,
)
from sensor_state_data import DeviceKey, SensorUpdate

from homeassistant.components.bluetooth.passive_update_processor import (
    PassiveBluetoothEntityKey,
)
from homeassistant.components.bmx_monitor import sensor
from homeassistant.components.bmx_monitor.const import CONF_BATTERY_TYPE, DOMAIN
from homeassistant.components.bmx_monitor.device_data import MIN_POLL_INTERVAL
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

ADDRESS = "AA:BB:CC:DD:EE:FF"
LEGACY_ID = 0x004C
LEGACY_BODY = bytes.fromhex(
    "0215655f83caae16a10a702e31f30d58dd82" + "00010002" + "30"
)  # 48 %
ENHANCED_ID = 27928
ENHANCED_BODY = bytes.fromhex("95185a633bc8fafdea8897c7c435")  # 12.5 V, 67 %
LEGACY = (LEGACY_ID, LEGACY_BODY)
ENHANCED = (ENHANCED_ID, ENHANCED_BODY)
GATT_READING = BM2Reading(12.5, 67, 2, "gatt")
CUSTOM_OPTIONS = {CONF_BATTERY_TYPE: Battery.custom.value}
LEADACID_OPTIONS = {CONF_BATTERY_TYPE: Battery.leadacid.value}


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


class Clock:
    """Monotonic time shared by injected advertisements and the poll timer."""

    def __init__(self) -> None:
        """Start at the real monotonic time."""
        self.now = monotonic()
        self._elapsed = 0.0

    def __call__(self) -> float:
        """Return the current time."""
        return self.now

    def advance(self, hass: HomeAssistant, seconds: float) -> None:
        """Move time forward, firing any debounce cooldown that expires."""
        self.now += seconds
        self._elapsed += seconds
        async_fire_time_changed(
            hass, dt_util.utcnow() + timedelta(seconds=self._elapsed)
        )


def _inject(
    hass: HomeAssistant,
    clock: Clock,
    packet: tuple[int, bytes],
    connectable: bool = True,
) -> None:
    """Send one BM2 advertisement, with the raw bytes HA receives."""
    manufacturer_id, body = packet
    inject_advertisement_with_time_and_source_connectable(
        hass,
        generate_ble_device(ADDRESS, "Battery Monitor"),
        generate_advertisement_data(
            local_name="Battery Monitor",
            manufacturer_data={manufacturer_id: body},
            rssi=-60,
        ),
        clock.now,
        "test-proxy",
        connectable,
        raw=bytes([len(body) + 3, 0xFF]) + manufacturer_id.to_bytes(2, "little") + body,
    )


def _reading_states(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, entry: MockConfigEntry
) -> dict[str, str]:
    """Return the states of the entry's reading sensors, keyed by sensor key."""
    states = {}
    for entity in er.async_entries_for_config_entry(entity_registry, entry.entry_id):
        key = entity.unique_id.removeprefix(f"{ADDRESS}-")
        if key != "signal_strength":
            state = hass.states.get(entity.entity_id)
            assert state is not None
            states[key] = state.state
    return states


@pytest.fixture
async def clock(hass: HomeAssistant) -> AsyncGenerator[Clock]:
    """Run a started Bluetooth stack whose poll timer follows the test clock."""
    await async_setup_with_default_adapter(hass)
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    await hass.async_block_till_done(wait_background_tasks=True)
    test_clock = Clock()
    with patch(
        "homeassistant.components.bluetooth.active_update_processor.monotonic_time_coarse",
        side_effect=test_clock,
    ):
        yield test_clock


async def _setup(
    hass: HomeAssistant,
    clock: Clock,
    options: dict[str, Any],
    packet: tuple[int, bytes],
    connectable: bool = True,
) -> MockConfigEntry:
    """Set up from a real advertisement; validation decodes it passively."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id=ADDRESS, options=options)
    entry.add_to_hass(hass)
    _inject(hass, clock, packet, connectable)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    return entry


@pytest.mark.usefixtures("mock_bluetooth", "entity_registry_enabled_by_default")
@pytest.mark.parametrize(
    ("packet", "options", "connectable", "connects", "expected"),
    [
        pytest.param(
            LEGACY,
            {},
            True,
            True,
            {
                "battery_chemistry": "Automatic",
                "battery_percent": "48",
                "bm2_generation": str(BM2Generation.LEGACY),
            },
            id="legacy-automatic",
        ),
        # The device's own percentage disagrees with the chosen curve.
        pytest.param(LEGACY, LEADACID_OPTIONS, True, True, {}, id="legacy-chosen"),
        pytest.param(
            ENHANCED,
            {},
            True,
            True,
            {
                "battery_chemistry": "Automatic",
                "battery_voltage": "12.5",
                "battery_percent": "67",
                "bm2_generation": str(BM2Generation.ENHANCED),
            },
            id="enhanced-automatic",
        ),
        pytest.param(
            ENHANCED,
            {},
            False,
            False,
            {
                "battery_chemistry": "Automatic",
                "battery_voltage": "12.5",
                "battery_percent": "67",
                "bm2_generation": str(BM2Generation.ENHANCED),
            },
            id="enhanced-automatic-no-connectable-path",
        ),
        pytest.param(
            ENHANCED,
            LEADACID_OPTIONS,
            True,
            False,
            {
                "battery_chemistry": "Lead-acid",
                "battery_voltage": "12.5",
                "battery_percent": "90",
                "battery_status": "normal",
                "bm2_generation": str(BM2Generation.ENHANCED),
            },
            id="enhanced-chosen",
        ),
        pytest.param(
            ENHANCED,
            CUSTOM_OPTIONS,
            True,
            False,
            {
                "battery_chemistry": "Custom battery",
                "battery_voltage": "12.5",
                "battery_percent": "75",
                "battery_status": "normal",
                "bm2_generation": str(BM2Generation.ENHANCED),
            },
            id="enhanced-custom",
        ),
    ],
)
async def test_advertisement_publishing_and_connection_rules(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    clock: Clock,
    packet: tuple[int, bytes],
    options: dict[str, Any],
    connectable: bool,
    connects: bool,
    expected: dict[str, str],
) -> None:
    """Adverts publish what they carry; GATT is used only for what they lack."""
    with patch.object(
        BM2Protocol,
        "async_poll",
        new_callable=AsyncMock,
        side_effect=BleakError("connection failed"),
    ) as poll:
        entry = await _setup(hass, clock, options, packet, connectable)
        assert poll.await_count == int(connects)
        # A failed read publishes nothing beyond what the advertisement carried.
        assert _reading_states(hass, entity_registry, entry) == expected
        assert entry.runtime_data.last_poll_successful is not connects
        assert await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.usefixtures("mock_bluetooth", "entity_registry_enabled_by_default")
async def test_enhanced_chosen_never_connects(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    clock: Clock,
) -> None:
    """Later advertisements keep updating sensors without any connection."""
    with patch.object(BM2Protocol, "async_poll", new_callable=AsyncMock) as poll:
        entry = await _setup(hass, clock, LEADACID_OPTIONS, ENHANCED)
        clock.advance(hass, MIN_POLL_INTERVAL * 4)
        # 14.5 V, 80 %
        _inject(hass, clock, (28183, bytes.fromhex("ef5156042924d1202023336420b7")))
        await hass.async_block_till_done(wait_background_tasks=True)
        poll.assert_not_awaited()
        states = _reading_states(hass, entity_registry, entry)
        assert states["battery_voltage"] == "14.5"
        assert states["battery_percent"] == "100"
        assert states["battery_status"] == "charging"
        status_entity = entity_registry.async_get_entity_id(
            "sensor", DOMAIN, f"{ADDRESS}-battery_status"
        )
        assert status_entity is not None
        status_state = hass.states.get(status_entity)
        assert status_state is not None
        assert status_state.attributes["device_class"] == "enum"
        assert status_state.attributes["options"] == [
            "critical",
            "low",
            "normal",
            "charging",
            "floating",
        ]
        assert await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.usefixtures("mock_bluetooth", "entity_registry_enabled_by_default")
async def test_legacy_chosen_reads_at_fixed_interval(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    clock: Clock,
) -> None:
    """Adverts trigger reads no more often than the interval; a failure keeps data."""
    with patch.object(
        BM2Protocol,
        "async_poll",
        new_callable=AsyncMock,
        side_effect=[
            GATT_READING,
            BM2Reading(12.06, 30, 0, "gatt"),
            BleakError("connection failed"),
        ],
    ) as poll:
        entry = await _setup(hass, clock, LEADACID_OPTIONS, LEGACY)
        assert poll.await_count == 1
        voltage_derived = {
            "battery_chemistry": "Lead-acid",
            "battery_voltage": "12.5",
            "battery_percent": "90",
            "battery_status": "normal",
            "bm2_generation": str(BM2Generation.LEGACY),
        }
        assert _reading_states(hass, entity_registry, entry) == voltage_derived

        # Identical adverts still trigger reads, but not inside the interval.
        clock.advance(hass, MIN_POLL_INTERVAL - 1)
        _inject(hass, clock, LEGACY)
        await hass.async_block_till_done(wait_background_tasks=True)
        assert poll.await_count == 1

        clock.advance(hass, 1)
        _inject(hass, clock, LEGACY)
        await hass.async_block_till_done(wait_background_tasks=True)
        assert poll.await_count == 2
        voltage_derived |= {
            "battery_voltage": "12.06",
            "battery_percent": "50",
            "battery_status": "critical",
        }
        assert _reading_states(hass, entity_registry, entry) == voltage_derived

        clock.advance(hass, MIN_POLL_INTERVAL)
        _inject(hass, clock, LEGACY)
        await hass.async_block_till_done(wait_background_tasks=True)
        assert poll.await_count == 3
        assert not entry.runtime_data.last_poll_successful
        # Neither the advert's own 48 % nor anything cached is published.
        assert _reading_states(hass, entity_registry, entry) == voltage_derived
        assert await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.usefixtures("mock_bluetooth", "entity_registry_enabled_by_default")
async def test_no_second_read_while_connecting(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, clock: Clock
) -> None:
    """An advertisement during a real library read doesn't queue another read.

    Only the Bluetooth connection is faked, so bmx-ble's own async_poll runs and
    marks the read as in progress while it connects.
    """
    # 12.5 V; lead-acid derives the published status from voltage.
    notification = AES.new(BM2_AES_KEY, AES.MODE_CBC, BM2_AES_IV).encrypt(
        bytes.fromhex("004e2464" + "00" * 12)
    )
    client = MagicMock(address=ADDRESS)
    client.start_notify = AsyncMock(
        side_effect=lambda _uuid, callback: callback(0, bytearray(notification))
    )
    client.stop_notify = AsyncMock()
    client.disconnect = AsyncMock()
    connecting = asyncio.Event()
    release = asyncio.Event()

    async def connect(*_args: Any, **_kwargs: Any) -> MagicMock:
        connecting.set()
        await release.wait()
        return client

    entry = MockConfigEntry(domain=DOMAIN, unique_id=ADDRESS, options=LEADACID_OPTIONS)
    entry.add_to_hass(hass)
    with patch(
        "bmx_ble.protocol.establish_connection", side_effect=connect
    ) as establish:
        _inject(hass, clock, LEGACY)
        await hass.async_block_till_done()
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        await asyncio.wait_for(connecting.wait(), 5)
        device_data = entry.runtime_data._update_method.__self__
        assert device_data.ignore_advertisement

        # Past the minimum interval, so only the in-progress read stops a poll.
        clock.advance(hass, MIN_POLL_INTERVAL + 1)
        _inject(hass, clock, LEGACY)
        await hass.async_block_till_done()

        release.set()
        await hass.async_block_till_done(wait_background_tasks=True)
        assert not device_data.ignore_advertisement
        # Let the debounce cooldown expire; a queued duplicate would run now.
        clock.advance(hass, 11)
        await hass.async_block_till_done(wait_background_tasks=True)

        assert establish.await_count == 1
        client.disconnect.assert_awaited_once()
        states = _reading_states(hass, entity_registry, entry)
        assert states["battery_voltage"] == "12.5"
        assert states["battery_status"] == "normal"
        assert await hass.config_entries.async_unload(entry.entry_id)
