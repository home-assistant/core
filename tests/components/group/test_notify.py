"""The tests for the notify.group platform."""

from collections.abc import Generator, Mapping
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, call, patch

import pytest

from homeassistant import config as hass_config
from homeassistant.components import notify
from homeassistant.components.group import DOMAIN, SERVICE_RELOAD
from homeassistant.components.notify import (
    ATTR_MESSAGE,
    ATTR_TITLE,
    DOMAIN as NOTIFY_DOMAIN,
    SERVICE_SEND_MESSAGE,
    NotifyEntity,
)
from homeassistant.config_entries import ConfigEntry, ConfigFlow
from homeassistant.const import (
    ATTR_ENTITY_ID,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.setup import async_setup_component

from tests.common import (
    MockConfigEntry,
    MockEntity,
    MockModule,
    MockPlatform,
    get_fixture_path,
    mock_config_flow,
    mock_integration,
    mock_platform,
    setup_test_component_platform,
)


class MockNotifyPlatform(MockPlatform):
    """Help to set up a legacy test notify platform."""

    def __init__(self, async_get_service: Any) -> None:
        """Initialize platform."""
        super().__init__()
        self.async_get_service = async_get_service


def mock_notify_platform(
    hass: HomeAssistant,
    tmp_path: Path,
    async_get_service: Any = None,
):
    """Specialize the mock platform for legacy notify service."""
    loaded_platform = MockNotifyPlatform(async_get_service)
    mock_platform(hass, "test.notify", loaded_platform)

    return loaded_platform


async def help_setup_notify(
    hass: HomeAssistant,
    tmp_path: Path,
    targets: dict[str, None] | None = None,
    group_setup: list[dict[str, None]] | None = None,
) -> MagicMock:
    """Help set up a platform notify service."""
    send_message_mock = MagicMock()

    class _TestNotifyService(notify.BaseNotificationService):
        def __init__(self, targets: dict[str, None] | None) -> None:
            """Initialize service."""
            self._targets = targets
            super().__init__()

        @property
        def targets(self) -> Mapping[str, Any] | None:
            """Return a dictionary of registered targets."""
            return self._targets

        def send_message(self, message: str, **kwargs: Any) -> None:
            """Send a message."""
            send_message_mock(message, kwargs)

    async def async_get_service(
        hass: HomeAssistant,
        config: ConfigType,
        discovery_info: DiscoveryInfoType | None = None,
    ) -> notify.BaseNotificationService:
        """Get notify service for mocked platform."""
        return _TestNotifyService(targets)

    # Mock platform with service
    mock_notify_platform(hass, tmp_path, async_get_service=async_get_service)
    # Setup the platform
    items: list[dict[str, Any]] = [{"platform": "test"}]
    items.extend(group_setup or [])
    await async_setup_component(hass, "notify", {"notify": items})
    await hass.async_block_till_done()

    # Return mock for assertion service calls
    return send_message_mock


async def test_send_message_with_data(hass: HomeAssistant, tmp_path: Path) -> None:
    """Test sending a message with to a notify group."""
    assert await async_setup_component(
        hass,
        "group",
        {},
    )
    await hass.async_block_till_done()

    group_setup = [
        {
            "platform": "group",
            "name": "My notification group",
            "services": [
                {"service": "test_service1"},
                {
                    "action": "test_service2",
                    "data": {
                        "target": "unnamed device",
                        "data": {"test": "message", "default": "default"},
                    },
                },
            ],
        }
    ]
    send_message_mock = await help_setup_notify(
        hass, tmp_path, {"service1": 1, "service2": 2}, group_setup
    )
    assert hass.services.has_service("notify", "my_notification_group")

    # Test sending a message to a notify group.
    await hass.services.async_call(
        "notify",
        "my_notification_group",
        {"message": "Hello", "title": "Test notification", "data": {"hello": "world"}},
        blocking=True,
    )
    send_message_mock.assert_has_calls(
        [
            call(
                "Hello",
                {
                    "title": "Test notification",
                    "target": [1],
                    "data": {"hello": "world"},
                },
            ),
            call(
                "Hello",
                {
                    "title": "Test notification",
                    "target": [2],
                    "data": {"hello": "world", "test": "message", "default": "default"},
                },
            ),
        ]
    )
    send_message_mock.reset_mock()

    # Test sending a message which overrides service defaults to a notify group
    await hass.services.async_call(
        "notify",
        "my_notification_group",
        {
            "message": "Hello",
            "title": "Test notification",
            "data": {"hello": "world", "default": "override"},
        },
        blocking=True,
    )
    send_message_mock.assert_has_calls(
        [
            call(
                "Hello",
                {
                    "title": "Test notification",
                    "target": [1],
                    "data": {"hello": "world", "default": "override"},
                },
            ),
            call(
                "Hello",
                {
                    "title": "Test notification",
                    "target": [2],
                    "data": {
                        "hello": "world",
                        "test": "message",
                        "default": "override",
                    },
                },
            ),
        ]
    )


async def test_invalid_configuration(
    hass: HomeAssistant, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Test failing to set up group with an invalid configuration."""
    assert await async_setup_component(
        hass,
        "group",
        {},
    )
    await hass.async_block_till_done()

    group_setup = [
        {
            "platform": "group",
            "name": "My invalid notification group",
            "services": [
                {
                    "service": "test_service1",
                    "action": "test_service2",
                    "data": {
                        "target": "unnamed device",
                        "data": {"test": "message", "default": "default"},
                    },
                },
            ],
        }
    ]
    await help_setup_notify(hass, tmp_path, {"service1": 1, "service2": 2}, group_setup)
    assert not hass.services.has_service("notify", "my_invalid_notification_group")
    assert (
        "Invalid config for 'notify' from integration 'group':"
        " Cannot specify both 'service' and 'action'." in caplog.text
    )


async def test_reload_notify(hass: HomeAssistant, tmp_path: Path) -> None:
    """Verify we can reload the notify service."""
    assert await async_setup_component(
        hass,
        "group",
        {},
    )
    await hass.async_block_till_done()

    await help_setup_notify(
        hass,
        tmp_path,
        {"service1": 1, "service2": 2},
        [
            {
                "name": "group_notify",
                "platform": "group",
                "services": [{"action": "test_service1"}],
            }
        ],
    )

    assert hass.services.has_service(notify.DOMAIN, "test_service1")
    assert hass.services.has_service(notify.DOMAIN, "test_service2")
    assert hass.services.has_service(notify.DOMAIN, "group_notify")

    yaml_path = get_fixture_path("configuration.yaml", "group")

    with patch.object(hass_config, "YAML_CONFIG_FILE", yaml_path):
        await hass.services.async_call(
            "group",
            SERVICE_RELOAD,
            {},
            blocking=True,
        )
        await hass.async_block_till_done()

    assert hass.services.has_service(notify.DOMAIN, "test_service1")
    assert hass.services.has_service(notify.DOMAIN, "test_service2")
    assert not hass.services.has_service(notify.DOMAIN, "group_notify")
    assert hass.services.has_service(notify.DOMAIN, "new_group_notify")


class MockFlow(ConfigFlow):
    """Test flow."""


@pytest.fixture
def config_flow_fixture(hass: HomeAssistant) -> Generator[None]:
    """Mock config flow."""
    mock_platform(hass, "test.config_flow")

    with mock_config_flow("test", MockFlow):
        yield


class MockNotifyEntity(MockEntity, NotifyEntity):
    """Mock Email notifier entity to use in tests."""

    def __init__(self, **values: Any) -> None:
        """Initialize the mock entity."""
        super().__init__(**values)
        self.send_message_mock_calls = MagicMock()

    async def async_send_message(self, message: str, title: str | None = None) -> None:
        """Send a notification message."""
        self.send_message_mock_calls(message, title=title)


async def help_async_setup_entry_init(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> bool:
    """Set up test config entry."""
    await hass.config_entries.async_forward_entry_setups(
        config_entry, [Platform.NOTIFY]
    )
    return True


async def help_async_unload_entry(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> bool:
    """Unload test config entry."""
    return await hass.config_entries.async_unload_platforms(
        config_entry, [Platform.NOTIFY]
    )


@pytest.fixture
async def mock_notifiers(
    hass: HomeAssistant, config_flow_fixture: None
) -> list[NotifyEntity]:
    """Set up the notify entities."""
    entity = MockNotifyEntity(name="test", entity_id="notify.test")
    entity2 = MockNotifyEntity(name="test2", entity_id="notify.test2")
    entities = [entity, entity2]
    test_entry = MockConfigEntry(domain="test")
    test_entry.add_to_hass(hass)
    mock_integration(
        hass,
        MockModule(
            "test",
            async_setup_entry=help_async_setup_entry_init,
            async_unload_entry=help_async_unload_entry,
        ),
    )
    setup_test_component_platform(hass, NOTIFY_DOMAIN, entities, from_config_entry=True)
    assert await hass.config_entries.async_setup(test_entry.entry_id)
    await hass.async_block_till_done()
    return entities


async def test_notify_entity_group(
    hass: HomeAssistant, mock_notifiers: list[NotifyEntity]
) -> None:
    """Test sending a message to a notify group."""
    entity, entity2 = mock_notifiers
    assert entity.send_message_mock_calls.call_count == 0
    assert entity2.send_message_mock_calls.call_count == 0

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        options={
            "group_type": "notify",
            "name": "Test Group",
            "entities": ["notify.test", "notify.test2"],
            "hide_members": True,
        },
        title="Test Group",
    )
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        NOTIFY_DOMAIN,
        SERVICE_SEND_MESSAGE,
        {
            ATTR_MESSAGE: "Hello",
            ATTR_TITLE: "Test notification",
            ATTR_ENTITY_ID: "notify.test_group",
        },
        blocking=True,
    )

    assert entity.send_message_mock_calls.call_count == 1
    assert entity.send_message_mock_calls.call_args == call(
        "Hello", title="Test notification"
    )
    assert entity2.send_message_mock_calls.call_count == 1
    assert entity2.send_message_mock_calls.call_args == call(
        "Hello", title="Test notification"
    )


async def test_state_reporting(hass: HomeAssistant) -> None:
    """Test sending a message to a notify group."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        options={
            "group_type": "notify",
            "name": "Test Group",
            "entities": ["notify.test", "notify.test2"],
            "hide_members": True,
        },
        title="Test Group",
    )
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("notify.test_group").state == STATE_UNAVAILABLE

    hass.states.async_set("notify.test", STATE_UNAVAILABLE)
    hass.states.async_set("notify.test2", STATE_UNAVAILABLE)
    await hass.async_block_till_done()
    assert hass.states.get("notify.test_group").state == STATE_UNAVAILABLE

    hass.states.async_set("notify.test", "2021-01-01T23:59:59.123+00:00")
    hass.states.async_set("notify.test2", "2021-01-01T23:59:59.123+00:00")
    await hass.async_block_till_done()
    assert hass.states.get("notify.test_group").state == STATE_UNKNOWN
