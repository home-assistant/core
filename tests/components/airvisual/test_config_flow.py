"""Define tests for the AirVisual config flow."""
from unittest.mock import patch

from pyairvisual.errors import (
    AirVisualError,
    InvalidKeyError,
    KeyExpiredError,
    NodeProError,
    NotFoundError,
    UnauthorizedError,
)
import pytest

from homeassistant import data_entry_flow
from homeassistant.components.airvisual.const import (
    CONF_CITY,
    CONF_COUNTRY,
    CONF_GEOGRAPHIES,
    CONF_INTEGRATION_TYPE,
    DOMAIN,
    INTEGRATION_TYPE_GEOGRAPHY_COORDS,
    INTEGRATION_TYPE_GEOGRAPHY_NAME,
    INTEGRATION_TYPE_NODE_PRO,
)
from homeassistant.config_entries import SOURCE_REAUTH, SOURCE_USER
from homeassistant.const import (
    CONF_API_KEY,
    CONF_IP_ADDRESS,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_PASSWORD,
    CONF_SHOW_ON_MAP,
    CONF_STATE,
)


@pytest.mark.parametrize(
    "config,data,unique_id",
    [
        (
            {
                CONF_API_KEY: "abcde12345",
                CONF_LATITUDE: 51.528308,
                CONF_LONGITUDE: -0.3817765,
            },
            {
                "type": INTEGRATION_TYPE_GEOGRAPHY_COORDS,
            },
            "51.528308, -0.3817765",
        ),
        (
            {
                CONF_IP_ADDRESS: "192.168.1.100",
                CONF_PASSWORD: "12345",
            },
            {
                "type": INTEGRATION_TYPE_NODE_PRO,
            },
            "192.168.1.100",
        ),
    ],
)
async def test_duplicate_error(hass, config, config_entry, data):
    """Test that errors are shown when duplicate entries are added."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=data
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=config
    )
    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    "data,exc,errors,integration_type",
    [
        (
            {
                CONF_API_KEY: "abcde12345",
                CONF_CITY: "Beijing",
                CONF_STATE: "Beijing",
                CONF_COUNTRY: "China",
            },
            InvalidKeyError,
            {CONF_API_KEY: "invalid_api_key"},
            INTEGRATION_TYPE_GEOGRAPHY_NAME,
        ),
        (
            {
                CONF_API_KEY: "abcde12345",
                CONF_CITY: "Beijing",
                CONF_STATE: "Beijing",
                CONF_COUNTRY: "China",
            },
            KeyExpiredError,
            {CONF_API_KEY: "invalid_api_key"},
            INTEGRATION_TYPE_GEOGRAPHY_NAME,
        ),
        (
            {
                CONF_API_KEY: "abcde12345",
                CONF_CITY: "Beijing",
                CONF_STATE: "Beijing",
                CONF_COUNTRY: "China",
            },
            UnauthorizedError,
            {CONF_API_KEY: "invalid_api_key"},
            INTEGRATION_TYPE_GEOGRAPHY_NAME,
        ),
        (
            {
                CONF_API_KEY: "abcde12345",
                CONF_CITY: "Beijing",
                CONF_STATE: "Beijing",
                CONF_COUNTRY: "China",
            },
            NotFoundError,
            {CONF_CITY: "location_not_found"},
            INTEGRATION_TYPE_GEOGRAPHY_NAME,
        ),
        (
            {
                CONF_API_KEY: "abcde12345",
                CONF_CITY: "Beijing",
                CONF_STATE: "Beijing",
                CONF_COUNTRY: "China",
            },
            AirVisualError,
            {"base": "unknown"},
            INTEGRATION_TYPE_GEOGRAPHY_NAME,
        ),
        (
            {
                CONF_IP_ADDRESS: "192.168.1.100",
                CONF_PASSWORD: "my_password",
            },
            NodeProError,
            {CONF_IP_ADDRESS: "cannot_connect"},
            INTEGRATION_TYPE_NODE_PRO,
        ),
    ],
)
async def test_errors(hass, data, exc, errors, integration_type):
    """Test that an exceptions show an error."""
    with patch("pyairvisual.air_quality.AirQuality.city", side_effect=exc):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data={"type": integration_type}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=data
        )
        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["errors"] == errors


@pytest.mark.parametrize(
    "config,config_entry_version,unique_id",
    [
        (
            {
                CONF_API_KEY: "abcde12345",
                CONF_GEOGRAPHIES: [
                    {CONF_LATITUDE: 51.528308, CONF_LONGITUDE: -0.3817765},
                    {
                        CONF_CITY: "Beijing",
                        CONF_STATE: "Beijing",
                        CONF_COUNTRY: "China",
                    },
                ],
            },
            1,
            "abcde12345",
        )
    ],
)
async def test_migration(hass, config, config_entry, setup_airvisual, unique_id):
    """Test migrating from version 1 to the current version."""
    config_entries = hass.config_entries.async_entries(DOMAIN)
    assert len(config_entries) == 2

    assert config_entries[0].unique_id == "51.528308, -0.3817765"
    assert config_entries[0].title == "Cloud API (51.528308, -0.3817765)"
    assert config_entries[0].data == {
        CONF_API_KEY: "abcde12345",
        CONF_LATITUDE: 51.528308,
        CONF_LONGITUDE: -0.3817765,
        CONF_INTEGRATION_TYPE: INTEGRATION_TYPE_GEOGRAPHY_COORDS,
    }

    assert config_entries[1].unique_id == "Beijing, Beijing, China"
    assert config_entries[1].title == "Cloud API (Beijing, Beijing, China)"
    assert config_entries[1].data == {
        CONF_API_KEY: "abcde12345",
        CONF_CITY: "Beijing",
        CONF_STATE: "Beijing",
        CONF_COUNTRY: "China",
        CONF_INTEGRATION_TYPE: INTEGRATION_TYPE_GEOGRAPHY_NAME,
    }


async def test_options_flow(hass, config_entry):
    """Test config flow options."""
    with patch(
        "homeassistant.components.airvisual.async_setup_entry", return_value=True
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        result = await hass.config_entries.options.async_init(config_entry.entry_id)

        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "init"

        result = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input={CONF_SHOW_ON_MAP: False}
        )

        assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
        assert config_entry.options == {CONF_SHOW_ON_MAP: False}


async def test_step_geography_by_coords(hass, config, setup_airvisual):
    """Test setting up a geography entry by latitude/longitude."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={"type": INTEGRATION_TYPE_GEOGRAPHY_COORDS},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=config
    )

    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["title"] == "Cloud API (51.528308, -0.3817765)"
    assert result["data"] == {
        CONF_API_KEY: "abcde12345",
        CONF_LATITUDE: 51.528308,
        CONF_LONGITUDE: -0.3817765,
        CONF_INTEGRATION_TYPE: INTEGRATION_TYPE_GEOGRAPHY_COORDS,
    }


