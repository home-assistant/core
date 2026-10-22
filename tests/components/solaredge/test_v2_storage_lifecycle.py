"""Battery inventory and storage counter lifecycle regressions."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

from aiosolaredge.v2 import PermissionDeniedError, Reading
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.solaredge.v2_runtime import SolarEdgeV2Coordinator
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.update_coordinator import UpdateFailed

from .test_v2_runtime import coordinator, entry_data

NOW = datetime(2026, 10, 22, 12, tzinfo=UTC)


async def _load_sensor_platform(
    hass: HomeAssistant, entry: MockConfigEntry, coord: SolarEdgeV2Coordinator
) -> None:
    """Forward the native sensor platform for an already prepared coordinator."""
    entry.runtime_data = {"v2_coordinator": coord}
    entry.mock_state(hass, ConfigEntryState.LOADED)
    await hass.config_entries.async_forward_entry_setups(entry, [Platform.SENSOR])
    await hass.async_block_till_done()


def _battery_ids(registry: er.EntityRegistry, entry: MockConfigEntry) -> list[str]:
    return [
        item.unique_id
        for item in er.async_entries_for_config_entry(registry, entry.entry_id)
        if "_battery_" in item.unique_id
    ]


def battery(serial: str, values: tuple[int, ...] = (100, 130)) -> dict:
    """Battery."""
    samples = [
        {
            "timestamp": (
                NOW - timedelta(minutes=15 * (len(values) - i - 1))
            ).isoformat(),
            "value": value,
        }
        for i, value in enumerate(values)
    ]
    return {
        "serialNumber": serial,
        "unit": "WH",
        "lifetimeEnergyCharged": samples,
        "lifetimeEnergyDischarged": samples,
    }


async def test_inactive_inventory_member_does_not_poison_active_total(
    hass: HomeAssistant,
) -> None:
    """Test inactive inventory member does not poison active total."""
    entry = MockConfigEntry(domain="solaredge", data=entry_data())
    entry.add_to_hass(hass)
    coord = coordinator(hass, entry)
    coord.state["metadata"] = {"timezone": "UTC"}
    coord.state["inventory"] = {
        "batteries": [
            {"serialNumber": "OLD", "active": False},
            {"serialNumber": "B1", "active": True},
        ]
    }
    coord.api._get = AsyncMock(return_value={"batteries": [battery("B1")]})
    result = await coord._read_job("storage", NOW)
    assert result["B1_battery_charge_energy"].value == 30
    assert result["storage_charge_energy"].value == 30


async def test_new_active_battery_does_not_disable_site_polling(
    hass: HomeAssistant,
) -> None:
    """Test new active battery does not disable site polling."""
    entry = MockConfigEntry(domain="solaredge", data=entry_data())
    entry.add_to_hass(hass)
    coord = coordinator(hass, entry)
    coord.state["metadata"] = {"timezone": "UTC"}
    coord.state["inventory"] = {"batteries": [{"serialNumber": "B1", "active": True}]}
    # A previous successful weekly inventory is not due for another six days.
    coord.state["due"] = {
        "metadata": (NOW + timedelta(days=6)).timestamp(),
        "inventory": (NOW + timedelta(days=6)).timestamp(),
    }
    coord.api.lifetime_energy = AsyncMock(return_value=Reading(1000, NOW))
    coord.api.power = AsyncMock(return_value=Reading(50, NOW))
    coord.api.overview = AsyncMock(return_value={"energy_today": Reading(100, NOW)})
    coord.api._get = AsyncMock(
        return_value={"batteries": [battery("B1"), battery("B2")]}
    )
    with patch(
        "homeassistant.components.solaredge.v2_runtime.dt_util.utcnow", return_value=NOW
    ):
        try:
            result = await coord._async_update_data()
        except UpdateFailed as exc:
            pytest.fail(f"New active B2 disabled whole site: {exc}")
    assert result["lifetime_energy"].value == 1000
    assert result["average_power"].value == 50
    assert result["energy_today"].value == 100
    assert result["storage_charge_energy"].value is None
    assert "B2_battery_charge_energy" not in result
    assert coord.state["due"]["inventory"] == (NOW + timedelta(days=6)).timestamp()
    coord.api._get.assert_awaited_once()
    restored = coordinator(hass, entry)
    await restored._async_setup()
    assert restored.state["inventory"] == coord.state["inventory"]
    assert restored.state["readings"]["storage_charge_energy"]["value"] is None
    # No forced inventory fetch: only the existing weekly deadline discovers B2.
    restored.api.inventory = AsyncMock(
        return_value={
            "batteries": [
                {"serialNumber": "B1", "active": True},
                {"serialNumber": "B2", "active": True},
            ]
        }
    )
    restored.api._get = AsyncMock(
        return_value={"batteries": [battery("B1"), battery("B2")]}
    )
    await restored._read_job("inventory", NOW)
    recovered = await restored._read_job("storage", NOW)
    assert recovered["storage_charge_energy"].value == 60


@pytest.mark.usefixtures("recorder_mock")
async def test_inventory_recovery_adds_battery_entities_without_reload(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test inventory recovery adds battery entities without reload."""
    entry = MockConfigEntry(domain="solaredge", data=entry_data())
    entry.add_to_hass(hass)
    coord = coordinator(hass, entry)
    await _load_sensor_platform(hass, entry, coord)
    assert "123_B1_battery_charge_energy" not in _battery_ids(entity_registry, entry)
    coord.state["inventory"] = {"batteries": [{"serialNumber": "B1"}]}
    coord.async_set_updated_data({"B1_battery_charge_energy": Reading(30, NOW)})
    await hass.async_block_till_done()
    assert "123_B1_battery_charge_energy" in _battery_ids(entity_registry, entry)


