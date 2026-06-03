"""Tests relating to sensor platform setup for the Powersensor integration."""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, Mock, patch

from powersensor_local import VirtualHousehold
from powersensor_local.devices import PowersensorDevices
import pytest

from homeassistant.components.powersensor_au.const import (
    CFG_ROLES,
    CREATE_PLUG_SIGNAL,
    CREATE_SENSOR_SIGNAL,
    DOMAIN,
    ROLE_APPLIANCE,
    ROLE_HOUSENET,
    ROLE_SOLAR,
    ROLE_UPDATE_SIGNAL,
    UPDATE_VHH_SIGNAL,
)
from homeassistant.components.powersensor_au.models import PowersensorRuntimeData
from homeassistant.components.powersensor_au.sensor import (
    CONSUMPTION_DESCRIPTIONS,
    PLUG_DESCRIPTIONS,
    PRODUCTION_DESCRIPTIONS,
    SENSOR_DESCRIPTIONS,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)

from tests.common import MockConfigEntry

MAC = "a4cf1218f158"
OTHER_MAC = "a4cf1218f159"


def _make_mock_dispatcher(sensors: dict[str, str | None] | None = None) -> Mock:
    """Return a minimal mock dispatcher for sensor platform tests."""
    dispatcher = Mock()
    dispatcher.plugs = set()
    dispatcher.sensors = sensors if sensors is not None else {}
    dispatcher.disconnect = AsyncMock()
    return dispatcher


def _make_mock_devices() -> MagicMock:
    """Return a minimal mock for PowersensorDevices."""

    devices = MagicMock(spec=PowersensorDevices)
    devices.start = AsyncMock(return_value=0)
    devices.stop = AsyncMock()
    devices.rescan = AsyncMock()
    devices.subscribe = Mock()
    devices.unsubscribe = Mock()
    return devices


@pytest.fixture
def config_entry(hass: HomeAssistant):
    """Mock config entry test fixture for powersensor_au entities."""
    mock_devices = _make_mock_devices()
    mock_dispatcher = _make_mock_dispatcher()
    entry = MockConfigEntry(domain=DOMAIN, version=2, minor_version=2)
    entry.runtime_data = PowersensorRuntimeData(
        vhh=VirtualHousehold(False),
        dispatcher=mock_dispatcher,
        devices=mock_devices,
    )
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.powersensor_au.PowersensorDevices",
            return_value=mock_devices,
        ),
        patch(
            "homeassistant.components.powersensor_au.PowersensorMessageDispatcher",
            return_value=mock_dispatcher,
        ),
    ):
        yield entry


def _entity_keys(hass: HomeAssistant, entry: MockConfigEntry) -> set[str]:
    """Return the set of unique_ids for entities registered under entry."""
    ent_reg = er.async_get(hass)
    return {
        e.unique_id for e in er.async_entries_for_config_entry(ent_reg, entry.entry_id)
    }


# ---------------------------------------------------------------------------
# Setup / role update
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_setup_entry(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch, config_entry
) -> None:
    """Test that a role update causes UPDATE_VHH_SIGNAL to be sent only when role changes."""
    entry = config_entry

    def real_update_entry(entry, *, data, **kwargs):
        object.__setattr__(entry, "data", data)

    monkeypatch.setattr(hass.config_entries, "async_update_entry", real_update_entry)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

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


# ---------------------------------------------------------------------------
# Sensor discovery
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_discovered_sensor(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch, config_entry
) -> None:
    """A house-net sensor produces 5 entities; a solar sensor adds another 5."""
    entry = config_entry
    monkeypatch.setattr(hass.config_entries, "async_update_entry", Mock())

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    async_dispatcher_send(hass, CREATE_SENSOR_SIGNAL, MAC, "house-net")
    for _ in range(10):
        await hass.async_block_till_done()

    ent_reg = er.async_get(hass)
    entries_after_first = er.async_entries_for_config_entry(ent_reg, entry.entry_id)
    assert len(entries_after_first) == 5

    async_dispatcher_send(hass, CREATE_SENSOR_SIGNAL, OTHER_MAC, "solar")
    await hass.async_block_till_done()

    entries_after_second = er.async_entries_for_config_entry(ent_reg, entry.entry_id)
    assert len(entries_after_second) == 10


