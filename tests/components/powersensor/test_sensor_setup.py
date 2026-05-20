"""Tests relating to sensor platform setup for the Powersensor integration."""

import importlib
from typing import Any
from unittest.mock import Mock

from powersensor_local import VirtualHousehold
import pytest

from homeassistant.components.powersensor.const import (
    CFG_ROLES,
    CREATE_PLUG_SIGNAL,
    CREATE_SENSOR_SIGNAL,
    DOMAIN,
    PLUG_ADDED_TO_HA_SIGNAL,
    ROLE_APPLIANCE,
    ROLE_HOUSENET,
    ROLE_SOLAR,
    ROLE_UPDATE_SIGNAL,
    UPDATE_VHH_SIGNAL,
)
from homeassistant.components.powersensor.models import PowersensorRuntimeData
from homeassistant.components.powersensor.sensor import (
    PLUG_DESCRIPTIONS,
    SENSOR_DESCRIPTIONS,
    PowersensorEntity,
    PowersensorPlugEntity,
    PowersensorSensorEntity,
    async_setup_entry,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)

from tests.common import MockConfigEntry

MAC = "a4cf1218f158"
OTHER_MAC = "a4cf1218f159"


def _make_mock_dispatcher() -> Mock:
    """Return a minimal mock dispatcher for sensor platform tests."""
    dispatcher = Mock()
    dispatcher.plugs = {}
    dispatcher.drain_on_start_sensor_queue = Mock(return_value=[])
    return dispatcher


@pytest.fixture
def config_entry():
    """Return a MockConfigEntry with typed runtime data for sensor platform tests."""
    entry = MockConfigEntry(domain=DOMAIN)
    entry.runtime_data = PowersensorRuntimeData(
        vhh=VirtualHousehold(False),
        dispatcher=_make_mock_dispatcher(),  # type: ignore[arg-type]
        zeroconf=None,
    )
    return entry


@pytest.mark.asyncio
async def test_setup_entry(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch, config_entry
) -> None:
    """Test that a role update causes UPDATE_VHH_SIGNAL to be sent only when role changes.

    Verifies that:
    - async_setup_entry completes without error.
    - A ROLE_UPDATE_SIGNAL for a house-net sensor triggers UPDATE_VHH_SIGNAL
      when the role is new (not yet persisted).
    - A second ROLE_UPDATE_SIGNAL with the same role does NOT trigger
      UPDATE_VHH_SIGNAL again.
    """
    entry = config_entry

    def real_update_entry(entry, *, data, **kwargs):
        object.__setattr__(entry, "data", data)

    monkeypatch.setattr(hass.config_entries, "async_update_entry", real_update_entry)
    entities = []

    def callback(new_entities, *args, **kwargs):
        entities.extend(new_entities)

    await async_setup_entry(hass, entry, callback)

    mock_handler = Mock()
    async_dispatcher_connect(hass, UPDATE_VHH_SIGNAL, mock_handler)
    await hass.async_block_till_done()

    # First signal: role is new — should trigger VHH update.
    async_dispatcher_send(hass, ROLE_UPDATE_SIGNAL, MAC, "house-net")
    for _ in range(4):
        await hass.async_block_till_done()

    mock_handler.assert_called_once_with()

    # Second signal: same role — must NOT trigger another VHH update.
    async_dispatcher_send(hass, ROLE_UPDATE_SIGNAL, MAC, "house-net")
    for _ in range(4):
        await hass.async_block_till_done()

    mock_handler.assert_called_once_with()  # still exactly one call


