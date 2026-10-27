"""Tests for TP-Link Omada integration init."""

from datetime import timedelta
from functools import partial
import logging
from unittest.mock import AsyncMock, MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    async_load_json_array_fixture,
    async_load_json_object_fixture,
)
from tplink_omada_client.devices import OmadaGateway, OmadaListDevice
from tplink_omada_client.exceptions import (
    ConnectionFailed,
    LoginFailed,
    OmadaClientException,
    UnsupportedControllerVersion,
)

from homeassistant.components.tplink_omada.const import DOMAIN
from homeassistant.components.tplink_omada.coordinator import (
    POLL_CLIENTS,
    OmadaCoordinator,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.update_coordinator import UpdateFailed
from homeassistant.util import dt as dt_util

MOCK_ENTRY_DATA = {
    "host": "https://fake.omada.host",
    "verify_ssl": True,
    "site": "SiteId",
    "username": "test-username",
    "password": "test-password",
}


async def _async_poll_devices(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Advance to the next device poll and let it complete."""
    freezer.tick(timedelta(seconds=POLL_CLIENTS + 1))
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done(wait_background_tasks=True)


@pytest.mark.parametrize(
    ("side_effect", "entry_state", "translation_key"),
    [
        (
            UnsupportedControllerVersion("4.0.0"),
            ConfigEntryState.SETUP_ERROR,
            "unsupported_controller",
        ),
        (
            LoginFailed(401, "invalid credentials"),
            ConfigEntryState.SETUP_ERROR,
            "auth_failed",
        ),
        (
            ConnectionFailed(),
            ConfigEntryState.SETUP_RETRY,
            "cannot_connect",
        ),
        (
            OmadaClientException(),
            ConfigEntryState.SETUP_RETRY,
            "unexpected_error",
        ),
    ],
)
async def test_setup_entry_login_failed_raises_configentryauthfailed(
    hass: HomeAssistant,
    mock_omada_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    side_effect: OmadaClientException,
    entry_state: ConfigEntryState,
    translation_key: str,
) -> None:
    """Test setup entry with login failed raises ConfigEntryAuthFailed."""
    mock_omada_client.login.side_effect = side_effect

    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is entry_state
    assert mock_config_entry.error_reason_translation_key == translation_key
    assert mock_config_entry.error_reason_translation_placeholders is None


async def test_coordinator_update_failure_is_translated(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_omada_site_client: MagicMock,
) -> None:
    """Test coordinator API failures raise a translated UpdateFailed."""
    coordinator = OmadaCoordinator(
        hass, mock_config_entry, mock_omada_site_client, "test"
    )
    with (
        patch.object(
            OmadaCoordinator,
            "poll_update",
            side_effect=OmadaClientException("boom"),
        ),
        pytest.raises(UpdateFailed) as err,
    ):
        await coordinator._async_update_data()

    assert err.value.translation_domain == DOMAIN
    assert err.value.translation_key == "api_error"


async def test_automatic_missing_device_cleanup(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_omada_client: MagicMock,
) -> None:
    """Test missing devices are removed during setup and the controller is kept."""
    mock_config_entry = MockConfigEntry(
        title="Test Omada Controller",
        domain=DOMAIN,
        data=dict(MOCK_ENTRY_DATA),
        unique_id="12345_SiteId",
        version=2,
    )
    mock_config_entry.add_to_hass(hass)

    device_entry = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, "99:99:99:99:99:99")},
        manufacturer="TPLink",
        name="Old Device",
        model="Some old model",
    )

    assert device_registry.async_get(device_entry.id) == device_entry

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert device_registry.async_get(device_entry.id) is None
    assert device_registry.async_get_device_by_identifier(
        (DOMAIN, "00-11-22-33-44-55"), mock_config_entry.entry_id
    )
    assert device_registry.async_get_device_by_identifier(
        (DOMAIN, "54-AF-97-00-00-01"), mock_config_entry.entry_id
    )


async def test_startup_cleanup_runs_before_platform_setup(
    hass: HomeAssistant,
    mock_omada_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test stale entries release entity IDs before platforms are set up."""
    mock_config_entry.add_to_hass(hass)

    stale_device = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, "99:99:99:99:99:99")},
        manufacturer="TP-Link",
        model="Test",
        name="Test PoE Switch",
    )
    entity_registry.async_get_or_create(
        "sensor",
        DOMAIN,
        "stale_device_status",
        config_entry=mock_config_entry,
        device_id=stale_device.id,
        suggested_object_id="test_poe_switch_device_status",
    )

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert device_registry.async_get(stale_device.id) is None
    assert (
        entity_registry.async_get_entity_id(
            "sensor", DOMAIN, "54-AF-97-00-00-01_device_status"
        )
        == "sensor.test_poe_switch_device_status"
    )


