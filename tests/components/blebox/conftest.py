"""PyTest fixtures and test helpers."""

from unittest import mock

import blebox_uniapi
import pytest

from homeassistant.components.blebox.const import DOMAIN
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_SUPPORTED_FEATURES,
    CONF_HOST,
    CONF_PORT,
)
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


@pytest.fixture
def wrapper(request):
    """Return an entity wrapper from given fixture name."""
    return request.getfixturevalue(request.param)


class Wrapper:
    """Convenience wrapper for testing entities and their states."""

    def __init__(self, feature_mock, entity_id):
        """Set the mock object."""
        self._feature_mock = feature_mock
        self._entity_id = entity_id
        self._hass = None
        self._entity = None

    async def setup(self, hass, config):
        """Return a registered entity."""
        self._hass = hass

        config_entry = mock_config()
        config_entry.add_to_hass(hass)
        assert await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()

        entity_registry = await hass.helpers.entity_registry.async_get_registry()
        self._entity = entity_registry.async_get(self._entity_id)
        return self._entity

    async def service(self, domain, service_name, **kwargs):
        """Call the given serice with parameters."""
        hass = self._hass
        entity = self._entity
        self._feature_mock.async_update = AsyncMock(side_effect=None)
        await hass.services.async_call(
            domain,
            service_name,
            {"entity_id": entity.entity_id, **kwargs},
            blocking=True,
        )

    @property
    def feature_mock(self):
        """Return the mock needed by test helpers."""
        return self._feature_mock

    @property
    def state(self):
        """Return the state for the current entity."""
        return self._hass.states.get(self._entity.entity_id)

    @property
    async def device(self):
        """Return the device info for the current entity."""
        hass = self._hass
        entity = self._entity

        device_registry = await hass.helpers.device_registry.async_get_registry()
        return device_registry.async_get(entity.device_id)

    @property
    def state_value(self):
        """Return the state value."""
        return self.state.state

    @property
    def unique_id(self):
        """Return the entity unique id."""
        return self._entity.unique_id

    @property
    def attributes(self):
        """Return the state attributes."""
        return self.state.attributes

    @property
    def device_class(self):
        """Return the device class."""
        return self.attributes[ATTR_DEVICE_CLASS]

    @property
    def supported_features(self):
        """Return the supported features."""
        return self.attributes[ATTR_SUPPORTED_FEATURES]
