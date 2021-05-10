"""The tests for the Onkyo media player platform."""
import pytest

from homeassistant import config_entries
from homeassistant.components import ssdp
from homeassistant.components.onkyo.const import CONF_SOURCES, DOMAIN, UNKNOWN_MODEL
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_SOURCE
from homeassistant.data_entry_flow import (
    RESULT_TYPE_ABORT,
    RESULT_TYPE_CREATE_ENTRY,
    RESULT_TYPE_FORM,
)

from tests.common import MockConfigEntry, patch

MOCK_YAML_CONFIG = {
    "platform": "onkyo",
    CONF_NAME: "my_receiver",
    CONF_HOST: "1.2.3.4",
    "sources": {
        "video6": "PC",
        "tv": "Tv",
        "db": "Bluray",
    },
}


@pytest.fixture(name="client")
def client_fixture():
    """Patch of client library for tests."""
    with patch(
        "homeassistant.components.onkyo.onkyo_rcv", autospec=True
    ) as mock_client_class:
        client = mock_client_class.return_value
        client.host = "1.2.3.4"
        client.identifier = "0123456789"
        client.info = {"identifier": "0123456789"}
        client.model_name = "SN0123456789"
        yield client


@pytest.fixture(name="client_unknown")
def client_unknown_fixture():
    """Patch of client library for tests."""
    with patch(
        "homeassistant.components.onkyo.onkyo_rcv", autospec=True
    ) as mock_client_unknown_class:
        client_unknown = mock_client_unknown_class.return_value
        client_unknown.model_name = UNKNOWN_MODEL
        yield client_unknown


async def test_form_import(hass, client):
    """Test we can import yaml config."""
    with patch(
        "homeassistant.components.onkyo.config_flow.onkyo_rcv",
        return_value=client,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data=MOCK_YAML_CONFIG,
        )

    await hass.async_block_till_done()
    assert result["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "my_receiver"


async def test_form(hass, client):
    """Test we get the form."""
    with patch(
        "homeassistant.components.onkyo.config_flow.onkyo_rcv",
        return_value=client,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={CONF_SOURCE: config_entries.SOURCE_USER},
            data=MOCK_YAML_CONFIG,
        )

    await hass.async_block_till_done()
    assert result["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "my_receiver"


async def test_form_client_unknown(hass, client_unknown):
    """Test client unknown."""
    with patch(
        "homeassistant.components.onkyo.config_flow.onkyo_rcv",
        return_value=client_unknown,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={CONF_SOURCE: config_entries.SOURCE_USER},
            data=MOCK_YAML_CONFIG,
        )

    await hass.async_block_till_done()
    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] == {"base": "receiver_unknown"}


async def test_form_updates_unique_id(hass, client):
    """Test duplicated unique_id."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "1.2.3.4",
        },
        unique_id="0123456789",
    )
    entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.onkyo.config_flow.onkyo_rcv",
        return_value=client,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={CONF_SOURCE: config_entries.SOURCE_USER},
            data=MOCK_YAML_CONFIG,
        )

    await hass.async_block_till_done()

    assert result["type"] == RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"


async def test_options_flow(hass, client):
    """Test options config flow."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "1.2.3.4", CONF_SOURCES: "video1"},
        options={CONF_SOURCES: {"fm": "fm", "am": "am"}},
        unique_id="0123456789",
    )
    entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.onkyo.config_flow.onkyo_rcv",
        return_value=client,
    ):
        result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "init"

    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_SOURCES: ["video1", "tv", "fm"]},
    )
    assert result2["type"] == RESULT_TYPE_FORM
    assert result2["step_id"] == "customize"

    result3 = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"video1": "MyVideo", "tv": "MyTv", "fm": "MyTuner"},
    )
    assert result3["type"] == RESULT_TYPE_CREATE_ENTRY
    await hass.async_block_till_done()


async def test_options_sources_empty_flow(hass, client):
    """Test options config flow."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "1.2.3.4",
        },
        unique_id="0123456789",
    )
    entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.onkyo.config_flow.onkyo_rcv",
        return_value=client,
    ):
        result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "init"

    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={}
    )
    assert result2["type"] == RESULT_TYPE_CREATE_ENTRY
    await hass.async_block_till_done()


async def test_form_receiver_notfound(hass):
    """Test we handle cannot connect error."""
    with patch(
        "homeassistant.components.onkyo.config_flow.onkyo_rcv",
        side_effect=OSError,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={CONF_SOURCE: config_entries.SOURCE_USER},
            data=MOCK_YAML_CONFIG,
        )

    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_form_ssdp(hass, client):
    """Test ssdp discovery."""
    discovery_infos = {
        ssdp.ATTR_UPNP_FRIENDLY_NAME: "Onkyo Receiver",
        ssdp.ATTR_SSDP_LOCATION: "http://hostname",
    }
    with patch(
        "homeassistant.components.onkyo.config_flow.onkyo_rcv",
        return_value=client,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={CONF_SOURCE: config_entries.SOURCE_SSDP},
            data=discovery_infos,
        )

    assert result["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "Onkyo Receiver"
