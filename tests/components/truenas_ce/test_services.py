"""Coverage for the domain-level services and their config-entry resolution."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.truenas_ce.const import (
    CONF_DATASET_PASSPHRASES,
    DOMAIN,
    SERVICE_ALERT_CONFIG_ENTRY,
    SERVICE_ALERT_DISMISS,
    SERVICE_ALERT_LIST,
    SERVICE_ALERT_PROPERTIES,
    SERVICE_ALERT_RESTORE,
    SERVICE_ALERT_UUID,
    SERVICE_CONFIG_ENTRY,
    SERVICE_PASSPHRASE_DATASET_PATH,
    SERVICE_PASSPHRASE_LIST,
    SERVICE_PASSPHRASE_REMOVE,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry

_SAMPLE_ALERTS = [
    {"uuid": "u1", "formatted": "Alert one", "level": "WARNING", "id": "1"},
    {"uuid": "u2", "formatted": "Alert two", "level": "CRITICAL", "id": "2"},
]


def _fake_coordinator(alerts: list[dict[str, Any]] | None = None) -> SimpleNamespace:
    """A minimal stand-in for TrueNASCoordinator covering runtime_data uses."""
    api = SimpleNamespace(query=AsyncMock(return_value=alerts or []), error="")
    return SimpleNamespace(api=api, async_refresh=AsyncMock())


async def _add_loaded_entry(
    hass: HomeAssistant,
    runtime_data: SimpleNamespace,
    data: dict[str, Any] | None = None,
) -> MockConfigEntry:
    """Add a config entry and mark it LOADED with the given runtime_data.

    Mirrors how HA itself sets state: patching only the entry-level
    ``async_setup_entry`` (never the domain-level ``async_setup``, which must
    run for real so it registers the services under test) and letting
    ``hass.config_entries.async_setup`` drive the entry to ``LOADED``.
    """
    entry = MockConfigEntry(domain=DOMAIN, data=data or {})
    entry.add_to_hass(hass)

    def _fake_setup_entry(_hass: HomeAssistant, config_entry: Any) -> bool:
        config_entry.runtime_data = runtime_data
        return True

    with patch(
        "homeassistant.components.truenas_ce.async_setup_entry",
        side_effect=_fake_setup_entry,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


@pytest.mark.parametrize(
    ("service", "data"),
    [
        (SERVICE_ALERT_DISMISS, {SERVICE_ALERT_UUID: "u1"}),
        (SERVICE_ALERT_RESTORE, {SERVICE_ALERT_UUID: "u1"}),
        (SERVICE_PASSPHRASE_REMOVE, {SERVICE_PASSPHRASE_DATASET_PATH: "tank/data"}),
    ],
)
async def test_void_service_no_entries_raises(
    hass: HomeAssistant, service: str, data: dict[str, Any]
) -> None:
    """Without any config entry, void-returning services raise."""
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    with pytest.raises(ServiceValidationError, match="No TrueNAS instances"):
        await hass.services.async_call(DOMAIN, service, data, blocking=True)


@pytest.mark.parametrize(
    ("service", "data"),
    [
        (SERVICE_ALERT_LIST, {}),
        (SERVICE_PASSPHRASE_LIST, {}),
    ],
)
async def test_response_service_no_entries_returns_error(
    hass: HomeAssistant, service: str, data: dict[str, Any]
) -> None:
    """Without any config entry, response-returning services report an error."""
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    result = await hass.services.async_call(
        DOMAIN, service, data, blocking=True, return_response=True
    )
    assert result is not None
    assert "No TrueNAS instances" in result["error"]


async def test_alert_dismiss_single_entry_calls_query_and_refreshes(
    hass: HomeAssistant,
) -> None:
    """A single loaded entry is used implicitly; dismiss issues the RPC call."""
    coordinator = _fake_coordinator()
    await _add_loaded_entry(hass, coordinator)

    await hass.services.async_call(
        DOMAIN,
        SERVICE_ALERT_DISMISS,
        {SERVICE_ALERT_UUID: "u1"},
        blocking=True,
    )

    coordinator.api.query.assert_awaited_once_with("alert.dismiss", ["u1"])
    coordinator.async_refresh.assert_awaited_once()


async def test_alert_restore_single_entry_calls_query_and_refreshes(
    hass: HomeAssistant,
) -> None:
    """A single loaded entry is used implicitly; restore issues the RPC call."""
    coordinator = _fake_coordinator()
    await _add_loaded_entry(hass, coordinator)

    await hass.services.async_call(
        DOMAIN,
        SERVICE_ALERT_RESTORE,
        {SERVICE_ALERT_UUID: "u2"},
        blocking=True,
    )

    coordinator.api.query.assert_awaited_once_with("alert.restore", ["u2"])
    coordinator.async_refresh.assert_awaited_once()


async def test_alert_list_default_properties_filters_fields(
    hass: HomeAssistant,
) -> None:
    """Default properties (``uuid,formatted``) trim the response fields."""
    coordinator = _fake_coordinator(_SAMPLE_ALERTS)
    await _add_loaded_entry(hass, coordinator)

    result = await hass.services.async_call(
        DOMAIN, SERVICE_ALERT_LIST, {}, blocking=True, return_response=True
    )

    assert result == {
        "alerts": [
            {"uuid": "u1", "formatted": "Alert one"},
            {"uuid": "u2", "formatted": "Alert two"},
        ]
    }


async def test_alert_list_non_list_response_is_handled_defensively(
    hass: HomeAssistant,
) -> None:
    """A malformed (non-list) alert.list response yields an error, not a crash."""
    coordinator = _fake_coordinator()
    coordinator.api.query.return_value = {"unexpected": "structure"}
    await _add_loaded_entry(hass, coordinator)

    result = await hass.services.async_call(
        DOMAIN, SERVICE_ALERT_LIST, {}, blocking=True, return_response=True
    )

    assert result == {"alerts": [], "error": "Unexpected alert.list response"}


async def test_alert_list_wildcard_properties_returns_raw_alerts(
    hass: HomeAssistant,
) -> None:
    """``properties: "*"`` returns the alerts unfiltered."""
    coordinator = _fake_coordinator(_SAMPLE_ALERTS)
    await _add_loaded_entry(hass, coordinator)

    result = await hass.services.async_call(
        DOMAIN,
        SERVICE_ALERT_LIST,
        {SERVICE_ALERT_PROPERTIES: "*"},
        blocking=True,
        return_response=True,
    )

    assert result == {"alerts": _SAMPLE_ALERTS}


async def test_passphrase_remove_single_entry_updates_entry_data(
    hass: HomeAssistant,
) -> None:
    """Removing a stored passphrase drops just that dataset's key."""
    coordinator = _fake_coordinator()
    entry = await _add_loaded_entry(
        hass,
        coordinator,
        data={CONF_DATASET_PASSPHRASES: {"tank/data": "secret", "tank/other": "s2"}},
    )

    await hass.services.async_call(
        DOMAIN,
        SERVICE_PASSPHRASE_REMOVE,
        {SERVICE_PASSPHRASE_DATASET_PATH: "tank/data"},
        blocking=True,
    )

    assert entry.data[CONF_DATASET_PASSPHRASES] == {"tank/other": "s2"}


