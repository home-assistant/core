"""Tests for the Habitron domain services (driven via the public interface)."""

from unittest.mock import AsyncMock

import pytest

from homeassistant.components.habitron.const import DOMAIN, RESTART_ALL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import device_registry as dr

from .const import MOCK_HOST

from tests.common import MockConfigEntry


def _hub_device(hass: HomeAssistant, entry_id: str) -> dr.DeviceEntry:
    """Register a Habitron device linked to the config entry."""
    return dr.async_get(hass).async_get_or_create(
        config_entry_id=entry_id,
        identifiers={(DOMAIN, "hub-device")},
    )


async def test_hub_restart_and_reboot_target_device(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
) -> None:
    """hub_restart/hub_reboot resolve the hub from the targeted device."""
    entry = setup_integration
    hub = entry.runtime_data
    device = _hub_device(hass, entry.entry_id)
    hub.comm.hub_restart = AsyncMock()
    hub.comm.hub_reboot = AsyncMock()

    await hass.services.async_call(
        DOMAIN, "hub_restart", {"device_id": device.id}, blocking=True
    )
    hub.comm.hub_restart.assert_awaited_once_with()

    await hass.services.async_call(
        DOMAIN, "hub_reboot", {"device_id": device.id}, blocking=True
    )
    hub.comm.hub_reboot.assert_awaited_once_with()


async def test_single_hub_fallback_without_device(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
) -> None:
    """With one hub configured, omitting device_id still targets that hub."""
    hub = setup_integration.runtime_data
    hub.comm.hub_restart = AsyncMock()
    await hass.services.async_call(DOMAIN, "hub_restart", {}, blocking=True)
    hub.comm.hub_restart.assert_awaited_once_with()


@pytest.mark.parametrize(
    ("service", "data", "method", "expected_arg"),
    [
        ("mod_restart", {"mod_nmbr": 5}, "module_restart", 105),
        ("rtr_restart", {}, "module_restart", 0),
        ("save_module_smc", {"mod_nmbr": 3}, "save_smc_file", 103),
        ("save_module_smg", {"mod_nmbr": 3}, "save_smg_file", 103),
        ("save_module_status", {"mod_nmbr": 3}, "save_module_status", 103),
        ("save_router_smr", {}, "save_smr_file", None),
        ("save_router_status", {}, "save_router_status", None),
    ],
)
async def test_service_forwards_to_comm(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    service: str,
    data: dict,
    method: str,
    expected_arg: int | None,
) -> None:
    """Each hub-acting service forwards to the matching comm helper."""
    entry = setup_integration
    hub = entry.runtime_data
    device = _hub_device(hass, entry.entry_id)
    setattr(hub.comm, method, AsyncMock())

    await hass.services.async_call(
        DOMAIN, service, {"device_id": device.id, **data}, blocking=True
    )

    comm_method = getattr(hub.comm, method)
    if expected_arg is None:
        comm_method.assert_awaited_once_with()
    else:
        comm_method.assert_awaited_once_with(expected_arg)


async def test_mod_restart_all_when_no_number(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
) -> None:
    """Omitting the module number restarts all modules (RESTART_ALL sentinel)."""
    entry = setup_integration
    hub = entry.runtime_data
    device = _hub_device(hass, entry.entry_id)
    hub.comm.module_restart = AsyncMock()

    await hass.services.async_call(
        DOMAIN, "mod_restart", {"device_id": device.id}, blocking=True
    )
    hub.comm.module_restart.assert_awaited_once_with(RESTART_ALL)


async def test_service_foreign_device_raises(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
) -> None:
    """A device that is not on a Habitron hub raises a validation error."""
    other = MockConfigEntry(domain="other_domain")
    other.add_to_hass(hass)
    device = dr.async_get(hass).async_get_or_create(
        config_entry_id=other.entry_id,
        identifiers={("other_domain", "x")},
    )
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN, "hub_restart", {"device_id": device.id}, blocking=True
        )


async def test_update_entity_matches_host(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
) -> None:
    """update_entity forwards the event to the hub whose host matches."""
    hub = setup_integration.runtime_data
    hub.comm.update_entity = AsyncMock()

    await hass.services.async_call(
        DOMAIN,
        "update_entity",
        {
            "hub_uid": MOCK_HOST,
            "mod_nmbr": 2,
            "evnt_type": 1,
            "evnt_arg1": 3,
            "evnt_arg2": 1,
        },
        blocking=True,
    )
    hub.comm.update_entity.assert_awaited_once_with(MOCK_HOST, 2, 1, 3, 1, 0, 0, 0)


async def test_update_entity_unknown_host_ignored(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
) -> None:
    """An unknown host is dropped quietly (no forwarding, no error)."""
    hub = setup_integration.runtime_data
    hub.comm.update_entity = AsyncMock()

    await hass.services.async_call(
        DOMAIN,
        "update_entity",
        {
            "hub_uid": "9.9.9.9",
            "mod_nmbr": 2,
            "evnt_type": 1,
            "evnt_arg1": 3,
            "evnt_arg2": 1,
        },
        blocking=True,
    )
    hub.comm.update_entity.assert_not_awaited()