async def test_inventory_denial_invalidates_cached_storage(hass: HomeAssistant) -> None:
    """Test inventory denial invalidates cached storage."""
    entry = MockConfigEntry(domain="solaredge", data=entry_data())
    entry.add_to_hass(hass)
    coord = coordinator(hass, entry)
    coord.state["metadata"] = {"timezone": "UTC"}
    coord.state["inventory"] = {"batteries": [{"serialNumber": "B1"}]}
    coord._save_readings(
        {
            "storage_charge_energy": Reading(30, NOW - timedelta(hours=4)),
            "B1_battery_charge_energy": Reading(30, NOW - timedelta(hours=4)),
        },
        NOW,
    )
    coord.api.lifetime_energy = AsyncMock(return_value=Reading(1000, NOW))
    coord.api.power = AsyncMock(return_value=Reading(50, NOW))
    coord.api.site = AsyncMock(
        return_value={"siteId": 123, "location": {"timezone": "UTC"}}
    )
    coord.api.inventory = AsyncMock(side_effect=PermissionDeniedError())
    coord.api.overview = AsyncMock(return_value={"energy_today": Reading(100, NOW)})
    with patch(
        "homeassistant.components.solaredge.v2_runtime.dt_util.utcnow", return_value=NOW
    ):
        result = await coord._async_update_data()
    assert result["lifetime_energy"].value == 1000
    assert coord.state["inventory"] is None
    assert result["storage_charge_energy"].value is None
    assert result["B1_battery_charge_energy"].value is None


@pytest.mark.parametrize("devices", [[], [{"serialNumber": "B1", "active": False}]])
async def test_no_active_inventory_clears_all_dependent_cache(
    hass: HomeAssistant, devices: list[dict]
) -> None:
    """Test no active inventory clears all dependent cache."""
    entry = MockConfigEntry(domain="solaredge", data=entry_data())
    entry.add_to_hass(hass)
    coord = coordinator(hass, entry)
    coord.state["metadata"] = {"timezone": "UTC"}
    coord.state["inventory"] = {"batteries": [{"serialNumber": "B1"}]}
    coord._save_readings(
        {
            key: Reading(30, NOW - timedelta(hours=4))
            for key in (
                "storage_charge_energy",
                "storage_discharge_energy",
                "B1_battery_charge_energy",
                "B1_battery_discharge_energy",
            )
        },
        NOW,
    )
    coord.api.storage_daily = AsyncMock()
    coord.api.inventory = AsyncMock(return_value={"batteries": devices})
    await coord._read_job("inventory", NOW)
    await coord._read_job("storage", NOW)
    assert all(
        item["value"] is None and item["timestamp"] == NOW.isoformat()
        for item in coord.state["readings"].values()
    )
    assert not coord.state["periods"]
    coord.api.storage_daily.assert_not_called()


