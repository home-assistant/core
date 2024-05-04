"""The tests for the Ring component."""

from datetime import timedelta
from unittest.mock import patch

import pytest
import requests_mock
from ring_doorbell import AuthenticationError, RingError, RingTimeout

from homeassistant.components import ring
from homeassistant.components.camera import DOMAIN as CAMERA_DOMAIN
from homeassistant.components.light import DOMAIN as LIGHT_DOMAIN
from homeassistant.components.ring import DOMAIN
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.const import CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.issue_registry import IssueRegistry
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from tests.common import MockConfigEntry, async_fire_time_changed, load_fixture


async def test_setup(hass: HomeAssistant, requests_mock: requests_mock.Mocker) -> None:
    """Test the setup."""
    await async_setup_component(hass, ring.DOMAIN, {})

    requests_mock.post(
        "https://oauth.ring.com/oauth/token", text=load_fixture("oauth.json", "ring")
    )
    requests_mock.post(
        "https://api.ring.com/clients_api/session",
        text=load_fixture("session.json", "ring"),
    )
    requests_mock.get(
        "https://api.ring.com/clients_api/ring_devices",
        text=load_fixture("devices.json", "ring"),
    )
    requests_mock.get(
        "https://api.ring.com/clients_api/chimes/999999/health",
        text=load_fixture("chime_health_attrs.json", "ring"),
    )
    requests_mock.get(
        "https://api.ring.com/clients_api/doorbots/987652/health",
        text=load_fixture("doorboot_health_attrs.json", "ring"),
    )


async def test_auth_failed_on_setup(
    hass: HomeAssistant,
    requests_mock: requests_mock.Mocker,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test auth failure on setup entry."""
    mock_config_entry.add_to_hass(hass)
    with patch(
        "ring_doorbell.Ring.update_data",
        side_effect=AuthenticationError,
    ):
        assert not any(mock_config_entry.async_get_active_flows(hass, {SOURCE_REAUTH}))
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        assert any(mock_config_entry.async_get_active_flows(hass, {SOURCE_REAUTH}))
        assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


@pytest.mark.parametrize(
    ("error_type", "log_msg"),
    [
        (
            RingTimeout,
            "Timeout communicating with API: ",
        ),
        (
            RingError,
            "Error communicating with API: ",
        ),
    ],
    ids=["timeout-error", "other-error"],
)
async def test_error_on_setup(
    hass: HomeAssistant,
    requests_mock: requests_mock.Mocker,
    mock_config_entry: MockConfigEntry,
    caplog,
    error_type,
    log_msg,
) -> None:
    """Test auth failure on setup entry."""
    mock_config_entry.add_to_hass(hass)
    with patch(
        "ring_doorbell.Ring.update_data",
        side_effect=error_type,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY

        assert [
            record.message
            for record in caplog.records
            if record.levelname == "DEBUG"
            and record.name == "homeassistant.config_entries"
            and log_msg in record.message
            and DOMAIN in record.message
        ]


async def test_auth_failure_on_global_update(
    hass: HomeAssistant,
    requests_mock: requests_mock.Mocker,
    mock_config_entry: MockConfigEntry,
    caplog,
) -> None:
    """Test authentication failure on global data update."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert not any(mock_config_entry.async_get_active_flows(hass, {SOURCE_REAUTH}))
    with patch(
        "ring_doorbell.Ring.update_devices",
        side_effect=AuthenticationError,
    ):
        async_fire_time_changed(hass, dt_util.now() + timedelta(minutes=20))
        await hass.async_block_till_done()

        assert "Authentication failed while fetching devices data: " in [
            record.message
            for record in caplog.records
            if record.levelname == "ERROR"
            and record.name == "homeassistant.components.ring.coordinator"
        ]

        assert any(mock_config_entry.async_get_active_flows(hass, {SOURCE_REAUTH}))


async def test_auth_failure_on_device_update(
    hass: HomeAssistant,
    requests_mock: requests_mock.Mocker,
    mock_config_entry: MockConfigEntry,
    caplog,
) -> None:
    """Test authentication failure on device data update."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert not any(mock_config_entry.async_get_active_flows(hass, {SOURCE_REAUTH}))
    with patch(
        "ring_doorbell.RingDoorBell.history",
        side_effect=AuthenticationError,
    ):
        async_fire_time_changed(hass, dt_util.now() + timedelta(minutes=20))
        await hass.async_block_till_done(wait_background_tasks=True)

        assert "Authentication failed while fetching devices data: " in [
            record.message
            for record in caplog.records
            if record.levelname == "ERROR"
            and record.name == "homeassistant.components.ring.coordinator"
        ]

        assert any(mock_config_entry.async_get_active_flows(hass, {SOURCE_REAUTH}))


@pytest.mark.parametrize(
    ("error_type", "log_msg"),
    [
        (
            RingTimeout,
            "Error fetching devices data: Timeout communicating with API: ",
        ),
        (
            RingError,
            "Error fetching devices data: Error communicating with API: ",
        ),
    ],
    ids=["timeout-error", "other-error"],
)
async def test_error_on_global_update(
    hass: HomeAssistant,
    requests_mock: requests_mock.Mocker,
    mock_config_entry: MockConfigEntry,
    caplog,
    error_type,
    log_msg,
) -> None:
    """Test error on global data update."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    with patch(
        "ring_doorbell.Ring.update_devices",
        side_effect=error_type,
    ):
        async_fire_time_changed(hass, dt_util.now() + timedelta(minutes=20))
        await hass.async_block_till_done(wait_background_tasks=True)

        assert log_msg in [
            record.message for record in caplog.records if record.levelname == "ERROR"
        ]

        assert mock_config_entry.entry_id in hass.data[DOMAIN]