async def test_passphrase_remove_unknown_dataset_raises(hass: HomeAssistant) -> None:
    """Removing a dataset with no stored passphrase is rejected."""
    coordinator = _fake_coordinator()
    await _add_loaded_entry(
        hass, coordinator, data={CONF_DATASET_PASSPHRASES: {"tank/data": "secret"}}
    )

    with pytest.raises(ServiceValidationError, match="No stored passphrase"):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_PASSPHRASE_REMOVE,
            {SERVICE_PASSPHRASE_DATASET_PATH: "tank/unknown"},
            blocking=True,
        )


async def test_passphrase_list_single_entry_returns_sorted_dataset_names(
    hass: HomeAssistant,
) -> None:
    """passphrase_list reports dataset names only, never the stored values."""
    coordinator = _fake_coordinator()
    await _add_loaded_entry(
        hass,
        coordinator,
        data={CONF_DATASET_PASSPHRASES: {"tank/b": "s1", "tank/a": "s2"}},
    )

    result = await hass.services.async_call(
        DOMAIN, SERVICE_PASSPHRASE_LIST, {}, blocking=True, return_response=True
    )

    assert result == {"datasets": ["tank/a", "tank/b"]}


@pytest.mark.parametrize(
    ("service", "data"),
    [
        (SERVICE_ALERT_DISMISS, {SERVICE_ALERT_UUID: "u1"}),
        (SERVICE_ALERT_RESTORE, {SERVICE_ALERT_UUID: "u1"}),
        (SERVICE_PASSPHRASE_REMOVE, {SERVICE_PASSPHRASE_DATASET_PATH: "tank/data"}),
    ],
)
async def test_void_service_multiple_entries_without_target_raises(
    hass: HomeAssistant, service: str, data: dict[str, Any]
) -> None:
    """With >1 loaded entry and no explicit target, void services must fail."""
    await _add_loaded_entry(hass, _fake_coordinator())
    await _add_loaded_entry(hass, _fake_coordinator())

    with pytest.raises(ServiceValidationError, match="Multiple TrueNAS instances"):
        await hass.services.async_call(DOMAIN, service, data, blocking=True)


