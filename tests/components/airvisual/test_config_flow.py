"""Define tests for the AirVisual config flow."""
from asynctest import patch
from pyairvisual.errors import InvalidKeyError, NotFoundError

from homeassistant import data_entry_flow
from homeassistant.components.airvisual import (
    CONF_GEOGRAPHIES,
    CONF_NODE_PRO_ID,
    DOMAIN,
    INTEGRATION_TYPE_GEOGRAPHY,
    INTEGRATION_TYPE_NODE_PRO,
)
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.const import (
    CONF_API_KEY,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_SHOW_ON_MAP,
)
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


async def test_duplicate_error(hass):
    """Test that errors are shown when duplicate entries are added."""
    geography_conf = {
        CONF_API_KEY: "abcde12345",
        CONF_LATITUDE: 51.528308,
        CONF_LONGITUDE: -0.3817765,
    }
    node_pro_conf = {CONF_NODE_PRO_ID: "fghij67890"}

    MockConfigEntry(
        domain=DOMAIN, unique_id="51.528308, -0.3817765", data=geography_conf
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data=geography_conf
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"

    MockConfigEntry(
        domain=DOMAIN, unique_id="fghij67890", data=node_pro_conf
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data=node_pro_conf
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"


async def test_invalid_identifier(hass):
    """Test that an invalid API key or Node/Pro ID throws an error."""
    geography_conf = {
        CONF_API_KEY: "abcde12345",
        CONF_LATITUDE: 51.528308,
        CONF_LONGITUDE: -0.3817765,
    }
    node_pro_conf = {CONF_NODE_PRO_ID: "fghij67890"}

    with patch(
        "pyairvisual.api.API.nearest_city", side_effect=InvalidKeyError,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=geography_conf
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["errors"] == {CONF_API_KEY: "invalid_api_key"}

    with patch(
        "pyairvisual.api.API.node", side_effect=NotFoundError,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=node_pro_conf
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["errors"] == {CONF_NODE_PRO_ID: "invalid_node_pro_id"}


async def test_migration_1_2(hass):
    """Test migrating from version 1 to version 2."""
    conf = {
        CONF_API_KEY: "abcde12345",
        CONF_GEOGRAPHIES: [
            {CONF_LATITUDE: 51.528308, CONF_LONGITUDE: -0.3817765},
            {CONF_LATITUDE: 35.48847, CONF_LONGITUDE: 137.5263065},
        ],
    }

    config_entry = MockConfigEntry(
        domain=DOMAIN, version=1, unique_id="abcde12345", data=conf
    )
    config_entry.add_to_hass(hass)

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1

    with patch("pyairvisual.api.API.nearest_city"):
        assert await async_setup_component(hass, DOMAIN, {DOMAIN: conf})

    config_entries = hass.config_entries.async_entries(DOMAIN)

    assert len(config_entries) == 2

    assert config_entries[0].unique_id == "51.528308, -0.3817765"
    assert config_entries[0].title == "Cloud API (51.528308, -0.3817765)"
    assert config_entries[0].data == {
        CONF_API_KEY: "abcde12345",
        CONF_LATITUDE: 51.528308,
        CONF_LONGITUDE: -0.3817765,
    }

    assert config_entries[1].unique_id == "35.48847, 137.5263065"
    assert config_entries[1].title == "Cloud API (35.48847, 137.5263065)"
    assert config_entries[1].data == {
        CONF_API_KEY: "abcde12345",
        CONF_LATITUDE: 35.48847,
        CONF_LONGITUDE: 137.5263065,
    }


async def test_options_flow(hass):
    """Test config flow options."""
    geography_conf = {
        CONF_API_KEY: "abcde12345",
        CONF_LATITUDE: 51.528308,
        CONF_LONGITUDE: -0.3817765,
    }

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="51.528308, -0.3817765",
        data=geography_conf,
        options={CONF_SHOW_ON_MAP: True},
    )
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.airvisual.async_setup_entry", return_value=True
    ):
        result = await hass.config_entries.options.async_init(config_entry.entry_id)

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "init"

        result = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input={CONF_SHOW_ON_MAP: False}
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert config_entry.options == {CONF_SHOW_ON_MAP: False}


async def test_step_geography(hass):
    """Test that the user is taken to the correct flow based on integration type."""
    geography_conf = {
        CONF_API_KEY: "abcde12345",
        CONF_LATITUDE: 51.528308,
        CONF_LONGITUDE: -0.3817765,
    }

    with patch(
        "homeassistant.components.airvisual.async_setup_entry", return_value=True
    ), patch("pyairvisual.api.API.nearest_city"):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=geography_conf
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert result["title"] == "Cloud API (51.528308, -0.3817765)"
        assert result["data"] == {
            CONF_API_KEY: "abcde12345",
            CONF_LATITUDE: 51.528308,
            CONF_LONGITUDE: -0.3817765,
        }


async def test_step_import(hass):
    """Test that the import step works for both types of configuration."""
    geography_conf = {
        CONF_API_KEY: "abcde12345",
        CONF_LATITUDE: 51.528308,
        CONF_LONGITUDE: -0.3817765,
    }
    node_pro_conf = {CONF_NODE_PRO_ID: "fghij67890"}

    with patch(
        "homeassistant.components.airvisual.async_setup_entry", return_value=True
    ), patch("pyairvisual.api.API.nearest_city"):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=geography_conf
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert result["title"] == "Cloud API (51.528308, -0.3817765)"
        assert result["data"] == {
            CONF_API_KEY: "abcde12345",
            CONF_LATITUDE: 51.528308,
            CONF_LONGITUDE: -0.3817765,
        }

    with patch(
        "homeassistant.components.airvisual.async_setup_entry", return_value=True
    ), patch("pyairvisual.api.API.node"):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=node_pro_conf
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert result["title"] == "Node/Pro (fghij67890)"
        assert result["data"] == {CONF_NODE_PRO_ID: "fghij67890"}


async def test_step_user(hass):
    """Test that the form is served with no input."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={"type": INTEGRATION_TYPE_GEOGRAPHY},
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "geography"

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={"type": INTEGRATION_TYPE_NODE_PRO},
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "node_pro"
