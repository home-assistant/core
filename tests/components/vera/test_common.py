"""Tests for common vera code."""
from datetime import timedelta

from asynctest import MagicMock
from pyvera import VeraController
from requests.adapters import Response

from homeassistant.components.vera import SubscriptionRegistry
from homeassistant.core import HomeAssistant
from homeassistant.util.dt import utcnow

from tests.common import async_fire_time_changed


async def test_subscription_registry(hass: HomeAssistant) -> None:
    """Test subscription registry polling."""
    devices = ["device1"]
    alerts = ["alert1"]
    response = MagicMock(spec=Response)
    response.json.return_value = {"devices": devices, "alerts": alerts}

    controller = MagicMock(spec=VeraController)
    controller.data_request.return_value = response

    subscription_registry = SubscriptionRegistry(hass)
    subscription_registry.set_controller(controller)
    # pylint: disable=protected-access
    subscription_registry._event = event_mock = MagicMock()
    subscription_registry.start()

    event_mock.reset_mock()
    controller.data_request.reset_mock()
    async_fire_time_changed(hass, utcnow() + timedelta(seconds=1))
    await hass.async_block_till_done()
    event_mock.assert_called_once_with(devices, alerts)
    assert controller.data_request.call_count == 2

    event_mock.reset_mock()
    controller.data_request.reset_mock()
    async_fire_time_changed(hass, utcnow() + timedelta(seconds=1))
    await hass.async_block_till_done()
    event_mock.assert_called_once_with(devices, alerts)
    assert controller.data_request.call_count == 2

    subscription_registry.stop()

    event_mock.reset_mock()
    controller.data_request.reset_mock()
    async_fire_time_changed(hass, utcnow() + timedelta(seconds=5))
    await hass.async_block_till_done()
    event_mock.assert_not_called()
    controller.data_request.assert_not_called()
