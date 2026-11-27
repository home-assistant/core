"""Test the BTHome events."""

from collections.abc import Generator
import logging
import time
from typing import Any
from unittest.mock import patch

from cryptography.hazmat.primitives.ciphers.aead import AESCCM
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_capture_events
from pytest_homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    FakeScanner,
    generate_advertisement_data,
    generate_ble_device,
    inject_advertisement_with_time_and_source_connectable,
    inject_bluetooth_service_info,
)

from homeassistant.components.bluetooth import async_register_scanner
from homeassistant.components.bthome.const import (
    BTHOME_BLE_EVENT,
    CONF_BINDKEY,
    CONF_SLEEPY_DEVICE,
    DOMAIN,
)
from homeassistant.components.event import EventEntityStateAttribute
from homeassistant.const import (
    ATTR_FRIENDLY_NAME,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant

from . import BTHOME_UUID, make_bthome_v2_adv


@pytest.mark.parametrize(
    ("mac_address", "advertisement", "bind_key", "result"),
    [
        (
            "A4:C1:38:8D:18:B2",
            make_bthome_v2_adv(
                "A4:C1:38:8D:18:B2",
                b"\x40\x3a\x00\x3a\x01\x3a\x03",
            ),
            None,
            [
                {
                    "entity": "event.test_device_18b2_button_2",
                    ATTR_FRIENDLY_NAME: "Test Device 18B2 Button 2",
                    EventEntityStateAttribute.EVENT_TYPE: "press",
                },
                {
                    "entity": "event.test_device_18b2_button_3",
                    ATTR_FRIENDLY_NAME: "Test Device 18B2 Button 3",
                    EventEntityStateAttribute.EVENT_TYPE: "triple_press",
                },
            ],
        ),
        (
            "A4:C1:38:8D:18:B2",
            make_bthome_v2_adv(
                "A4:C1:38:8D:18:B2",
                b"\x40\x3a\x04",
            ),
            None,
            [
                {
                    "entity": "event.test_device_18b2_button",
                    ATTR_FRIENDLY_NAME: "Test Device 18B2 Button",
                    EventEntityStateAttribute.EVENT_TYPE: "long_press",
                }
            ],
        ),
        (
            "A4:C1:38:8D:18:B2",
            make_bthome_v2_adv(
                "A4:C1:38:8D:18:B2",
                b"\x40\x3a\x81",
            ),
            None,
            [
                {
                    "entity": "event.test_device_18b2_button",
                    ATTR_FRIENDLY_NAME: "Test Device 18B2 Button",
                    EventEntityStateAttribute.EVENT_TYPE: "hold_release",
                }
            ],
        ),
        (
            "A4:C1:38:8D:18:B2",
            make_bthome_v2_adv(
                "A4:C1:38:8D:18:B2",
                b"\x40\x3b\x00\x01\x3b\x00\x02",
            ),
            None,
            [
                {
                    "entity": "event.test_device_18b2_command_1",
                    ATTR_FRIENDLY_NAME: "Test Device 18B2 Command 1",
                    EventEntityStateAttribute.EVENT_TYPE: "on",
                },
                {
                    "entity": "event.test_device_18b2_command_2",
                    ATTR_FRIENDLY_NAME: "Test Device 18B2 Command 2",
                    EventEntityStateAttribute.EVENT_TYPE: "toggle",
                },
            ],
        ),
    ],
)
async def test_v2_events(
    hass: HomeAssistant,
    mac_address: str,
    advertisement: BluetoothServiceInfoBleak,
    bind_key: str | None,
    result: list[dict[str, str]],
) -> None:
    """Test the different BTHome V2 events."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=mac_address,
        data={"bindkey": bind_key},
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 0

    inject_bluetooth_service_info(
        hass,
        advertisement,
    )
    await hass.async_block_till_done()
    assert len(hass.states.async_all()) == len(result)

    for meas in result:
        state = hass.states.get(meas["entity"])
        attributes = state.attributes
        assert attributes[ATTR_FRIENDLY_NAME] == meas[ATTR_FRIENDLY_NAME]
        assert (
            attributes[EventEntityStateAttribute.EVENT_TYPE]
            == meas[EventEntityStateAttribute.EVENT_TYPE]
        )
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Ensure entities are restored
    for meas in result:
        state = hass.states.get(meas["entity"])
        assert state != STATE_UNAVAILABLE

    # Now inject again
    inject_bluetooth_service_info(
        hass,
        advertisement,
    )
    await hass.async_block_till_done()
    assert len(hass.states.async_all()) == len(result)

    for meas in result:
        state = hass.states.get(meas["entity"])
        attributes = state.attributes
        assert attributes[ATTR_FRIENDLY_NAME] == meas[ATTR_FRIENDLY_NAME]
        assert (
            attributes[EventEntityStateAttribute.EVENT_TYPE]
            == meas[EventEntityStateAttribute.EVENT_TYPE]
        )
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


BUTTON_ADDRESS = "A4:C1:38:8D:18:B2"
STRONG_PROXY = "strong_proxy"
WEAK_PROXY = "weak_proxy"
CONNECTABLE_PROXY = "connectable_proxy"
WINDOW_ENTITY_ID = "binary_sensor.test_device_18b2_window"
BUTTON_ENTITY_ID = "event.test_device_18b2_button"


@pytest.fixture
def proxies(hass: HomeAssistant) -> Generator[None]:
    """Register a strong, a weak and a connectable proxy for the whole test."""
    cancels = [
        async_register_scanner(hass, FakeScanner(STRONG_PROXY, STRONG_PROXY)),
        async_register_scanner(hass, FakeScanner(WEAK_PROXY, WEAK_PROXY)),
        async_register_scanner(
            hass, FakeScanner(CONNECTABLE_PROXY, CONNECTABLE_PROXY, connectable=True)
        ),
    ]
    yield
    for cancel in cancels:
        cancel()


def _inject_button_payload(
    hass: HomeAssistant,
    payload: bytes,
    source: str,
    rssi: int,
    adv_time: float,
    connectable: bool = False,
) -> None:
    """Inject a button advertisement heard by one proxy."""
    inject_advertisement_with_time_and_source_connectable(
        hass,
        generate_ble_device(BUTTON_ADDRESS, "Test Device"),
        generate_advertisement_data(
            local_name="Test Device",
            service_data={BTHOME_UUID: payload},
            service_uuids=[BTHOME_UUID],
            rssi=rssi,
        ),
        adv_time,
        source,
        connectable=connectable,
    )


@pytest.mark.usefixtures("proxies")
@pytest.mark.parametrize(
    ("first_payload", "second_payload", "expected_events"),
    [
        pytest.param(
            b"\x44\x00\x01\x3a\x01",
            b"\x44\x00\x02\x3a\x02",
            ["press", "double_press"],
            id="sleepy_with_packet_id",
        ),
        pytest.param(
            b"\x40\x00\x01\x3a\x01",
            b"\x40\x00\x02\x3a\x02",
            ["press"],
            id="not_sleepy",
        ),
        pytest.param(
            b"\x44\x3a\x01",
            b"\x44\x3a\x02",
            ["press", "double_press"],
            id="no_packet_id",
        ),
    ],
)
async def test_event_from_non_owner_proxy(
    hass: HomeAssistant,
    first_payload: bytes,
    second_payload: bytes,
    expected_events: list[str],
) -> None:
    """Test a sleepy device's new packet heard only by a weaker proxy."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id=BUTTON_ADDRESS)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    events = async_capture_events(hass, BTHOME_BLE_EVENT)
    now = time.monotonic()

    _inject_button_payload(hass, first_payload, STRONG_PROXY, -60, now)
    # Hand the weak proxy a copy, so the device is known by both proxies
    _inject_button_payload(hass, first_payload, WEAK_PROXY, -90, now + 0.1)
    await hass.async_block_till_done()
    # The weak proxy is not 16 dB stronger, so only the event-driven rule takes it
    _inject_button_payload(hass, second_payload, WEAK_PROXY, -90, now + 5)
    await hass.async_block_till_done()

    assert [event.data["event_type"] for event in events] == expected_events


@pytest.mark.usefixtures("proxies")
async def test_copies_of_one_packet_fire_one_event(hass: HomeAssistant) -> None:
    """Test copies of one packet from several proxies fire one event."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id=BUTTON_ADDRESS)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    events = async_capture_events(hass, BTHOME_BLE_EVENT)
    now = time.monotonic()

    _inject_button_payload(hass, b"\x44\x00\x01\x3a\x01", STRONG_PROXY, -60, now)
    _inject_button_payload(hass, b"\x44\x00\x01\x3a\x01", WEAK_PROXY, -90, now + 1)
    _inject_button_payload(hass, b"\x44\x00\x02\x3a\x02", WEAK_PROXY, -90, now + 5)
    _inject_button_payload(hass, b"\x44\x00\x02\x3a\x02", STRONG_PROXY, -60, now + 5.5)
    await hass.async_block_till_done()

    assert [event.data["event_type"] for event in events] == ["press", "double_press"]


@pytest.mark.usefixtures("proxies")
async def test_reload_keeps_taking_packets_from_any_proxy(
    hass: HomeAssistant,
) -> None:
    """Test a reload keeps the newest state and registers the device again."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id=BUTTON_ADDRESS)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    events = async_capture_events(hass, BTHOME_BLE_EVENT)
    now = time.monotonic()

    _inject_button_payload(
        hass, b"\x44\x00\x01\x3a\x01\x2d\x01", STRONG_PROXY, -60, now
    )
    _inject_button_payload(
        hass, b"\x44\x00\x01\x3a\x01\x2d\x01", WEAK_PROXY, -90, now + 0.1
    )
    await hass.async_block_till_done()
    _inject_button_payload(hass, b"\x44\x00\x02\x2d\x00", WEAK_PROXY, -90, now + 5)
    await hass.async_block_till_done()
    assert hass.states.get(WINDOW_ENTITY_ID).state == STATE_OFF

    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(WINDOW_ENTITY_ID).state == STATE_OFF
    assert [event.data["event_type"] for event in events] == ["press"]

    _inject_button_payload(hass, b"\x44\x00\x03\x2d\x01", STRONG_PROXY, -60, now + 10)
    await hass.async_block_till_done()
    assert hass.states.get(WINDOW_ENTITY_ID).state == STATE_ON
    # The strong proxy owns the device, so only the event-driven rule takes this
    _inject_button_payload(hass, b"\x44\x00\x04\x2d\x00", WEAK_PROXY, -90, now + 15)
    await hass.async_block_till_done()
    assert hass.states.get(WINDOW_ENTITY_ID).state == STATE_OFF


@pytest.mark.usefixtures("proxies")
@pytest.mark.parametrize(
    ("first_payload", "second_payload", "late_proxy", "connectable"),
    [
        pytest.param(
            b"\x44\x00\x01\x3a\x01\x2d\x01",
            b"\x44\x00\x02\x3a\x02\x2d\x00",
            STRONG_PROXY,
            False,
            id="packet_id",
        ),
        pytest.param(
            b"\x44\x3a\x01\x2d\x01",
            b"\x44\x3a\x02\x2d\x00",
            STRONG_PROXY,
            False,
            id="no_packet_id",
        ),
        pytest.param(
            b"\x44\x3a\x01\x2d\x01",
            b"\x44\x3a\x02\x2d\x00",
            CONNECTABLE_PROXY,
            True,
            id="no_packet_id_connectable",
        ),
    ],
)
async def test_late_copy_of_older_packet_is_ignored(
    hass: HomeAssistant,
    first_payload: bytes,
    second_payload: bytes,
    late_proxy: str,
    connectable: bool,
) -> None:
    """Test a stronger proxy's late copy of an older packet keeps the newer one."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id=BUTTON_ADDRESS)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    events = async_capture_events(hass, BTHOME_BLE_EVENT)
    now = time.monotonic()

    _inject_button_payload(hass, first_payload, STRONG_PROXY, -60, now)
    _inject_button_payload(hass, first_payload, WEAK_PROXY, -90, now + 0.1)
    await hass.async_block_till_done()
    _inject_button_payload(hass, second_payload, WEAK_PROXY, -90, now + 5)
    await hass.async_block_till_done()
    # 30 dB stronger, but a repeat of the older packet within the repeat window
    _inject_button_payload(hass, first_payload, late_proxy, -60, now + 6, connectable)
    await hass.async_block_till_done()

    assert hass.states.get(WINDOW_ENTITY_ID).state == STATE_OFF
    assert [event.data["event_type"] for event in events] == ["press", "double_press"]

    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(WINDOW_ENTITY_ID).state == STATE_OFF
    assert [event.data["event_type"] for event in events] == ["press", "double_press"]


@pytest.mark.parametrize(
    "mock_bluetooth_storage",
    [
        (
            {
                STRONG_PROXY: {BUTTON_ADDRESS: (b"\x44\x00\x01\x2d\x01", -60, 60)},
                WEAK_PROXY: {BUTTON_ADDRESS: (b"\x44\x00\x02\x2d\x00", -90, 10)},
            },
            {BUTTON_ADDRESS: (WEAK_PROXY, (b"\x44\x00\x02\x2d\x00", -90, 10))},
        )
    ],
    indirect=True,
)
async def test_setup_replays_accepted_packet(hass: HomeAssistant) -> None:
    """Test setup after a restart replays the packet accepted before it."""
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id=BUTTON_ADDRESS, data={CONF_SLEEPY_DEVICE: True}
    )
    entry.add_to_hass(hass)

    # Startup kept the strong proxy's older open, the weak proxy's close came later
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(WINDOW_ENTITY_ID).state == STATE_OFF


@pytest.mark.usefixtures("proxies")
@pytest.mark.parametrize(
    "mock_bluetooth_storage",
    [({}, {BUTTON_ADDRESS: (WEAK_PROXY, (b"\x44\x00\x07\x3a\x01", -90, 7200))})],
    indirect=True,
)
async def test_restored_press_fires_no_event(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test a press replayed from before a restart doesn't fire an event."""
    caplog.set_level(logging.DEBUG, "homeassistant.components.bthome")
    events = async_capture_events(hass, BTHOME_BLE_EVENT)
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id=BUTTON_ADDRESS, data={CONF_SLEEPY_DEVICE: True}
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert events == []
    assert hass.states.get(BUTTON_ENTITY_ID).state == STATE_UNKNOWN
    assert (
        "Not firing button press of a replayed packet restored from before the start"
        in caplog.text
    )

    _inject_button_payload(
        hass, b"\x44\x00\x08\x3a\x01", STRONG_PROXY, -60, time.monotonic()
    )
    await hass.async_block_till_done()

    assert [event.data["event_type"] for event in events] == ["press"]
    assert hass.states.get(BUTTON_ENTITY_ID).state != STATE_UNKNOWN


@pytest.mark.usefixtures("proxies")
async def test_reload_fires_no_event_for_last_press(hass: HomeAssistant) -> None:
    """Test a reload doesn't fire the last press again."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id=BUTTON_ADDRESS)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    events = async_capture_events(hass, BTHOME_BLE_EVENT)
    _inject_button_payload(
        hass, b"\x44\x00\x01\x3a\x01", STRONG_PROXY, -60, time.monotonic()
    )
    await hass.async_block_till_done()
    pressed = hass.states.get(BUTTON_ENTITY_ID).state

    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()

    assert [event.data["event_type"] for event in events] == ["press"]
    assert hass.states.get(BUTTON_ENTITY_ID).state == pressed


@pytest.mark.usefixtures("proxies")
async def test_press_during_reload_fires_event(hass: HomeAssistant) -> None:
    """Test a press received while the entry reloads still fires an event."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id=BUTTON_ADDRESS)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    events = async_capture_events(hass, BTHOME_BLE_EVENT)
    now = time.monotonic()
    _inject_button_payload(hass, b"\x44\x00\x01\x3a\x01", STRONG_PROXY, -60, now)
    await hass.async_block_till_done()

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    _inject_button_payload(hass, b"\x44\x00\x02\x3a\x02", STRONG_PROXY, -60, now + 5)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert [event.data["event_type"] for event in events] == ["press", "double_press"]


@pytest.mark.usefixtures("proxies")
async def test_press_before_first_start_fires_event(hass: HomeAssistant) -> None:
    """Test a press heard after startup but before the entry starts fires."""
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id=BUTTON_ADDRESS, data={CONF_SLEEPY_DEVICE: True}
    )
    entry.add_to_hass(hass)
    events = async_capture_events(hass, BTHOME_BLE_EVENT)
    _inject_button_payload(
        hass, b"\x44\x00\x01\x3a\x01", STRONG_PROXY, -60, time.monotonic() + 1
    )

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert [event.data["event_type"] for event in events] == ["press"]