@pytest.mark.asyncio
async def test_discovered_sensor(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch, config_entry
) -> None:
    """Test that CREATE_SENSOR_SIGNAL creates the right number of entities.

    A house-net sensor should produce 5 entities (battery, role, rssi, watts,
    summation_energy). A subsequent solar sensor should add another 5.
    """
    entry = config_entry
    monkeypatch.setattr(hass.config_entries, "async_update_entry", Mock())
    entities = []

    def callback(new_entities, *args, **kwargs):
        entities.extend(new_entities)

    await async_setup_entry(hass, entry, callback)

    async_dispatcher_send(hass, CREATE_SENSOR_SIGNAL, MAC, "house-net")
    for _ in range(10):
        await hass.async_block_till_done()

    assert len(entities) == 5

    async_dispatcher_send(hass, CREATE_SENSOR_SIGNAL, OTHER_MAC, "solar")
    await hass.async_block_till_done()
    assert len(entities) == 10


@pytest.mark.asyncio
async def test_role_change_adds_role_specific_entities(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch, config_entry
) -> None:
    """Test that a role change adds missing role-specific entities without duplicates.

    Verifies that:
    - Changing a sensor's role from house-net to water adds the two water-specific
      entities (water_flow_rate, total_water_consumption).
    - Changing back from water to house-net is a no-op: power/total_energy were
      already created at discovery time so they must NOT be re-added (which would
      trigger duplicate-unique-ID warnings from HA).
    - A second house-net → water change is also a no-op: those water entities
      were already added during the first role change and are tracked in
      runtime.role_specific_entities_added.
    - Old role-specific entities are left as unavailable rather than deleted;
      removal is left to the user via the HA UI.
    """

    entry = config_entry
    entry.add_to_hass(hass)

    def real_update_entry(ent, *, data, **kwargs):
        object.__setattr__(ent, "data", data)

    monkeypatch.setattr(hass.config_entries, "async_update_entry", real_update_entry)

    added_batches: list[list] = []

    def add_callback(new_entities, *args, **kwargs):
        added_batches.append(list(new_entities))

    await async_setup_entry(hass, entry, add_callback)

    # Discover as house-net (5 entities: battery_level, rssi_ble, device_role, power, total_energy).
    async_dispatcher_send(hass, CREATE_SENSOR_SIGNAL, MAC, "house-net")
    for _ in range(10):
        await hass.async_block_till_done()

    assert len(added_batches) == 1
    assert len(added_batches[0]) == 5
    discovered_keys = {e.entity_description.key for e in added_batches[0]}
    assert "total_energy" in discovered_keys
    assert "power" in discovered_keys

    # Change role to water — should add exactly the 2 water-specific entities.
    async_dispatcher_send(hass, ROLE_UPDATE_SIGNAL, MAC, "water")
    for _ in range(10):
        await hass.async_block_till_done()

    assert len(added_batches) == 2
    water_keys = {e.entity_description.key for e in added_batches[1]}
    assert water_keys == {"water_flow_rate", "total_water_consumption"}

    # Change back to house-net — power/total_energy already exist from initial
    # discovery so this must be a no-op (no new sensor batch).
    async_dispatcher_send(hass, ROLE_UPDATE_SIGNAL, MAC, "house-net")
    for _ in range(10):
        await hass.async_block_till_done()

    _role_gated_keys = {
        desc.key for desc in SENSOR_DESCRIPTIONS if desc.supported_roles is not None
    }
    sensor_batches_after_restore = [
        b
        for b in added_batches[2:]
        if any(
            hasattr(e, "entity_description")
            and e.entity_description.key in _role_gated_keys
            for e in b
        )
    ]
    assert len(sensor_batches_after_restore) == 0, (
        "power/total_energy must not be re-added; they already exist from discovery"
    )

    # Change back to water again — water entities are already tracked in
    # role_specific_entities_added so this must also be a no-op.
    batch_count_before = len(added_batches)
    async_dispatcher_send(hass, ROLE_UPDATE_SIGNAL, MAC, "water")
    for _ in range(10):
        await hass.async_block_till_done()

    new_sensor_batches = [
        b
        for b in added_batches[batch_count_before:]
        if any(
            hasattr(e, "entity_description")
            and e.entity_description.key in _role_gated_keys
            for e in b
        )
    ]
    assert len(new_sensor_batches) == 0, (
        "water entities must not be re-added on a second role change to water"
    )


