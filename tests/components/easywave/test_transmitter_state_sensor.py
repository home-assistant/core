"""Tests for the Easywave transmitter state-sensor entities."""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.components.easywave.const import (
    CONF_BUTTON_COUNT,
    CONF_ENTRY_TYPE,
    CONF_GROUPING_MODE,
    CONF_OPERATING_TYPE,
    CONF_TRANSMITTER_SERIAL,
    CONF_USAGE_TYPE,
    DOMAIN,
    ENTRY_TYPE_TRANSMITTER,
    TRANSMITTER_GROUPING_SINGLE,
    TRANSMITTER_USAGE_COVER,
    TRANSMITTER_USAGE_SWITCH,
)
from homeassistant.components.event import ATTR_EVENT_TYPE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import MOCK_ENTRY_DATA, MOCK_TRANSMITTER_SERIAL

from tests.common import MockConfigEntry

MOCK_SUBENTRY_ID = "binary_sensor_subentry_test"


def _get_event_entity_id(hass: HomeAssistant, uid_suffix: str) -> str:
    """Look up an event entity by unique_id suffix."""
    unique_id = f"{MOCK_SUBENTRY_ID}_{uid_suffix}"
    registry = er.async_get(hass)
    entity_id = registry.async_get_entity_id("event", DOMAIN, unique_id)
    assert entity_id is not None, f"No event entity for unique_id {unique_id}"
    return entity_id


def _get_binary_sensor_entity_id(hass: HomeAssistant, uid_suffix: str) -> str:
    """Look up a binary_sensor entity by unique_id suffix."""
    unique_id = f"{MOCK_SUBENTRY_ID}_{uid_suffix}"
    registry = er.async_get(hass)
    entity_id = registry.async_get_entity_id("binary_sensor", DOMAIN, unique_id)
    assert entity_id is not None, f"No binary_sensor entity for unique_id {unique_id}"
    return entity_id


def _make_gateway(extra_data: dict[str, object]) -> MockConfigEntry:
    """Return a gateway entry with a transmitter subentry using given data."""
    return MockConfigEntry(
        version=1,
        domain=DOMAIN,
        title="Easywave Gateway",
        data=MOCK_ENTRY_DATA,
        source="usb",
        unique_id="easywave_12345",
        options={
            "devices": [
                {
                    "id": MOCK_SUBENTRY_ID,
                    "title": "Test Transmitter",
                    "unique_id": f"transmitter_{MOCK_TRANSMITTER_SERIAL}",
                    "data": {
                        CONF_ENTRY_TYPE: ENTRY_TYPE_TRANSMITTER,
                        CONF_TRANSMITTER_SERIAL: MOCK_TRANSMITTER_SERIAL,
                        **extra_data,
                    },
                }
            ]
        },
    )


def _patch_integration() -> tuple[Any, Any, Any, Any]:
    """Return patches for transceiver and coordinator."""
    mock_transceiver = MagicMock()
    mock_transceiver.is_connected = True
    mock_transceiver.usb_serial_number = "12345"
    mock_transceiver.hw_version = "1.0"
    mock_transceiver.fw_version = "2.0"
    mock_transceiver.device_path = "/dev/ttyACM0"

    mock_coordinator = MagicMock()
    mock_coordinator.async_config_entry_first_refresh = AsyncMock()
    mock_coordinator.async_shutdown = AsyncMock()
    mock_coordinator.async_add_listener = MagicMock(return_value=lambda: None)
    mock_coordinator.transceiver = mock_transceiver
    mock_coordinator.is_offline = False
    mock_coordinator.register_transmitter_entities = MagicMock()
    mock_coordinator.unregister_transmitter_entity = MagicMock()
    mock_coordinator.data = {"is_connected": True, "device_path": "/dev/ttyACM0"}

    transceiver_patch = patch(
        "homeassistant.components.easywave.RX11Transceiver",
        return_value=mock_transceiver,
    )
    coordinator_patch = patch(
        "homeassistant.components.easywave.EasywaveCoordinator",
        return_value=mock_coordinator,
    )

    return transceiver_patch, coordinator_patch, mock_transceiver, mock_coordinator


