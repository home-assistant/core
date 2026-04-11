"""Test for setup methods for the SDM API.

The tests fake out the subscriber/devicemanager and simulate setup behavior
and failure modes.

By default all tests use test fixtures that run in each possible configuration
mode (e.g. yaml, ConfigEntry, etc) however some tests override and just run in
relevant modes.
"""

from collections.abc import Generator
import datetime
from http import HTTPStatus
import logging
from unittest.mock import AsyncMock, patch

import aiohttp
from google_nest_sdm.exceptions import (
    ApiException,
    AuthException,
    ConfigurationException,
    SubscriberException,
    SubscriberTimeoutException,
)
import pytest

from homeassistant.components.nest import DOMAIN
from homeassistant.components.nest.const import OAUTH2_TOKEN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.util.dt import utcnow

from .common import (
    PROJECT_ID,
    SUBSCRIBER_ID,
    TEST_CONFIG_NEW_SUBSCRIPTION,
    CreateDevice,
    PlatformSetup,
    create_nest_event,
)

from tests.test_util.aiohttp import AiohttpClientMocker

PLATFORM = "sensor"

EXPIRED_TOKEN_TIMESTAMP = datetime.datetime(2022, 4, 8).timestamp()


@pytest.fixture
def platforms() -> list[str]:
    """Fixture to setup the platforms to test."""
    return ["sensor"]


@pytest.fixture
def error_caplog(
    caplog: pytest.LogCaptureFixture,
) -> Generator[pytest.LogCaptureFixture]:
    """Fixture to capture nest init error messages."""
    with caplog.at_level(logging.ERROR, logger="homeassistant.components.nest"):
        yield caplog


@pytest.fixture
def warning_caplog(
    caplog: pytest.LogCaptureFixture,
) -> Generator[pytest.LogCaptureFixture]:
    """Fixture to capture nest init warning messages."""
    with caplog.at_level(logging.WARNING, logger="homeassistant.components.nest"):
        yield caplog


async def test_setup_success(
    hass: HomeAssistant, error_caplog: pytest.LogCaptureFixture, setup_platform
) -> None:
    """Test successful setup."""
    await setup_platform()
    assert not error_caplog.records

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].state is ConfigEntryState.LOADED


@pytest.mark.parametrize("nest_test_config", [(TEST_CONFIG_NEW_SUBSCRIPTION)])
async def test_setup_success_new_subscription_format(
    hass: HomeAssistant, error_caplog: pytest.LogCaptureFixture, setup_platform
) -> None:
    """Test successful setup."""
    await setup_platform()
    assert not error_caplog.records

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].state is ConfigEntryState.LOADED


@pytest.mark.parametrize("subscriber_id", [("invalid-subscriber-format")])
async def test_setup_configuration_failure(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    subscriber_id,
    setup_base_platform,
) -> None:
    """Test configuration error."""
    await setup_base_platform()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].state is ConfigEntryState.SETUP_ERROR

    # This error comes from the python google-nest-sdm library, as a check added
    # to prevent common misconfigurations (e.g. confusing topic and subscriber)
    assert "Subscription misconfigured. Expected subscriber_id" in caplog.text


@pytest.mark.parametrize(
    ("subscriber_side_effect", "expected_log_message"),
    [
        (SubscriberException(), "Subscriber error:"),
        (SubscriberTimeoutException(), "Subscriber timed out"),
    ],
)
async def test_setup_subscriber_failure(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    setup_base_platform,
    expected_log_message: str,
) -> None:
    """Test subscriber error handling (SubscriberException and SubscriberTimeoutException)."""
    await setup_base_platform()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].state is ConfigEntryState.SETUP_RETRY

    assert expected_log_message in caplog.text


async def test_setup_device_manager_failure(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, setup_base_platform
) -> None:
    """Test device manager api failure."""
    with (
        patch(
            "homeassistant.components.nest.api.GoogleNestSubscriber.async_get_device_manager",
            side_effect=ApiException(),
        ),
    ):
        await setup_base_platform()

    assert "Error communicating with the Device Access API" in caplog.text

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].state is ConfigEntryState.SETUP_RETRY


