"""The tests for notify services that change targets."""

from unittest.mock import Mock, patch

import yaml

from homeassistant import config as hass_config
from homeassistant.components import notify
from homeassistant.const import SERVICE_RELOAD
from homeassistant.core import HomeAssistant
from homeassistant.helpers.discovery import async_load_platform
from homeassistant.helpers.reload import async_setup_reload_service
from homeassistant.loader import DATA_INTEGRATIONS
from homeassistant.setup import async_setup_component

from tests.common import MockPlatform, mock_platform


class MockNotifyPlatform(MockPlatform):
    """Help to set up test notify service."""

    def __init__(self, async_get_service=None):
        """Return the notify service."""
        super().__init__()
        if not async_get_service:
            return
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

    def __init__(self, hass, target_list={"a": 1, "b": 2}, name="notify"):
        """Initialize the service."""

        async def _async_make_reloadable(hass):
            """Initialize the reload service."""
            await async_setup_reload_service(hass, name, [notify.DOMAIN])

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


async def test_invalid_platform(hass, caplog, tmp_path):
    """Test service setup with an invalid platform."""
    loaded_platform = MockNotifyPlatform()
    mock_platform(hass, "testnotify.notify", loaded_platform)
    integration = hass.data[DATA_INTEGRATIONS]["testnotify"]
    integration.file_path = tmp_path
    # Setup the second testnotify2 platform dynamically
    await async_load_platform(
        hass,
        "notify",
        "testnotify",
        {"notify": [{"platform": "testnotify"}]},
        hass_config={"notify": [{"platform": "testnotify"}]},
    )
    await hass.async_block_till_done()
    assert "Invalid notify platform" in caplog.text


async def test_invalid_service(hass, caplog, tmp_path):
    """Test service setup with an invalid service object or platform."""

    async def async_get_service(hass, config, discovery_info=None):
        """Return None for an invalid notify service."""
        return None

    loaded_platform = MockNotifyPlatform(async_get_service=async_get_service)
    mock_platform(hass, "testnotify.notify", loaded_platform)
    integration = hass.data[DATA_INTEGRATIONS]["testnotify"]
    integration.file_path = tmp_path
    # Setup the second testnotify2 platform dynamically
    await async_load_platform(
        hass,
        "notify",
        "testnotify",
        {"notify": [{"platform": "testnotify"}]},
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


async def test_platform_setup_with_error(hass, caplog, tmp_path):
    """Test service setup with an invalid setup."""

    async def async_get_service(hass, config, discovery_info=None):
        """Return None for an invalid notify service."""
        raise Exception("Setup error")

    loaded_platform = MockNotifyPlatform(async_get_service=async_get_service)
    mock_platform(hass, "testnotify.notify", loaded_platform)
    integration = hass.data[DATA_INTEGRATIONS]["testnotify"]
    integration.file_path = tmp_path
    # Setup the second testnotify2 platform dynamically
    await async_load_platform(
        hass,
        "notify",
        "testnotify",
        {"notify": [{"platform": "testnotify"}]},
        hass_config={"notify": [{"platform": "testnotify"}]},
    )
    await hass.async_block_till_done()
    assert "Error setting up platform testnotify" in caplog.text


async def test_setup_platform_and_reload(hass, caplog, tmp_path):
    """Test service setup and reload."""
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

    # Initialize a second platform
    loaded_platform2 = MockNotifyPlatform(async_get_service=async_get_service2)
    mock_platform(hass, "testnotify2.notify", loaded_platform2)

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
        {"notify": [{"platform": "testnotify2"}]},
        hass_config={"notify": [{"platform": "testnotify"}]},
    )
    await hass.async_block_till_done()
    assert hass.services.has_service("testnotify2", SERVICE_RELOAD)
    assert hass.services.has_service(notify.DOMAIN, "testnotify2_c")
    assert hass.services.has_service(notify.DOMAIN, "testnotify2_d")
    assert get_service_called.call_count == 1
    assert get_service_called.call_args[0][0] == {}
    assert get_service_called.call_args[0][1] == {
        "notify": [{"platform": "testnotify2"}]
    }
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