async def test_device_update_removes_disappeared_device(
    hass: HomeAssistant,
    mock_omada_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a device-list update removes the devices it no longer reports."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    removed_mac = "54-AF-97-00-00-01"
    assert device_registry.async_get_device_by_identifier(
        (DOMAIN, removed_mac), mock_config_entry.entry_id
    )

    site_client = mock_omada_client.get_site_client.return_value
    site_client.get_devices = AsyncMock(
        side_effect=partial(_get_devices_without, hass, removed_mac)
    )
    await _async_poll_devices(hass, freezer)

    assert (
        device_registry.async_get_device_by_identifier(
            (DOMAIN, removed_mac), mock_config_entry.entry_id
        )
        is None
    )
    assert (
        entity_registry.async_get_entity_id("update", DOMAIN, f"{removed_mac}_firmware")
        is None
    )


async def test_empty_device_update_keeps_devices(
    hass: HomeAssistant,
    mock_omada_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test an empty device list is treated as a glitch and removes nothing."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    switch_mac = "54-AF-97-00-00-01"
    sensor_entity_id = "sensor.test_poe_switch_device_status"
    assert hass.states.get(sensor_entity_id) is not None

    site_client = mock_omada_client.get_site_client.return_value
    site_client.get_devices = AsyncMock(return_value=[])
    await _async_poll_devices(hass, freezer)

    assert device_registry.async_get_device_by_identifier(
        (DOMAIN, switch_mac), mock_config_entry.entry_id
    )
    assert (
        entity_registry.async_get_entity_id("update", DOMAIN, f"{switch_mac}_firmware")
        is not None
    )
    assert hass.states.get(sensor_entity_id) is not None
    assert hass.states.get(sensor_entity_id).state not in {"unknown", "unavailable"}


async def test_failed_poll_keeps_devices(
    hass: HomeAssistant,
    mock_omada_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a failed device poll removes nothing."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    switch_mac = "54-AF-97-00-00-01"
    site_client = mock_omada_client.get_site_client.return_value
    site_client.get_devices = AsyncMock(side_effect=OmadaClientException)
    await _async_poll_devices(hass, freezer)

    assert device_registry.async_get_device_by_identifier(
        (DOMAIN, switch_mac), mock_config_entry.entry_id
    )


async def test_registration_failure_is_logged_and_retried(
    hass: HomeAssistant,
    mock_omada_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a transient switch fetch failure is logged and registration retries."""
    mock_config_entry.add_to_hass(hass)

    site_client = mock_omada_client.get_site_client.return_value
    original_get_switch = site_client.get_switch.return_value
    fail_switch_fetch = True

    async def _get_switch(device: OmadaListDevice) -> object:
        if fail_switch_fetch:
            raise OmadaClientException("switch fetch failed")
        return original_get_switch

    site_client.get_switch = AsyncMock(side_effect=_get_switch)

    with caplog.at_level(
        logging.DEBUG, logger="homeassistant.components.tplink_omada.controller"
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)

    assert "Failed to register entities for Omada device" in caplog.text
    assert "switch fetch failed" in caplog.text
    assert hass.states.get("switch.test_poe_switch_port_1_poe") is None

    # The failed device was left unprocessed, so the next update retries.
    fail_switch_fetch = False
    await _async_poll_devices(hass, freezer)

    assert hass.states.get("switch.test_poe_switch_port_1_poe") is not None


async def _get_devices_without(
    hass: HomeAssistant, excluded_mac: str
) -> list[OmadaListDevice]:
    """Return devices from the devices fixture, skipping one MAC."""
    devices_data = await async_load_json_array_fixture(hass, "devices.json", DOMAIN)
    return [
        OmadaListDevice(device)
        for device in devices_data
        if device["mac"] != excluded_mac
    ]


async def test_cleanup_recreates_device_when_reappears(
    hass: HomeAssistant,
    mock_omada_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a removed device is registered again when it returns."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    removed_mac = "54-AF-97-00-00-01"
    update_unique_id = f"{removed_mac}_firmware"
    assert device_registry.async_get_device_by_identifier(
        (DOMAIN, removed_mac), mock_config_entry.entry_id
    )
    assert (
        entity_registry.async_get_entity_id("update", DOMAIN, update_unique_id)
        is not None
    )

    site_client = mock_omada_client.get_site_client.return_value

    # Remove the switch from the controller's device list
    site_client.get_devices = AsyncMock(
        side_effect=partial(_get_devices_without, hass, removed_mac)
    )
    await _async_poll_devices(hass, freezer)

    assert (
        device_registry.async_get_device_by_identifier(
            (DOMAIN, removed_mac), mock_config_entry.entry_id
        )
        is None
    )
    assert (
        entity_registry.async_get_entity_id("update", DOMAIN, update_unique_id) is None
    )

    # Switch returns to the controller, and the next poll registers it again
    devices_data = await async_load_json_array_fixture(hass, "devices.json", DOMAIN)
    site_client.get_devices = AsyncMock(
        return_value=[OmadaListDevice(d) for d in devices_data]
    )
    await _async_poll_devices(hass, freezer)

    assert device_registry.async_get_device_by_identifier(
        (DOMAIN, removed_mac), mock_config_entry.entry_id
    )
    assert (
        entity_registry.async_get_entity_id("update", DOMAIN, update_unique_id)
        is not None
    )


async def test_cleanup_recreates_gateway_ports_after_successful_refresh(
    hass: HomeAssistant,
    mock_omada_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a returning gateway is not rebuilt from stale port data."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    gateway_mac = "AA-BB-CC-DD-EE-FF"
    assert device_registry.async_get_device_by_identifier(
        (DOMAIN, gateway_mac), mock_config_entry.entry_id
    )

    def gateway_port_entities() -> list[er.RegistryEntry]:
        return [
            entry
            for entry in entity_registry.entities.values()
            if entry.platform == DOMAIN
            and entry.domain in {"binary_sensor", "switch"}
            and entry.unique_id.startswith(f"{gateway_mac}_")
        ]

    assert gateway_port_entities()

    site_client = mock_omada_client.get_site_client.return_value

    # Remove the gateway from the controller's device list
    site_client.get_devices = AsyncMock(
        side_effect=partial(_get_devices_without, hass, gateway_mac)
    )
    await _async_poll_devices(hass, freezer)

    assert (
        device_registry.async_get_device_by_identifier(
            (DOMAIN, gateway_mac), mock_config_entry.entry_id
        )
        is None
    )
    assert not gateway_port_entities()

    # The gateway returns, but its refresh fails: no port entities are built
    # from the cached port lists, and registration stays retryable.
    site_client.get_gateway = AsyncMock(
        side_effect=OmadaClientException("gateway unavailable")
    )
    devices_data = await async_load_json_array_fixture(hass, "devices.json", DOMAIN)
    site_client.get_devices = AsyncMock(
        return_value=[OmadaListDevice(device) for device in devices_data]
    )
    await _async_poll_devices(hass, freezer)

    assert not gateway_port_entities()

    # A successful refresh rebuilds the port entities.
    gateway_data = await async_load_json_object_fixture(
        hass, "gateway-TL-ER7212PC.json", DOMAIN
    )
    site_client.get_gateway = AsyncMock(return_value=OmadaGateway(gateway_data))
    await _async_poll_devices(hass, freezer)

    assert device_registry.async_get_device_by_identifier(
        (DOMAIN, gateway_mac), mock_config_entry.entry_id
    )
    assert gateway_port_entities()


async def test_migrate_entry_v1_to_v2(
    hass: HomeAssistant,
    mock_omada_client: MagicMock,
) -> None:
    """Test migration of a version 1 config entry to version 2."""
    entry = MockConfigEntry(
        title="Test Omada Controller",
        domain=DOMAIN,
        data=dict(MOCK_ENTRY_DATA),
        unique_id="12345",
        version=1,
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.version == 2
    assert entry.unique_id == "12345_SiteId"
    assert entry.state is ConfigEntryState.LOADED
