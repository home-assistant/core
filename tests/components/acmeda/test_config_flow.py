"""Define tests for the Acmeda config flow."""
from unittest.mock import patch

import aiopulse
import pytest

from homeassistant import data_entry_flow
from homeassistant.components.acmeda.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_HOST

from tests.common import MockConfigEntry

DUMMY_HOST1 = "127.0.0.1"
DUMMY_HOST2 = "127.0.0.2"

CONFIG = {
    CONF_HOST: DUMMY_HOST1,
}


@pytest.fixture
def mock_hub_discover():
    """Mock the hub discover method."""
    with patch("aiopulse.Hub.discover") as mock_discover:
        yield mock_discover


@pytest.fixture
def mock_hub_run():
    """Mock the hub run method."""
    with patch("aiopulse.Hub.run") as mock_run:
        yield mock_run


async def async_generator(items):
    """Async yields items provided in a list."""
    for item in items:
        yield item


async def test_show_form_no_hubs(hass, mock_hub_discover):
    """Test that flow aborts if no hubs are discovered."""
    mock_hub_discover.return_value = async_generator([])

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "no_devices_found"

    # Check we performed the discovery
    assert len(mock_hub_discover.mock_calls) == 1


async def test_show_form_one_hub(hass, mock_hub_discover, mock_hub_run):
    """Test that a config is created when one hub discovered."""

    dummy_hub_1 = aiopulse.Hub(DUMMY_HOST1)
    dummy_hub_1.id = "ABC123"

    mock_hub_discover.return_value = async_generator([dummy_hub_1])

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == dummy_hub_1.id
    assert result["result"].data == {
        "host": DUMMY_HOST1,
    }

    # Check we performed the discovery
    assert len(mock_hub_discover.mock_calls) == 1


async def test_show_form_two_hubs(hass, mock_hub_discover):
    """Test that the form is served when more than one hub discovered."""

    dummy_hub_1 = aiopulse.Hub(DUMMY_HOST1)
    dummy_hub_1.id = "ABC123"

    dummy_hub_2 = aiopulse.Hub(DUMMY_HOST1)
    dummy_hub_2.id = "DEF456"

    mock_hub_discover.return_value = async_generator([dummy_hub_1, dummy_hub_2])

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"

    # Check we performed the discovery
    assert len(mock_hub_discover.mock_calls) == 1


async def test_create_second_entry(hass, mock_hub_run, mock_hub_discover):
    """Test that a config is created when a second hub is discovered."""

    dummy_hub_1 = aiopulse.Hub(DUMMY_HOST1)
    dummy_hub_1.id = "ABC123"

    dummy_hub_2 = aiopulse.Hub(DUMMY_HOST2)
    dummy_hub_2.id = "DEF456"

    mock_hub_discover.return_value = async_generator([dummy_hub_1, dummy_hub_2])

    MockConfigEntry(domain=DOMAIN, unique_id=dummy_hub_1.id, data=CONFIG).add_to_hass(
        hass
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == dummy_hub_2.id
    assert result["result"].data == {
        "host": DUMMY_HOST2,
    }


async def test_already_configured(hass, mock_hub_discover):
    """Test that flow aborts when all hubs are configured."""

    dummy_hub_1 = aiopulse.Hub(DUMMY_HOST1)
    dummy_hub_1.id = "ABC123"

    mock_hub_discover.return_value = async_generator([dummy_hub_1])

    MockConfigEntry(domain=DOMAIN, unique_id=dummy_hub_1.id, data=CONFIG).add_to_hass(
        hass
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] == "abort"
    assert result["reason"] == "no_devices_found"
