"""Test Mikrotik setup process."""
from datetime import timedelta

import librouteros

# from homeassistant.components.mikrotik import const
from homeassistant import data_entry_flow
from homeassistant.components import mikrotik
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PASSWORD, CONF_USERNAME

from . import MOCK_HUB1, MOCK_HUB2
from .test_hub import setup_mikrotik_integration

from tests.common import MockConfigEntry

DEMO_CONFIG = {
    CONF_NAME: "Home router",
    mikrotik.const.CONF_HUBS: [MOCK_HUB1, MOCK_HUB2],
    mikrotik.const.CONF_FORCE_DHCP: False,
    mikrotik.CONF_ARP_PING: False,
    mikrotik.CONF_DETECTION_TIME: timedelta(seconds=30),
}

DEMO_CONFIG_ENTRY = {
    CONF_NAME: "Home router",
    mikrotik.const.CONF_HUBS: {
        MOCK_HUB1[CONF_HOST]: MOCK_HUB1,
        MOCK_HUB2[CONF_HOST]: MOCK_HUB2,
    },
    mikrotik.const.CONF_FORCE_DHCP: False,
    mikrotik.const.CONF_ARP_PING: False,
    mikrotik.const.CONF_DETECTION_TIME: 30,
}


async def test_import_successfull(hass, api):
    """Test import step."""
    result = await hass.config_entries.flow.async_init(
        mikrotik.DOMAIN, context={"source": "import"}, data=DEMO_CONFIG
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "Home router"
    assert result["data"][CONF_NAME] == "Home router"
    assert result["data"][mikrotik.const.CONF_HUBS][MOCK_HUB1[CONF_HOST]] == MOCK_HUB1
    assert result["data"][mikrotik.const.CONF_HUBS][MOCK_HUB2[CONF_HOST]] == MOCK_HUB2


async def test_import_conn_error(hass, api):
    """Import fails in case of connection error."""
    api.side_effect = librouteros.exceptions.LibRouterosError

    result = await hass.config_entries.flow.async_init(
        mikrotik.DOMAIN, context={"source": "import"}, data=DEMO_CONFIG
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "conn_error"


async def test_import_existing_host(hass, api):
    """Test importing existing hosts fails."""
    # if same host is mentioned the import fails
    config = {**DEMO_CONFIG, mikrotik.const.CONF_HUBS: [MOCK_HUB1, MOCK_HUB1]}

    result = await hass.config_entries.flow.async_init(
        mikrotik.DOMAIN, context={"source": "import"}, data=config
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"

    # if host is configured in a different entry then abort
    entry = MockConfigEntry(domain=mikrotik.DOMAIN, data=DEMO_CONFIG_ENTRY)
    entry.add_to_hass(hass)

    config = {**DEMO_CONFIG, mikrotik.const.CONF_HUBS: [MOCK_HUB1]}
    result = await hass.config_entries.flow.async_init(
        mikrotik.DOMAIN, context={"source": "import"}, data=config
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"


async def test_flow_works(hass, api):
    """Test config flow."""

    result = await hass.config_entries.flow.async_init(
        mikrotik.DOMAIN, context={"source": "user"}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_NAME: "Mikrotik", mikrotik.const.CONF_NUM_HUBS: 1},
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "hub"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=MOCK_HUB1
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "Mikrotik"
    assert result["data"][CONF_NAME] == "Mikrotik"
    assert result["data"][mikrotik.const.CONF_HUBS][MOCK_HUB1[CONF_HOST]] == MOCK_HUB1


async def test_flow_multiple_hubs(hass, api):
    """Test config flow with multiple hubs."""

    result = await hass.config_entries.flow.async_init(
        mikrotik.DOMAIN, context={"source": "user"}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_NAME: "Mikrotik", mikrotik.const.CONF_NUM_HUBS: 2},
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "hub"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=MOCK_HUB1
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "hub"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=MOCK_HUB2
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "Mikrotik"
    assert result["data"][CONF_NAME] == "Mikrotik"
    assert len(result["data"][mikrotik.const.CONF_HUBS]) == 2
    assert result["data"][mikrotik.const.CONF_HUBS][MOCK_HUB1[CONF_HOST]] == MOCK_HUB1
    assert result["data"][mikrotik.const.CONF_HUBS][MOCK_HUB2[CONF_HOST]] == MOCK_HUB2


async def test_entering_same_host_twice(hass, api):
    """Test entering same host twice."""
    result = await hass.config_entries.flow.async_init(
        mikrotik.DOMAIN, context={"source": "user"}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_NAME: "Mikrotik", mikrotik.const.CONF_NUM_HUBS: 2},
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "hub"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=MOCK_HUB1
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "hub"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=MOCK_HUB1
    )

    assert result["errors"] == {"host": "hub_exists"}
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "hub"


async def test_entered_host_exists(hass, api):
    """Test entered host exists in another config entry."""

    entry = MockConfigEntry(domain=mikrotik.DOMAIN, data=DEMO_CONFIG_ENTRY)
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        mikrotik.DOMAIN, context={"source": "user"}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_NAME: "Mikrotik", mikrotik.const.CONF_NUM_HUBS: 1},
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=MOCK_HUB1
    )

    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"


async def test_connection_error(hass, api):
    """Test error when connection is unsuccessful."""
    api.side_effect = librouteros.exceptions.LibRouterosError

    result = await hass.config_entries.flow.async_init(
        mikrotik.DOMAIN, context={"source": "user"}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_NAME: "Mikrotik", mikrotik.const.CONF_NUM_HUBS: 1},
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=MOCK_HUB1
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {"base": "cannot_connect"}
    assert result["step_id"] == "hub"


async def test_wrong_credentials(hass, api):
    """Test error when credentials are wrong."""

    api.side_effect = librouteros.exceptions.LibRouterosError(
        "invalid user name or password"
    )

    result = await hass.config_entries.flow.async_init(
        mikrotik.DOMAIN, context={"source": "user"}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_NAME: "Mikrotik", mikrotik.const.CONF_NUM_HUBS: 1},
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=MOCK_HUB1
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {
        CONF_USERNAME: "wrong_credentials",
        CONF_PASSWORD: "wrong_credentials",
    }
    assert result["step_id"] == "hub"


async def test_options(hass, api):
    """Test updating options."""
    mikrotik_mock = await setup_mikrotik_integration(hass)
    result = await hass.config_entries.options.async_init(
        mikrotik_mock.config_entry.entry_id
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            mikrotik.CONF_DETECTION_TIME: 30,
            mikrotik.CONF_ARP_PING: True,
            mikrotik.const.CONF_FORCE_DHCP: False,
        },
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["data"] == {
        mikrotik.CONF_DETECTION_TIME: 30,
        mikrotik.CONF_ARP_PING: True,
        mikrotik.const.CONF_FORCE_DHCP: False,
    }
