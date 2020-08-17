"""Fixtures for pywemo."""
import asynctest
import pytest
import pywemo


@pytest.fixture
def pywemo_device(request):
    """Fixture for WeMoDevice instances."""
    device_model = getattr(request.cls, "DEVICE_MODEL")
    device = asynctest.create_autospec(getattr(pywemo, device_model))
    device.host = "localhost"
    device.port = 0
    device.name = request.cls.DEVICE_NAME
    device.serialnumber = request.cls.DEVICE_SERIAL_NUMBER
    device.model_name = request.cls.DEVICE_MODEL
    return device


@pytest.fixture
def pywemo_bridge_light(request):
    """Fixture for Bridge Light instances."""
    light = asynctest.create_autospec(pywemo.ouimeaux_device.bridge.Light)
    light.name = request.cls.DEVICE_NAME
    light.uniqueID = request.cls.DEVICE_SERIAL_NUMBER
    return light


@pytest.fixture
def pywemo_registry():
    """Fixture for SubscriptionRegistry instances."""
    return asynctest.create_autospec(pywemo.SubscriptionRegistry)