@pytest.mark.parametrize("token_expiration_time", [EXPIRED_TOKEN_TIMESTAMP])
@pytest.mark.parametrize(
    ("token_response_args", "expected_state", "expected_steps"),
    [
        # Cases that retry integration setup
        (
            {"status": HTTPStatus.INTERNAL_SERVER_ERROR},
            ConfigEntryState.SETUP_RETRY,
            [],
        ),
        ({"exc": aiohttp.ClientError("No internet")}, ConfigEntryState.SETUP_RETRY, []),
        # Cases that require the user to reauthenticate in a config flow
        (
            {"status": HTTPStatus.BAD_REQUEST},
            ConfigEntryState.SETUP_ERROR,
            ["reauth_confirm"],
        ),
        (
            {"status": HTTPStatus.FORBIDDEN},
            ConfigEntryState.SETUP_ERROR,
            ["reauth_confirm"],
        ),
    ],
)
async def test_expired_token_refresh_error(
    hass: HomeAssistant,
    setup_base_platform: PlatformSetup,
    aioclient_mock: AiohttpClientMocker,
    token_response_args: dict,
    expected_state: ConfigEntryState,
    expected_steps: list[str],
) -> None:
    """Test errors when attempting to refresh the auth token."""

    aioclient_mock.post(
        OAUTH2_TOKEN,
        **token_response_args,
    )

    await setup_base_platform()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].state is expected_state

    flows = hass.config_entries.flow.async_progress()
    assert expected_steps == [flow["step_id"] for flow in flows]


@pytest.mark.parametrize("subscriber_side_effect", [AuthException()])
async def test_subscriber_auth_failure(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    setup_base_platform,
) -> None:
    """Test subscriber throws an authentication error."""
    await setup_base_platform()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].state is ConfigEntryState.SETUP_ERROR

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["step_id"] == "reauth_confirm"


@pytest.mark.parametrize("subscriber_side_effect", [ConfigurationException()])
async def test_subscriber_configuration_failure(
    hass: HomeAssistant,
    error_caplog: pytest.LogCaptureFixture,
    setup_base_platform,
) -> None:
    """Test configuration error."""
    await setup_base_platform()
    assert "Configuration error: " in error_caplog.text

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].state is ConfigEntryState.SETUP_ERROR


async def test_unload_entry(hass: HomeAssistant, setup_platform) -> None:
    """Test successful unload of a ConfigEntry."""
    await setup_platform()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    entry = entries[0]
    assert entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(entry.entry_id)
    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_remove_entry(
    hass: HomeAssistant,
    setup_base_platform: PlatformSetup,
    aioclient_mock: AiohttpClientMocker,
    subscriber: AsyncMock,
) -> None:
    """Test successful unload of a ConfigEntry."""
    await setup_base_platform()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    entry = entries[0]
    assert entry.state is ConfigEntryState.LOADED
    # Assert entry was imported if from configuration.yaml
    assert entry.data.get("subscriber_id") == SUBSCRIBER_ID
    assert entry.data.get("project_id") == PROJECT_ID

    aioclient_mock.clear_requests()
    aioclient_mock.delete(
        f"https://pubsub.googleapis.com/v1/{SUBSCRIBER_ID}",
        json={},
    )

    assert not subscriber.stop.called

    assert await hass.config_entries.async_remove(entry.entry_id)

    assert aioclient_mock.call_count == 1
    assert subscriber.stop.called

    entries = hass.config_entries.async_entries(DOMAIN)
    assert not entries


async def test_home_assistant_stop(
    hass: HomeAssistant,
    setup_platform: PlatformSetup,
    subscriber: AsyncMock,
) -> None:
    """Test successful subscriber shutdown when HomeAssistant stops."""
    await setup_platform()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    entry = entries[0]
    assert entry.state is ConfigEntryState.LOADED

    assert not subscriber.stop.called
    await hass.async_stop()
    assert subscriber.stop.called


