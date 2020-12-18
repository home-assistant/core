"""Tests for the wemo component."""
import pywemo

from homeassistant.components.wemo import CONF_DISCOVERY, CONF_STATIC
from homeassistant.components.wemo.const import DOMAIN
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from .conftest import MOCK_HOST, MOCK_NAME, MOCK_PORT, MOCK_SERIAL_NUMBER

from tests.async_mock import Mock, create_autospec, patch


async def test_config_no_config(hass):
    """Component setup succeeds when there are no config entry for the domain."""
    assert await async_setup_component(hass, DOMAIN, {})


async def test_config_no_static(hass):
    """Component setup succeeds when there are no static config entries."""
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {CONF_DISCOVERY: False}})


async def test_static_duplicate_static_entry(hass, pywemo_device):
    """Duplicate static entries are merged into a single entity."""
    static_config_entry = f"{MOCK_HOST}:{MOCK_PORT}"
    assert await async_setup_component(
        hass,
        DOMAIN,
        {
            DOMAIN: {
                CONF_DISCOVERY: False,
                CONF_STATIC: [
                    static_config_entry,
                    static_config_entry,
                ],
            },
        },
    )
    await hass.async_block_till_done()
    entity_reg = await hass.helpers.entity_registry.async_get_registry()
    entity_entries = list(entity_reg.entities.values())
    assert len(entity_entries) == 1


async def test_static_config_with_port(hass, pywemo_device):
    """Static device with host and port is added and removed."""
    assert await async_setup_component(
        hass,
        DOMAIN,
        {
            DOMAIN: {
                CONF_DISCOVERY: False,
                CONF_STATIC: [f"{MOCK_HOST}:{MOCK_PORT}"],
            },
        },
    )
    await hass.async_block_till_done()
    entity_reg = await hass.helpers.entity_registry.async_get_registry()
    entity_entries = list(entity_reg.entities.values())
    assert len(entity_entries) == 1


async def test_static_config_without_port(hass, pywemo_device):
    """Static device with host and no port is added and removed."""
    assert await async_setup_component(
        hass,
        DOMAIN,
        {
            DOMAIN: {
                CONF_DISCOVERY: False,
                CONF_STATIC: [MOCK_HOST],
            },
        },
    )
    await hass.async_block_till_done()
    entity_reg = await hass.helpers.entity_registry.async_get_registry()
    entity_entries = list(entity_reg.entities.values())
    assert len(entity_entries) == 1


async def test_static_config_with_invalid_host(hass):
    """Component setup fails if a static host is invalid."""
    setup_success = await async_setup_component(
        hass,
        DOMAIN,
        {
            DOMAIN: {
                CONF_DISCOVERY: False,
                CONF_STATIC: [""],
            },
        },
    )
    assert not setup_success


async def test_discovery(hass, pywemo_registry):
    """Verify that discovery dispatches devices to the platform for setup."""

    def create_device(counter):
        """Create a unique mock Motion detector device for each counter value."""
        device = create_autospec(pywemo.Motion, instance=True)
        device.host = f"{MOCK_HOST}_{counter}"
        device.port = MOCK_PORT + counter
        device.name = f"{MOCK_NAME}_{counter}"
        device.serialnumber = f"{MOCK_SERIAL_NUMBER}_{counter}"
        device.model_name = "Motion"
        device.get_state.return_value = 0  # Default to Off
        return device

    pywemo_devices = [create_device(0), create_device(1)]
    mock_stop = Mock()
    expected_device_count = 4

    def async_call_later(hass, delay, action):
        async def async_run_action_after_platform_setup():
            """Run the 'action' after the platform has been setup.

            This forces the async_dispatcher_send logic to be tested.
            """
            await pywemo_registry.semaphore.acquire()  # Returns after platform setup.
            count = len(pywemo_devices)
            if count < expected_device_count:
                pywemo_devices.append(create_device(count))
                await action(dt_util.utcnow())

        hass.async_create_task(async_run_action_after_platform_setup())
        return mock_stop

    # Setup the component and start discovery.
    with patch(
        "pywemo.discover_devices", return_value=pywemo_devices
    ) as mock_discovery, patch(
        "homeassistant.components.wemo.async_call_later", side_effect=async_call_later
    ):
        assert await async_setup_component(
            hass, DOMAIN, {DOMAIN: {CONF_DISCOVERY: True}}
        )
        await hass.async_block_till_done()
        mock_discovery.assert_called()

    # Verify that the expected number of devices were setup.
    entity_reg = await hass.helpers.entity_registry.async_get_registry()
    entity_entries = list(entity_reg.entities.values())
    assert len(entity_entries) == expected_device_count

    # Verify that discovery stops when hass is stopped.
    await hass.async_stop()
    await hass.async_block_till_done()
    mock_stop.assert_called_once()