@pytest.mark.parametrize(
    "config",
    [
        {
            CONF_API_KEY: "abcde12345",
            CONF_CITY: "Beijing",
            CONF_STATE: "Beijing",
            CONF_COUNTRY: "China",
        }
    ],
)
async def test_step_geography_by_name(hass, config, setup_airvisual):
    """Test setting up a geography entry by city/state/country."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={"type": INTEGRATION_TYPE_GEOGRAPHY_NAME},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=config
    )

    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["title"] == "Cloud API (Beijing, Beijing, China)"
    assert result["data"] == {
        CONF_API_KEY: "abcde12345",
        CONF_CITY: "Beijing",
        CONF_STATE: "Beijing",
        CONF_COUNTRY: "China",
        CONF_INTEGRATION_TYPE: INTEGRATION_TYPE_GEOGRAPHY_NAME,
    }


@pytest.mark.parametrize(
    "config",
    [
        {
            CONF_IP_ADDRESS: "192.168.1.100",
            CONF_PASSWORD: "my_password",
        }
    ],
)
async def test_step_node_pro(hass, config, setup_airvisual):
    """Test the Node/Pro step."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data={"type": "AirVisual Node/Pro"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=config
    )
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["title"] == "Node/Pro (192.168.1.100)"
    assert result["data"] == {
        CONF_IP_ADDRESS: "192.168.1.100",
        CONF_PASSWORD: "my_password",
        CONF_INTEGRATION_TYPE: INTEGRATION_TYPE_NODE_PRO,
    }


async def test_step_reauth(hass, config_entry, setup_airvisual):
    """Test that the reauth step works."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_REAUTH}, data=config_entry.data
    )
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    new_api_key = "defgh67890"

    with patch(
        "homeassistant.components.airvisual.async_setup_entry", return_value=True
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_API_KEY: new_api_key}
        )
        assert result["type"] == data_entry_flow.FlowResultType.ABORT
        assert result["reason"] == "reauth_successful"

    assert len(hass.config_entries.async_entries()) == 1
    assert hass.config_entries.async_entries()[0].data[CONF_API_KEY] == new_api_key


async def test_step_user(hass):
    """Test the user ("pick the integration type") step."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={"type": INTEGRATION_TYPE_GEOGRAPHY_COORDS},
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "geography_by_coords"

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={"type": INTEGRATION_TYPE_GEOGRAPHY_NAME},
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "geography_by_name"

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={"type": INTEGRATION_TYPE_NODE_PRO},
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "node_pro"