@pytest.mark.usefixtures("recorder_mock")
async def test_battery_discovery_deduplicates_and_unloads(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test battery discovery deduplicates and unloads."""
    entry = MockConfigEntry(domain="solaredge", data=entry_data())
    entry.add_to_hass(hass)
    coord = coordinator(hass, entry)
    await _load_sensor_platform(hass, entry, coord)
    for serials in (["B1"], ["B1", "B2"], ["B1", "B2"], ["B1", "B2"]):
        coord.state["inventory"] = {
            "batteries": [{"serialNumber": serial} for serial in serials]
        }
        coord.async_set_updated_data({})
        await hass.async_block_till_done()
    ids = _battery_ids(entity_registry, entry)
    assert len(ids) == len(set(ids))
    assert sum("_B1_" in identity for identity in ids) == 4
    assert sum("_B2_" in identity for identity in ids) == 4
    await entry._async_process_on_unload(hass)
    coord.state["inventory"] = {"batteries": [{"serialNumber": "B3"}]}
    coord.async_set_updated_data({})
    await hass.async_block_till_done()
    assert _battery_ids(entity_registry, entry) == ids


@pytest.mark.usefixtures("recorder_mock")
async def test_inactive_history_and_missing_active_stay_distinct(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Keep inactive serial entities unavailable, missing active totals unknown."""
    entry = MockConfigEntry(domain="solaredge", data=entry_data())
    entry.add_to_hass(hass)
    coord = coordinator(hass, entry)
    coord.state["metadata"] = {"timezone": "UTC"}
    coord.state["inventory"] = {
        "batteries": [
            {"serialNumber": "OLD", "active": False},
            {"serialNumber": "B1", "active": True},
            {"serialNumber": "B2", "active": True},
        ]
    }
    coord.api._get = AsyncMock(return_value={"batteries": [battery("B1")]})
    result = await coord._read_job("storage", NOW)
    assert result["B1_battery_charge_energy"].value == 30
    assert result["B2_battery_charge_energy"].value is None
    assert result["storage_charge_energy"].value is None
    # Battery energy is disabled by default; these were enabled by the user.
    ids = {}
    for serial in ("OLD", "B2"):
        ids[serial] = entity_registry.async_get_or_create(
            "sensor",
            "solaredge",
            f"123_{serial}_battery_charge_energy",
            config_entry=entry,
        ).entity_id
    coord.data = result
    await _load_sensor_platform(hass, entry, coord)
    assert hass.states.get(ids["OLD"]).state == "unavailable"
    missing = hass.states.get(ids["B2"])
    assert missing.state == "unknown"
    assert missing.attributes["sample_timestamp"] is None


@pytest.mark.parametrize(
    "inventory",
    [None, {"batteries": []}, {"batteries": [{"serialNumber": "B1", "active": False}]}],
)
async def test_restored_missing_capability_never_republishes_old_storage(
    hass: HomeAssistant, inventory: dict | None
) -> None:
    """Invalidate historical cache dependencies without bypassing its schedule."""
    entry = MockConfigEntry(domain="solaredge", data=entry_data())
    entry.add_to_hass(hass)
    coord = coordinator(hass, entry)
    coord.state["metadata"] = {"timezone": "UTC"}
    coord.state["inventory"] = inventory
    coord.state["next_poll"] = (NOW + timedelta(hours=2)).timestamp()
    coord._save_readings(
        {
            "lifetime_energy": Reading(1000, NOW),
            "storage_charge_energy": Reading(30, NOW),
            "B1_battery_charge_energy": Reading(30, NOW),
        },
        NOW,
    )
    await coord.store.async_save(coord.state)
    restored = coordinator(hass, entry)
    with patch(
        "homeassistant.components.solaredge.v2_runtime.dt_util.utcnow", return_value=NOW
    ):
        await restored._async_setup()
        result = await restored._async_update_data()
    assert result["lifetime_energy"].value == 1000
    assert result["storage_charge_energy"].value is None
    assert result["B1_battery_charge_energy"].value is None
    saved = await restored.store.async_load()
    assert saved["readings"]["storage_charge_energy"]["value"] is None
    assert not saved["periods"]
    assert saved["next_poll"] == coord.state["next_poll"]