@pytest.mark.asyncio
async def test_initially_known_plugs_and_sensors(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch, config_entry
) -> None:
    """Test that pre-populated plugs and sensors in runtime_data create entities on setup.

    One plug (7 measurement entities) + one house-net sensor (5 measurement
    entities) = 12 entities total.
    """
    entry = config_entry
    entry.runtime_data.dispatcher.plugs[MAC] = None
    entry.runtime_data.dispatcher.drain_on_start_sensor_queue = Mock(
        return_value=[(OTHER_MAC, "house-net")]
    )
    monkeypatch.setattr(hass.config_entries, "async_update_entry", Mock())
    entities = []

    def callback(new_entities, *args, **kwargs):
        entities.extend(new_entities)

    await async_setup_entry(hass, entry, callback)
    assert len(entities) == 12


@pytest.mark.asyncio
async def test_role_change_to_appliance_persists_role(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch, config_entry
) -> None:
    """Test that changing a sensor's role to appliance persists the role without error.

    Regression test: previously the appliance early-return fired before the
    role was written to entry.data, so water → appliance transitions were silently
    dropped and the persisted role was never updated.
    """
    entry = config_entry
    entry.add_to_hass(hass)

    updated_data: dict = {}

    def real_update_entry(ent, *, data, **kwargs):
        object.__setattr__(ent, "data", data)
        updated_data.update(data)

    monkeypatch.setattr(hass.config_entries, "async_update_entry", real_update_entry)

    added_batches: list[list] = []

    def add_callback(new_entities, *args, **kwargs):
        added_batches.append(list(new_entities))

    await async_setup_entry(hass, entry, add_callback)

    # Discover sensor as water — adds 3 universal + 2 water-specific entities.
    async_dispatcher_send(hass, CREATE_SENSOR_SIGNAL, MAC, "water")
    for _ in range(10):
        await hass.async_block_till_done()

    assert len(added_batches) == 1

    # Change role to appliance
    async_dispatcher_send(hass, ROLE_UPDATE_SIGNAL, MAC, ROLE_APPLIANCE)
    for _ in range(10):
        await hass.async_block_till_done()

    # New entity batch should have been added.
    assert len(added_batches) == 2, "Expect power related entries to get added"

    # Role must have been written to entry data.
    assert updated_data.get(CFG_ROLES, {}).get(MAC) == ROLE_APPLIANCE, (
        "Role was not persisted for appliance transition"
    )


@pytest.mark.asyncio
async def test_role_update_to_house_net_for_plug_mac_is_ignored(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch, config_entry
) -> None:
    """Test that a ROLE_UPDATE_SIGNAL for a plug MAC is silently ignored.

    Covers sensor.py:673 — the early return when mac_address is in dispatcher.plugs.
    Plugs have all their entities created unconditionally at discovery time so
    a role update signal should never trigger entity creation or role persistence.
    """
    entry = config_entry
    entry.add_to_hass(hass)

    update_entry = Mock()
    monkeypatch.setattr(hass.config_entries, "async_update_entry", update_entry)

    # Register the plug MAC in the dispatcher so the guard fires.
    entry.runtime_data.dispatcher.plugs[MAC] = Mock()

    entities: list = []

    def add_callback(new_entities, *args, **kwargs):
        entities.extend(new_entities)

    await async_setup_entry(hass, entry, add_callback)
    await hass.async_block_till_done()

    entities.clear()  # entities have been created we want to check for new ones
    async_dispatcher_send(hass, ROLE_UPDATE_SIGNAL, MAC, "house-net")
    for _ in range(5):
        await hass.async_block_till_done()

    # No entity-creation callback and no entry data write should have happened.
    assert not entities
    update_entry.assert_not_called()