async def test_remove_entry_delete_subscriber_failure(
    hass: HomeAssistant,
    setup_base_platform: PlatformSetup,
    aioclient_mock: AiohttpClientMocker,
    subscriber: AsyncMock,
) -> None:
    """Test a failure when deleting the subscription."""
    await setup_base_platform()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    entry = entries[0]
    assert entry.state is ConfigEntryState.LOADED

    aioclient_mock.clear_requests()
    aioclient_mock.delete(
        f"https://pubsub.googleapis.com/v1/{SUBSCRIBER_ID}",
        status=HTTPStatus.NOT_FOUND,
    )

    assert not subscriber.stop.called

    assert await hass.config_entries.async_remove(entry.entry_id)

    assert aioclient_mock.call_count == 1
    assert subscriber.stop.called

    entries = hass.config_entries.async_entries(DOMAIN)
    assert not entries


@pytest.mark.parametrize("config_entry_unique_id", [DOMAIN, None])
async def test_migrate_unique_id(
    hass: HomeAssistant,
    error_caplog,
    setup_platform,
    config_entry,
    config_entry_unique_id,
) -> None:
    """Test successful setup."""

    assert config_entry.state is ConfigEntryState.NOT_LOADED
    assert config_entry.unique_id == config_entry_unique_id

    await setup_platform()

    assert config_entry.state is ConfigEntryState.LOADED
    assert config_entry.unique_id == PROJECT_ID


async def test_add_devices(
    hass: HomeAssistant,
    setup_platform: PlatformSetup,
    create_device: CreateDevice,
    subscriber: AsyncMock,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test that adding devices after initial setup works."""
    device_id1 = "enterprises/project-id/devices/device-id"
    traits = {
        "sdm.devices.traits.Temperature": {
            "ambientTemperatureCelsius": 25.1,
        },
    }
    create_device.create(raw_traits=traits, raw_data={"name": device_id1})
    await setup_platform()

    device_entries = dr.async_entries_for_config_entry(
        device_registry, hass.config_entries.async_entries(DOMAIN)[0].entry_id
    )
    assert len(device_entries) == 1

    # Add a second device and trigger a notification to refresh
    device_id2 = "enterprises/project-id/devices/device-id-2"
    create_device.create(raw_traits=traits, raw_data={"name": device_id2})

    event_message = create_nest_event(
        {
            "eventId": "some-event-id",
            "timestamp": utcnow().isoformat(timespec="seconds"),
            "relationUpdate": {
                "type": "UPDATED",
                "subject": "some-subject",
                "object": "some-object",
            },
        },
    )
    await subscriber.async_receive_event(event_message)
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    device_entries = dr.async_entries_for_config_entry(
        device_registry, hass.config_entries.async_entries(DOMAIN)[0].entry_id
    )
    assert len(device_entries) == 2


async def test_stale_device_cleanup(
    hass: HomeAssistant,
    setup_platform: PlatformSetup,
    create_device: CreateDevice,
    subscriber: AsyncMock,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test that stale devices are removed."""
    # Device #1 will be returned by the API.
    device_id1 = "enterprises/project-id/devices/device-id"
    device_registry.async_get_or_create(
        config_entry_id=hass.config_entries.async_entries(DOMAIN)[0].entry_id,
        identifiers={(DOMAIN, device_id1)},
        manufacturer="Google Nest",
    )
    create_device.create(
        raw_traits={
            "sdm.devices.traits.Temperature": {
                "ambientTemperatureCelsius": 25.1,
            },
        },
        raw_data={"name": device_id1},
    )

    # Device #2 is stale and should be removed.
    device_registry.async_get_or_create(
        config_entry_id=hass.config_entries.async_entries(DOMAIN)[0].entry_id,
        identifiers={(DOMAIN, "enterprises/project-id/devices/device-id-stale")},
        manufacturer="Google Nest",
    )

    # Verify both devices are registered before setup.
    device_entries = dr.async_entries_for_config_entry(
        device_registry, hass.config_entries.async_entries(DOMAIN)[0].entry_id
    )
    assert len(device_entries) == 2

    # Setup should remove the stale device.
    await setup_platform()

    device_entries = dr.async_entries_for_config_entry(
        device_registry, hass.config_entries.async_entries(DOMAIN)[0].entry_id
    )
    assert len(device_entries) == 1
    assert device_entries[0].identifiers == {(DOMAIN, device_id1)}
