"""The tests for notify services that change targets."""

from unittest.mock import Mock, patch

import yaml

from homeassistant import config as hass_config
from homeassistant.components import notify
from homeassistant.const import SERVICE_RELOAD
from homeassistant.core import HomeAssistant
from homeassistant.helpers.reload import async_setup_reload_service
from homeassistant.loader import DATA_INTEGRATIONS
from homeassistant.setup import async_setup_component

from tests.common import MockPlatform, mock_platform


class MockNotifyPlatform(MockPlatform):
    """Help to set up test notify service."""

    def __init__(self, async_get_service):
        """Return the notify service."""
        super().__init__()
        self.async_get_service = async_get_service


async def test_same_targets(hass: HomeAssistant):
    """Test not changing the targets in a notify service."""
    test = NotificationService(hass)
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


async def test_add_targets(hass: HomeAssistant):
    """Test adding the targets in a notify service."""
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


async def test_remove_targets(hass: HomeAssistant):
    """Test removing targets from the targets in a notify service."""
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
    """A test class for notification services."""

    def __init__(self, hass, target_list={"a": 1, "b": 2}):
        """Initialize the service."""

        async def _async_make_reloadable(hass):
            """Initialize the reload service."""
            await async_setup_reload_service(hass, "testnotify", [notify.DOMAIN])

        self.hass = hass
        self.target_list = target_list
        hass.async_create_task(_async_make_reloadable(hass))

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


async def test_setup_platform_and_reload(hass, caplog, tmp_path):
    """Test service setup and reload."""
    get_service_called = Mock()

    async def async_get_service(hass, config, discovery_info=None):
        """Get notify service for mocked platform."""
        get_service_called()
        targetlist = {"a": 1, "b": 2}
        return NotificationService(hass, targetlist)

    # Mock notify services file
    services_yaml_file = tmp_path / "services.yaml"
    services_config = yaml.dump(
        {"notify": [{"description": "My custom notify service", "fields": {}}]}
    )
    services_yaml_file.write_text(services_config)
    loaded_platform = MockNotifyPlatform(async_get_service=async_get_service)
    mock_platform(hass, "testnotify.notify", loaded_platform)
    integration = hass.data[DATA_INTEGRATIONS]["testnotify"]
    integration.file_path = tmp_path

    # Setup the platform
    await notify.async_setup(hass, {"notify": [{"platform": "testnotify"}]})
    await hass.async_block_till_done()
    assert hass.services.has_service("testnotify", SERVICE_RELOAD)
    assert hass.services.has_service(notify.DOMAIN, "testnotify_a")
    assert hass.services.has_service(notify.DOMAIN, "testnotify_b")
    assert get_service_called.call_count == 1

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
        await hass.async_block_till_done()

    # Check if the notify services still exist
    assert hass.services.has_service(notify.DOMAIN, "testnotify_a")
    assert hass.services.has_service(notify.DOMAIN, "testnotify_b")
    assert get_service_called.call_count == 2
