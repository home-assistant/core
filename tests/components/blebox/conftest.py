"""PyTest fixtures and test helpers."""
from unittest import mock
from unittest.mock import AsyncMock, PropertyMock, patch

import blebox_uniapi
import pytest

from homeassistant.components.blebox.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry
from tests.components.light.conftest import mock_light_profiles  # noqa: F401


def patch_product_identify(path=None, **kwargs):
    """Patch the blebox_uniapi Products class."""
    patcher = patch.object(
        blebox_uniapi.box.Box, "async_from_host", AsyncMock(**kwargs)
    )
    patcher.start()
    return blebox_uniapi.box.Box


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


def mock_only_feature(spec, set_spec: bool = True, **kwargs):
    """Mock just the feature, without the product setup."""
    return mock.create_autospec(spec, set_spec, True, **kwargs)


def mock_feature(category, spec, set_spec: bool = True, **kwargs):
    """Mock a feature along with whole product setup."""
    feature_mock = mock_only_feature(spec, set_spec, **kwargs)
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
def feature_fixture(request):
    """Return an entity wrapper from given fixture name."""
    return request.getfixturevalue(request.param)


async def async_setup_entities(hass, entity_ids):
    """Return configured entries with the given entity ids."""

    config_entry = mock_config()
    config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    entity_registry = er.async_get(hass)
    return [entity_registry.async_get(entity_id) for entity_id in entity_ids]


async def async_setup_entity(hass, entity_id):
    """Return a configured entry with the given entity_id."""

    return (await async_setup_entities(hass, [entity_id]))[0]
