"""Test Home Assistant config flow for BleBox devices."""

import blebox_uniapi
import pytest

from homeassistant.components.blebox import config_flow

from .conftest import mock_only_feature, setup_product_mock


def init_config_flow(hass):
    """Init a configuration flow."""
    flow = config_flow.BleBoxConfigFlow()
    flow.hass = hass
    return flow


@pytest.fixture
def feature_mock():
    """Return a mocked feature."""
    feature = mock_only_feature(
        blebox_uniapi.feature.Temperature,
        unique_id="BleBox-tempSensor-1afe34db9437-0.temperature",
        full_name="tempSensor-0.temperature",
        device_class="temperature",
        unit="celsius",
        current=None,
    )

    product = setup_product_mock(
        "sensors", [feature], "homeassistant.components.blebox.config_flow.Products",
    )
    product.name = "My tempSensor"

    return feature


async def test_flow_works(hass, feature_mock):
    """Test that config flow works."""

    flow = init_config_flow(hass)

    result = await flow.async_step_user()

    assert result["type"] == "form"
    assert result["step_id"] == "user"

    result = await flow.async_step_user(
        {
            # config_flow.CONF_NAME: "my device",
            config_flow.CONF_HOST: "172.2.3.4",
            config_flow.CONF_PORT: 80,
        },
    )

    assert result["type"] == "create_entry"
    assert result["title"] == "My tempSensor"
    assert result["data"] == {
        config_flow.CONF_HOST: "172.2.3.4",
        config_flow.CONF_PORT: 80,
        # config_flow.CONF_NAME: "my device",
    }
