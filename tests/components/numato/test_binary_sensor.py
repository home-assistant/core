"""Tests for the numato binary_sensor platform."""

import logging
from unittest.mock import patch

import pytest

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import discovery
from homeassistant.setup import async_setup_component

from .common import NUMATO_CFG, mockup_raise
from .numato_mock import NumatoGpioError, NumatoModuleMock

MOCKUP_ENTITY_IDS = {
    "binary_sensor.numato_binary_sensor_mock_port2",
    "binary_sensor.numato_binary_sensor_mock_port3",
    "binary_sensor.numato_binary_sensor_mock_port4",
}


async def test_failing_setups_no_entities(
    hass: HomeAssistant, numato_fixture, monkeypatch
) -> None:
    """When port setup fails, no entity shall be created."""
    monkeypatch.setattr(numato_fixture.NumatoDeviceMock, "setup", mockup_raise)
    assert await async_setup_component(hass, "numato", NUMATO_CFG)
    await hass.async_block_till_done()
    for entity_id in MOCKUP_ENTITY_IDS:
        assert entity_id not in hass.states.async_entity_ids()


async def test_setup_callbacks(hass: HomeAssistant, numato_fixture) -> None:
    """During setup a callback shall be registered."""

    with patch.object(
        NumatoModuleMock.NumatoDeviceMock, "add_event_detect"
    ) as mock_add_event_detect:
        numato_fixture.discover()
        assert await async_setup_component(hass, "numato", NUMATO_CFG)
        await hass.async_block_till_done()  # wait until services are registered

    mock_add_event_detect.assert_called()
    assert {call.args[0] for call in mock_add_event_detect.mock_calls} == {
        int(port)
        for port in NUMATO_CFG["numato"]["devices"][0]["binary_sensors"]["ports"]
    }
    assert all(callable(call.args[1]) for call in mock_add_event_detect.mock_calls)
    assert all(
        call.args[2] == numato_fixture.BOTH for call in mock_add_event_detect.mock_calls
    )


async def test_hass_binary_sensor_notification(
    hass: HomeAssistant, numato_fixture
) -> None:
    """Test regular operations from within Home Assistant."""
    assert await async_setup_component(hass, "numato", NUMATO_CFG)
    await hass.async_block_till_done()  # wait until services are registered
    assert (
        hass.states.get("binary_sensor.numato_binary_sensor_mock_port2").state == "on"
    )
    await hass.async_add_executor_job(numato_fixture.devices[0].callbacks[2], 2, False)
    await hass.async_block_till_done()
    assert (
        hass.states.get("binary_sensor.numato_binary_sensor_mock_port2").state == "off"
    )


async def test_binary_sensor_setup_without_discovery_info(
    hass: HomeAssistant, config, numato_fixture
) -> None:
    """Test handling of empty discovery_info."""
    numato_fixture.discover()
    await discovery.async_load_platform(
        hass, Platform.BINARY_SENSOR, "numato", None, config
    )
    for entity_id in MOCKUP_ENTITY_IDS:
        assert entity_id not in hass.states.async_entity_ids()
    await hass.async_block_till_done()  # wait for numato platform to be loaded
    for entity_id in MOCKUP_ENTITY_IDS:
        assert entity_id in hass.states.async_entity_ids()


async def test_binary_sensor_setup_no_notify(
    hass: HomeAssistant,
    numato_fixture,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Setup of a device without notification capability shall print an info message."""
    caplog.set_level(logging.INFO)

    def raise_notification_error(self, port, callback, direction):
        raise NumatoGpioError(
            f"{repr(self)} Mockup device doesn't support notifications."
        )

    with patch.object(
        NumatoModuleMock.NumatoDeviceMock,
        "add_event_detect",
        raise_notification_error,
    ):
        numato_fixture.discover()
        assert await async_setup_component(hass, "numato", NUMATO_CFG)
        await hass.async_block_till_done()  # wait until services are registered

    assert all(
        f"updates on binary sensor numato_binary_sensor_mock_port{port} only in polling mode"
        in caplog.text
        for port in NUMATO_CFG["numato"]["devices"][0]["binary_sensors"]["ports"]
    )
