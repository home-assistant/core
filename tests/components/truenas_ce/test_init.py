"""Unit tests for __init__.py (setup/unload, entity cleanup, service handlers).

Most helpers here are pure functions tested with bare mocks/``SimpleNamespace``,
like test_coordinator.py. ``async_setup_entry``/
``async_unload_entry`` go through the real ``hass`` fixture and
``MockConfigEntry`` instead, since they are HA's own config-entry lifecycle
entrypoints.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.components import truenas_ce as init_module
from homeassistant.components.truenas_ce import (
    _force_entity_unit,
    _migrate_data_size_units,
    _migrate_description,
)
from homeassistant.components.truenas_ce.const import DOMAIN
from homeassistant.components.truenas_ce.helper import scaled_data_unit
from homeassistant.components.truenas_ce.sensor_types import (
    TrueNASSensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


def _desc(**kwargs: Any) -> TrueNASSensorEntityDescription:
    kwargs.setdefault("name", None)
    return TrueNASSensorEntityDescription(**kwargs)


def _config_entry(
    *,
    entry_id: str = "entry1",
    data: dict[str, Any] | None = None,
    options: dict[str, Any] | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        entry_id=entry_id,
        data={CONF_NAME: "TrueNAS", **(data or {})},
        options=options or {},
        state=ConfigEntryState.LOADED,
    )


# ---------------------------
#   _migrate_data_size_units / _force_entity_unit
# ---------------------------
def test_force_entity_unit_writes_new_unit_option() -> None:
    """A newly computed unit that differs from the stored option triggers an update."""
    ent_reg = MagicMock()
    ent_reg.async_get_entity_id.return_value = "sensor.truenas_pool_usage"
    # Existing option ("MB") must differ from the newly-computed unit ("GB" for
    # 5e9 bytes decimal) so the update branch actually fires.
    existing_entry = SimpleNamespace(options={"sensor": {"unit_of_measurement": "MB"}})
    ent_reg.async_get.return_value = existing_entry
    description = _desc(key="pool_size", data_attribute="size")

    _force_entity_unit(ent_reg, "TrueNAS", description, "pool1", 5_000_000_000, False)

    ent_reg.async_update_entity_options.assert_called_once()
    entity_id, domain, options = ent_reg.async_update_entity_options.call_args.args
    assert entity_id == "sensor.truenas_pool_usage"
    assert domain == "sensor"
    assert options["unit_of_measurement"] == "GB"


def test_force_entity_unit_noop_when_entity_missing() -> None:
    """No update happens when the entity id can't be resolved from the unique id."""
    ent_reg = MagicMock()
    ent_reg.async_get_entity_id.return_value = None
    description = _desc(key="pool_size", data_attribute="size")

    _force_entity_unit(ent_reg, "TrueNAS", description, "pool1", 100, False)

    ent_reg.async_update_entity_options.assert_not_called()


def test_force_entity_unit_noop_when_unit_unchanged() -> None:
    """No update happens when the computed unit already matches the stored option."""
    ent_reg = MagicMock()
    ent_reg.async_get_entity_id.return_value = "sensor.truenas_pool_usage"
    # Pre-set the option to whatever scaled_data_unit will compute for value=0.
    unit, _ = scaled_data_unit(0, False)
    existing_entry = SimpleNamespace(options={"sensor": {"unit_of_measurement": unit}})
    ent_reg.async_get.return_value = existing_entry
    description = _desc(key="pool_size", data_attribute="size")

    _force_entity_unit(ent_reg, "TrueNAS", description, "pool1", 0, False)

    ent_reg.async_update_entity_options.assert_not_called()


def test_migrate_data_size_units_processes_data_size_descriptions() -> None:
    """Migration processes every DATA_SIZE description found in the coordinator's data."""
    coordinator = MagicMock()
    coordinator.ds = {"pool": {"pool1": {"size": 5_000_000_000}}}
    entry = _config_entry(options={"data_unit": "GiB"})

    with (
        patch.object(init_module.er, "async_get", return_value=MagicMock()),
        patch.object(init_module, "_migrate_description") as migrate_mock,
    ):
        _migrate_data_size_units(MagicMock(), entry, coordinator)

    # Called at least once for a DATA_SIZE sensor description (pool available/usage).
    assert migrate_mock.called


def test_migrate_description_noop_when_data_not_dict() -> None:
    """Migration is skipped when the description's data path isn't present as a dict."""
    coordinator = MagicMock()
    coordinator.ds = {}
    description = _desc(key="pool_size", data_path="pool", data_attribute="size")

    with patch.object(init_module, "_force_entity_unit") as force_mock:
        _migrate_description(MagicMock(), coordinator, "TrueNAS", description, False)

    force_mock.assert_not_called()


def test_migrate_description_without_reference_calls_once() -> None:
    """A description without ``data_reference`` triggers a single force-unit call."""
    coordinator = MagicMock()
    coordinator.ds = {"system_info": {"uptime_seconds": 12345}}
    description = _desc(
        key="uptime", data_path="system_info", data_attribute="uptime_seconds"
    )
    ent_reg = MagicMock()

    with patch.object(init_module, "_force_entity_unit") as force_mock:
        _migrate_description(ent_reg, coordinator, "TrueNAS", description, False)

    force_mock.assert_called_once_with(
        ent_reg, "TrueNAS", description, None, 12345, False
    )


