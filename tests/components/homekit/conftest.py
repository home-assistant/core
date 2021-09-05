"""HomeKit session fixtures."""
from contextlib import suppress
import os
from unittest.mock import patch

from pyhap.accessory_driver import AccessoryDriver
import pytest

from homeassistant.components.device_tracker.legacy import YAML_DEVICES
from homeassistant.components.homekit.const import EVENT_HOMEKIT_CHANGED

from tests.common import async_capture_events, mock_device_registry, mock_registry


@pytest.fixture
def hk_driver(loop):
    """Return a custom AccessoryDriver instance for HomeKit accessory init."""
    with patch("pyhap.accessory_driver.AsyncZeroconf"), patch(
        "pyhap.accessory_driver.AccessoryEncoder"
    ), patch("pyhap.accessory_driver.HAPServer.async_stop"), patch(
        "pyhap.accessory_driver.HAPServer.async_start"
    ), patch(
        "pyhap.accessory_driver.AccessoryDriver.publish"
    ), patch(
        "pyhap.accessory_driver.AccessoryDriver.persist"
    ):
        yield AccessoryDriver(pincode=b"123-45-678", address="127.0.0.1", loop=loop)


@pytest.fixture
def mock_hap(loop, mock_zeroconf):
    """Return a custom AccessoryDriver instance for HomeKit accessory init."""
    with patch("pyhap.accessory_driver.AsyncZeroconf"), patch(
        "pyhap.accessory_driver.AccessoryEncoder"
    ), patch("pyhap.accessory_driver.HAPServer.async_stop"), patch(
        "pyhap.accessory_driver.HAPServer.async_start"
    ), patch(
        "pyhap.accessory_driver.AccessoryDriver.publish"
    ), patch(
        "pyhap.accessory_driver.AccessoryDriver.async_start"
    ), patch(
        "pyhap.accessory_driver.AccessoryDriver.async_stop"
    ), patch(
        "pyhap.accessory_driver.AccessoryDriver.persist"
    ):
        yield AccessoryDriver(pincode=b"123-45-678", address="127.0.0.1", loop=loop)


@pytest.fixture
def events(hass):
    """Yield caught homekit_changed events."""
    return async_capture_events(hass, EVENT_HOMEKIT_CHANGED)


@pytest.fixture(name="device_reg")
def device_reg_fixture(hass):
    """Return an empty, loaded, registry."""
    return mock_device_registry(hass)


@pytest.fixture(name="entity_reg")
def entity_reg_fixture(hass):
    """Return an empty, loaded, registry."""
    return mock_registry(hass)


@pytest.fixture
def demo_cleanup(hass):
    """Clean up device tracker demo file."""
    yield
    with suppress(FileNotFoundError):
        os.remove(hass.config.path(YAML_DEVICES))
