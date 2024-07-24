"""Tests for the Diagnostics integration."""

from http import HTTPStatus
from typing import cast

from syrupy import SnapshotAssertion
from syrupy.filters import props
from syrupy.types import PropertyFilter, PropertyName, PropertyPath

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntry
from homeassistant.setup import async_setup_component
from homeassistant.util.json import JsonObjectType

from tests.typing import ClientSessionGenerator


async def _get_diagnostics_for_config_entry(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    config_entry: ConfigEntry,
) -> JsonObjectType:
    """Return the diagnostics config entry for the specified domain."""
    assert await async_setup_component(hass, "diagnostics", {})
    await hass.async_block_till_done()

    client = await hass_client()
    response = await client.get(
        f"/api/diagnostics/config_entry/{config_entry.entry_id}"
    )
    assert response.status == HTTPStatus.OK
    return cast(JsonObjectType, await response.json())


async def get_diagnostics_for_config_entry(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    config_entry: ConfigEntry,
) -> JsonObjectType:
    """Return the diagnostics config entry for the specified domain."""
    data = await _get_diagnostics_for_config_entry(hass, hass_client, config_entry)
    return cast(JsonObjectType, data["data"])


async def snapshot_get_diagnostics_for_config_entry(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    config_entry: ConfigEntry,
    snapshot: SnapshotAssertion,
) -> JsonObjectType:
    """Snapshot get_diagnostics_for_config_entry."""
    snapshot_exclude_functions: list[PropertyFilter] = [
        props("created_at", "modified_at")  # we don't care about these
    ]

    if snapshot._exclude:
        # if snaspshot has exclude functions, add them to the list
        snapshot_exclude_functions.append(snapshot._exclude)

    def prop_filter(*, prop: PropertyName, path: PropertyPath) -> bool:
        """Filter out properties."""
        return any(
            exclude(prop=prop, path=path) for exclude in snapshot_exclude_functions
        )

    diagnostics = await get_diagnostics_for_config_entry(
        hass, hass_client, config_entry
    )
    assert diagnostics == snapshot(exclude=prop_filter)
    return diagnostics


async def _get_diagnostics_for_device(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    config_entry: ConfigEntry,
    device: DeviceEntry,
) -> JsonObjectType:
    """Return the diagnostics for the specified device."""
    assert await async_setup_component(hass, "diagnostics", {})

    client = await hass_client()
    response = await client.get(
        f"/api/diagnostics/config_entry/{config_entry.entry_id}/device/{device.id}"
    )
    assert response.status == HTTPStatus.OK
    return cast(JsonObjectType, await response.json())


async def get_diagnostics_for_device(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    config_entry: ConfigEntry,
    device: DeviceEntry,
) -> JsonObjectType:
    """Return the diagnostics for the specified device."""
    data = await _get_diagnostics_for_device(hass, hass_client, config_entry, device)
    return cast(JsonObjectType, data["data"])
