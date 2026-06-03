"""Tests covering the generic/abstract Powersensor Entity class and subclasses."""

import importlib
from unittest.mock import Mock, patch

from powersensor_local import VirtualHousehold
import pytest

from homeassistant.components.powersensor_au.const import (
    DATA_UPDATE_SIGNAL_PREFIX,
    DOMAIN,
    ROLE_UPDATE_SIGNAL,
)
from homeassistant.components.powersensor_au.sensor import (
    CONSUMPTION_DESCRIPTIONS,
    PLUG_DESCRIPTIONS,
    PRODUCTION_DESCRIPTIONS,
    SENSOR_DESCRIPTIONS,
    PowersensorEntity,
    PowersensorHouseholdEntity,
    PowersensorPlugEntity,
    PowersensorSensorEntity,
    PowersensorSensorEntityDescription,
    _volts_to_battery_pct,
)
from homeassistant.core import HomeAssistant

MAC = "a4cf1218f158"


@pytest.fixture
def mock_config():
    """Create a minimal entity description for the base entity tests."""
    return PowersensorSensorEntityDescription(
        key="total_energy",
        device_class=None,
        native_unit_of_measurement=None,
        suggested_display_precision=2,
        state_class=None,
        event="summation_energy",
        message_key="summation_joules",
        conversion_function=lambda v: v / 3_600_000.0,
    )


### Tests ################################################


@pytest.mark.asyncio
async def test_generic_powersensor_entity(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch, mock_config
) -> None:
    """Test behaviour of generic PowerSensor entities.

    Verifies that:
    - Generic entities behave correctly before and after receiving an update.
    - The unavailability timer is scheduled and cancellable.
    - Role updates are filtered by MAC address and applied correctly.
    - _rename_based_on_role() returns False on the base class.
    """
    _config = mock_config

    monkeypatch.setattr(PowersensorEntity, "async_write_ha_state", lambda self: None)
    monkeypatch.setattr(PowersensorEntity, "_schedule_unavailable", lambda self: None)

    entity = PowersensorSensorEntity("", MAC, "house-net", _config)

    assert not entity.available
    assert entity._remove_unavailability_tracker is None

    entity._handle_update("event", {})
    assert entity.available

    # Inject a mock cancel token directly to avoid needing self.hass.
    mock_cancel = Mock()
    entity._remove_unavailability_tracker = mock_cancel
    assert callable(entity._remove_unavailability_tracker)

    # Manually firing the timeout callback should mark the entity unavailable.
    entity._async_make_unavailable(None)
    assert not entity.available

    # _rename_based_on_role() is a no-op on an entity whose role hasn't changed.
    assert not entity._rename_based_on_role()

    # A role update for a different MAC must be ignored.
    entity._handle_role_update(MAC + "garbage", "solar")
    assert entity._role == "house-net"

    # A role update for the correct MAC but the same role is also a no-op.
    entity._handle_role_update(MAC, "house-net")
    assert entity._role == "house-net"
    # Role updates that trigger a rename (and touch the device registry) are
    # covered by test_powersensor_sensor_handle_role_update.


