"""Define tests for the AirVisual config flow."""
from pyairvisual.errors import InvalidKeyError, NodeProError

from homeassistant import data_entry_flow
from homeassistant.components.airvisual import (
    CONF_GEOGRAPHIES,
    CONF_INTEGRATION_TYPE,
    DOMAIN,
    INTEGRATION_TYPE_GEOGRAPHY,
    INTEGRATION_TYPE_NODE_PRO,
)
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.const import (
    CONF_API_KEY,
    CONF_IP_ADDRESS,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_PASSWORD,
    CONF_SHOW_ON_MAP,
)
from homeassistant.setup import async_setup_component

from tests.async_mock import patch
from tests.common import MockConfigEntry


async def test_duplicate_error(hass):
    """Test that errors are shown when duplicate entries are added."""
    geography_conf = {
        CONF_API_KEY: "abcde12345",
        CONF_LATITUDE: 51.528308,
        CONF_LONGITUDE: -0.3817765,
    }

    MockConfigEntry(
        domain=DOMAIN, unique_id="51.528308, -0.3817765", data=geography_conf
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data=geography_conf
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"

    node_pro_conf = {CONF_IP_ADDRESS: "192.168.1.100", CONF_PASSWORD: "12345"}

    MockConfigEntry(
        domain=DOMAIN, unique_id="192.168.1.100", data=node_pro_conf
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data={"type": "AirVisual Node/Pro"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=node_pro_conf
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

    with patch(
        "pyairvisual.api.API.nearest_city",
        side_effect=InvalidKeyError,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=geography_conf
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["errors"] == {CONF_API_KEY: "invalid_api_key"}


async def test_migration(hass):
    """Test migrating from version 1 to the current version."""
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

    with patch("pyairvisual.api.API.nearest_city"), patch.object(
        hass.config_entries, "async_forward_entry_setup"
    ):
        assert await async_setup_component(hass, DOMAIN, {DOMAIN: conf})
        await hass.async_block_till_done()

    config_entries = hass.config_entries.async_entries(DOMAIN)

    assert len(config_entries) == 2

    assert config_entries[0].unique_id == "51.528308, -0.3817765"
    assert config_entries[0].title == "Cloud API (51.528308, -0.3817765)"
    assert config_entries[0].data == {
        CONF_API_KEY: "abcde12345",
        CONF_LATITUDE: 51.528308,
        CONF_LONGITUDE: -0.3817765,
        CONF_INTEGRATION_TYPE: INTEGRATION_TYPE_GEOGRAPHY,
    }

    assert config_entries[1].unique_id == "35.48847, 137.5263065"
    assert config_entries[1].title == "Cloud API (35.48847, 137.5263065)"
    assert config_entries[1].data == {
        CONF_API_KEY: "abcde12345",
        CONF_LATITUDE: 35.48847,
        CONF_LONGITUDE: 137.5263065,
        CONF_INTEGRATION_TYPE: INTEGRATION_TYPE_GEOGRAPHY,
    }


async def test_node_pro_error(hass):
    """Test that an invalid Node/Pro ID shows an error."""
    node_pro_conf = {CONF_IP_ADDRESS: "192.168.1.100", CONF_PASSWORD: "my_password"}

    with patch(
        "pyairvisual.node.Node.from_samba",
        side_effect=NodeProError,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data={"type": "AirVisual Node/Pro"}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=node_pro_conf
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["errors"] == {CONF_IP_ADDRESS: "unable_to_connect"}


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
    """Test the geograph (cloud API) step."""
    conf = {
        CONF_API_KEY: "abcde12345",
        CONF_LATITUDE: 51.528308,
        CONF_LONGITUDE: -0.3817765,
    }

    with patch(
        "homeassistant.components.airvisual.async_setup_entry", return_value=True
    ), patch("pyairvisual.api.API.nearest_city"):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=conf
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert result["title"] == "Cloud API (51.528308, -0.3817765)"
        assert result["data"] == {
            CONF_API_KEY: "abcde12345",
            CONF_LATITUDE: 51.528308,
            CONF_LONGITUDE: -0.3817765,
            CONF_INTEGRATION_TYPE: INTEGRATION_TYPE_GEOGRAPHY,
        }


async def test_step_import(hass):
    """Test the import step for both types of configuration."""
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
            CONF_INTEGRATION_TYPE: INTEGRATION_TYPE_GEOGRAPHY,
        }


async def test_step_node_pro(hass):
    """Test the Node/Pro step."""
    conf = {CONF_IP_ADDRESS: "192.168.1.100", CONF_PASSWORD: "my_password"}

    with patch(
        "homeassistant.components.airvisual.async_setup_entry", return_value=True
    ), patch("pyairvisual.node.Node.from_samba"):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data={"type": "AirVisual Node/Pro"}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=conf
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert result["title"] == "Node/Pro (192.168.1.100)"
        assert result["data"] == {
            CONF_IP_ADDRESS: "192.168.1.100",
            CONF_PASSWORD: "my_password",
            CONF_INTEGRATION_TYPE: INTEGRATION_TYPE_NODE_PRO,
        }


async def test_step_reauth(hass):
    """Test that the reauth step works."""
    geography_conf = {
        CONF_API_KEY: "abcde12345",
        CONF_LATITUDE: 51.528308,
        CONF_LONGITUDE: -0.3817765,
    }

    MockConfigEntry(
        domain=DOMAIN, unique_id="51.528308, -0.3817765", data=geography_conf
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "reauth"}, data=geography_conf
    )
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "reauth_confirm"

    with patch(
        "homeassistant.components.simplisafe.async_setup_entry", return_value=True
    ), patch("pyairvisual.api.API.nearest_city"):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_API_KEY: "defgh67890"}
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
        assert result["reason"] == "reauth_successful"

    assert len(hass.config_entries.async_entries()) == 1


async def test_step_user(hass):
    """Test the user ("pick the integration type") step."""
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
