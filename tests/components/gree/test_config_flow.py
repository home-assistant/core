"""Tests for the Gree Integration."""
import pytest

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.gree.const import DOMAIN as GREE_DOMAIN

from .common import MockDiscovery, build_device_mock

from tests.async_mock import patch


@pytest.fixture(autouse=True, name="discovery")
def discovery_fixture(hass):
    """Patch the discovery service."""
    with patch("homeassistant.components.gree.config_flow.Discovery") as mock:
        mock.return_value = MockDiscovery([build_device_mock()])
        yield mock


async def test_creating_entry_sets_up_climate(hass, setup):
    """Test setting up Gree creates the climate components."""
    result = await hass.config_entries.flow.async_init(
        GREE_DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # Confirmation form
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY

    await hass.async_block_till_done()

    assert len(setup.mock_calls) == 1


async def test_creating_entry_has_no_devices(hass, discovery, setup):
    """Test setting up Gree creates the climate components."""
    discovery.return_value = MockDiscovery([])

    result = await hass.config_entries.flow.async_init(
        GREE_DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # Confirmation form
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT

    await hass.async_block_till_done()

    assert len(setup.mock_calls) == 0
