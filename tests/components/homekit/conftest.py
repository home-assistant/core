"""HomeKit session fixtures."""
from contextlib import suppress
import os
from unittest.mock import patch

import pytest

from homeassistant.components.device_tracker.legacy import YAML_DEVICES
from homeassistant.components.homekit.accessories import HomeDriver
from homeassistant.components.homekit.const import BRIDGE_NAME, EVENT_HOMEKIT_CHANGED
from homeassistant.components.homekit.iidmanager import AccessoryIIDStorage

from tests.common import async_capture_events


@pytest.fixture
def iid_storage(hass):
    """Mock the iid storage."""
    with patch.object(AccessoryIIDStorage, "_async_schedule_save"):
        yield AccessoryIIDStorage(hass, "")


@pytest.fixture
def run_driver(hass, event_loop, iid_storage):
    """Return a custom AccessoryDriver instance for HomeKit accessory init.

    This mock does not mock async_stop, so the driver will not be stopped
    """
    with patch("pyhap.accessory_driver.AsyncZeroconf"), patch(
        "pyhap.accessory_driver.AccessoryEncoder"
    ), patch("pyhap.accessory_driver.HAPServer"), patch(
        "pyhap.accessory_driver.AccessoryDriver.publish"
    ), patch(
        "pyhap.accessory_driver.AccessoryDriver.persist",
    ):
        yield HomeDriver(
            hass,
            pincode=b"123-45-678",
            entry_id="",
            entry_title="mock entry",
            bridge_name=BRIDGE_NAME,
            iid_storage=iid_storage,
            address="127.0.0.1",
            loop=event_loop,
        )


@pytest.fixture
def hk_driver(hass, event_loop, iid_storage):
    """Return a custom AccessoryDriver instance for HomeKit accessory init."""
    with patch("pyhap.accessory_driver.AsyncZeroconf"), patch(
        "pyhap.accessory_driver.AccessoryEncoder"
    ), patch("pyhap.accessory_driver.HAPServer.async_stop"), patch(
        "pyhap.accessory_driver.HAPServer.async_start"
    ), patch(
        "pyhap.accessory_driver.AccessoryDriver.publish",
    ), patch(
        "pyhap.accessory_driver.AccessoryDriver.persist",
    ):
        yield HomeDriver(
            hass,
            pincode=b"123-45-678",
            entry_id="",
            entry_title="mock entry",
            bridge_name=BRIDGE_NAME,
            iid_storage=iid_storage,
            address="127.0.0.1",
            loop=event_loop,
        )


@pytest.fixture
def mock_hap(hass, event_loop, iid_storage, mock_zeroconf):
    """Return a custom AccessoryDriver instance for HomeKit accessory init."""
    with patch("pyhap.accessory_driver.AsyncZeroconf"), patch(
        "pyhap.accessory_driver.AccessoryEncoder"
    ), patch("pyhap.accessory_driver.HAPServer.async_stop"), patch(
        "pyhap.accessory_driver.HAPServer.async_start"
    ), patch(
        "pyhap.accessory_driver.AccessoryDriver.publish",
    ), patch(
        "pyhap.accessory_driver.AccessoryDriver.async_start",
    ), patch(
        "pyhap.accessory_driver.AccessoryDriver.async_stop",
    ), patch(
        "pyhap.accessory_driver.AccessoryDriver.persist",
    ):
        yield HomeDriver(
            hass,
            pincode=b"123-45-678",
            entry_id="",
            entry_title="mock entry",
            bridge_name=BRIDGE_NAME,
            iid_storage=iid_storage,
            address="127.0.0.1",
            loop=event_loop,
        )


@pytest.fixture
def events(hass):
    """Yield caught homekit_changed events."""
    return async_capture_events(hass, EVENT_HOMEKIT_CHANGED)


@pytest.fixture
def demo_cleanup(hass):
    """Clean up device tracker demo file."""
    yield
    with suppress(FileNotFoundError):
        os.remove(hass.config.path(YAML_DEVICES))
