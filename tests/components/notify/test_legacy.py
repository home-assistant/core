"""The tests for legacy notify services."""

from collections.abc import Mapping
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
import voluptuous as vol

from homeassistant.components import notify
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.setup import async_setup_component

from tests.common import MockPlatform, mock_platform


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


async def help_setup_notify(
    hass: HomeAssistant, tmp_path: Path, targets: dict[str, None] | None = None
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
    mock_notify_platform(hass, tmp_path, "test", async_get_service=async_get_service)
    # Setup the platform
    await async_setup_component(hass, "notify", {"notify": [{"platform": "test"}]})
    await hass.async_block_till_done()

    # Return mock for assertion service calls
    return send_message_mock


async def test_sending_none_message(hass: HomeAssistant, tmp_path: Path) -> None:
    """Test send with None as message."""
    send_message_mock = await help_setup_notify(hass, tmp_path)
    with pytest.raises(vol.Invalid) as exc:
        await hass.services.async_call(
            notify.DOMAIN, notify.SERVICE_NOTIFY, {notify.ATTR_MESSAGE: None}
        )
        await hass.async_block_till_done()
    assert (
        str(exc.value)
        == "template value is None for dictionary value @ data['message']"
    )
    send_message_mock.assert_not_called()


async def test_sending_templated_message(hass: HomeAssistant, tmp_path: Path) -> None:
    """Send a templated message."""
    send_message_mock = await help_setup_notify(hass, tmp_path)
    hass.states.async_set("sensor.temperature", 10)
    data = {
        notify.ATTR_MESSAGE: "{{states.sensor.temperature.state}}",
        notify.ATTR_TITLE: "{{ states.sensor.temperature.name }}",
    }
    await hass.services.async_call(notify.DOMAIN, notify.SERVICE_NOTIFY, data)
    await hass.async_block_till_done()
    send_message_mock.assert_called_once_with(
        "10", {"title": "temperature", "data": None}
    )


async def test_method_forwards_correct_data(
    hass: HomeAssistant, tmp_path: Path
) -> None:
    """Test that all data from the service gets forwarded to service."""
    send_message_mock = await help_setup_notify(hass, tmp_path)
    data = {
        notify.ATTR_MESSAGE: "my message",
        notify.ATTR_TITLE: "my title",
        notify.ATTR_DATA: {"hello": "world"},
    }
    await hass.services.async_call(notify.DOMAIN, notify.SERVICE_NOTIFY, data)
    await hass.async_block_till_done()
    send_message_mock.assert_called_once_with(
        "my message", {"title": "my title", "data": {"hello": "world"}}
    )


async def test_calling_notify_from_script_loaded_from_yaml_without_title(
    hass: HomeAssistant, tmp_path: Path
) -> None:
    """Test if we can call a notify from a script."""
    send_message_mock = await help_setup_notify(hass, tmp_path)
    step = {
        "service": "notify.notify",
        "data": {
            "data": {"push": {"sound": "US-EN-Morgan-Freeman-Roommate-Is-Arriving.wav"}}
        },
        "data_template": {"message": "Test 123 {{ 2 + 2 }}\n"},
    }
    await async_setup_component(
        hass, "script", {"script": {"test": {"sequence": step}}}
    )
    await hass.services.async_call("script", "test")
    await hass.async_block_till_done()
    send_message_mock.assert_called_once_with(
        "Test 123 4",
        {"data": {"push": {"sound": "US-EN-Morgan-Freeman-Roommate-Is-Arriving.wav"}}},
    )


async def test_calling_notify_from_script_loaded_from_yaml_with_title(
    hass: HomeAssistant, tmp_path: Path
) -> None:
    """Test if we can call a notify from a script."""
    send_message_mock = await help_setup_notify(hass, tmp_path)
    step = {
        "service": "notify.notify",
        "data": {
            "data": {"push": {"sound": "US-EN-Morgan-Freeman-Roommate-Is-Arriving.wav"}}
        },
        "data_template": {"message": "Test 123 {{ 2 + 2 }}\n", "title": "Test"},
    }
    await async_setup_component(
        hass, "script", {"script": {"test": {"sequence": step}}}
    )
    await hass.services.async_call("script", "test")
    await hass.async_block_till_done()
    send_message_mock.assert_called_once_with(
        "Test 123 4",
        {
            "title": "Test",
            "data": {
                "push": {"sound": "US-EN-Morgan-Freeman-Roommate-Is-Arriving.wav"}
            },
        },
    )


async def test_targets_are_services(hass: HomeAssistant, tmp_path: Path) -> None:
    """Test that all targets are exposed as individual services."""
    await help_setup_notify(hass, tmp_path, targets={"a": 1, "b": 2})
    assert hass.services.has_service("notify", "notify") is not None
    assert hass.services.has_service("notify", "test_a") is not None
    assert hass.services.has_service("notify", "test_b") is not None


async def test_messages_to_targets_route(hass: HomeAssistant, tmp_path: Path) -> None:
    """Test message routing to specific target services."""
    send_message_mock = await help_setup_notify(
        hass, tmp_path, targets={"target_name": "test target id"}
    )

    await hass.services.async_call(
        "notify",
        "test_target_name",
        {"message": "my message", "title": "my title", "data": {"hello": "world"}},
    )
    await hass.async_block_till_done()

    send_message_mock.assert_called_once_with(
        "my message",
        {"target": ["test target id"], "title": "my title", "data": {"hello": "world"}},
    )