async def test_button_binary_sensor_created(hass: HomeAssistant) -> None:
    """Test sensor entities are created for type-1 individual (4-button) transmitter."""
    gateway = _make_gateway(
        {
            CONF_OPERATING_TYPE: "1",
            CONF_BUTTON_COUNT: 4,
            CONF_GROUPING_MODE: TRANSMITTER_GROUPING_SINGLE,
        }
    )
    gateway.add_to_hass(hass)
    hass.config.country = "DE"

    t_patch, c_patch, _, mock_coordinator = _patch_integration()
    with t_patch, c_patch:
        assert await hass.config_entries.async_setup(gateway.entry_id)
        await hass.async_block_till_done()

    # Four event entities should exist for buttons a-d; initial state is None
    # (no event has been fired yet).
    for suffix in ("button_a", "button_b", "button_c", "button_d"):
        state = hass.states.get(_get_event_entity_id(hass, suffix))
        assert state is not None, f"Missing event entity for {suffix}"
        assert state.state == "unknown"

    # register_transmitter_entities is called once per entity: four times for the
    # button EventEntities and once for the battery sensor.
    assert mock_coordinator.register_transmitter_entities.call_count == 5


async def test_button_binary_sensor_handle_telegram(hass: HomeAssistant) -> None:
    """Test sensor goes pressed on press and released on universal release."""
    gateway = _make_gateway(
        {
            CONF_OPERATING_TYPE: "1",
            CONF_BUTTON_COUNT: 4,
            CONF_GROUPING_MODE: TRANSMITTER_GROUPING_SINGLE,
        }
    )
    gateway.add_to_hass(hass)
    hass.config.country = "DE"

    captured_entities: list = []

    def _capture_entities(entities: list) -> None:
        captured_entities.extend(entities)

    t_patch, c_patch, _, mock_coordinator = _patch_integration()
    mock_coordinator.register_transmitter_entities.side_effect = _capture_entities

    with t_patch, c_patch:
        assert await hass.config_entries.async_setup(gateway.entry_id)
        await hass.async_block_till_done()

    entity_a = next(
        (e for e in captured_entities if getattr(e, "_button_index", None) == 0), None
    )
    entity_b = next(
        (e for e in captured_entities if getattr(e, "_button_index", None) == 1), None
    )
    assert entity_a is not None
    assert entity_b is not None

    # Press button A (index=0)
    entity_a.handle_telegram(0x01, 0)
    assert entity_a._is_pressed is True
    assert entity_a.state_attributes.get(ATTR_EVENT_TYPE) == "pressed"

    # Release — button A should clear its pressed flag
    entity_a.handle_telegram(0x00, 0)
    assert entity_a._is_pressed is False
    assert entity_a.state_attributes.get(ATTR_EVENT_TYPE) == "released"

    # Press button B (index=1)
    entity_b.handle_telegram(0x01, 1)
    assert entity_b._is_pressed is True
    assert entity_b.state_attributes.get(ATTR_EVENT_TYPE) == "pressed"

    # Release arrives with button=0 (universal) — button B must also clear
    entity_b.handle_telegram(0x00, 0)
    assert entity_b._is_pressed is False
    assert entity_b.state_attributes.get(ATTR_EVENT_TYPE) == "released"


async def test_button_binary_sensor_ignores_other_button(hass: HomeAssistant) -> None:
    """Test binary sensor ignores telegrams for a different button index."""
    gateway = _make_gateway(
        {
            CONF_OPERATING_TYPE: "1",
            CONF_BUTTON_COUNT: 4,
            CONF_GROUPING_MODE: TRANSMITTER_GROUPING_SINGLE,
        }
    )
    gateway.add_to_hass(hass)
    hass.config.country = "DE"

    captured_entities: list = []

    def _capture_entities(entities: list) -> None:
        captured_entities.extend(entities)

    t_patch, c_patch, _, mock_coordinator = _patch_integration()
    mock_coordinator.register_transmitter_entities.side_effect = _capture_entities

    with t_patch, c_patch:
        assert await hass.config_entries.async_setup(gateway.entry_id)
        await hass.async_block_till_done()

    # Get the button_a entity (index=0)
    entity = next(
        (e for e in captured_entities if getattr(e, "_button_index", None) == 0),
        None,
    )
    assert entity is not None

    # Telegram for button index 1 should not change button_a entity
    entity.handle_telegram(0x01, 1)
    assert entity._is_pressed is False


