"""Test Home Assistant config flow for BleBox devices."""

from asynctest import CoroutineMock, mock, patch
import blebox_uniapi
import pytest

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.blebox import async_unload_entry, config_flow
from homeassistant.setup import async_setup_component

from .conftest import mock_config, mock_only_feature, setup_product_mock

from tests.common import mock_coro


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


@pytest.fixture
def product_class_mock():
    """Return a mocked feature."""
    path = "homeassistant.components.blebox.config_flow.Products"
    patcher = patch(path, mock.DEFAULT, blebox_uniapi.products.Products, True, True)
    yield patcher


async def test_flow_with_connection_failure(hass, product_class_mock):
    """Test that config flow works."""
    with product_class_mock as products_class:
        products_class.async_from_host = CoroutineMock(
            side_effect=config_flow.CannotConnect
        )
        flow = init_config_flow(hass)
        result = await flow.async_step_user()
        result = await flow.async_step_user({"host": "172.2.3.4", "port": 80})
        assert result["errors"] == {"base": "cannot_connect"}


async def test_flow_with_api_failure(hass, product_class_mock):
    """Test that config flow works."""
    with product_class_mock as products_class:
        products_class.async_from_host = CoroutineMock(
            side_effect=blebox_uniapi.error.ClientError
        )
        flow = init_config_flow(hass)
        result = await flow.async_step_user()
        result = await flow.async_step_user({"host": "172.2.3.4", "port": 80})
        assert result["errors"] == {"base": "cannot_connect"}


async def test_flow_with_unknown_failure(hass, product_class_mock):
    """Test that config flow works."""
    with product_class_mock as products_class:
        products_class.async_from_host = CoroutineMock(side_effect=RuntimeError)

        flow = init_config_flow(hass)
        result = await flow.async_step_user()
        result = await flow.async_step_user({"host": "172.2.3.4", "port": 80})
        assert result["errors"] == {"base": "unknown"}


async def test_already_configured(hass):
    """Test that same device cannot be added twice."""

    feature = mock_only_feature(
        blebox_uniapi.feature.Cover,
        unique_id="BleBox-gateBox-1afe34db9437-0.position",
        full_name="gateBox-0.position",
        device_class="gate",
        state=0,
        async_update=CoroutineMock(),
        current=None,
    )

    setup_product_mock(
        "covers", [feature], "homeassistant.components.blebox.Products",
    )

    config = mock_config("172.1.2.3")
    config.add_to_hass(hass)

    await hass.config_entries.async_setup(config.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.flow.async_init(
        "blebox", context={"source": "user"}, data={"host": "172.1.2.3", "port": 80},
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"


async def test_async_setup(hass):
    """Test async_setup (for coverage)."""
    assert await async_setup_component(hass, "blebox", {"host": "172.2.3.4"})


async def test_async_setup_entry(hass):
    """Test async_setup_entry (for coverage)."""
    config = mock_config()
    config.add_to_hass(hass)

    with patch.object(
        hass.config_entries,
        "async_forward_entry_setup",
        side_effect=lambda *_: mock_coro(True),
    ) as mock_load:
        assert await hass.config_entries.async_setup(config.entry_id)
        assert config.state == config_entries.ENTRY_STATE_LOADED
        assert len(mock_load.mock_calls) == 1  # 1 platform for now


async def test_async_unload_entry(hass):
    """Test async_unload_entry (for coverage)."""
    config = mock_config("172.90.80.70")
    config.add_to_hass(hass)
    with patch.object(
        hass.config_entries,
        "async_forward_entry_unload",
        side_effect=lambda *_: mock_coro(True),
    ) as mock_unload:
        assert await async_unload_entry(hass, config)
        assert config.state == config_entries.ENTRY_STATE_NOT_LOADED
        assert len(mock_unload.mock_calls) == 1  # 1 platform for now