@pytest.mark.asyncio
async def test_discovered_sensor_with_no_role_creates_only_universal_entities(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch, config_entry
) -> None:
    """A sensor arriving with role=None only gets the three universal entities."""
    entry = config_entry
    monkeypatch.setattr(hass.config_entries, "async_update_entry", Mock())

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    async_dispatcher_send(hass, CREATE_SENSOR_SIGNAL, MAC, None)
    for _ in range(10):
        await hass.async_block_till_done()

    universal_count = sum(1 for d in SENSOR_DESCRIPTIONS if d.supported_roles is None)
    ent_reg = er.async_get(hass)
    registered = er.async_entries_for_config_entry(ent_reg, entry.entry_id)
    assert len(registered) == universal_count


@pytest.mark.asyncio
async def test_role_update_for_unknown_mac_persists_role(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch, config_entry
) -> None:
    """A ROLE_UPDATE_SIGNAL for a MAC not yet in the dispatcher still persists the role."""
    entry = config_entry

    updated_data: dict[str, Any] = {}

    def real_update_entry(ent, *, data, **kwargs):
        object.__setattr__(ent, "data", data)
        updated_data.update(data)

    monkeypatch.setattr(hass.config_entries, "async_update_entry", real_update_entry)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    async_dispatcher_send(hass, ROLE_UPDATE_SIGNAL, MAC, "house-net")
    for _ in range(5):
        await hass.async_block_till_done()

    assert updated_data.get(CFG_ROLES, {}).get(MAC) == "house-net"


@pytest.mark.asyncio
async def test_role_change_adds_role_specific_entities(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch, config_entry
) -> None:
    """Role changes add missing entities without duplicates."""
    entry = config_entry

    def real_update_entry(ent, *, data, **kwargs):
        object.__setattr__(ent, "data", data)

    monkeypatch.setattr(hass.config_entries, "async_update_entry", real_update_entry)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    ent_reg = er.async_get(hass)

    # Discover as house-net (5 entities).
    async_dispatcher_send(hass, CREATE_SENSOR_SIGNAL, MAC, "house-net")
    for _ in range(10):
        await hass.async_block_till_done()

    after_housenet = er.async_entries_for_config_entry(ent_reg, entry.entry_id)
    assert len(after_housenet) == 5
    housenet_keys = {e.unique_id.split("_", 1)[1] for e in after_housenet}
    assert "total_energy" in housenet_keys
    assert "power" in housenet_keys

    # Change role to water — should add exactly the 2 water-specific entities.
    async_dispatcher_send(hass, ROLE_UPDATE_SIGNAL, MAC, "water")
    for _ in range(10):
        await hass.async_block_till_done()

    after_water = er.async_entries_for_config_entry(ent_reg, entry.entry_id)
    new_keys = {
        e.unique_id.split("_", 1)[1] for e in after_water if e not in after_housenet
    }
    assert new_keys == {"water_flow_rate", "total_water_consumption"}

    count_after_water = len(after_water)

    # Back to house-net — no duplicate entities.
    async_dispatcher_send(hass, ROLE_UPDATE_SIGNAL, MAC, "house-net")
    for _ in range(10):
        await hass.async_block_till_done()

    after_back_to_housenet = er.async_entries_for_config_entry(ent_reg, entry.entry_id)
    assert len(after_back_to_housenet) == count_after_water

    # Back to water — already tracked, also a no-op.
    async_dispatcher_send(hass, ROLE_UPDATE_SIGNAL, MAC, "water")
    for _ in range(10):
        await hass.async_block_till_done()

    after_back_to_water = er.async_entries_for_config_entry(ent_reg, entry.entry_id)
    assert len(after_back_to_water) == count_after_water


