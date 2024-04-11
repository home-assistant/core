"""The tests for notify services that change targets."""

import asyncio
import copy
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, Mock, patch

import pytest
import yaml

from homeassistant import config as hass_config
from homeassistant.components import notify
from homeassistant.components.notify import (
    DOMAIN,
    SERVICE_SEND_MESSAGE,
    NotifyEntity,
    NotifyEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    SERVICE_RELOAD,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers.discovery import async_load_platform
from homeassistant.helpers.reload import async_setup_reload_service
from homeassistant.setup import async_setup_component

from tests.common import (
    MockConfigEntry,
    MockEntity,
    MockModule,
    MockPlatform,
    async_get_persistent_notifications,
    mock_integration,
    mock_platform,
    mock_restore_cache,
    setup_test_component_platform,
)

TEST_KWARGS = {"message": "Test message"}


class MockNotifyEntity(MockEntity, NotifyEntity):
    """Mock Email notitier entity to use in tests."""

    send_message_mock_calls = MagicMock()

    async def async_send_message(self, message: str) -> None:
        """Send a notification message."""
        self.send_message_mock_calls(message=message)


class MockNotifyEntityNonAsync(MockEntity, NotifyEntity):
    """Mock Email notitier entity to use in tests."""

    send_message_mock_calls = MagicMock()

    def send_message(self, message: str) -> None:
        """Send a notification message."""
        self.send_message_mock_calls(message=message)


async def help_async_setup_entry_init(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> bool:
    """Set up test config entry."""
    await hass.config_entries.async_forward_entry_setup(config_entry, DOMAIN)
    return True


async def help_async_unload_entry(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> bool:
    """Unload test config emntry."""
    return await hass.config_entries.async_unload_platforms(
        config_entry, [Platform.NOTIFY]
    )


@pytest.mark.parametrize(
    "entity",
    [
        MockNotifyEntityNonAsync(name="test", entity_id="notify.test"),
        MockNotifyEntity(name="test", entity_id="notify.test"),
    ],
    ids=["non_async", "async"],
)
async def test_send_message_service(
    hass: HomeAssistant, config_flow_fixture: None, entity: NotifyEntity
) -> None:
    """Test send_message service."""

    config_entry = MockConfigEntry(domain="test")
    config_entry.add_to_hass(hass)

    mock_integration(
        hass,
        MockModule(
            "test",
            async_setup_entry=help_async_setup_entry_init,
            async_unload_entry=help_async_unload_entry,
        ),
    )
    setup_test_component_platform(hass, DOMAIN, [entity], from_config_entry=True)
    assert await hass.config_entries.async_setup(config_entry.entry_id)

    state = hass.states.get("notify.test")
    assert state.state is STATE_UNKNOWN

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SEND_MESSAGE,
        copy.deepcopy(TEST_KWARGS) | {"entity_id": "notify.test"},
        blocking=True,
    )
    await hass.async_block_till_done()

    entity.send_message_mock_calls.assert_called_once()

    # Test unloading the entry succeeds
    assert await hass.config_entries.async_unload(config_entry.entry_id)


@pytest.mark.parametrize(
    ("state", "init_state"),
    [
        ("2021-01-01T23:59:59+00:00", "2021-01-01T23:59:59+00:00"),
        (STATE_UNAVAILABLE, STATE_UNKNOWN),
    ],
)
async def test_restore_state(
    hass: HomeAssistant, config_flow_fixture: None, state: str, init_state: str
) -> None:
    """Test we restore state integration."""
    mock_restore_cache(hass, (State("notify.test", state),))

    mock_integration(
        hass,
        MockModule(
            "test",
            async_setup_entry=help_async_setup_entry_init,
        ),
    )

    entity = MockNotifyEntity(name="test", entity_id="notify.test")
    setup_test_component_platform(hass, DOMAIN, [entity], from_config_entry=True)

    config_entry = MockConfigEntry(domain="test")
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)

    state = hass.states.get("notify.test")
    assert state is not None
    assert state.state is init_state


async def test_name(hass: HomeAssistant, config_flow_fixture: None) -> None:
    """Test notify name."""

    mock_platform(hass, "test.config_flow")
    mock_integration(
        hass,
        MockModule(
            "test",
            async_setup_entry=help_async_setup_entry_init,
        ),
    )

    # Unnamed notify entity -> no name
    entity1 = NotifyEntity()
    entity1.entity_id = "notify.test1"

    # Unnamed notify entity and has_entity_name True -> unnamed
    entity2 = NotifyEntity()
    entity2.entity_id = "notify.test3"
    entity2._attr_has_entity_name = True

    # Named notify entity and has_entity_name True -> named
    entity3 = NotifyEntity()
    entity3.entity_id = "notify.test4"
    entity3.entity_description = NotifyEntityDescription("test", has_entity_name=True)

    setup_test_component_platform(
        hass, DOMAIN, [entity1, entity2, entity3], from_config_entry=True
    )

    config_entry = MockConfigEntry(domain="test")
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(entity1.entity_id)
    assert state
    assert state.attributes == {}

    state = hass.states.get(entity2.entity_id)
    assert state
    assert state.attributes == {}

    state = hass.states.get(entity3.entity_id)
    assert state
    assert state.attributes == {}


class MockNotifyPlatform(MockPlatform):
    """Help to set up a legacy test notify service."""

    def __init__(self, async_get_service: Any = None, get_service: Any = None) -> None:
        """Return a legacy notify service."""
        super().__init__()
        if get_service:
            self.get_service = get_service
        if async_get_service:
            self.async_get_service = async_get_service


def mock_notify_platform(
    hass: HomeAssistant,
    tmp_path: Path,
    integration: str = "notify",
    async_get_service: Any = None,
    get_service: Any = None,
):
    """Specialize the mock platform for legacy notify service."""
    loaded_platform = MockNotifyPlatform(async_get_service, get_service)
    mock_platform(hass, f"{integration}.notify", loaded_platform)

    return loaded_platform


async def test_same_targets(hass: HomeAssistant) -> None:
    """Test not changing the targets in a legacy notify service."""
    test = NotificationService(hass)
    await test.async_setup(hass, "notify", "test")
    await test.async_register_services()
    await hass.async_block_till_done()

    assert hasattr(test, "registered_targets")
    assert test.registered_targets == {"test_a": 1, "test_b": 2}

    await test.async_register_services()
    await hass.async_block_till_done()
    assert test.registered_targets == {"test_a": 1, "test_b": 2}


async def test_change_targets(hass: HomeAssistant) -> None:
    """Test changing the targets in a legacy notify service."""
    test = NotificationService(hass)
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


async def test_add_targets(hass: HomeAssistant) -> None:
    """Test adding the targets in a legacy notify service."""
    test = NotificationService(hass)
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


async def test_remove_targets(hass: HomeAssistant) -> None:
    """Test removing targets from the targets in a legacy notify service."""
    test = NotificationService(hass)
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


class NotificationService(notify.BaseNotificationService):
    """A test class for legacy notification services."""

    def __init__(
        self,
        hass: HomeAssistant,
        target_list: dict[str, Any] | None = None,
        name="notify",
    ) -> None:
        """Initialize the service."""

        async def _async_make_reloadable(hass: HomeAssistant) -> None:
            """Initialize the reload service."""
            await async_setup_reload_service(hass, name, [notify.DOMAIN])

        self.hass = hass
        self.target_list = target_list or {"a": 1, "b": 2}
        hass.async_create_task(_async_make_reloadable(hass))

    @property
    def targets(self):
        """Return a dictionary of devices."""
        return self.target_list


async def test_warn_template(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
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
    notifications = async_get_persistent_notifications(hass)
    assert len(notifications) == 1


async def test_invalid_platform(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, tmp_path: Path
) -> None:
    """Test service setup with an invalid platform."""
    mock_notify_platform(hass, tmp_path, "testnotify1")
    # Setup the platform
    await async_setup_component(
        hass, "notify", {"notify": [{"platform": "testnotify1"}]}
    )
    await hass.async_block_till_done()
    assert "Invalid notify platform" in caplog.text
    caplog.clear()
    # Setup the second testnotify2 platform dynamically
    mock_notify_platform(hass, tmp_path, "testnotify2")
    await async_load_platform(
        hass,
        "notify",
        "testnotify2",
        {},
        hass_config={"notify": [{"platform": "testnotify2"}]},
    )
    await hass.async_block_till_done()
    assert "Invalid notify platform" in caplog.text


async def test_invalid_service(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, tmp_path: Path
) -> None:
    """Test service setup with an invalid service object or platform."""

    def get_service(hass, config, discovery_info=None):
        """Return None for an invalid notify service."""
        return None

    mock_notify_platform(hass, tmp_path, "testnotify", get_service=get_service)
    # Setup the second testnotify2 platform dynamically
    await async_load_platform(
        hass,
        "notify",
        "testnotify",
        {},
        hass_config={"notify": [{"platform": "testnotify"}]},
    )
    await hass.async_block_till_done()
    assert "Failed to initialize notification service testnotify" in caplog.text
    caplog.clear()

    await async_load_platform(
        hass,
        "notify",
        "testnotifyinvalid",
        {"notify": [{"platform": "testnotifyinvalid"}]},
        hass_config={"notify": [{"platform": "testnotifyinvalid"}]},
    )
    await hass.async_block_till_done()
    assert "Unknown notification service specified" in caplog.text


async def test_platform_setup_with_error(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, tmp_path: Path
) -> None:
    """Test service setup with an invalid setup."""

    async def async_get_service(hass, config, discovery_info=None):
        """Return None for an invalid notify service."""
        raise Exception("Setup error")

    mock_notify_platform(
        hass, tmp_path, "testnotify", async_get_service=async_get_service
    )
    # Setup the second testnotify2 platform dynamically
    await async_load_platform(
        hass,
        "notify",
        "testnotify",
        {},
        hass_config={"notify": [{"platform": "testnotify"}]},
    )
    await hass.async_block_till_done()
    assert "Error setting up platform testnotify" in caplog.text


async def test_reload_with_notify_builtin_platform_reload(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, tmp_path: Path
) -> None:
    """Test reload using the legacy notify platform reload method."""

    async def async_get_service(hass, config, discovery_info=None):
        """Get notify service for mocked platform."""
        targetlist = {"a": 1, "b": 2}
        return NotificationService(hass, targetlist, "testnotify")

    # platform with service
    mock_notify_platform(
        hass, tmp_path, "testnotify", async_get_service=async_get_service
    )

    # Perform a reload using the notify module for testnotify (without services)
    await notify.async_reload(hass, "testnotify")

    # Setup the platform
    await async_setup_component(
        hass, "notify", {"notify": [{"platform": "testnotify"}]}
    )
    await hass.async_block_till_done()
    assert hass.services.has_service(notify.DOMAIN, "testnotify_a")
    assert hass.services.has_service(notify.DOMAIN, "testnotify_b")

    # Perform a reload using the notify module for testnotify (with services)
    await notify.async_reload(hass, "testnotify")
    assert hass.services.has_service(notify.DOMAIN, "testnotify_a")
    assert hass.services.has_service(notify.DOMAIN, "testnotify_b")


async def test_setup_platform_and_reload(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, tmp_path: Path
) -> None:
    """Test service setup and reload."""
    get_service_called = Mock()

    async def async_get_service(hass, config, discovery_info=None):
        """Get notify service for mocked platform."""
        get_service_called(config, discovery_info)
        targetlist = {"a": 1, "b": 2}
        return NotificationService(hass, targetlist, "testnotify")

    async def async_get_service2(hass, config, discovery_info=None):
        """Get legacy notify service for mocked platform."""
        get_service_called(config, discovery_info)
        targetlist = {"c": 3, "d": 4}
        return NotificationService(hass, targetlist, "testnotify2")

    # Mock first platform
    mock_notify_platform(
        hass, tmp_path, "testnotify", async_get_service=async_get_service
    )

    # Initialize a second platform testnotify2
    mock_notify_platform(
        hass, tmp_path, "testnotify2", async_get_service=async_get_service2
    )

    # Setup the testnotify platform
    await async_setup_component(
        hass, "notify", {"notify": [{"platform": "testnotify"}]}
    )
    await hass.async_block_till_done()
    assert hass.services.has_service("testnotify", SERVICE_RELOAD)
    assert hass.services.has_service(notify.DOMAIN, "testnotify_a")
    assert hass.services.has_service(notify.DOMAIN, "testnotify_b")
    assert get_service_called.call_count == 1
    assert get_service_called.call_args[0][0] == {"platform": "testnotify"}
    assert get_service_called.call_args[0][1] is None
    get_service_called.reset_mock()

    # Setup the second testnotify2 platform dynamically
    await async_load_platform(
        hass,
        "notify",
        "testnotify2",
        {},
        hass_config={"notify": [{"platform": "testnotify"}]},
    )
    await hass.async_block_till_done()
    assert hass.services.has_service("testnotify2", SERVICE_RELOAD)
    assert hass.services.has_service(notify.DOMAIN, "testnotify2_c")
    assert hass.services.has_service(notify.DOMAIN, "testnotify2_d")
    assert get_service_called.call_count == 1
    assert get_service_called.call_args[0][0] == {}
    assert get_service_called.call_args[0][1] == {}
    get_service_called.reset_mock()

    # Perform a reload
    new_yaml_config_file = tmp_path / "configuration.yaml"
    new_yaml_config = yaml.dump({"notify": [{"platform": "testnotify"}]})
    new_yaml_config_file.write_text(new_yaml_config)

    with patch.object(hass_config, "YAML_CONFIG_FILE", new_yaml_config_file):
        await hass.services.async_call(
            "testnotify",
            SERVICE_RELOAD,
            {},
            blocking=True,
        )
        await hass.services.async_call(
            "testnotify2",
            SERVICE_RELOAD,
            {},
            blocking=True,
        )
        await hass.async_block_till_done()

    # Check if the notify services from setup still exist
    assert hass.services.has_service(notify.DOMAIN, "testnotify_a")
    assert hass.services.has_service(notify.DOMAIN, "testnotify_b")
    assert get_service_called.call_count == 1
    assert get_service_called.call_args[0][0] == {"platform": "testnotify"}
    assert get_service_called.call_args[0][1] is None

    # Check if the dynamically notify services from setup were removed
    assert not hass.services.has_service(notify.DOMAIN, "testnotify2_c")
    assert not hass.services.has_service(notify.DOMAIN, "testnotify2_d")


async def test_setup_platform_before_notify_setup(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, tmp_path: Path
) -> None:
    """Test trying to setup a platform before legacy notify service is setup."""
    get_service_called = Mock()

    async def async_get_service(hass, config, discovery_info=None):
        """Get notify service for mocked platform."""
        get_service_called(config, discovery_info)
        targetlist = {"a": 1, "b": 2}
        return NotificationService(hass, targetlist, "testnotify")

    async def async_get_service2(hass, config, discovery_info=None):
        """Get notify service for mocked platform."""
        get_service_called(config, discovery_info)
        targetlist = {"c": 3, "d": 4}
        return NotificationService(hass, targetlist, "testnotify2")

    # Mock first platform
    mock_notify_platform(
        hass, tmp_path, "testnotify", async_get_service=async_get_service
    )

    # Initialize a second platform testnotify2
    mock_notify_platform(
        hass, tmp_path, "testnotify2", async_get_service=async_get_service2
    )

    hass_config = {"notify": [{"platform": "testnotify"}]}

    # Setup the second testnotify2 platform from discovery
    load_coro = async_load_platform(
        hass, Platform.NOTIFY, "testnotify2", {}, hass_config=hass_config
    )

    # Setup the testnotify platform
    setup_coro = async_setup_component(hass, "notify", hass_config)

    load_task = asyncio.create_task(load_coro)
    setup_task = asyncio.create_task(setup_coro)

    await asyncio.gather(load_task, setup_task)

    await hass.async_block_till_done()
    assert hass.services.has_service(notify.DOMAIN, "testnotify_a")
    assert hass.services.has_service(notify.DOMAIN, "testnotify_b")
    assert hass.services.has_service(notify.DOMAIN, "testnotify2_c")
    assert hass.services.has_service(notify.DOMAIN, "testnotify2_d")


async def test_setup_platform_after_notify_setup(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, tmp_path: Path
) -> None:
    """Test trying to setup a platform after legacy notify service is set up."""
    get_service_called = Mock()

    async def async_get_service(hass, config, discovery_info=None):
        """Get notify service for mocked platform."""
        get_service_called(config, discovery_info)
        targetlist = {"a": 1, "b": 2}
        return NotificationService(hass, targetlist, "testnotify")

    async def async_get_service2(hass, config, discovery_info=None):
        """Get notify service for mocked platform."""
        get_service_called(config, discovery_info)
        targetlist = {"c": 3, "d": 4}
        return NotificationService(hass, targetlist, "testnotify2")

    # Mock first platform
    mock_notify_platform(
        hass, tmp_path, "testnotify", async_get_service=async_get_service
    )

    # Initialize a second platform testnotify2
    mock_notify_platform(
        hass, tmp_path, "testnotify2", async_get_service=async_get_service2
    )

    hass_config = {"notify": [{"platform": "testnotify"}]}

    # Setup the second testnotify2 platform from discovery
    load_coro = async_load_platform(
        hass, Platform.NOTIFY, "testnotify2", {}, hass_config=hass_config
    )

    # Setup the testnotify platform
    setup_coro = async_setup_component(hass, "notify", hass_config)

    setup_task = asyncio.create_task(setup_coro)
    load_task = asyncio.create_task(load_coro)

    await asyncio.gather(load_task, setup_task)

    await hass.async_block_till_done()
    assert hass.services.has_service(notify.DOMAIN, "testnotify_a")
    assert hass.services.has_service(notify.DOMAIN, "testnotify_b")
    assert hass.services.has_service(notify.DOMAIN, "testnotify2_c")
    assert hass.services.has_service(notify.DOMAIN, "testnotify2_d")