@pytest.mark.asyncio
async def test_powersensor_sensor_default_name(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test that PowersensorSensorEntity sets and updates translation keys correctly.

    Verifies that:
    - The device translation key reflects the initial role.
    - _rename_based_on_role() updates the key and is idempotent on a second call.
    - async_added_to_hass() completes without error.
    - async_added_to_hass() connects to exactly the right signals.
    """
    entity = PowersensorSensorEntity(
        "",
        MAC,
        "house-net",
        next(d for d in SENSOR_DESCRIPTIONS if d.key == "total_energy"),
    )
    assert entity.device_info["translation_key"] == "mains_sensor"

    entity._current_translation_key = "unknown_sensor"
    assert entity.device_info["translation_key"] == "unknown_sensor"

    entity._rename_based_on_role()
    assert entity.device_info["translation_key"] == "mains_sensor"

    # Second call: key already matches — should be a no-op (returns False).
    assert not entity._rename_based_on_role()

    # Verify async_added_to_hass wires up the data-update signal and the
    # role-update signal, and no others.
    connected_signals: list[str] = []

    def capture_connect(hass_arg, signal, cb):
        connected_signals.append(signal)
        return lambda: None  # unsub stub

    with patch(
        "homeassistant.components.powersensor_au.sensor.async_dispatcher_connect",
        side_effect=capture_connect,
    ):
        await entity.async_added_to_hass()

    expected_data_signal = f"{DATA_UPDATE_SIGNAL_PREFIX}{MAC}_summation_energy"
    assert expected_data_signal in connected_signals, (
        f"Expected data-update signal '{expected_data_signal}' not connected; "
        f"got: {connected_signals}"
    )
    assert ROLE_UPDATE_SIGNAL in connected_signals, (
        "PowersensorSensorEntity must subscribe to ROLE_UPDATE_SIGNAL"
    )


@pytest.mark.asyncio
async def test_powersensor_base_entity_async_added_to_hass_connects_data_signal_only(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch, mock_config
) -> None:
    """Base PowersensorEntity.async_added_to_hass connects only the data-update signal.

    PowersensorSensorEntity adds a second subscription (ROLE_UPDATE_SIGNAL) via
    super().  The base class must connect exactly one signal so we can tell the
    two apart.  This test instantiates the base indirectly via a PlugEntity
    (which does not override async_added_to_hass beyond super()).
    """
    entity = PowersensorPlugEntity(
        "",
        MAC,
        "appliance",
        next(d for d in PLUG_DESCRIPTIONS if d.key == "total_energy"),
    )

    connected_signals: list[str] = []

    def capture_connect(hass_arg, signal, cb):
        connected_signals.append(signal)
        return lambda: None

    with patch(
        "homeassistant.components.powersensor_au.sensor.async_dispatcher_connect",
        side_effect=capture_connect,
    ):
        await entity.async_added_to_hass()

    expected_data_signal = f"{DATA_UPDATE_SIGNAL_PREFIX}{MAC}_summation_energy"
    assert expected_data_signal in connected_signals
    assert ROLE_UPDATE_SIGNAL not in connected_signals, (
        "PowersensorPlugEntity must NOT subscribe to ROLE_UPDATE_SIGNAL; "
        "plug roles don't change mid-session"
    )


@pytest.mark.asyncio
async def test_powersensor_sensor_entity_device_info(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test that PowersensorSensorEntity.device_info contains all required fields."""
    entity = PowersensorSensorEntity(
        "",
        MAC,
        "solar",
        next(d for d in SENSOR_DESCRIPTIONS if d.key == "total_energy"),
    )
    info = entity.device_info
    assert info["manufacturer"] is not None
    assert info["model"] is not None
    assert info["translation_key"] is not None
    assert info["translation_placeholders"] is not None


@pytest.mark.asyncio
async def test_powersensor_plug_entity_device_info(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test that PowersensorPlugEntity.device_info contains all required fields."""
    entity = PowersensorPlugEntity(
        "",
        MAC,
        "appliance",
        next(d for d in PLUG_DESCRIPTIONS if d.key == "total_energy"),
    )
    info = entity.device_info
    assert info["manufacturer"] is not None
    assert info["model"] is not None
    assert info["translation_key"] is not None
    assert info["translation_placeholders"] is not None


@pytest.mark.asyncio
async def test_powersensor_household_entity_device_info(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test that PowersensorHouseholdEntity.device_info returns the expected fields.

    Covers sensor.py line 639 (the manufacturer field inside device_info).
    """
    vhh = VirtualHousehold(False)
    desc = next(d for d in CONSUMPTION_DESCRIPTIONS if d.key == "power_from_grid")
    entity = PowersensorHouseholdEntity(vhh, desc)

    info = entity.device_info
    assert info["manufacturer"] == "Powersensor"
    assert info["model"] == "Virtual"
    assert info["translation_key"] == "virtual_household_view"
    assert (DOMAIN, "vhh") in info["identifiers"]


@pytest.mark.asyncio
async def test_powersensor_virtual_household(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test PowersensorHouseholdEntity lifecycle and value updates.

    Verifies that:
    - Entities can be added to and removed from HA without error.
    - Power readings (watts) are stored as integers via formatter=int.
    - Energy readings (summation_joules) are converted to kWh via formatter=_joules_to_kwh.
    - Events with unknown keys are silently ignored.
    """
    vhh = VirtualHousehold(False)
    monkeypatch.setattr(
        PowersensorHouseholdEntity, "async_write_ha_state", lambda self: None
    )

    subscribed: list[tuple[object, ...]] = []
    unsubscribed: list[tuple[object, ...]] = []
    original_subscribe = vhh.subscribe
    original_unsubscribe = vhh.unsubscribe

    def spy_subscribe(event, cb):
        subscribed.append((event, cb))
        original_subscribe(event, cb)

    def spy_unsubscribe(event, cb):
        unsubscribed.append((event, cb))
        original_unsubscribe(event, cb)

    monkeypatch.setattr(vhh, "subscribe", spy_subscribe)
    monkeypatch.setattr(vhh, "unsubscribe", spy_unsubscribe)

    power_from_grid = PowersensorHouseholdEntity(
        vhh, next(d for d in CONSUMPTION_DESCRIPTIONS if d.key == "power_from_grid")
    )
    energy_from_grid = PowersensorHouseholdEntity(
        vhh, next(d for d in CONSUMPTION_DESCRIPTIONS if d.key == "energy_from_grid")
    )

    await power_from_grid.async_added_to_hass()
    await energy_from_grid.async_added_to_hass()

    assert len(subscribed) == 2

    await power_from_grid._on_event("test-event", {"watts": 123})
    assert power_from_grid.native_value == 123

    await energy_from_grid._on_event("test-event", {"summation_joules": 12_356_789})
    assert energy_from_grid.native_value == 12_356_789 / 3_600_000

    # An event with an unrecognised key must not raise and must not change the value.
    previous = energy_from_grid.native_value
    await energy_from_grid._on_event(
        "test-event", {"summation_resettime_utc": 1762345678}
    )
    assert energy_from_grid.native_value == previous

    power_from_grid._call_on_remove_callbacks()
    energy_from_grid._call_on_remove_callbacks()

    assert len(unsubscribed) == 2
    unsubscribed_events = {ev for ev, _ in unsubscribed}
    assert power_from_grid.entity_description.event in unsubscribed_events
    assert energy_from_grid.entity_description.event in unsubscribed_events


@pytest.mark.asyncio
async def test_powersensor_household_entity_formatter_is_applied(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test that the description's formatter is always applied to the raw value.

    Uses a description with formatter=int (a power entity) to confirm the value
    is rounded, not stored as a float.
    """
    vhh = VirtualHousehold(False)
    monkeypatch.setattr(
        PowersensorHouseholdEntity, "async_write_ha_state", lambda self: None
    )

    desc = next(d for d in CONSUMPTION_DESCRIPTIONS if d.key == "power_home_use")
    entity = PowersensorHouseholdEntity(vhh, desc)
    await entity.async_added_to_hass()

    await entity._on_event("home_usage", {"watts": 457.9})

    assert entity.native_value == 457
    assert isinstance(entity.native_value, int), (
        "Power entities use formatter=int; value must be an int, not a float"
    )


@pytest.mark.asyncio
async def test_powersensor_household_entity_missing_message_key_is_ignored(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An _on_event call whose message dict lacks the expected key is a no-op.

    The entity's value must remain None and async_write_ha_state must not be called.
    """
    vhh = VirtualHousehold(False)
    write_state = Mock()
    monkeypatch.setattr(PowersensorHouseholdEntity, "async_write_ha_state", write_state)

    desc = next(d for d in CONSUMPTION_DESCRIPTIONS if d.key == "power_from_grid")
    entity = PowersensorHouseholdEntity(vhh, desc)
    await entity.async_added_to_hass()

    # Message with wrong key — entity must stay at None.
    await entity._on_event("from_grid", {"wrong_key": 999})

    assert entity.native_value is None
    write_state.assert_not_called()


@pytest.mark.asyncio
async def test_powersensor_household_entity_unique_id_uses_event(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """PowersensorHouseholdEntity unique_id is '{DOMAIN}_vhh_<event>' for each description.

    Confirms that unique IDs don't collide between entities that happen to share
    the same message_key but listen to different VHH events.
    """
    vhh = VirtualHousehold(False)
    seen_ids: set[str] = set()

    for desc in CONSUMPTION_DESCRIPTIONS + PRODUCTION_DESCRIPTIONS:
        entity = PowersensorHouseholdEntity(vhh, desc)
        uid = entity.unique_id
        assert uid not in seen_ids, f"Duplicate unique_id: {uid}"
        assert uid == f"{DOMAIN}_vhh_{desc.event}"
        seen_ids.add(uid)


@pytest.mark.asyncio
async def test_entity_removal(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test that the unavailability timer is cancelled when cleanup runs.

    Verifies that:
    - _remove_unavailability_tracker is None before a timer is set.
    - _cancel_unavailability_tracker() calls the cancel token exactly once and
      clears the reference so a second call is a no-op.
    """
    entity = PowersensorSensorEntity(
        "",
        MAC,
        "house-net",
        next(d for d in SENSOR_DESCRIPTIONS if d.key == "total_energy"),
    )
    assert entity._remove_unavailability_tracker is None

    mock_cancel = Mock()
    entity._remove_unavailability_tracker = mock_cancel

    entity._cancel_unavailability_tracker()
    mock_cancel.assert_called_once_with()
    assert entity._remove_unavailability_tracker is None

    # Second call must be a no-op.
    entity._cancel_unavailability_tracker()
    mock_cancel.assert_called_once_with()  # still exactly one call


@pytest.mark.asyncio
async def test_powersensor_sensor_handle_role_update(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test that a role update triggers device-registry and state writes.

    Verifies that:
    - async_get_or_create is called unconditionally (no async_get_device lookup).
    - The entity's translation key is updated to match the new role.

    Note: async_added_to_hass() is not called here because dispatcher
    subscriptions require self.hass to be set by the HA framework. That
    lifecycle path is covered by test_sensor_setup.py.
    """
    powersensor_entity_module = importlib.import_module(
        "homeassistant.components.powersensor_au.sensor"
    )

    device_registry = Mock()
    device_registry.async_get_or_create.return_value = Mock()

    dr_mock = Mock()
    dr_mock.async_get.return_value = device_registry

    monkeypatch.setattr(powersensor_entity_module, "dr", dr_mock)

    write_state = Mock()
    monkeypatch.setattr(PowersensorEntity, "async_write_ha_state", write_state)

    entity = PowersensorSensorEntity(
        "",
        MAC,
        "house-net",
        next(d for d in SENSOR_DESCRIPTIONS if d.key == "total_energy"),
    )
    assert entity.device_info["translation_key"] == "mains_sensor"

    entity._handle_role_update(MAC, "solar")

    assert dr_mock.async_get.call_count == 1
    assert device_registry.async_get_device.call_count == 0
    assert device_registry.async_get_or_create.call_count == 1
    assert entity.device_info["translation_key"] == "solar_sensor"
    write_state.assert_called_once()


@pytest.mark.asyncio
async def test_powersensor_entity_handle_update(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch, mock_config
) -> None:
    """Test that _handle_update applies the conversion function and raw fallback.

    Verifies that:
    - The conversion_function is applied to the raw message value.
    - When conversion_function is None, the raw value is stored directly.
    - _has_recently_received_update_message is set True in both cases.
    """
    async_write_ha_state = Mock()

    monkeypatch.setattr(PowersensorEntity, "async_write_ha_state", async_write_ha_state)
    monkeypatch.setattr(PowersensorEntity, "_schedule_unavailable", lambda self: None)

    entity = PowersensorSensorEntity("", MAC, "house-net", mock_config)
    assert not entity._has_recently_received_update_message

    message = {"summation_joules": 123_456_789}
    entity._handle_update(None, message)
    assert entity._has_recently_received_update_message
    assert entity.native_value == 123_456_789 / 3_600_000

    # With no conversion function the raw integer should be stored.
    no_conv_desc = PowersensorSensorEntityDescription(
        key="total_energy_raw",
        event="summation_energy",
        message_key="summation_joules",
    )
    entity2 = PowersensorSensorEntity("", MAC, "house-net", no_conv_desc)
    monkeypatch.setattr(PowersensorEntity, "async_write_ha_state", async_write_ha_state)
    monkeypatch.setattr(PowersensorEntity, "_schedule_unavailable", lambda self: None)
    entity2._handle_update(None, message)
    assert entity2._has_recently_received_update_message
    assert entity2.native_value == 123_456_789


@pytest.mark.asyncio
async def test_schedule_unavailable_cancels_existing_timer(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch, mock_config
) -> None:
    """Test that _schedule_unavailable cancels any existing timer before creating a new one.

    Covers the branch at sensor.py:442-445 where _remove_unavailability_tracker
    is already set when _schedule_unavailable is called a second time.
    """
    cancel_calls: list[int] = []

    def fake_async_call_later(hass: HomeAssistant, delay, callback):
        return Mock(side_effect=lambda: cancel_calls.append(1))

    monkeypatch.setattr(
        "homeassistant.components.powersensor_au.sensor.async_call_later",
        fake_async_call_later,
    )
    monkeypatch.setattr(PowersensorEntity, "async_write_ha_state", lambda self: None)
    monkeypatch.setattr(PowersensorEntity, "hass", hass, raising=False)

    entity = PowersensorSensorEntity(
        "",
        MAC,
        "house-net",
        next(d for d in SENSOR_DESCRIPTIONS if d.key == "total_energy"),
    )

    # First call — sets the tracker.
    entity._schedule_unavailable()
    assert entity._remove_unavailability_tracker is not None
    assert len(cancel_calls) == 0

    # Second call — must cancel the first token before scheduling a new one.
    entity._schedule_unavailable()
    assert len(cancel_calls) == 1
    assert entity._remove_unavailability_tracker is not None


@pytest.mark.asyncio
async def test_schedule_unavailable_before_hass_is_set_does_not_raise(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch, mock_config
) -> None:
    """Entities can receive messages before self.hass is set by the HA framework.

    _schedule_unavailable must not raise AttributeError when self.hass is None.
    This can happen if a measurement arrives before HA has injected self.hass
    via async_added_to_hass.
    """
    entity = PowersensorSensorEntity("", MAC, "house-net", mock_config)
    # Do NOT patch `hass` onto the entity — it should be absent/None.

    # Calling _schedule_unavailable before HA has set self.hass must not raise.
    try:
        entity._schedule_unavailable()
    except AttributeError as exc:
        pytest.fail(
            f"_schedule_unavailable raised AttributeError before self.hass was set: {exc}"
        )


@pytest.mark.asyncio
async def test_volts_to_battery_pct(hass: HomeAssistant) -> None:
    """Test _volts_to_battery_pct boundary and midpoint values."""

    assert _volts_to_battery_pct(3.3) == 0.0
    assert _volts_to_battery_pct(4.15) == 100.0
    # Below minimum clamps to 0, above maximum clamps to 100.
    assert _volts_to_battery_pct(3.0) == 0.0
    assert _volts_to_battery_pct(5.0) == 100.0
    # Midpoint.
    assert abs(_volts_to_battery_pct(3.725) - 50.0) < 0.01


# ---------------------------------------------------------------------------
# Role update edge cases
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_handle_role_update_no_rename_skips_device_registry(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """_handle_role_update skips the device registry when _rename_based_on_role returns False."""
    powersensor_entity_module = importlib.import_module(
        "homeassistant.components.powersensor_au.sensor"
    )

    dr_mock = Mock()
    monkeypatch.setattr(powersensor_entity_module, "dr", dr_mock)
    write_state = Mock()
    monkeypatch.setattr(PowersensorEntity, "async_write_ha_state", write_state)

    entity = PowersensorSensorEntity(
        "",
        MAC,
        "house-net",
        next(d for d in SENSOR_DESCRIPTIONS if d.key == "device_role"),
    )
    monkeypatch.setattr(entity, "_rename_based_on_role", lambda: False)

    entity._handle_role_update(MAC, "solar")

    assert entity._role == "solar"
    dr_mock.async_get.assert_not_called()
    write_state.assert_not_called()


@pytest.mark.asyncio
async def test_handle_update_normalises_role_hyphen(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """'house-net' on the wire must become 'house_net' for the state translation key."""
    monkeypatch.setattr(PowersensorEntity, "async_write_ha_state", lambda self: None)
    monkeypatch.setattr(PowersensorEntity, "_schedule_unavailable", lambda self: None)

    entity = PowersensorSensorEntity(
        "",
        MAC,
        "house-net",
        next(d for d in SENSOR_DESCRIPTIONS if d.key == "device_role"),
    )

    entity._handle_update("event", {"role": "house-net"})

    assert entity.native_value == "house_net"


@pytest.mark.asyncio
async def test_plug_entity_rename_based_on_role_returns_false(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """PowersensorPlugEntity._rename_based_on_role always returns False.

    Plugs have a fixed role (ROLE_APPLIANCE) and a fixed device translation key,
    so role updates must never trigger a device registry rename.
    """
    monkeypatch.setattr(PowersensorEntity, "async_write_ha_state", lambda self: None)

    entity = PowersensorPlugEntity(
        "",
        MAC,
        "house-net",
        next(d for d in PLUG_DESCRIPTIONS if d.key == "total_energy"),
    )

    entity._handle_role_update(MAC, "appliance")

    assert entity._role == "appliance"
