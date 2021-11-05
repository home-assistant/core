"""The tests for notify services that change targets."""
from typing import cast
from unittest.mock import Mock, call

from homeassistant.components import notify
from homeassistant.components.notify.const import (
    ATTR_DATA,
    ATTR_MESSAGE,
    ATTR_TARGET,
    ATTR_TITLE,
    DOMAIN,
    SERVICE_NOTIFY,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.service_platform import async_get_platforms
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


async def test_same_targets(hass: HomeAssistant):
    """Test not changing the targets in a notify service."""
    test = LegacyNotificationService(hass)
    await test.async_setup(hass, "notify", "test")
    await test.async_register_services()
    await hass.async_block_till_done()

    assert hasattr(test, "registered_targets")
    assert test.registered_targets == {"test_a": 1, "test_b": 2}

    await test.async_register_services()
    await hass.async_block_till_done()
    assert test.registered_targets == {"test_a": 1, "test_b": 2}


async def test_change_targets(hass: HomeAssistant):
    """Test changing the targets in a notify service."""
    test = LegacyNotificationService(hass)
    await test.async_setup(hass, "notify", "test")
    await test.async_register_services()
    await hass.async_block_till_done()

    assert hasattr(test, "registered_targets")
    assert test.registered_targets == {"test_a": 1, "test_b": 2}

    test.target_list = {"a": 0}
    await test.async_register_services()
    await hass.async_block_till_done()
    assert test.target_list == {"a": 0}
    assert test.registered_targets == {"test_a": 0}


async def test_add_targets(hass: HomeAssistant):
    """Test adding the targets in a notify service."""
    test = LegacyNotificationService(hass)
    await test.async_setup(hass, "notify", "test")
    await test.async_register_services()
    await hass.async_block_till_done()

    assert hasattr(test, "registered_targets")
    assert test.registered_targets == {"test_a": 1, "test_b": 2}

    test.target_list = {"a": 1, "b": 2, "c": 3}
    await test.async_register_services()
    await hass.async_block_till_done()
    assert test.target_list == {"a": 1, "b": 2, "c": 3}
    assert test.registered_targets == {"test_a": 1, "test_b": 2, "test_c": 3}


async def test_remove_targets(hass: HomeAssistant):
    """Test removing targets from the targets in a notify service."""
    test = LegacyNotificationService(hass)
    await test.async_setup(hass, "notify", "test")
    await test.async_register_services()
    await hass.async_block_till_done()

    assert hasattr(test, "registered_targets")
    assert test.registered_targets == {"test_a": 1, "test_b": 2}

    test.target_list = {"c": 1}
    await test.async_register_services()
    await hass.async_block_till_done()
    assert test.target_list == {"c": 1}
    assert test.registered_targets == {"test_c": 1}


class LegacyNotificationService(notify.BaseNotificationService):
    """A test class for legacy notification services."""

    def __init__(self, hass):
        """Initialize the service."""
        self.hass = hass
        self.target_list = {"a": 1, "b": 2}

    @property
    def targets(self):
        """Return a dictionary of devices."""
        return self.target_list


async def test_warn_template(hass, caplog):
    """Test warning when template used."""
    assert await async_setup_component(hass, "notify", {})

    await hass.services.async_call(
        "notify",
        "persistent_notification",
        {"message": "{{ 1 + 1 }}", "title": "Test notif {{ 1 + 1 }}"},
        blocking=True,
    )
    # We should only log it once
    assert caplog.text.count("Passing templates to notify service is deprecated") == 1
    assert hass.states.get("persistent_notification.notification") is not None


class NotificationService(notify.NotifyService):
    """A test class for notification services."""


async def test_notify_service(
    hass: HomeAssistant, enable_custom_integrations: None
) -> None:
    """Test call notify send message."""
    entry = MockConfigEntry()
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    service_platforms = async_get_platforms(hass, "test")
    assert service_platforms
    notify_platform = next(
        platform for platform in service_platforms if platform.domain == "notify"
    )
    service_name = f"{notify_platform.platform_name}_{SERVICE_NOTIFY}"
    assert notify_platform.services
    notify_service = cast(notify.NotifyService, notify_platform.services[service_name])
    notify_service.send_message = Mock()  # type: ignore[assignment]
    service_data = {
        ATTR_MESSAGE: "World",
        ATTR_TITLE: "Hello",
        ATTR_TARGET: ["target_one", "target_two"],
        ATTR_DATA: {"data_one": 1},
    }

    await hass.services.async_call(
        DOMAIN,
        service_name,
        service_data,
        blocking=True,
    )

    assert notify_service.send_message.call_count == 1
    assert notify_service.send_message.call_args == call(
        "World",
        title="Hello",
        target=["target_one", "target_two"],
        data={"data_one": 1},
    )


async def test_setup_unload_notify(
    hass: HomeAssistant, enable_custom_integrations: None
) -> None:
    """Test set up and unload the notify integration."""
    entry = MockConfigEntry()
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    service_platforms = async_get_platforms(hass, "test")
    assert service_platforms
    notify_platform = next(
        platform for platform in service_platforms if platform.domain == "notify"
    )
    service_name = f"{notify_platform.platform_name}_{SERVICE_NOTIFY}"
    assert service_name in notify_platform.services

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert not notify_platform.services
