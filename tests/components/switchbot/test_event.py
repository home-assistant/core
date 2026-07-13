"""Test the switchbot event entities."""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from itertools import count
from unittest.mock import patch

import pytest

from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.components.switchbot.const import DOMAIN
from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, callback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.setup import async_setup_component

from . import (
    CLIMATE_PANEL_SERVICE_INFO,
    CONTACT_SENSOR_SERVICE_INFO,
    KEYPAD_VISION_PRO_INFO,
)

from tests.common import MockConfigEntry
from tests.components.bluetooth import (
    generate_advertisement_data,
    generate_ble_device,
    inject_bluetooth_service_info,
)


def _with_doorbell_seq(
    info: BluetoothServiceInfoBleak, seq: int = 1
) -> BluetoothServiceInfoBleak:
    """Return a BLE service info with the doorbell seq bits set."""
    mfr_data = bytearray(info.manufacturer_data[2409])
    mfr_data[12] = (mfr_data[12] & 0b11111000) | (seq & 0b00000111)
    updated_mfr_data = {2409: bytes(mfr_data)}
    return BluetoothServiceInfoBleak(
        name=info.name,
        manufacturer_data=updated_mfr_data,
        service_data=info.service_data,
        service_uuids=info.service_uuids,
        address=info.address,
        rssi=info.rssi,
        source=info.source,
        advertisement=generate_advertisement_data(
            local_name=info.name,
            manufacturer_data=updated_mfr_data,
            service_data=info.service_data,
            service_uuids=info.service_uuids,
        ),
        device=generate_ble_device(info.address, info.name),
        time=info.time,
        connectable=info.connectable,
        tx_power=info.tx_power,
    )