@pytest.mark.asyncio
async def test_role_update_for_plug_persists_appliance_role(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch, config_entry
) -> None:
    """Test that a ROLE_UPDATE_SIGNAL for a plug MAC only persists appliance role.

    Plugs may legitimately receive a role update to appliance (e.g. after
    initial discovery when role was None). The role should be written to
    entry.data but no sensor entities should be created and no VHH signal
    should be sent.
    """
    entry = config_entry
    entry.add_to_hass(hass)

    updated_data: dict = {}

    def real_update_entry(ent, *, data, **kwargs):
        object.__setattr__(ent, "data", data)
        updated_data.update(data)

    monkeypatch.setattr(hass.config_entries, "async_update_entry", real_update_entry)

    entry.runtime_data.dispatcher.plugs[MAC] = Mock()

    entities: list = []

    def add_callback(new_entities, *args, **kwargs):
        entities.extend(new_entities)

    await async_setup_entry(hass, entry, add_callback)
    await hass.async_block_till_done()
    entities.clear()  # discard plug entities created during setup

    async_dispatcher_send(hass, ROLE_UPDATE_SIGNAL, MAC, ROLE_APPLIANCE)
    for _ in range(5):
        await hass.async_block_till_done()

    # No sensor entities should have been created.
    assert not entities
    # But the appliance role must have been persisted.
    assert updated_data.get(CFG_ROLES, {}).get(MAC) == ROLE_APPLIANCE

    # A non-appliance role update for a plug must be fully ignored —
    # no entity creation and no entry data write beyond what's already there.
    updated_data.clear()
    async_dispatcher_send(hass, ROLE_UPDATE_SIGNAL, MAC, "house-net")
    for _ in range(5):
        await hass.async_block_till_done()

    assert not entities
    assert not updated_data


@pytest.mark.asyncio
async def test_handle_discovered_plug_creates_entities_and_signals(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch, config_entry
) -> None:
    """Test that CREATE_PLUG_SIGNAL triggers entity creation and PLUG_ADDED_TO_HA_SIGNAL.

    Covers sensor.py:774-775 — async_add_entities and async_dispatcher_send
    inside handle_discovered_plug.
    """

    entry = config_entry
    entry.add_to_hass(hass)

    monkeypatch.setattr(hass.config_entries, "async_update_entry", Mock())

    added_entities: list = []

    def add_callback(new_entities, *args, **kwargs):
        added_entities.extend(new_entities)

    await async_setup_entry(hass, entry, add_callback)
    await hass.async_block_till_done()

    # Capture PLUG_ADDED_TO_HA_SIGNAL.
    plug_added_calls: list[tuple] = []

    def on_plug_added(mac, host, port, name):
        plug_added_calls.append((mac, host, port, name))

    async_dispatcher_connect(hass, PLUG_ADDED_TO_HA_SIGNAL, on_plug_added)

    async_dispatcher_send(
        hass, CREATE_PLUG_SIGNAL, MAC, "192.168.0.33", 49476, "plug-name"
    )
    for _ in range(5):
        await hass.async_block_till_done()

    # Plug entities (PLUG_DESCRIPTIONS) must have been added.
    assert len(added_entities) > 0
    # PLUG_ADDED_TO_HA_SIGNAL must have been sent with correct args.
    assert plug_added_calls == [(MAC, "192.168.0.33", 49476, "plug-name")]