# ---------------------------------------------------------------------------
# VHH entity creation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_vhh_mains_entities_created_when_housenet_sensor_present(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Mains VHH entities are added once a house-net sensor is in dispatcher.sensors."""
    mock_devices = _make_mock_devices()
    mock_dispatcher = _make_mock_dispatcher(sensors={MAC: ROLE_HOUSENET})
    entry = MockConfigEntry(domain=DOMAIN)
    entry.runtime_data = PowersensorRuntimeData(
        vhh=VirtualHousehold(False),
        dispatcher=mock_dispatcher,
        devices=mock_devices,
    )
    entry.add_to_hass(hass)
    monkeypatch.setattr(hass.config_entries, "async_update_entry", Mock())

    with (
        patch(
            "homeassistant.components.powersensor_au.PowersensorDevices",
            return_value=mock_devices,
        ),
        patch(
            "homeassistant.components.powersensor_au.PowersensorMessageDispatcher",
            return_value=mock_dispatcher,
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    ent_reg = er.async_get(hass)
    registered = er.async_entries_for_config_entry(ent_reg, entry.entry_id)
    registered_unique_ids = {e.unique_id for e in registered}
    expected_mains_keys = {f"{DOMAIN}_vhh_{d.event}" for d in CONSUMPTION_DESCRIPTIONS}
    assert expected_mains_keys.issubset(registered_unique_ids), (
        f"Missing mains VHH entities: {expected_mains_keys - registered_unique_ids}"
    )


@pytest.mark.asyncio
async def test_vhh_mains_entities_not_duplicated_on_second_update_vhh_signal(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Mains VHH entities are added exactly once even if UPDATE_VHH_SIGNAL fires twice."""
    mock_devices = _make_mock_devices()
    entry = MockConfigEntry(domain=DOMAIN)
    entry.runtime_data = PowersensorRuntimeData(
        vhh=VirtualHousehold(False),
        dispatcher=_make_mock_dispatcher(sensors={MAC: ROLE_HOUSENET}),
        devices=mock_devices,
    )
    entry.add_to_hass(hass)
    monkeypatch.setattr(hass.config_entries, "async_update_entry", Mock())

    with patch(
        "homeassistant.components.powersensor_au.PowersensorDevices",
        return_value=mock_devices,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    ent_reg = er.async_get(hass)
    count_after_setup = len(er.async_entries_for_config_entry(ent_reg, entry.entry_id))

    # Fire UPDATE_VHH_SIGNAL a second time.
    async_dispatcher_send(hass, UPDATE_VHH_SIGNAL)
    for _ in range(5):
        await hass.async_block_till_done()

    count_after_second_signal = len(
        er.async_entries_for_config_entry(ent_reg, entry.entry_id)
    )
    assert count_after_setup == count_after_second_signal, (
        "VHH mains entities must not be added a second time"
    )


@pytest.mark.asyncio
async def test_vhh_solar_entities_created_when_solar_sensor_discovered(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Solar VHH entities are added when a solar sensor appears alongside a mains sensor."""
    mock_devices = _make_mock_devices()
    mock_dispatcher = _make_mock_dispatcher(sensors={MAC: ROLE_HOUSENET})
    entry = MockConfigEntry(domain=DOMAIN)
    entry.runtime_data = PowersensorRuntimeData(
        vhh=VirtualHousehold(True),
        dispatcher=mock_dispatcher,
        devices=mock_devices,
    )
    entry.add_to_hass(hass)

    def real_update_entry(ent, *, data, **kwargs):
        object.__setattr__(ent, "data", data)

    monkeypatch.setattr(hass.config_entries, "async_update_entry", real_update_entry)

    with (
        patch(
            "homeassistant.components.powersensor_au.PowersensorDevices",
            return_value=mock_devices,
        ),
        patch(
            "homeassistant.components.powersensor_au.PowersensorMessageDispatcher",
            return_value=mock_dispatcher,
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    entry.runtime_data.dispatcher.sensors[OTHER_MAC] = ROLE_SOLAR

    async_dispatcher_send(hass, CREATE_SENSOR_SIGNAL, OTHER_MAC, ROLE_SOLAR)
    for _ in range(10):
        await hass.async_block_till_done()

    ent_reg = er.async_get(hass)
    registered_unique_ids = {
        e.unique_id for e in er.async_entries_for_config_entry(ent_reg, entry.entry_id)
    }
    expected_solar_keys = {f"{DOMAIN}_vhh_{d.event}" for d in PRODUCTION_DESCRIPTIONS}
    assert expected_solar_keys.issubset(registered_unique_ids), (
        f"Missing solar VHH entities: {expected_solar_keys - registered_unique_ids}"
    )


# ---------------------------------------------------------------------------
# Plug discovery
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_handle_discovered_plug_creates_entities(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch, config_entry
) -> None:
    """CREATE_PLUG_SIGNAL triggers PowersensorPlugEntity creation for all PLUG_DESCRIPTIONS."""
    entry = config_entry
    monkeypatch.setattr(hass.config_entries, "async_update_entry", Mock())

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    async_dispatcher_send(hass, CREATE_PLUG_SIGNAL, MAC)
    for _ in range(5):
        await hass.async_block_till_done()

    ent_reg = er.async_get(hass)
    registered = er.async_entries_for_config_entry(ent_reg, entry.entry_id)
    assert len(registered) == len(PLUG_DESCRIPTIONS)


@pytest.mark.asyncio
async def test_handle_discovered_plug_creates_entities_once_on_duplicate_signal(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch, config_entry
) -> None:
    """Firing CREATE_PLUG_SIGNAL twice for the same MAC creates each entity only once."""
    entry = config_entry
    monkeypatch.setattr(hass.config_entries, "async_update_entry", Mock())

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    async_dispatcher_send(hass, CREATE_PLUG_SIGNAL, MAC)
    for _ in range(5):
        await hass.async_block_till_done()

    ent_reg = er.async_get(hass)
    first_count = len(er.async_entries_for_config_entry(ent_reg, entry.entry_id))
    assert first_count == len(PLUG_DESCRIPTIONS)

    async_dispatcher_send(hass, CREATE_PLUG_SIGNAL, MAC)
    for _ in range(5):
        await hass.async_block_till_done()

    second_count = len(er.async_entries_for_config_entry(ent_reg, entry.entry_id))
    assert second_count == first_count


@pytest.mark.asyncio
async def test_role_update_for_plug_mac_persists_role_but_creates_no_entities(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch, config_entry
) -> None:
    """A ROLE_UPDATE_SIGNAL for a plug MAC persists the role but creates no entities."""
    entry = config_entry

    updated_data: dict[str, Any] = {}

    def real_update_entry(ent, *, data, **kwargs):
        object.__setattr__(ent, "data", data)
        updated_data.update(data)

    monkeypatch.setattr(hass.config_entries, "async_update_entry", real_update_entry)
    entry.runtime_data.dispatcher.plugs.add(MAC)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    ent_reg = er.async_get(hass)
    count_before = len(er.async_entries_for_config_entry(ent_reg, entry.entry_id))

    async_dispatcher_send(hass, ROLE_UPDATE_SIGNAL, MAC, "house-net")
    for _ in range(5):
        await hass.async_block_till_done()

    count_after = len(er.async_entries_for_config_entry(ent_reg, entry.entry_id))
    assert count_after == count_before
    assert updated_data.get(CFG_ROLES, {}).get(MAC) == "house-net"


@pytest.mark.asyncio
async def test_role_update_for_plug_persists_appliance_role(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch, config_entry
) -> None:
    """ROLE_UPDATE_SIGNAL for a plug MAC only persists the appliance role."""
    entry = config_entry

    updated_data: dict[str, Any] = {}

    def real_update_entry(ent, *, data, **kwargs):
        object.__setattr__(ent, "data", data)
        updated_data.update(data)

    monkeypatch.setattr(hass.config_entries, "async_update_entry", real_update_entry)
    entry.runtime_data.dispatcher.plugs.add(MAC)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    ent_reg = er.async_get(hass)
    count_before = len(er.async_entries_for_config_entry(ent_reg, entry.entry_id))

    async_dispatcher_send(hass, ROLE_UPDATE_SIGNAL, MAC, ROLE_APPLIANCE)
    for _ in range(5):
        await hass.async_block_till_done()

    assert (
        len(er.async_entries_for_config_entry(ent_reg, entry.entry_id)) == count_before
    )
    assert updated_data.get(CFG_ROLES, {}).get(MAC) == ROLE_APPLIANCE

    updated_data.clear()
    async_dispatcher_send(hass, ROLE_UPDATE_SIGNAL, MAC, "house-net")
    for _ in range(5):
        await hass.async_block_till_done()

    assert (
        len(er.async_entries_for_config_entry(ent_reg, entry.entry_id)) == count_before
    )
    assert updated_data.get(CFG_ROLES, {}).get(MAC) == "house-net"


# ---------------------------------------------------------------------------
# Appliance role persistence
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_role_change_to_appliance_persists_role(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch, config_entry
) -> None:
    """Regression: water → appliance transition must persist the role."""
    entry = config_entry

    updated_data: dict[str, Any] = {}

    def real_update_entry(ent, *, data, **kwargs):
        object.__setattr__(ent, "data", data)
        updated_data.update(data)

    monkeypatch.setattr(hass.config_entries, "async_update_entry", real_update_entry)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    ent_reg = er.async_get(hass)

    async_dispatcher_send(hass, CREATE_SENSOR_SIGNAL, MAC, "water")
    for _ in range(10):
        await hass.async_block_till_done()

    water_entity_count = len(er.async_entries_for_config_entry(ent_reg, entry.entry_id))
    assert water_entity_count > 0

    async_dispatcher_send(hass, ROLE_UPDATE_SIGNAL, MAC, ROLE_APPLIANCE)
    for _ in range(10):
        await hass.async_block_till_done()

    assert updated_data.get(CFG_ROLES, {}).get(MAC) == ROLE_APPLIANCE
    assert (
        len(er.async_entries_for_config_entry(ent_reg, entry.entry_id))
        > water_entity_count
    )


@pytest.mark.asyncio
async def test_solar_reload_scheduled_when_vhh_has_no_solar(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """VHH solar entities are not added when no solar sensor is present."""
    mock_devices = _make_mock_devices()
    entry = MockConfigEntry(domain=DOMAIN)
    entry.runtime_data = PowersensorRuntimeData(
        vhh=VirtualHousehold(False),
        dispatcher=_make_mock_dispatcher(sensors={MAC: ROLE_HOUSENET}),
        devices=mock_devices,
    )
    entry.add_to_hass(hass)
    monkeypatch.setattr(hass.config_entries, "async_update_entry", Mock())

    with patch(
        "homeassistant.components.powersensor_au.PowersensorDevices",
        return_value=mock_devices,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    ent_reg = er.async_get(hass)
    registered_unique_ids = {
        e.unique_id for e in er.async_entries_for_config_entry(ent_reg, entry.entry_id)
    }
    solar_keys = {f"{DOMAIN}_vhh_{d.event}" for d in PRODUCTION_DESCRIPTIONS}
    assert not solar_keys.intersection(registered_unique_ids), (
        "Solar VHH entities must not be created when no solar sensor is present"
    )
