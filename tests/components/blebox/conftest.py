"""PyTest fixtures and test helpers."""

from unittest import mock

from asynctest import CoroutineMock, PropertyMock, patch
import blebox_uniapi

from homeassistant.components.blebox import const
from homeassistant.const import CONF_HOST, CONF_PORT

from tests.common import MockConfigEntry


def patch_product_identify(path=None, **kwargs):
    """Patch the blebox_uniapi Products class."""
    if path is None:
        path = "homeassistant.components.blebox.Products"

    patcher = patch(path, mock.DEFAULT, blebox_uniapi.products.Products, True, True)
    products_class = patcher.start()
    products_class.async_from_host = CoroutineMock(**kwargs)
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
    return MockConfigEntry(
        domain=const.DOMAIN, data={CONF_HOST: ip_address, CONF_PORT: 80},
    )


class BleBoxTestHelper:
    """Helper methods for tests."""

    HASS_TYPE = None  # override in subclass

    def __init__(self, feature_mock):
        """Set the mock object."""
        self._feature_mock = feature_mock

    def default_mock(self):
        """Return the mock needed by test helpers."""
        return self._feature_mock

    async def async_mock_entities(self, hass):
        """Return a new entities configured through HASS."""

        config = mock_config()
        config.add_to_hass(hass)

        domain = hass.data.setdefault(const.DOMAIN, {})
        products = domain.setdefault(const.PRODUCTS, {})
        products[config.entry_id] = self.default_mock().product

        all_entries = []

        def add_entries(entries, update):
            for entry in entries:
                entry.hass = hass
                all_entries.append(entry)

        platform = self.HASS_TYPE
        assert await platform.async_setup_entry(hass, config, add_entries) is True
        return all_entries

    async def async_updated_entity(self, hass, index):
        """Return an already-updated entity created through HASS."""
        entity = (await self.async_mock_entities(hass))[index]
        await entity.async_update()
        return entity