@pytest.mark.usefixtures("proxies")
async def test_identical_press_during_reload_fires_event(hass: HomeAssistant) -> None:
    """Test a later press without packet id, identical to the last, still fires."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id=BUTTON_ADDRESS)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    events = async_capture_events(hass, BTHOME_BLE_EVENT)
    now = time.monotonic()
    _inject_button_payload(hass, b"\x44\x3a\x01", STRONG_PROXY, -60, now)
    await hass.async_block_till_done()

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    _inject_button_payload(hass, b"\x44\x3a\x01", STRONG_PROXY, -60, now + 20)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert [event.data["event_type"] for event in events] == ["press", "press"]


BINDKEY = "231d39c1d7cc1ab1aee224cd096db932"


def _encrypted_payload(payload: bytes, counter: int) -> bytes:
    """Return a BTHome v2 payload of a trigger-based device, encrypted."""
    adv_info = 0x45
    counter_bytes = counter.to_bytes(4, "little")
    nonce = (
        bytes.fromhex(BUTTON_ADDRESS.replace(":", ""))
        + b"\xd2\xfc"
        + bytes([adv_info])
        + counter_bytes
    )
    encrypted = AESCCM(bytes.fromhex(BINDKEY), tag_length=4).encrypt(
        nonce, payload, None
    )
    return bytes([adv_info]) + encrypted[:-4] + counter_bytes + encrypted[-4:]


@pytest.mark.usefixtures("proxies")
async def test_press_decrypted_after_reauth_fires_event(hass: HomeAssistant) -> None:
    """Test a press that couldn't be decrypted fires once the bindkey is added."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id=BUTTON_ADDRESS)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    events = async_capture_events(hass, BTHOME_BLE_EVENT)
    _inject_button_payload(
        hass,
        _encrypted_payload(b"\x00\x01\x3a\x01", 1),
        STRONG_PROXY,
        -60,
        time.monotonic(),
    )
    await hass.async_block_till_done()
    assert events == []

    hass.config_entries.async_update_entry(
        entry, data=entry.data | {CONF_BINDKEY: BINDKEY}
    )
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()

    assert [event.data["event_type"] for event in events] == ["press"]


@pytest.mark.usefixtures("proxies")
async def test_press_while_unloading_reaches_event_entity(
    hass: HomeAssistant,
) -> None:
    """Test a press after the event entity unloaded is delivered after reload."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id=BUTTON_ADDRESS)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    events = async_capture_events(hass, BTHOME_BLE_EVENT)
    now = time.monotonic()
    _inject_button_payload(hass, b"\x44\x00\x01\x3a\x01", STRONG_PROXY, -60, now)
    await hass.async_block_till_done()
    unload_platforms = hass.config_entries.async_unload_platforms_or_raise

    async def _unload_platforms_then_press(*args: Any) -> None:
        await unload_platforms(*args)
        _inject_button_payload(
            hass, b"\x44\x00\x02\x3a\x02", STRONG_PROXY, -60, now + 5
        )

    with patch.object(
        hass.config_entries,
        "async_unload_platforms_or_raise",
        _unload_platforms_then_press,
    ):
        assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()

    assert [event.data["event_type"] for event in events] == ["press", "double_press"]
    assert (
        hass.states.get(BUTTON_ENTITY_ID).attributes[
            EventEntityStateAttribute.EVENT_TYPE
        ]
        == "double_press"
    )