@pytest.mark.parametrize(
    ("error_type", "log_msg"),
    [
        (
            RingTimeout,
            "Error fetching devices data: Timeout communicating with API for device Front: ",
        ),
        (
            RingError,
            "Error fetching devices data: Error communicating with API for device Front: ",
        ),
    ],
    ids=["timeout-error", "other-error"],
)
async def test_error_on_device_update(
    hass: HomeAssistant,
    requests_mock: requests_mock.Mocker,
    mock_config_entry: MockConfigEntry,
    caplog,
    error_type,
    log_msg,
) -> None:
    """Test auth failure on data update."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    with patch(
        "ring_doorbell.RingDoorBell.history",
        side_effect=error_type,
    ):
        async_fire_time_changed(hass, dt_util.now() + timedelta(minutes=20))
        await hass.async_block_till_done(wait_background_tasks=True)

        assert log_msg in [
            record.message for record in caplog.records if record.levelname == "ERROR"
        ]
        assert mock_config_entry.entry_id in hass.data[DOMAIN]


async def test_issue_deprecated_service_ring_update(
    hass: HomeAssistant,
    issue_registry: IssueRegistry,
    caplog: pytest.LogCaptureFixture,
    requests_mock: requests_mock.Mocker,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the issue is raised on deprecated service ring.update."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(DOMAIN, "update", {}, blocking=True)

    issue = issue_registry.async_get_issue("ring", "deprecated_service_ring_update")
    assert issue
    assert issue.issue_domain == "ring"
    assert issue.issue_id == "deprecated_service_ring_update"
    assert issue.translation_key == "deprecated_service_ring_update"

    assert (
        "Detected use of service 'ring.update'. "
        "This is deprecated and will stop working in Home Assistant 2024.10. "
        "Use 'homeassistant.update_entity' instead which updates all ring entities"
    ) in caplog.text


@pytest.mark.parametrize(
    ("domain", "old_unique_id"),
    [
        (
            LIGHT_DOMAIN,
            123456,
        ),
        (
            CAMERA_DOMAIN,
            654321,
        ),
    ],
)
async def test_update_unique_id(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    caplog: pytest.LogCaptureFixture,
    requests_mock: requests_mock.Mocker,
    domain: str,
    old_unique_id: int | str,
) -> None:
    """Test unique_id update of integration."""
    entry = MockConfigEntry(
        title="Ring",
        domain=DOMAIN,
        data={
            CONF_USERNAME: "foo@bar.com",
            "token": {"access_token": "mock-token"},
        },
        unique_id="foo@bar.com",
    )
    entry.add_to_hass(hass)

    entity = entity_registry.async_get_or_create(
        domain=domain,
        platform=DOMAIN,
        unique_id=old_unique_id,
        config_entry=entry,
    )
    assert entity.unique_id == old_unique_id
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    entity_migrated = entity_registry.async_get(entity.entity_id)
    assert entity_migrated
    assert entity_migrated.unique_id == str(old_unique_id)
    assert (f"Fixing non string unique id {old_unique_id}") in caplog.text


async def test_update_unique_id_existing(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    caplog: pytest.LogCaptureFixture,
    requests_mock: requests_mock.Mocker,
) -> None:
    """Test unique_id update of integration."""
    old_unique_id = 123456
    entry = MockConfigEntry(
        title="Ring",
        domain=DOMAIN,
        data={
            CONF_USERNAME: "foo@bar.com",
            "token": {"access_token": "mock-token"},
        },
        unique_id="foo@bar.com",
    )
    entry.add_to_hass(hass)

    entity = entity_registry.async_get_or_create(
        domain=CAMERA_DOMAIN,
        platform=DOMAIN,
        unique_id=old_unique_id,
        config_entry=entry,
    )
    entity_existing = entity_registry.async_get_or_create(
        domain=CAMERA_DOMAIN,
        platform=DOMAIN,
        unique_id=str(old_unique_id),
        config_entry=entry,
    )
    assert entity.unique_id == old_unique_id
    assert entity_existing.unique_id == str(old_unique_id)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    entity_not_migrated = entity_registry.async_get(entity.entity_id)
    entity_existing = entity_registry.async_get(entity_existing.entity_id)
    assert entity_not_migrated
    assert entity_existing
    assert entity_not_migrated.unique_id == old_unique_id
    assert (
        f"Cannot migrate to unique_id '{old_unique_id}', "
        f"already exists for '{entity_existing.entity_id}', "
        "You may have to delete unavailable ring entities"
    ) in caplog.text


async def test_update_unique_id_no_update(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    caplog: pytest.LogCaptureFixture,
    requests_mock: requests_mock.Mocker,
) -> None:
    """Test unique_id update of integration."""
    correct_unique_id = "123456"
    entry = MockConfigEntry(
        title="Ring",
        domain=DOMAIN,
        data={
            CONF_USERNAME: "foo@bar.com",
            "token": {"access_token": "mock-token"},
        },
        unique_id="foo@bar.com",
    )
    entry.add_to_hass(hass)

    entity = entity_registry.async_get_or_create(
        domain=CAMERA_DOMAIN,
        platform=DOMAIN,
        unique_id="123456",
        config_entry=entry,
    )
    assert entity.unique_id == correct_unique_id
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    entity_migrated = entity_registry.async_get(entity.entity_id)
    assert entity_migrated
    assert entity_migrated.unique_id == correct_unique_id
    assert "Fixing non string unique id" not in caplog.text
