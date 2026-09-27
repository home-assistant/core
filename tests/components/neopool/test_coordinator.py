"""Tests for the NeoPool coordinator."""

from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock

from freezegun.api import FrozenDateTimeFactory
from neopool_modbus.registers import MAX_RELAY_GPIO
import pytest

from homeassistant.components.neopool.const import (
    CONF_MODBUS_FRAMER,
    CONF_UNIT_ID,
    CONF_USE_AUX1,
    CURRENT_VERSION,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, issue_registry as ir

from . import setup_integration
from .conftest import MOCK_POOL_DATA, MOCK_SERIAL, _read_all_timers

from tests.common import MockConfigEntry, async_fire_time_changed


@pytest.mark.usefixtures("mock_neopool_client")
async def test_update_data_populates_firmware(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """The first successful read populates firmware on the device entry."""
    await setup_integration(hass, mock_config_entry)
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, MOCK_SERIAL), mock_config_entry.entry_id
    )
    assert device is not None
    assert "18.52" in (device.sw_version or "")


async def test_transient_modbus_failure_after_first_success_marks_unavailable(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_neopool_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A failure after at least one good read raises UpdateFailed (not ConfigEntryNotReady)."""
    await setup_integration(hass, mock_config_entry)
    coordinator = mock_config_entry.runtime_data
    assert coordinator.last_update_success is True

    mock_neopool_client.async_read_all.side_effect = ConnectionError("Modbus fail")
    freezer.tick(timedelta(seconds=60))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert coordinator.last_update_success is False
    assert mock_config_entry.state is ConfigEntryState.LOADED


async def test_corrupt_gpio_creates_repair_issue(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_neopool_client: MagicMock,
    issue_registry: ir.IssueRegistry,
) -> None:
    """A GPIO register outside 0..MAX_RELAY_GPIO opens a corrupted_gpio issue."""
    bad_data = dict(MOCK_POOL_DATA)
    bad_data["MBF_PAR_FILT_GPIO"] = MAX_RELAY_GPIO + 1
    mock_neopool_client.async_read_all = AsyncMock(return_value=bad_data)

    await setup_integration(hass, mock_config_entry)

    issue = issue_registry.async_get_issue(DOMAIN, "corrupted_gpio")
    assert issue is not None
    assert issue.severity is ir.IssueSeverity.ERROR


@pytest.mark.usefixtures("mock_neopool_client")
async def test_clean_gpio_does_not_create_issue(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """A clean read does not open a corrupted_gpio issue."""
    await setup_integration(hass, mock_config_entry)
    assert issue_registry.async_get_issue(DOMAIN, "corrupted_gpio") is None


async def test_corrupt_gpio_self_heals_on_next_clean_read(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_neopool_client: MagicMock,
    issue_registry: ir.IssueRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """The corrupted_gpio issue clears once a subsequent poll reads clean values."""
    bad_data = dict(MOCK_POOL_DATA)
    bad_data["MBF_PAR_FILT_GPIO"] = MAX_RELAY_GPIO + 1
    mock_neopool_client.async_read_all = AsyncMock(return_value=bad_data)
    await setup_integration(hass, mock_config_entry)

    assert issue_registry.async_get_issue(DOMAIN, "corrupted_gpio") is not None

    mock_neopool_client.async_read_all = AsyncMock(return_value=dict(MOCK_POOL_DATA))
    freezer.tick(timedelta(seconds=60))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert issue_registry.async_get_issue(DOMAIN, "corrupted_gpio") is None


@pytest.mark.usefixtures("mock_neopool_client")
async def test_corrupt_gpio_clears_stale_issue_from_previous_session(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Stale issue from a previous HA session clears on first poll."""
    ir.async_create_issue(
        hass,
        DOMAIN,
        "corrupted_gpio",
        is_fixable=False,
        severity=ir.IssueSeverity.ERROR,
        translation_key="corrupted_gpio",
        translation_placeholders={"details": "- stale"},
    )
    assert issue_registry.async_get_issue(DOMAIN, "corrupted_gpio") is not None

    await setup_integration(hass, mock_config_entry)

    assert issue_registry.async_get_issue(DOMAIN, "corrupted_gpio") is None


async def test_corrupt_gpio_logs_error_only_on_state_change(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_neopool_client: MagicMock,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """ERROR log fires only when the set of corrupted register keys changes."""
    bad_data = dict(MOCK_POOL_DATA)
    bad_data["MBF_PAR_FILT_GPIO"] = MAX_RELAY_GPIO + 1
    mock_neopool_client.async_read_all = AsyncMock(return_value=bad_data)
    await setup_integration(hass, mock_config_entry)

    initial_errors = sum(
        1 for r in caplog.records if "Corrupted GPIO register" in r.getMessage()
    )
    assert initial_errors == 1

    freezer.tick(timedelta(seconds=60))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    total_errors = sum(
        1 for r in caplog.records if "Corrupted GPIO register" in r.getMessage()
    )
    assert total_errors == 1


async def test_corrupt_gpio_updates_issue_on_value_change(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_neopool_client: MagicMock,
    issue_registry: ir.IssueRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """The repair issue details refresh when a corrupted register value changes."""
    first = dict(MOCK_POOL_DATA)
    first["MBF_PAR_FILT_GPIO"] = MAX_RELAY_GPIO + 1
    mock_neopool_client.async_read_all = AsyncMock(return_value=first)

    await setup_integration(hass, mock_config_entry)
    issue = issue_registry.async_get_issue(DOMAIN, "corrupted_gpio")
    assert issue is not None
    assert issue.translation_placeholders is not None
    assert str(MAX_RELAY_GPIO + 1) in issue.translation_placeholders["details"]

    second = dict(MOCK_POOL_DATA)
    second["MBF_PAR_FILT_GPIO"] = MAX_RELAY_GPIO + 2
    mock_neopool_client.async_read_all = AsyncMock(return_value=second)
    freezer.tick(timedelta(seconds=60))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    issue = issue_registry.async_get_issue(DOMAIN, "corrupted_gpio")
    assert issue is not None
    assert issue.translation_placeholders is not None
    assert str(MAX_RELAY_GPIO + 2) in issue.translation_placeholders["details"]


async def test_follow_up_refresh_callback_runs(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_neopool_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """request_refresh_with_followup schedules a refresh that fires after the delay."""
    await setup_integration(hass, mock_config_entry)
    coordinator = mock_config_entry.runtime_data

    initial_count = mock_neopool_client.async_read_all.await_count
    coordinator.request_refresh_with_followup(delay=0.1)
    freezer.tick(timedelta(seconds=0.2))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert mock_neopool_client.async_read_all.await_count > initial_count


async def test_timer_block_data_merged_into_coordinator(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_neopool_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """When read_all_timers returns timer blocks, the per-block fields land in data."""

    def _timers(
        enabled_timers: list[str] | None = None, **_kwargs: object
    ) -> dict[str, dict[str, object]]:
        return {
            "filtration1": {
                "enable": 1,
                "on": 8 * 3600,
                "interval": 4 * 3600,
                "stop": 12 * 3600,
                "period": 86400,
                "countdown": 3600,
            },
            "filtration2": {
                "enable": 0,
                "on": None,
                "interval": None,
                "stop": None,
                "period": None,
                "countdown": 0,
            },
        }

    mock_neopool_client.read_all_timers.side_effect = _timers
    await setup_integration(hass, mock_config_entry)
    # filtration1 start/stop register their context after setup; poll again so
    # the coordinator reads their block.
    freezer.tick(timedelta(seconds=60))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    coordinator = mock_config_entry.runtime_data

    assert coordinator.data["filtration1_enable"] == 1
    assert coordinator.data["filtration1_start"] == 8 * 3600
    assert coordinator.data["filtration1_stop"] == 12 * 3600
    assert coordinator.data["filtration2_stop"] is None


def _capture_timer_calls(mock_neopool_client: MagicMock) -> list[tuple]:
    """Record the enabled_timers list per read_all_timers call."""
    calls: list[tuple] = []

    def _capture(
        enabled_timers: list[str] | None = None, **kwargs: object
    ) -> dict[str, dict[str, object]]:
        calls.append((enabled_timers,))
        return _read_all_timers(enabled_timers)

    mock_neopool_client.read_all_timers.side_effect = _capture
    return calls


async def _poll_once_more(
    hass: HomeAssistant,
    coordinator: object,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Trigger a poll after entity listeners have registered their contexts."""
    freezer.tick(timedelta(seconds=60))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


async def test_no_filtration_polled_when_all_entities_disabled(
    hass: HomeAssistant,
    mock_neopool_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """With filtration2/3 time entities disabled, only filtration1 polls.

    filtration1 start/stop are registry-enabled by default; filtration2/3 are
    not, so their blocks must stay out of the read.
    """
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Pool",
        unique_id="neopool_gate_default",
        version=CURRENT_VERSION,
        data={
            "host": "192.0.2.20",
            "port": 502,
            "name": "Pool",
            CONF_UNIT_ID: 1,
            CONF_MODBUS_FRAMER: "tcp",
        },
        options={CONF_MODBUS_FRAMER: "tcp"},
    )
    calls = _capture_timer_calls(mock_neopool_client)
    await setup_integration(hass, entry)
    await _poll_once_more(hass, entry.runtime_data, freezer)

    enabled_timers = calls[-1][0]
    assert enabled_timers is not None
    assert "filtration1" in enabled_timers
    assert "filtration2" not in enabled_timers
    assert "filtration3" not in enabled_timers


async def test_aux_base_polls_but_b_subtimer_gated_when_disabled(
    hass: HomeAssistant,
    mock_neopool_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """With use_aux1 on, the base block polls but the second subtimer does not.

    relay_aux1 stays option-gated (the aux switch needs its enable state); the
    relay_aux1b start/stop entities are registry-disabled by default, so they
    never register a context and the block stays out of the read.
    """
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Pool",
        unique_id="neopool_gate_aux_default",
        version=CURRENT_VERSION,
        data={
            "host": "192.0.2.22",
            "port": 502,
            "name": "Pool",
            CONF_UNIT_ID: 1,
            CONF_MODBUS_FRAMER: "tcp",
        },
        options={CONF_MODBUS_FRAMER: "tcp", CONF_USE_AUX1: True},
    )
    calls = _capture_timer_calls(mock_neopool_client)
    await setup_integration(hass, entry)
    await _poll_once_more(hass, entry.runtime_data, freezer)

    enabled_timers = calls[-1][0]
    assert enabled_timers is not None
    assert "relay_aux1" in enabled_timers
    assert "relay_aux1b" not in enabled_timers


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_aux_b_subtimer_polls_when_enabled(
    hass: HomeAssistant,
    mock_neopool_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Enabling the second aux subtimer's entities starts polling its block.

    With every entity enabled, relay_aux1b start/stop register their block as
    an update context, so it joins the read alongside the base block.
    """
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Pool",
        unique_id="neopool_gate_aux_b",
        version=CURRENT_VERSION,
        data={
            "host": "192.0.2.23",
            "port": 502,
            "name": "Pool",
            CONF_UNIT_ID: 1,
            CONF_MODBUS_FRAMER: "tcp",
        },
        options={CONF_MODBUS_FRAMER: "tcp", CONF_USE_AUX1: True},
    )
    calls = _capture_timer_calls(mock_neopool_client)
    await setup_integration(hass, entry)
    await _poll_once_more(hass, entry.runtime_data, freezer)

    enabled_timers = calls[-1][0]
    assert enabled_timers is not None
    assert "relay_aux1" in enabled_timers
    assert "relay_aux1b" in enabled_timers
