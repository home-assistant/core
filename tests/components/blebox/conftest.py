"""PyTest fixtures and test helpers."""

from unittest import mock

import blebox_uniapi
import pytest

from homeassistant.components.blebox.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.setup import async_setup_component

from tests.async_mock import AsyncMock, PropertyMock, patch
from tests.common import MockConfigEntry


def patch_product_identify(path=None, **kwargs):
    """Patch the blebox_uniapi Products class."""
    if path is None:
        path = "homeassistant.components.blebox.Products"
    patcher = patch(path, mock.DEFAULT, blebox_uniapi.products.Products, True, True)
    products_class = patcher.start()
    products_class.async_from_host = AsyncMock(**kwargs)
    return products_class


def setup_product_mock(category, feature_mocks, path=None):
    """Mock a product returning the given features."""

    product_mock = mock.create_autospec(
        blebox_uniapi.box.Box, True, True, features=None
    )
    type(product_mock).features = PropertyMock(return_value={category: feature_mocks})

    for feature in feature_mocks:
        type(feature).product = PropertyMock(return_value=product_mock)

    patch_product_identify(path, return_value=product_mock)
    return product_mock


def mock_only_feature(spec, **kwargs):
    """Mock just the feature, without the product setup."""
    return mock.create_autospec(spec, True, True, **kwargs)


def mock_feature(category, spec, **kwargs):
    """Mock a feature along with whole product setup."""
    feature_mock = mock_only_feature(spec, **kwargs)
    feature_mock.async_update = AsyncMock()
    product = setup_product_mock(category, [feature_mock])

    type(feature_mock.product).name = PropertyMock(return_value="Some name")
    type(feature_mock.product).type = PropertyMock(return_value="some type")
    type(feature_mock.product).model = PropertyMock(return_value="some model")
    type(feature_mock.product).brand = PropertyMock(return_value="BleBox")
    type(feature_mock.product).firmware_version = PropertyMock(return_value="1.23")
    type(feature_mock.product).unique_id = PropertyMock(return_value="abcd0123ef5678")
    type(feature_mock).product = PropertyMock(return_value=product)
    return feature_mock


def mock_config(ip_address="172.100.123.4"):
    """Return a Mock of the HA entity config."""
    return MockConfigEntry(domain=DOMAIN, data={CONF_HOST: ip_address, CONF_PORT: 80})


@pytest.fixture(name="config")
def config_fixture():
    """Create hass config fixture."""
    return {DOMAIN: {CONF_HOST: "172.100.123.4", CONF_PORT: 80}}


@pytest.fixture(name="feature")
def feature(request):
    """Return an entity wrapper from given fixture name."""
    return request.getfixturevalue(request.param)


async def async_setup_entity(hass, config, entity_id):
    """Return a configured entity with the given entity_id."""
    config_entry = mock_config()
    config_entry.add_to_hass(hass)
    assert await async_setup_component(hass, DOMAIN, config)
    await hass.async_block_till_done()

    entity_registry = await hass.helpers.entity_registry.async_get_registry()
    return entity_registry.async_get(entity_id)
