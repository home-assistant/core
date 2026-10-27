"""Tests for the WattWächter integration setup."""

from __future__ import annotations

from datetime import timedelta
from typing import Any
from unittest.mock import AsyncMock

from aio_wattwaechter import (
    WattwaechterAuthenticationError,
    WattwaechterConnectionError,
    WattwaechterError,
    WattwaechterNoDataError,
)
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.update import DOMAIN as UPDATE_DOMAIN
from homeassistant.components.wattwaechter.const import DEFAULT_SCAN_INTERVAL, DOMAIN
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.const import CONF_DEVICE_ID, CONF_MODEL
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .conftest import (
    MOCK_CONFIG_DATA,
    MOCK_DEVICE_ID,
    MOCK_HOST,
    MOCK_METER_DATA_WATER,
    MOCK_SYSTEM_INFO_GAS,
    MOCK_SYSTEM_INFO_WATER,
)

LEGACY_GW_ID = f"WWGW-{MOCK_DEVICE_ID}"


async def test_setup_and_unload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: AsyncMock,
) -> None:
    """Test successful integration setup and unload."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_setup_entry_connection_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: AsyncMock,
) -> None:
    """Test setup when device is unreachable."""
    mock_client.alive.side_effect = WattwaechterConnectionError("Connection refused")

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.parametrize(
    ("attribute", "value"),
    [
        ("side_effect", WattwaechterNoDataError("No data")),
        ("side_effect", WattwaechterConnectionError("Connection refused")),
        ("return_value", None),
    ],
    ids=["no_data", "connection_error", "returns_none"],
)
async def test_setup_entry_retries_on_meter_data_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: AsyncMock,
    attribute: str,
    value: Any,
) -> None:
    """Test setup retries when meter_data fails or returns no data."""
    setattr(mock_client.meter_data, attribute, value)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_entry_auth_error_starts_reauth(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: AsyncMock,
) -> None:
    """Test an authentication error during setup starts the reauth flow."""
    mock_client.meter_data.side_effect = WattwaechterAuthenticationError(
        "Invalid token"
    )

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == SOURCE_REAUTH
    assert flows[0]["context"]["entry_id"] == mock_config_entry.entry_id


@pytest.mark.parametrize(
    ("system_info_error", "expected_url"),
    [
        (None, "http://wattwaechter-aabbccddeeff.local"),
        (WattwaechterConnectionError("offline"), f"http://{MOCK_HOST}"),
    ],
    ids=["mdns", "ip_fallback"],
)
async def test_device_configuration_url(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: AsyncMock,
    device_registry: dr.DeviceRegistry,
    system_info_error: WattwaechterError | None,
    expected_url: str,
) -> None:
    """Test the configuration URL prefers the mDNS host and falls back to the IP."""
    mock_client.system_info.side_effect = system_info_error

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, MOCK_DEVICE_ID), mock_config_entry.entry_id
    )
    assert device is not None
    assert device.configuration_url == expected_url


@pytest.mark.parametrize(
    ("system_info_error", "expected_model"),
    [
        (None, "WattWächter Plus"),
        (WattwaechterConnectionError("offline"), "WattWächter Plus"),
    ],
    ids=["system_info", "entry_fallback"],
)
async def test_device_model(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: AsyncMock,
    device_registry: dr.DeviceRegistry,
    system_info_error: WattwaechterError | None,
    expected_model: str,
) -> None:
    """Test the device model comes from the system info, else from the entry."""
    mock_client.system_info.side_effect = system_info_error

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, MOCK_DEVICE_ID), mock_config_entry.entry_id
    )
    assert device is not None
    assert device.model == expected_model
    # The legacy mDNS model "WW-Plus" stored in the entry maps to the model ID
    assert device.model_id == "ww_plus"


async def test_device_model_follows_system_info(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    device_registry: dr.DeviceRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the model is updated once the system info arrives or changes."""
    mock_client.system_info.side_effect = WattwaechterConnectionError("offline")
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={**MOCK_CONFIG_DATA, CONF_MODEL: "WW-GW-MF"},
        unique_id=MOCK_DEVICE_ID,
        minor_version=2,
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, MOCK_DEVICE_ID), entry.entry_id
    )
    assert device is not None
    assert device.model == "WattWächter Gas/Wasser"

    mock_client.system_info.side_effect = None
    mock_client.system_info.return_value = MOCK_SYSTEM_INFO_WATER
    freezer.tick(timedelta(seconds=DEFAULT_SCAN_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    device = device_registry.async_get(device.id)
    assert device.model == "WattWächter Wasser"
    assert device.model_id == "ww_gw_mf"

    # The device is switched to gas
    mock_client.system_info.return_value = MOCK_SYSTEM_INFO_GAS
    freezer.tick(timedelta(seconds=DEFAULT_SCAN_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert device_registry.async_get(device.id).model == "WattWächter Gas"


async def test_migrate_gw_entry_to_bare_device_id(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a gas/water entry stored with the WWGW- prefix gets the bare ID."""
    mock_client.system_info.return_value = MOCK_SYSTEM_INFO_WATER
    mock_client.meter_data.return_value = MOCK_METER_DATA_WATER
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={**MOCK_CONFIG_DATA, CONF_DEVICE_ID: LEGACY_GW_ID},
        unique_id=LEGACY_GW_ID,
        minor_version=1,
    )
    entry.add_to_hass(hass)
    device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id, identifiers={(DOMAIN, LEGACY_GW_ID)}
    )
    sensor = entity_registry.async_get_or_create(
        SENSOR_DOMAIN,
        DOMAIN,
        f"{LEGACY_GW_ID}_8-0:1.0.0",
        config_entry=entry,
        device_id=device.id,
    )
    update = entity_registry.async_get_or_create(
        UPDATE_DOMAIN, DOMAIN, LEGACY_GW_ID, config_entry=entry, device_id=device.id
    )
    # Already carries the bare ID and must stay as it is
    ssid = entity_registry.async_get_or_create(
        SENSOR_DOMAIN,
        DOMAIN,
        f"{MOCK_DEVICE_ID}_ssid",
        config_entry=entry,
        device_id=device.id,
    )

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert entry.minor_version == 2
    assert entry.unique_id == MOCK_DEVICE_ID
    assert entry.data[CONF_DEVICE_ID] == MOCK_DEVICE_ID
    assert device_registry.async_get(device.id).identifiers == {
        (DOMAIN, MOCK_DEVICE_ID)
    }
    migrated_sensor = entity_registry.async_get(sensor.entity_id)
    assert migrated_sensor.unique_id == f"{MOCK_DEVICE_ID}_8-0:1.0.0"
    assert entity_registry.async_get(update.entity_id).unique_id == MOCK_DEVICE_ID
    assert (
        entity_registry.async_get(ssid.entity_id).unique_id == f"{MOCK_DEVICE_ID}_ssid"
    )


async def test_migrate_plus_entry_unchanged(
    hass: HomeAssistant, mock_client: AsyncMock
) -> None:
    """Test an entry that already uses the bare ID only gets the new version."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_CONFIG_DATA,
        unique_id=MOCK_DEVICE_ID,
        minor_version=1,
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert entry.minor_version == 2
    assert entry.unique_id == MOCK_DEVICE_ID
    assert entry.data == MOCK_CONFIG_DATA


async def test_migrate_keeps_id_when_device_configured_twice(
    hass: HomeAssistant, mock_client: AsyncMock
) -> None:
    """Test the old ID is kept when another entry already has the bare ID."""
    MockConfigEntry(
        domain=DOMAIN, data=MOCK_CONFIG_DATA, unique_id=MOCK_DEVICE_ID
    ).add_to_hass(hass)
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={**MOCK_CONFIG_DATA, CONF_DEVICE_ID: LEGACY_GW_ID},
        unique_id=LEGACY_GW_ID,
        minor_version=1,
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.minor_version == 2
    assert entry.unique_id == LEGACY_GW_ID
    assert entry.data[CONF_DEVICE_ID] == LEGACY_GW_ID