def test_migrate_description_with_reference_skips_non_dict_vals() -> None:
    """Non-dict values under a referenced data path are skipped, dict ones are migrated."""
    coordinator = MagicMock()
    coordinator.ds = {
        "pool": {
            "pool1": {"name": "tank", "size": 100},
            "pool2": "not-a-dict",
            "pool3": {"size": 200},
        }
    }
    description = _desc(
        key="pool_size",
        data_path="pool",
        data_reference="name",
        data_attribute="size",
    )
    ent_reg = MagicMock()

    with patch.object(init_module, "_force_entity_unit") as force_mock:
        _migrate_description(ent_reg, coordinator, "TrueNAS", description, True)

    assert force_mock.call_count == 2
    force_mock.assert_any_call(ent_reg, "TrueNAS", description, "tank", 100, True)
    force_mock.assert_any_call(ent_reg, "TrueNAS", description, "pool3", 200, True)


# ---------------------------
#   async_setup_entry / async_unload_entry
# ---------------------------
async def test_async_setup_entry_wires_coordinator_and_platforms(
    hass: HomeAssistant,
) -> None:
    """Entry setup creates the coordinator, forwards platforms, and runs unit migration."""
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_NAME: "TrueNAS"}, entry_id="e1")
    entry.add_to_hass(hass)
    hass.config_entries.async_forward_entry_setups = AsyncMock()

    coordinator = MagicMock()
    coordinator.async_config_entry_first_refresh = AsyncMock()
    coordinator.async_add_listener = MagicMock(return_value=MagicMock())

    with (
        patch.object(init_module, "TrueNASCoordinator", return_value=coordinator),
        patch.object(init_module, "_migrate_data_size_units") as migrate_mock,
        patch.object(init_module, "register_system_device") as register_device_mock,
    ):
        result = await hass.config_entries.async_setup(entry.entry_id)

    assert result is True
    assert entry.runtime_data is coordinator
    coordinator.async_config_entry_first_refresh.assert_awaited_once()
    hass.config_entries.async_forward_entry_setups.assert_awaited_once()
    migrate_mock.assert_called_once()
    register_device_mock.assert_called_once_with(hass, entry, coordinator)
    assert coordinator.system_device_id is register_device_mock.return_value


async def test_async_setup_entry_refresh_listener_dispatches_update_signal(
    hass: HomeAssistant,
) -> None:
    """The coordinator's refresh listener dispatches the update-sensors signal."""
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_NAME: "TrueNAS"}, entry_id="e1")
    entry.add_to_hass(hass)
    hass.config_entries.async_forward_entry_setups = AsyncMock()

    coordinator = MagicMock()
    coordinator.async_config_entry_first_refresh = AsyncMock()
    coordinator.async_add_listener = MagicMock(return_value=MagicMock())

    with (
        patch.object(init_module, "TrueNASCoordinator", return_value=coordinator),
        patch.object(init_module, "_migrate_data_size_units"),
        patch.object(init_module, "register_system_device"),
        patch.object(init_module, "async_dispatcher_send") as dispatch_mock,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        refresh_callback = coordinator.async_add_listener.call_args.args[0]
        refresh_callback()

    dispatch_mock.assert_called_once_with(
        hass, init_module.SIGNAL_UPDATE_SENSORS, coordinator
    )


async def test_async_unload_entry_stops_coordinator_on_success(
    hass: HomeAssistant,
) -> None:
    """Unloading stops app-stats polling and closes the API connection on success."""
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_NAME: "TrueNAS"}, entry_id="e1")
    entry.add_to_hass(hass)
    entry.mock_state(hass, ConfigEntryState.LOADED)
    hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)

    coordinator = SimpleNamespace(
        stop_app_stats=AsyncMock(),
        api=SimpleNamespace(close=AsyncMock()),
    )
    entry.runtime_data = coordinator

    with patch.object(init_module, "get_truenas_coordinator", return_value=coordinator):
        result = await hass.config_entries.async_unload(entry.entry_id)

    assert result is True
    coordinator.stop_app_stats.assert_awaited_once()
    coordinator.api.close.assert_awaited_once()
    assert not hasattr(entry, "runtime_data")


async def test_async_unload_entry_noop_when_platform_unload_fails(
    hass: HomeAssistant,
) -> None:
    """Unload leaves the coordinator's ``runtime_data`` intact when platform unload fails."""
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_NAME: "TrueNAS"}, entry_id="e1")
    entry.add_to_hass(hass)
    entry.mock_state(hass, ConfigEntryState.LOADED)
    hass.config_entries.async_unload_platforms = AsyncMock(return_value=False)
    entry.runtime_data = MagicMock()

    result = await hass.config_entries.async_unload(entry.entry_id)

    assert result is False
    assert hasattr(entry, "runtime_data")


async def test_async_unload_entry_handles_missing_coordinator(
    hass: HomeAssistant,
) -> None:
    """Unload succeeds even when no coordinator is found for the entry."""
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_NAME: "TrueNAS"}, entry_id="e1")
    entry.add_to_hass(hass)
    entry.mock_state(hass, ConfigEntryState.LOADED)
    hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)

    with patch.object(init_module, "get_truenas_coordinator", return_value=None):
        result = await hass.config_entries.async_unload(entry.entry_id)

    assert result is True
