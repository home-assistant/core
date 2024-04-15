"""The tests for the notify.group platform."""

from collections.abc import Mapping
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, call, patch

from homeassistant import config as hass_config
from homeassistant.components import notify
from homeassistant.components.group import SERVICE_RELOAD
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.setup import async_setup_component

from tests.common import MockPlatform, get_fixture_path, mock_platform


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
                    "service": "test_service2",
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
                "services": [{"service": "test_service1"}],
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