async def test_alert_list_multiple_entries_without_target_returns_error(
    hass: HomeAssistant,
) -> None:
    """With >1 loaded entry and no explicit target, response services report it."""
    await _add_loaded_entry(hass, _fake_coordinator(_SAMPLE_ALERTS))
    await _add_loaded_entry(hass, _fake_coordinator(_SAMPLE_ALERTS))

    result = await hass.services.async_call(
        DOMAIN, SERVICE_ALERT_LIST, {}, blocking=True, return_response=True
    )

    assert result == {
        "alerts": [],
        "error": "Multiple TrueNAS instances (2); please specify config_entry",
    }


async def test_alert_dismiss_explicit_config_entry_targets_right_entry(
    hass: HomeAssistant,
) -> None:
    """An explicit config_entry id routes the call to that entry only."""
    coordinator_1 = _fake_coordinator()
    coordinator_2 = _fake_coordinator()
    await _add_loaded_entry(hass, coordinator_1)
    entry_2 = await _add_loaded_entry(hass, coordinator_2)

    await hass.services.async_call(
        DOMAIN,
        SERVICE_ALERT_DISMISS,
        {SERVICE_ALERT_UUID: "u9", SERVICE_ALERT_CONFIG_ENTRY: entry_2.entry_id},
        blocking=True,
    )

    coordinator_2.api.query.assert_awaited_once_with("alert.dismiss", ["u9"])
    coordinator_1.api.query.assert_not_awaited()


async def test_passphrase_list_explicit_config_entry_targets_right_entry(
    hass: HomeAssistant,
) -> None:
    """An explicit config_entry id also applies to the passphrase services."""
    entry_1 = await _add_loaded_entry(
        hass, _fake_coordinator(), data={CONF_DATASET_PASSPHRASES: {"tank/one": "s"}}
    )
    await _add_loaded_entry(
        hass, _fake_coordinator(), data={CONF_DATASET_PASSPHRASES: {"tank/two": "s"}}
    )

    result = await hass.services.async_call(
        DOMAIN,
        SERVICE_PASSPHRASE_LIST,
        {SERVICE_CONFIG_ENTRY: entry_1.entry_id},
        blocking=True,
        return_response=True,
    )

    assert result == {"datasets": ["tank/one"]}


async def test_alert_dismiss_unloaded_target_raises(hass: HomeAssistant) -> None:
    """Explicitly targeting a NOT_LOADED entry is rejected."""
    await _add_loaded_entry(hass, _fake_coordinator())
    unloaded_entry = MockConfigEntry(domain=DOMAIN, data={})
    unloaded_entry.add_to_hass(hass)

    with pytest.raises(ServiceValidationError, match="not loaded"):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_ALERT_DISMISS,
            {
                SERVICE_ALERT_UUID: "u1",
                SERVICE_ALERT_CONFIG_ENTRY: unloaded_entry.entry_id,
            },
            blocking=True,
        )


async def test_alert_dismiss_unknown_target_raises(hass: HomeAssistant) -> None:
    """Targeting a config_entry id that doesn't exist at all is rejected."""
    await _add_loaded_entry(hass, _fake_coordinator())

    with pytest.raises(ServiceValidationError, match="not found"):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_ALERT_DISMISS,
            {SERVICE_ALERT_UUID: "u1", SERVICE_ALERT_CONFIG_ENTRY: "does-not-exist"},
            blocking=True,
        )