def _with_contact_button_count(
    info: BluetoothServiceInfoBleak, count: int
) -> BluetoothServiceInfoBleak:
    """Return a BLE service info with the contact sensor button_count bits set."""
    mfr_data = bytearray(info.manufacturer_data[2409])
    mfr_data[12] = (mfr_data[12] & 0b11110000) | (count & 0b00001111)
    updated_mfr_data = {2409: bytes(mfr_data)}
    return BluetoothServiceInfoBleak(
        name=info.name,
        manufacturer_data=updated_mfr_data,
        service_data=info.service_data,
        service_uuids=info.service_uuids,
        address=info.address,
        rssi=info.rssi,
        source=info.source,
        advertisement=generate_advertisement_data(
            local_name=info.name,
            manufacturer_data=updated_mfr_data,
            service_data=info.service_data,
            service_uuids=info.service_uuids,
        ),
        device=generate_ble_device(info.address, info.name),
        time=info.time,
        connectable=info.connectable,
        tx_power=info.tx_power,
    )


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_keypad_vision_pro_doorbell_event(
    hass: HomeAssistant,
    mock_entry_encrypted_factory: Callable[[str], MockConfigEntry],
) -> None:
    """Test keypad vision pro doorbell event uses doorbell_seq for detection."""
    # Make each ring's timestamp distinct so the entity's state value (which is
    # the iso-formatted timestamp at millisecond resolution) differs between
    # rings, ensuring state_changed fires for each. We avoid the `freezer`
    # fixture here because it patches time.monotonic, which warps loop.time
    # forward and causes the bluetooth manager's pre-scheduled unavailability
    # check to fire immediately and mark the injected device unavailable.
    timestamps = (
        datetime(2026, 1, 1, tzinfo=UTC) + timedelta(seconds=i) for i in count()
    )

    await async_setup_component(hass, DOMAIN, {})
    inject_bluetooth_service_info(hass, KEYPAD_VISION_PRO_INFO)

    entry = mock_entry_encrypted_factory(sensor_type="keypad_vision_pro")
    entry.add_to_hass(hass)

    entity_id = "event.test_name_doorbell"
    ring_states: list[str] = []

    @callback
    def _track_ring(event: Event[EventStateChangedData]) -> None:
        new_state = event.data["new_state"]
        if new_state and new_state.attributes.get("event_type") == "ring":
            ring_states.append(new_state.state)

    with (
        patch(
            "homeassistant.components.switchbot.sensor.switchbot.SwitchbotKeypadVision.update",
            return_value=True,
        ),
        patch(
            "homeassistant.components.event.dt_util.utcnow",
            side_effect=lambda: next(timestamps),
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        async_track_state_change_event(hass, entity_id, _track_ring)

        state = hass.states.get(entity_id)
        assert state
        assert state.state == STATE_UNKNOWN

        # First ring: seq changes from 0 → 1
        inject_bluetooth_service_info(
            hass, _with_doorbell_seq(KEYPAD_VISION_PRO_INFO, 1)
        )
        await hass.async_block_till_done()
        assert len(ring_states) == 1

        # Same seq repeated — no new ring event
        inject_bluetooth_service_info(
            hass, _with_doorbell_seq(KEYPAD_VISION_PRO_INFO, 1)
        )
        await hass.async_block_till_done()
        assert len(ring_states) == 1

        # Second ring: seq changes from 1 → 2
        inject_bluetooth_service_info(
            hass, _with_doorbell_seq(KEYPAD_VISION_PRO_INFO, 2)
        )
        await hass.async_block_till_done()
        assert len(ring_states) == 2

        # Seq wraps from 7 → 1 — still a ring
        inject_bluetooth_service_info(
            hass, _with_doorbell_seq(KEYPAD_VISION_PRO_INFO, 7)
        )
        await hass.async_block_till_done()
        assert len(ring_states) == 3

        inject_bluetooth_service_info(
            hass, _with_doorbell_seq(KEYPAD_VISION_PRO_INFO, 1)
        )
        await hass.async_block_till_done()
        assert len(ring_states) == 4


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_contact_sensor_button_event(
    hass: HomeAssistant,
    mock_entry_factory: Callable[[str], MockConfigEntry],
) -> None:
    """Test contact sensor button event fires on button_count changes and wrap-around."""
    # Make each press's timestamp distinct so the entity's state value (which is
    # the iso-formatted timestamp at millisecond resolution) differs between
    # presses, ensuring state_changed fires for each. We avoid the `freezer`
    # fixture here because it patches time.monotonic, which warps loop.time
    # forward and causes the bluetooth manager's pre-scheduled unavailability
    # check to fire immediately and mark the injected device unavailable.
    # The same workaround is used in test_keypad_vision_pro_doorbell_event.
    timestamps = (
        datetime(2026, 1, 1, tzinfo=UTC) + timedelta(seconds=i) for i in count()
    )

    await async_setup_component(hass, DOMAIN, {})
    inject_bluetooth_service_info(hass, CONTACT_SENSOR_SERVICE_INFO)

    entry = mock_entry_factory(sensor_type="contact")
    entry.add_to_hass(hass)

    entity_id = "event.test_name_button"
    press_states: list[str] = []

    @callback
    def _track_press(event: Event[EventStateChangedData]) -> None:
        new_state = event.data["new_state"]
        if new_state and new_state.attributes.get("event_type") == "press":
            press_states.append(new_state.state)

    with patch(
        "homeassistant.components.event.dt_util.utcnow",
        side_effect=lambda: next(timestamps),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        async_track_state_change_event(hass, entity_id, _track_press)

        state = hass.states.get(entity_id)
        assert state
        assert state.state == STATE_UNKNOWN

        inject_bluetooth_service_info(
            hass, _with_contact_button_count(CONTACT_SENSOR_SERVICE_INFO, 1)
        )
        await hass.async_block_till_done()
        assert len(press_states) == 1

        # Same count repeated, no new press fires.
        inject_bluetooth_service_info(
            hass, _with_contact_button_count(CONTACT_SENSOR_SERVICE_INFO, 1)
        )
        await hass.async_block_till_done()
        assert len(press_states) == 1

        inject_bluetooth_service_info(
            hass, _with_contact_button_count(CONTACT_SENSOR_SERVICE_INFO, 2)
        )
        await hass.async_block_till_done()
        assert len(press_states) == 2

        # Counter rolls over from 15 back to 1; still a press.
        inject_bluetooth_service_info(
            hass, _with_contact_button_count(CONTACT_SENSOR_SERVICE_INFO, 15)
        )
        await hass.async_block_till_done()
        assert len(press_states) == 3

        inject_bluetooth_service_info(
            hass, _with_contact_button_count(CONTACT_SENSOR_SERVICE_INFO, 1)
        )
        await hass.async_block_till_done()
        assert len(press_states) == 4


def _with_climate_panel_keystate(
    info: BluetoothServiceInfoBleak,
    *,
    on_counter: int = 0,
    off_counter: int = 0,
) -> BluetoothServiceInfoBleak:
    """Return a BLE service info with the Climate Panel keystate bytes set."""
    mfr_data = bytearray(info.manufacturer_data[2409])
    # Byte 13 = ON keystate, byte 14 = OFF keystate: bits[7:5] are the press
    # mode and bits[4:0] the counter. Use single-click mode (1) whenever a
    # press counter is set so the bytes resemble a real button press.
    mfr_data[13] = ((1 if on_counter else 0) << 5) | (on_counter & 0x1F)
    mfr_data[14] = ((1 if off_counter else 0) << 5) | (off_counter & 0x1F)
    updated_mfr_data = {2409: bytes(mfr_data)}
    return BluetoothServiceInfoBleak(
        name=info.name,
        manufacturer_data=updated_mfr_data,
        service_data=info.service_data,
        service_uuids=info.service_uuids,
        address=info.address,
        rssi=info.rssi,
        source=info.source,
        advertisement=generate_advertisement_data(
            local_name=info.name,
            manufacturer_data=updated_mfr_data,
            service_data=info.service_data,
            service_uuids=info.service_uuids,
        ),
        device=generate_ble_device(info.address, info.name),
        time=info.time,
        connectable=info.connectable,
        tx_power=info.tx_power,
    )


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_climate_panel_keystate_event(
    hass: HomeAssistant,
    mock_entry_encrypted_factory: Callable[[str], MockConfigEntry],
) -> None:
    """Test Climate Panel ON/OFF button events fire on keystate counter changes."""
    # Make each press's timestamp distinct so the entity's state value (the
    # iso-formatted timestamp) differs between presses, ensuring state_changed
    # fires each time. See test_keypad_vision_pro_doorbell_event for why the
    # `freezer` fixture is avoided here.
    timestamps = (
        datetime(2026, 1, 1, tzinfo=UTC) + timedelta(seconds=i) for i in count()
    )

    await async_setup_component(hass, DOMAIN, {})
    inject_bluetooth_service_info(hass, CLIMATE_PANEL_SERVICE_INFO)

    entry = mock_entry_encrypted_factory(sensor_type="climate_panel")
    entry.add_to_hass(hass)

    on_entity_id = "event.test_name_on_button"
    off_entity_id = "event.test_name_off_button"
    on_states: list[str] = []
    off_states: list[str] = []

    @callback
    def _track_on(event: Event[EventStateChangedData]) -> None:
        new_state = event.data["new_state"]
        if new_state and new_state.attributes.get("event_type") == "press":
            on_states.append(new_state.state)

    @callback
    def _track_off(event: Event[EventStateChangedData]) -> None:
        new_state = event.data["new_state"]
        if new_state and new_state.attributes.get("event_type") == "press":
            off_states.append(new_state.state)

    with patch(
        "homeassistant.components.event.dt_util.utcnow",
        side_effect=lambda: next(timestamps),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        async_track_state_change_event(hass, on_entity_id, _track_on)
        async_track_state_change_event(hass, off_entity_id, _track_off)

        # Both entities exist and start in the unknown (power-on) state.
        on_state = hass.states.get(on_entity_id)
        off_state = hass.states.get(off_entity_id)
        assert on_state
        assert off_state
        assert on_state.state == STATE_UNKNOWN
        assert off_state.state == STATE_UNKNOWN

        # ON press: on counter 0 → 1 fires; off counter stays 0.
        inject_bluetooth_service_info(
            hass, _with_climate_panel_keystate(CLIMATE_PANEL_SERVICE_INFO, on_counter=1)
        )
        await hass.async_block_till_done()
        assert len(on_states) == 1
        assert len(off_states) == 0

        # Same ON counter repeated — no new event.
        inject_bluetooth_service_info(
            hass, _with_climate_panel_keystate(CLIMATE_PANEL_SERVICE_INFO, on_counter=1)
        )
        await hass.async_block_till_done()
        assert len(on_states) == 1

        # OFF press: off counter 0 → 1 fires; on counter unchanged at 1.
        inject_bluetooth_service_info(
            hass,
            _with_climate_panel_keystate(
                CLIMATE_PANEL_SERVICE_INFO, on_counter=1, off_counter=1
            ),
        )
        await hass.async_block_till_done()
        assert len(on_states) == 1
        assert len(off_states) == 1

        # ON counter wraps from 30 back to 1 — still a press.
        inject_bluetooth_service_info(
            hass,
            _with_climate_panel_keystate(
                CLIMATE_PANEL_SERVICE_INFO, on_counter=30, off_counter=1
            ),
        )
        await hass.async_block_till_done()
        assert len(on_states) == 2
        inject_bluetooth_service_info(
            hass,
            _with_climate_panel_keystate(
                CLIMATE_PANEL_SERVICE_INFO, on_counter=1, off_counter=1
            ),
        )
        await hass.async_block_till_done()
        assert len(on_states) == 3