async def test_switch_binary_sensor_created(hass: HomeAssistant) -> None:
    """Test binary sensor entity is created for type-2 switch transmitter."""
    gateway = _make_gateway(
        {
            CONF_OPERATING_TYPE: "2",
            CONF_BUTTON_COUNT: 2,
            CONF_USAGE_TYPE: TRANSMITTER_USAGE_SWITCH,
        }
    )
    gateway.add_to_hass(hass)
    hass.config.country = "DE"

    t_patch, c_patch, _, _ = _patch_integration()
    with t_patch, c_patch:
        assert await hass.config_entries.async_setup(gateway.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get(_get_binary_sensor_entity_id(hass, "switch"))
    assert state is not None
    assert state.state == "unknown"


async def test_switch_binary_sensor_handle_telegram(hass: HomeAssistant) -> None:
    """Test switch binary sensor responds to press telegrams only."""
    gateway = _make_gateway(
        {
            CONF_OPERATING_TYPE: "2",
            CONF_BUTTON_COUNT: 2,
            CONF_USAGE_TYPE: TRANSMITTER_USAGE_SWITCH,
        }
    )
    gateway.add_to_hass(hass)
    hass.config.country = "DE"

    captured_entities: list = []

    def _capture_entities(entities: list) -> None:
        captured_entities.extend(entities)

    t_patch, c_patch, _, mock_coordinator = _patch_integration()
    mock_coordinator.register_transmitter_entities.side_effect = _capture_entities

    with t_patch, c_patch:
        assert await hass.config_entries.async_setup(gateway.entry_id)
        await hass.async_block_till_done()

    # Each transmitter registers one channel binary sensor + one battery sensor.
    assert len(captured_entities) == 2
    entity = next(
        e for e in captured_entities if e.translation_key != "battery_warning"
    )

    # Press button 0 → turn on (info_type=0x01)
    entity.handle_telegram(0x01, 0)
    assert entity.is_on is True

    # Release (info_type=0x00) → ignored
    entity.handle_telegram(0x00, 0)
    assert entity.is_on is True  # state unchanged on release

    # Press button 1 → turn off
    entity.handle_telegram(0x01, 1)
    assert entity.is_on is False


async def test_cover_binary_sensor_created(hass: HomeAssistant) -> None:
    """Test channel state sensor for a type-2 cover transmitter (Jalousie).

    Type-2 transmitters with TRANSMITTER_USAGE_COVER now create enum SensorEntity
    instances (like the type-3 motor sensor) instead of CoverEntity, so they
    appear under Sensors instead of Controls.
    """
    gateway = _make_gateway(
        {
            CONF_OPERATING_TYPE: "2",
            CONF_BUTTON_COUNT: 2,
            CONF_USAGE_TYPE: TRANSMITTER_USAGE_COVER,
        }
    )
    gateway.add_to_hass(hass)
    hass.config.country = "DE"

    captured_entities: list = []

    def _capture_entities(entities: list) -> None:
        captured_entities.extend(entities)

    t_patch, c_patch, _, mock_coordinator = _patch_integration()
    mock_coordinator.register_transmitter_entities.side_effect = _capture_entities

    with t_patch, c_patch:
        assert await hass.config_entries.async_setup(gateway.entry_id)
        await hass.async_block_till_done()

    # Look for the channel state sensor (sensor domain, not cover)
    registry = er.async_get(hass)
    sensor_entity_id = registry.async_get_entity_id(
        "sensor", DOMAIN, f"{MOCK_SUBENTRY_ID}_cover"
    )
    assert sensor_entity_id is not None, "Channel state sensor should be created"

    state = hass.states.get(sensor_entity_id)
    assert state is not None
    # Sensor starts with unknown state
    assert state.state in ("unknown", "unavailable")

    # Each transmitter registers one channel sensor + one battery sensor.
    assert len(captured_entities) == 2
    entity = next(
        e for e in captured_entities if e.translation_key != "battery_warning"
    )
    # Should be a transmitter channel sensor with correct translation key
    assert entity.translation_key == "transmitter_channel_state"


async def test_double_rocker_switch_creates_two_entities(hass: HomeAssistant) -> None:
    """Test that a double-rocker (4-button) type-2 switch creates two channel entities."""
    gateway = _make_gateway(
        {
            CONF_OPERATING_TYPE: "2",
            CONF_BUTTON_COUNT: 4,
            CONF_USAGE_TYPE: TRANSMITTER_USAGE_SWITCH,
        }
    )
    gateway.add_to_hass(hass)
    hass.config.country = "DE"

    t_patch, c_patch, _, _ = _patch_integration()
    with t_patch, c_patch:
        assert await hass.config_entries.async_setup(gateway.entry_id)
        await hass.async_block_till_done()

    state_ab = hass.states.get(_get_binary_sensor_entity_id(hass, "switch_ab"))
    state_cd = hass.states.get(_get_binary_sensor_entity_id(hass, "switch_cd"))
    assert state_ab is not None
    assert state_cd is not None


async def test_binary_sensor_unavailable_when_disconnected(hass: HomeAssistant) -> None:
    """Test binary sensor is unavailable when transceiver is disconnected."""
    gateway = _make_gateway(
        {
            CONF_OPERATING_TYPE: "1",
            CONF_BUTTON_COUNT: 4,
            CONF_GROUPING_MODE: TRANSMITTER_GROUPING_SINGLE,
        }
    )
    gateway.add_to_hass(hass)
    hass.config.country = "DE"

    t_patch, c_patch, mock_transceiver, _mock_coordinator = _patch_integration()
    mock_transceiver.is_connected = False

    with t_patch, c_patch:
        assert await hass.config_entries.async_setup(gateway.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get(_get_event_entity_id(hass, "button_a"))
    assert state is not None
    assert state.state == "unavailable"


# ---------------------------------------------------------------------------
# EWneo battery warning binary sensor
# ---------------------------------------------------------------------------

from homeassistant.components.easywave.const import (  # noqa: E402
    CONF_SENSOR_SERIAL,
    CONF_SENSOR_TYPES,
    ENTRY_TYPE_SENSOR,
    SENSOR_KIND_TEMPERATURE,
    TRANSMITTER_GROUPING_GROUP,
)

MOCK_SENSOR_SUBENTRY_ID = "battery_subentry_test"
MOCK_SENSOR_SERIAL = "bb" * 16


def _make_gateway_with_sensor() -> MockConfigEntry:
    """Return a gateway entry with one EWneo sensor subentry."""
    return MockConfigEntry(
        version=1,
        domain=DOMAIN,
        title="Easywave Gateway",
        data=MOCK_ENTRY_DATA,
        source="usb",
        unique_id="easywave_12345",
        options={
            "devices": [
                {
                    "id": MOCK_SENSOR_SUBENTRY_ID,
                    "title": "Living Room Sensor",
                    "unique_id": f"sensor_{MOCK_SENSOR_SERIAL}",
                    "data": {
                        CONF_ENTRY_TYPE: ENTRY_TYPE_SENSOR,
                        CONF_SENSOR_SERIAL: MOCK_SENSOR_SERIAL,
                        CONF_SENSOR_TYPES: [SENSOR_KIND_TEMPERATURE],
                    },
                }
            ]
        },
    )


async def test_battery_sensor_created_for_ewneo(hass: HomeAssistant) -> None:
    """Battery warning sensor entity is created for an EWneo sensor subentry."""
    from homeassistant.components.easywave.sensor import (  # noqa: PLC0415
        EasywaveNeoBatterySensor,
    )

    gateway = _make_gateway_with_sensor()
    gateway.add_to_hass(hass)
    hass.config.country = "DE"

    captured: list = []
    t_patch, c_patch, _, mock_coordinator = _patch_integration()
    mock_coordinator.register_sensor_entities = MagicMock(side_effect=captured.extend)
    mock_coordinator.unregister_sensor_entity = MagicMock()
    with t_patch, c_patch:
        assert await hass.config_entries.async_setup(gateway.entry_id)
        await hass.async_block_till_done()

    battery = next(
        (e for e in captured if isinstance(e, EasywaveNeoBatterySensor)), None
    )
    assert battery is not None, "EasywaveNeoBatterySensor not registered"
    # State is unknown until the first telegram.
    assert battery.native_value is None


async def test_battery_sensor_handle_telegram(hass: HomeAssistant) -> None:
    """Battery sensor reflects the battery level bits of the telegram."""
    from homeassistant.components.easywave.sensor import (  # noqa: PLC0415
        EasywaveNeoBatterySensor,
    )

    gateway = _make_gateway_with_sensor()
    gateway.add_to_hass(hass)
    hass.config.country = "DE"

    captured: list = []
    t_patch, c_patch, _, mock_coordinator = _patch_integration()
    mock_coordinator.register_sensor_entities = MagicMock(side_effect=captured.extend)
    mock_coordinator.unregister_sensor_entity = MagicMock()
    with t_patch, c_patch:
        assert await hass.config_entries.async_setup(gateway.entry_id)
        await hass.async_block_till_done()

    battery = next(
        (e for e in captured if isinstance(e, EasywaveNeoBatterySensor)), None
    )
    assert battery is not None

    # Level 7 (full) → ok.
    # Byte 1: bit6 has_battery=1, bits 5..3 = 7 (0b111) → 0b01111000 = 0x78
    battery.handle_telegram(bytes([0x00, 0x78, 0x10, 0x00, 0x00]))
    assert battery.native_value == "ok"

    # Level 0 → low.
    battery.handle_telegram(bytes([0x00, 0x40, 0x10, 0x00, 0x00]))
    assert battery.native_value == "low"

    # Learn telegram (bit7 set) is ignored — state stays low.
    battery.handle_telegram(bytes([0x00, 0xF8, 0x10, 0x00, 0x00]))
    assert battery.native_value == "low"

    # Level 6 → still low (only 7 = normal).
    battery.handle_telegram(bytes([0x00, 0x70, 0x10, 0x00, 0x00]))
    assert battery.native_value == "low"

    # Empty payload is ignored gracefully.
    battery.handle_telegram(b"")
    assert battery.native_value == "low"


# ---------------------------------------------------------------------------
# Restore-state tests
# ---------------------------------------------------------------------------


async def test_transmitter_battery_restores_low_state(hass: HomeAssistant) -> None:
    """Transmitter battery sensor restores 'low' state across HA restarts."""
    from homeassistant.components.easywave.sensor import (  # noqa: PLC0415
        EasywaveTransmitterBatterySensor,
    )

    gateway = _make_gateway(
        {
            CONF_OPERATING_TYPE: "1",
            CONF_BUTTON_COUNT: 4,
            CONF_GROUPING_MODE: TRANSMITTER_GROUPING_SINGLE,
        }
    )
    gateway.add_to_hass(hass)
    hass.config.country = "DE"

    mock_sensor_data = MagicMock()
    mock_sensor_data.native_value = "low"

    t_patch, c_patch, _, _mock_coordinator = _patch_integration()
    with (
        t_patch,
        c_patch,
        patch.object(
            EasywaveTransmitterBatterySensor,
            "async_get_last_sensor_data",
            new=AsyncMock(return_value=mock_sensor_data),
        ),
    ):
        assert await hass.config_entries.async_setup(gateway.entry_id)
        await hass.async_block_till_done()

    # Battery sensor unique_id is "<subentry_id>_battery_warning"
    registry = er.async_get(hass)
    entity_id = registry.async_get_entity_id(
        "sensor", DOMAIN, f"{MOCK_SUBENTRY_ID}_battery_warning"
    )
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "low"


async def test_transmitter_battery_ignores_invalid_restore_state(
    hass: HomeAssistant,
) -> None:
    """Transmitter battery sensor discards restored values not in its options."""
    from homeassistant.components.easywave.sensor import (  # noqa: PLC0415
        EasywaveTransmitterBatterySensor,
    )

    gateway = _make_gateway(
        {
            CONF_OPERATING_TYPE: "1",
            CONF_BUTTON_COUNT: 4,
            CONF_GROUPING_MODE: TRANSMITTER_GROUPING_SINGLE,
        }
    )
    gateway.add_to_hass(hass)
    hass.config.country = "DE"

    mock_sensor_data = MagicMock()
    mock_sensor_data.native_value = "invalid_state"

    t_patch, c_patch, _, _ = _patch_integration()
    with (
        t_patch,
        c_patch,
        patch.object(
            EasywaveTransmitterBatterySensor,
            "async_get_last_sensor_data",
            new=AsyncMock(return_value=mock_sensor_data),
        ),
    ):
        assert await hass.config_entries.async_setup(gateway.entry_id)
        await hass.async_block_till_done()

    registry = er.async_get(hass)
    entity_id = registry.async_get_entity_id(
        "sensor", DOMAIN, f"{MOCK_SUBENTRY_ID}_battery_warning"
    )
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    # Unknown/invalid → stays unavailable or unknown (not "invalid_state")
    assert state.state != "invalid_state"


async def test_channel_binary_sensor_restores_on_state(hass: HomeAssistant) -> None:
    """Channel binary sensor restores 'on' via extra_data (survives unavailable shutdown)."""
    from homeassistant.components.easywave.binary_sensor import (  # noqa: PLC0415
        EasywaveChannelBinarySensor,
    )

    gateway = _make_gateway(
        {
            CONF_OPERATING_TYPE: "2",
            CONF_BUTTON_COUNT: 2,
            CONF_USAGE_TYPE: TRANSMITTER_USAGE_SWITCH,
        }
    )
    gateway.add_to_hass(hass)
    hass.config.country = "DE"

    extra = MagicMock()
    extra.as_dict.return_value = {"is_on": True}

    t_patch, c_patch, _, _ = _patch_integration()
    with (
        t_patch,
        c_patch,
        patch.object(
            EasywaveChannelBinarySensor,
            "async_get_last_extra_data",
            new=AsyncMock(return_value=extra),
        ),
    ):
        assert await hass.config_entries.async_setup(gateway.entry_id)
        await hass.async_block_till_done()

    entity_id = _get_binary_sensor_entity_id(hass, "switch")
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "on"


async def test_channel_binary_sensor_restores_off_state(hass: HomeAssistant) -> None:
    """Channel binary sensor falls back to state-based restore when extra_data absent."""
    from homeassistant.components.easywave.binary_sensor import (  # noqa: PLC0415
        EasywaveChannelBinarySensor,
    )

    gateway = _make_gateway(
        {
            CONF_OPERATING_TYPE: "2",
            CONF_BUTTON_COUNT: 2,
            CONF_USAGE_TYPE: TRANSMITTER_USAGE_SWITCH,
        }
    )
    gateway.add_to_hass(hass)
    hass.config.country = "DE"

    last_state = MagicMock()
    last_state.state = "off"

    t_patch, c_patch, _, _ = _patch_integration()
    with (
        t_patch,
        c_patch,
        # No extra_data (e.g. first restart after upgrading) → fallback path
        patch.object(
            EasywaveChannelBinarySensor,
            "async_get_last_extra_data",
            new=AsyncMock(return_value=None),
        ),
        patch.object(
            EasywaveChannelBinarySensor,
            "async_get_last_state",
            new=AsyncMock(return_value=last_state),
        ),
    ):
        assert await hass.config_entries.async_setup(gateway.entry_id)
        await hass.async_block_till_done()

    entity_id = _get_binary_sensor_entity_id(hass, "switch")
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "off"


async def test_channel_binary_sensor_restores_on_via_real_pipeline(
    hass: HomeAssistant,
) -> None:
    """End-to-end: pre-seed RestoreStateData cache and verify channel restores 'on'.

    This test does NOT patch async_get_last_extra_data on the entity class.
    It seeds the actual restore_state cache via mock_restore_cache_with_extra_data,
    so the full pipeline (StoredState.from_dict → RestoredExtraData →
    async_get_last_extra_data → _ChannelRestoreData.from_dict) runs.
    """
    from homeassistant.const import STATE_UNAVAILABLE  # noqa: PLC0415
    from homeassistant.core import State  # noqa: PLC0415

    from tests.common import mock_restore_cache_with_extra_data  # noqa: PLC0415

    gateway = _make_gateway(
        {
            CONF_OPERATING_TYPE: "2",
            CONF_BUTTON_COUNT: 2,
            CONF_USAGE_TYPE: TRANSMITTER_USAGE_SWITCH,
        }
    )
    gateway.add_to_hass(hass)
    hass.config.country = "DE"

    # Pre-register the entity so its entity_id is predictable.
    registry = er.async_get(hass)
    entry = registry.async_get_or_create(
        "binary_sensor",
        DOMAIN,
        f"{MOCK_SUBENTRY_ID}_switch",
    )
    entity_id = entry.entity_id

    # Simulate a real shutdown: state is "unavailable" (transceiver was offline),
    # but extra_data preserves the actual is_on=True.
    mock_restore_cache_with_extra_data(
        hass,
        [(State(entity_id, STATE_UNAVAILABLE), {"is_on": True})],
    )

    t_patch, c_patch, _, _ = _patch_integration()
    with t_patch, c_patch:
        assert await hass.config_entries.async_setup(gateway.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None, f"Entity {entity_id} was never created"
    assert state.state == "on", (
        f"Expected 'on' restored from extra_data, got {state.state!r}. "
        "extra_data path is broken in real RestoreStateData pipeline."
    )


async def test_ewneo_battery_sensor_restores_state(hass: HomeAssistant) -> None:
    """EWneo battery sensor restores 'low' state across HA restarts."""
    from homeassistant.components.easywave.sensor import (  # noqa: PLC0415
        EasywaveNeoBatterySensor,
    )

    gateway = _make_gateway_with_sensor()
    gateway.add_to_hass(hass)
    hass.config.country = "DE"

    mock_sensor_data = MagicMock()
    mock_sensor_data.native_value = "low"

    t_patch, c_patch, _, mock_coordinator = _patch_integration()
    mock_coordinator.register_sensor_entities = MagicMock()
    mock_coordinator.unregister_sensor_entity = MagicMock()

    with (
        t_patch,
        c_patch,
        patch.object(
            EasywaveNeoBatterySensor,
            "async_get_last_sensor_data",
            new=AsyncMock(return_value=mock_sensor_data),
        ),
    ):
        assert await hass.config_entries.async_setup(gateway.entry_id)
        await hass.async_block_till_done()

    registry = er.async_get(hass)
    entity_id = registry.async_get_entity_id(
        "sensor", DOMAIN, f"{MOCK_SENSOR_SUBENTRY_ID}_battery_warning"
    )
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "low"


async def test_last_button_sensor_restores_state(hass: HomeAssistant) -> None:
    """Last-button sensor restores last known pressed button across HA restarts."""
    from homeassistant.components.easywave.sensor import (  # noqa: PLC0415
        EasywaveTransmitterLastButtonSensor,
    )

    gateway = _make_gateway(
        {
            CONF_OPERATING_TYPE: "1",
            CONF_BUTTON_COUNT: 4,
            CONF_GROUPING_MODE: TRANSMITTER_GROUPING_GROUP,
        }
    )
    gateway.add_to_hass(hass)
    hass.config.country = "DE"

    mock_sensor_data = MagicMock()
    mock_sensor_data.native_value = "b"

    t_patch, c_patch, _, _ = _patch_integration()
    with (
        t_patch,
        c_patch,
        patch.object(
            EasywaveTransmitterLastButtonSensor,
            "async_get_last_sensor_data",
            new=AsyncMock(return_value=mock_sensor_data),
        ),
    ):
        assert await hass.config_entries.async_setup(gateway.entry_id)
        await hass.async_block_till_done()

    registry = er.async_get(hass)
    entity_id = registry.async_get_entity_id(
        "sensor", DOMAIN, f"{MOCK_SUBENTRY_ID}_last_button"
    )
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "b"


async def test_motor_sensor_restores_state(hass: HomeAssistant) -> None:
    """Motor state sensor restores last known motor state across HA restarts."""
    from homeassistant.components.easywave.sensor import (  # noqa: PLC0415
        EasywaveTransmitterMotorSensor,
    )

    gateway = _make_gateway(
        {
            CONF_OPERATING_TYPE: "3",
            CONF_BUTTON_COUNT: 4,
        }
    )
    gateway.add_to_hass(hass)
    hass.config.country = "DE"

    mock_sensor_data = MagicMock()
    mock_sensor_data.native_value = "closed"

    t_patch, c_patch, _, _ = _patch_integration()
    with (
        t_patch,
        c_patch,
        patch.object(
            EasywaveTransmitterMotorSensor,
            "async_get_last_sensor_data",
            new=AsyncMock(return_value=mock_sensor_data),
        ),
    ):
        assert await hass.config_entries.async_setup(gateway.entry_id)
        await hass.async_block_till_done()

    registry = er.async_get(hass)
    entity_id = registry.async_get_entity_id(
        "sensor", DOMAIN, f"{MOCK_SUBENTRY_ID}_motor_state"
    )
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "closed"


async def test_channel_sensor_restores_opened_state(hass: HomeAssistant) -> None:
    """Channel state sensor (type-2 cover) restores 'opened' across HA restarts."""
    from homeassistant.components.easywave.sensor import (  # noqa: PLC0415
        EasywaveTransmitterChannelSensor,
    )

    gateway = _make_gateway(
        {
            CONF_OPERATING_TYPE: "2",
            CONF_BUTTON_COUNT: 2,
            CONF_USAGE_TYPE: TRANSMITTER_USAGE_COVER,
        }
    )
    gateway.add_to_hass(hass)
    hass.config.country = "DE"

    mock_sensor_data = MagicMock()
    mock_sensor_data.native_value = "opened"

    t_patch, c_patch, _, _ = _patch_integration()
    with (
        t_patch,
        c_patch,
        patch.object(
            EasywaveTransmitterChannelSensor,
            "async_get_last_sensor_data",
            new=AsyncMock(return_value=mock_sensor_data),
        ),
    ):
        assert await hass.config_entries.async_setup(gateway.entry_id)
        await hass.async_block_till_done()

    registry = er.async_get(hass)
    entity_id = registry.async_get_entity_id(
        "sensor", DOMAIN, f"{MOCK_SUBENTRY_ID}_cover"
    )
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "opened"


async def test_channel_sensor_restores_via_real_pipeline(
    hass: HomeAssistant,
) -> None:
    """End-to-end: channel state sensor restores 'closed' via real RestoreSensor pipeline."""
    from homeassistant.const import STATE_UNAVAILABLE  # noqa: PLC0415
    from homeassistant.core import State  # noqa: PLC0415

    from tests.common import mock_restore_cache_with_extra_data  # noqa: PLC0415

    gateway = _make_gateway(
        {
            CONF_OPERATING_TYPE: "2",
            CONF_BUTTON_COUNT: 2,
            CONF_USAGE_TYPE: TRANSMITTER_USAGE_COVER,
        }
    )
    gateway.add_to_hass(hass)
    hass.config.country = "DE"

    registry = er.async_get(hass)
    entry = registry.async_get_or_create(
        "sensor",
        DOMAIN,
        f"{MOCK_SUBENTRY_ID}_cover",
    )
    entity_id = entry.entity_id

    # Simulate a real shutdown: state is "unavailable" but SensorExtraStoredData
    # preserves native_value="closed".
    mock_restore_cache_with_extra_data(
        hass,
        [
            (
                State(entity_id, STATE_UNAVAILABLE),
                {
                    "native_value": "closed",
                    "native_unit_of_measurement": None,
                    "last_period": None,
                    "last_reset": None,
                    "status": None,
                    "state_class": None,
                },
            )
        ],
    )

    t_patch, c_patch, _, _ = _patch_integration()
    with t_patch, c_patch:
        assert await hass.config_entries.async_setup(gateway.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None, f"Entity {entity_id} was never created"
    assert state.state == "closed", (
        f"Expected 'closed' restored via real pipeline, got {state.state!r}."
    )


async def test_motor_sensor_restores_via_real_pipeline(
    hass: HomeAssistant,
) -> None:
    """End-to-end: motor state sensor restores 'opened' via real RestoreSensor pipeline.

    This test pre-seeds the actual RestoreStateData cache (not mocking
    async_get_last_sensor_data) so the full restore pipeline is exercised:
    StoredState → RestoredExtraData → SensorExtraStoredData → native_value.
    """
    from homeassistant.const import STATE_UNAVAILABLE  # noqa: PLC0415
    from homeassistant.core import State  # noqa: PLC0415

    from tests.common import mock_restore_cache_with_extra_data  # noqa: PLC0415

    gateway = _make_gateway(
        {
            CONF_OPERATING_TYPE: "3",
            CONF_BUTTON_COUNT: 4,
        }
    )
    gateway.add_to_hass(hass)
    hass.config.country = "DE"

    # Pre-register the motor sensor entity so its entity_id is predictable.
    registry = er.async_get(hass)
    entry = registry.async_get_or_create(
        "sensor",
        DOMAIN,
        f"{MOCK_SUBENTRY_ID}_motor_state",
    )
    entity_id = entry.entity_id

    # Simulate a real shutdown: state is "unavailable" (transceiver disconnected),
    # but SensorExtraStoredData preserves native_value="opened".
    mock_restore_cache_with_extra_data(
        hass,
        [
            (
                State(entity_id, STATE_UNAVAILABLE),
                {
                    "native_value": "opened",
                    "native_unit_of_measurement": None,
                    "last_period": None,
                    "last_reset": None,
                    "status": None,
                    "state_class": None,
                },
            )
        ],
    )

    t_patch, c_patch, _, _ = _patch_integration()
    with t_patch, c_patch:
        assert await hass.config_entries.async_setup(gateway.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None, f"Entity {entity_id} was never created"
    assert state.state == "opened", (
        f"Expected 'opened' restored via real pipeline, got {state.state!r}. "
        "The restore pipeline is broken for the motor state sensor."
    )


async def test_channel_sensor_4btn_restores_via_real_pipeline(
    hass: HomeAssistant,
) -> None:
    """End-to-end: 4-button cover channel sensors restore via real RestoreSensor pipeline."""
    from homeassistant.const import STATE_UNAVAILABLE  # noqa: PLC0415
    from homeassistant.core import State  # noqa: PLC0415

    from tests.common import mock_restore_cache_with_extra_data  # noqa: PLC0415

    gateway = _make_gateway(
        {
            CONF_OPERATING_TYPE: "2",
            CONF_BUTTON_COUNT: 4,
            CONF_USAGE_TYPE: TRANSMITTER_USAGE_COVER,
        }
    )
    gateway.add_to_hass(hass)
    hass.config.country = "DE"

    registry = er.async_get(hass)
    entry_ab = registry.async_get_or_create(
        "sensor",
        DOMAIN,
        f"{MOCK_SUBENTRY_ID}_cover_ab",
    )
    entry_cd = registry.async_get_or_create(
        "sensor",
        DOMAIN,
        f"{MOCK_SUBENTRY_ID}_cover_cd",
    )

    mock_restore_cache_with_extra_data(
        hass,
        [
            (
                State(entry_ab.entity_id, STATE_UNAVAILABLE),
                {
                    "native_value": "opened",
                    "native_unit_of_measurement": None,
                    "last_period": None,
                    "last_reset": None,
                    "status": None,
                    "state_class": None,
                },
            ),
            (
                State(entry_cd.entity_id, STATE_UNAVAILABLE),
                {
                    "native_value": "closed",
                    "native_unit_of_measurement": None,
                    "last_period": None,
                    "last_reset": None,
                    "status": None,
                    "state_class": None,
                },
            ),
        ],
    )

    t_patch, c_patch, _, _ = _patch_integration()
    with t_patch, c_patch:
        assert await hass.config_entries.async_setup(gateway.entry_id)
        await hass.async_block_till_done()

    state_ab = hass.states.get(entry_ab.entity_id)
    assert state_ab is not None
    assert state_ab.state == "opened", (
        f"Expected 'opened' for AB channel, got {state_ab.state!r}"
    )

    state_cd = hass.states.get(entry_cd.entity_id)
    assert state_cd is not None
    assert state_cd.state == "closed", (
        f"Expected 'closed' for CD channel, got {state_cd.state!r}"
    )
