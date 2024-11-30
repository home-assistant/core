"""Test for setup methods for the SDM API.

The tests fake out the subscriber/devicemanager and simulate setup behavior
and failure modes.

By default all tests use test fixtures that run in each possible configuration
mode (e.g. yaml, ConfigEntry, etc) however some tests override and just run in
relevant modes.
"""

from collections.abc import Generator
import logging
from typing import Any
from unittest.mock import patch

from google_nest_sdm.exceptions import (
    ApiException,
    AuthException,
    ConfigurationException,
    SubscriberException,
)
import pytest

from homeassistant.components.nest import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from .common import (
    PROJECT_ID,
    SUBSCRIBER_ID,
    TEST_CONFIG_NEW_SUBSCRIPTION,
    FakeSubscriber,
    PlatformSetup,
    YieldFixture,
)

PLATFORM = "sensor"


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


@pytest.fixture
def subscriber_side_effect() -> Any | None:
    """Fixture to inject failures into FakeSubscriber start."""
    return None


@pytest.fixture
def failing_subscriber(
    subscriber_side_effect: Any | None,
) -> YieldFixture[FakeSubscriber]:
    """Fixture overriding default subscriber behavior to allow failure injection."""
    subscriber = FakeSubscriber()
    with patch(
        "homeassistant.components.nest.api.GoogleNestSubscriber.start_async",
        side_effect=subscriber_side_effect,
    ):
        yield subscriber


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


@pytest.mark.parametrize("subscriber_side_effect", [SubscriberException()])
async def test_setup_susbcriber_failure(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    failing_subscriber,
    setup_base_platform,
) -> None:
    """Test configuration error."""
    await setup_base_platform()
    assert "Subscriber error:" in caplog.text

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].state is ConfigEntryState.SETUP_RETRY


async def test_setup_device_manager_failure(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, setup_base_platform
) -> None:
    """Test device manager api failure."""
    with (
        patch("homeassistant.components.nest.api.GoogleNestSubscriber.start_async"),
        patch(
            "homeassistant.components.nest.api.GoogleNestSubscriber.async_get_device_manager",
            side_effect=ApiException(),
        ),
    ):
        await setup_base_platform()

    assert "Device manager error:" in caplog.text

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].state is ConfigEntryState.SETUP_RETRY


@pytest.mark.parametrize("subscriber_side_effect", [AuthException()])
async def test_subscriber_auth_failure(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    setup_base_platform,
    failing_subscriber,
) -> None:
    """Test subscriber throws an authentication error."""
    await setup_base_platform()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].state is ConfigEntryState.SETUP_ERROR

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["step_id"] == "reauth_confirm"


@pytest.mark.parametrize("subscriber_side_effect", [(ConfigurationException())])
async def test_subscriber_configuration_failure(
    hass: HomeAssistant,
    error_caplog: pytest.LogCaptureFixture,
    setup_base_platform,
    failing_subscriber,
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
    setup_base_platform,
) -> None:
    """Test successful unload of a ConfigEntry."""
    with patch(
        "homeassistant.components.nest.api.GoogleNestSubscriber",
        return_value=FakeSubscriber(),
    ):
        await setup_base_platform()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    entry = entries[0]
    assert entry.state is ConfigEntryState.LOADED
    # Assert entry was imported if from configuration.yaml
    assert entry.data.get("subscriber_id") == SUBSCRIBER_ID
    assert entry.data.get("project_id") == PROJECT_ID

    with (
        patch("homeassistant.components.nest.api.GoogleNestSubscriber.subscriber_id"),
        patch(
            "homeassistant.components.nest.api.GoogleNestSubscriber.delete_subscription",
        ) as delete,
    ):
        assert await hass.config_entries.async_remove(entry.entry_id)
        assert delete.called

    entries = hass.config_entries.async_entries(DOMAIN)
    assert not entries


async def test_home_assistant_stop(
    hass: HomeAssistant,
    setup_platform: PlatformSetup,
    subscriber: FakeSubscriber,
) -> None:
    """Test successful subscriber shutdown when HomeAssistant stops."""
    await setup_platform()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    entry = entries[0]
    assert entry.state is ConfigEntryState.LOADED

    await hass.async_stop()
    assert subscriber.stop_calls == 1


async def test_remove_entry_delete_subscriber_failure(
    hass: HomeAssistant, setup_base_platform
) -> None:
    """Test a failure when deleting the subscription."""
    with patch(
        "homeassistant.components.nest.api.GoogleNestSubscriber",
        return_value=FakeSubscriber(),
    ):
        await setup_base_platform()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    entry = entries[0]
    assert entry.state is ConfigEntryState.LOADED

    with patch(
        "homeassistant.components.nest.api.GoogleNestSubscriber.delete_subscription",
        side_effect=SubscriberException(),
    ) as delete:
        assert await hass.config_entries.async_remove(entry.entry_id)
        assert delete.called

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