@pytest.mark.asyncio
async def test_solar_reload_scheduled_when_vhh_has_no_solar(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch, config_entry
) -> None:
    """Test that a reload is scheduled when a solar sensor is discovered but the VirtualHousehold lacks solar to start.

    The integration cannot enable solar on an existing VHH instance, so it
    triggers a reload so that __init__.py rebuilds VHH with with_solar=True.
    Solar entities must NOT be added in the current session (they would be
    subscribed to an incapable VHH instance).
    """

    entry = config_entry
    object.__setattr__(entry, "data", {CFG_ROLES: {OTHER_MAC: ROLE_HOUSENET}})

    # VirtualHousehold(False) means no solar support — matches fixture default.
    assert not entry.runtime_data.with_solar

    entry.add_to_hass(hass)

    def real_update_entry(ent, *, data, **kwargs):
        object.__setattr__(ent, "data", data)

    monkeypatch.setattr(hass.config_entries, "async_update_entry", real_update_entry)

    reload_calls: list[str] = []
    monkeypatch.setattr(
        hass.config_entries,
        "async_schedule_reload",
        reload_calls.append,
    )

    added_entities: list = []

    def collect_entities(entities: list, *_a: Any, **_kw: Any) -> None:
        added_entities.extend(entities)

    await async_setup_entry(hass, entry, collect_entities)
    await hass.async_block_till_done()

    # Discover a sensor first so it is not in dispatcher.plugs.
    async_dispatcher_send(hass, CREATE_SENSOR_SIGNAL, MAC, None)
    for _ in range(5):
        await hass.async_block_till_done()

    added_entities.clear()

    async_dispatcher_send(hass, ROLE_UPDATE_SIGNAL, MAC, ROLE_SOLAR)
    for _ in range(10):
        await hass.async_block_till_done()

    assert reload_calls == [entry.entry_id], (
        f"Expected async_schedule_reload to be called once with the entry id, got: {reload_calls}"
    )

    solar_entity_keys = {
        e.entity_description.key
        for e in added_entities
        if hasattr(e, "entity_description")
    }
    assert not any("solar" in k or "to_grid" in k for k in solar_entity_keys), (
        f"Solar entities must not be added to an incapable VHH; got: {solar_entity_keys}"
    )


@pytest.mark.asyncio
async def test_handle_role_update_no_rename_skips_device_registry(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test that _handle_role_update returns early when _rename_based_on_role is False.

    If the role changes but _rename_based_on_role() returns False,
    the device registry must not be touched and async_write_ha_state must not fire.
    """

    powersensor_entity_module = importlib.import_module(
        "homeassistant.components.powersensor.sensor"
    )

    dr_mock = Mock()
    monkeypatch.setattr(powersensor_entity_module, "dr", dr_mock)
    write_state = Mock()
    monkeypatch.setattr(PowersensorEntity, "async_write_ha_state", write_state)

    # Use the base class directly with _rename_based_on_role() hard-wired to False
    entity = PowersensorSensorEntity(
        "",
        MAC,
        "house-net",
        next(d for d in SENSOR_DESCRIPTIONS if d.key == "device_role"),
    )
    monkeypatch.setattr(entity, "_rename_based_on_role", lambda: False)

    entity._handle_role_update(MAC, "solar")

    assert entity._role == "solar"  # role was updated
    dr_mock.async_get.assert_not_called()  # device registry never touched
    write_state.assert_not_called()  # no state write


@pytest.mark.asyncio
async def test_handle_update_normalises_role_hyphen(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test that a device_role value with hyphens is normalised to underscores.

    'house-net' on the wire must become 'house_net' so it matches
    the translation key in strings.json.
    """
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
    """Test that _rename_based_on_role on PowersensorPlugEntity returns False.

    PowersensorPlugEntity does not override _rename_based_on_role so
    it inherits the base implementation which always returns False. A role update
    with a changed role exercises this path via _handle_role_update.
    """
    monkeypatch.setattr(PowersensorEntity, "async_write_ha_state", lambda self: None)

    entity = PowersensorPlugEntity(
        "",
        MAC,
        "house-net",
        next(d for d in PLUG_DESCRIPTIONS if d.key == "total_energy"),
    )

    entity._handle_role_update(MAC, "appliance")

    # Role was updated but _rename_based_on_role returned False so
    # async_write_ha_state was never called
    assert entity._role == "appliance"
