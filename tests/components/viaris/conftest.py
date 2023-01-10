"""pytest fixtures."""
from unittest.mock import MagicMock

import pytest

from homeassistant import core as ha
from homeassistant.components import mqtt
from homeassistant.setup import async_setup_component


@ha.callback
def mock_component(hass, component):
    """Mock a component is setup."""
    if component in hass.config.components:
        AssertionError(f"Integration {component} is already setup")

    hass.config.components.add(component)


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable custom integrations defined in the test dir."""
    yield


@pytest.fixture(autouse=True)
def mock_dependencies(hass):
    """Mock dependencies loaded."""
    mock_component(hass, "mqtt")


@pytest.fixture
async def mqtt_mock(hass, mqtt_client_mock, mqtt_config):
    """Fixture to mock MQTT component."""
    if mqtt_config is None:
        mqtt_config = {mqtt.CONF_BROKER: "mock-broker", mqtt.CONF_BIRTH_MESSAGE: {}}

    result = await async_setup_component(hass, mqtt.DOMAIN, {mqtt.DOMAIN: mqtt_config})
    assert result
    await hass.async_block_till_done()

    # Workaround: asynctest==0.13 fails on @functools.lru_cache
    spec = dir(hass.data["mqtt"])
    spec.remove("_matching_subscriptions")

    mqtt_component_mock = MagicMock(
        return_value=hass.data["mqtt"],
        spec_set=spec,
        wraps=hass.data["mqtt"],
    )
    # mqtt_component_mock._mqttc = mqtt_client_mock

    hass.data["mqtt"] = mqtt_component_mock
    component = hass.data["mqtt"]
    component.reset_mock()
    return component
