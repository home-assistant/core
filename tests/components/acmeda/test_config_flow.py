"""Define tests for the Acmeda config flow."""
import aiopulse
from asynctest.mock import patch
import pytest

from homeassistant import data_entry_flow
from homeassistant.components.acmeda.const import DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
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
    """Async ytields items provided in a list."""
    for item in items:
        yield item


async def test_show_form_no_hubs(hass, mock_hub_discover):
    """Test that flow aborts if no hubs are discovered."""
    mock_hub_discover.return_value = async_generator([])

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "no_hubs"

    # Check we performed the discovery
    assert len(mock_hub_discover.mock_calls) == 1


async def test_show_form_one_hub(hass, mock_hub_discover, mock_hub_run):
    """Test that a config is created when one hub discovered."""
    mock_hub_discover.return_value = async_generator([aiopulse.Hub(DUMMY_HOST1)])

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == DUMMY_HOST1
    assert result["result"].data == {
        "host": DUMMY_HOST1,
    }

    # Check we performed the discovery
    assert len(mock_hub_discover.mock_calls) == 1


async def test_show_form_two_hubs(hass, mock_hub_discover):
    """Test that the form is served when more than one hub discovered."""
    mock_hub_discover.return_value = async_generator(
        [aiopulse.Hub(DUMMY_HOST1), aiopulse.Hub(DUMMY_HOST2)]
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "init"

    # Check we performed the discovery
    assert len(mock_hub_discover.mock_calls) == 1


async def test_create_second_entry(hass, mock_hub_run, mock_hub_discover):
    """Test that a config is created when a second hub is discovered."""

    mock_hub_discover.return_value = async_generator([aiopulse.Hub(DUMMY_HOST2)])

    MockConfigEntry(domain=DOMAIN, unique_id="123-456", data=CONFIG).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == DUMMY_HOST2
    assert result["result"].data == {
        "host": DUMMY_HOST2,
    }


async def test_create_entry(hass, mock_hub_run):
    """Test that the import from a config entry succeeds."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data=CONFIG
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == DUMMY_HOST1
    assert result["result"].data == {
        "host": DUMMY_HOST1,
    }


async def test_duplicate_error(hass):
    """Test that flow aborts when a duplicate is added."""

    MockConfigEntry(domain=DOMAIN, unique_id="123-456", data=CONFIG).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data=CONFIG
    )

    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"


async def test_already_configured(hass, mock_hub_discover):
    """Test that flow aborts when all habs are configured."""

    mock_hub_discover.return_value = async_generator([aiopulse.Hub(DUMMY_HOST1)])

    MockConfigEntry(domain=DOMAIN, unique_id="123-456", data=CONFIG).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] == "abort"
    assert result["reason"] == "all_configured"
