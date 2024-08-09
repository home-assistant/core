"""Test the zabbix config flow."""

from unittest.mock import MagicMock, patch

import voluptuous as vol
from zabbix_utils import APIRequestError, ProcessingError

from homeassistant.components.zabbix.config_flow import (
    ZabbixConfigFlow,
    create_hostname,
    create_template,
)
from homeassistant.components.zabbix.const import (
    ALL_ZABBIX_HOSTS,
    CONF_ADD_ANOTHER_SENSOR,
    CONF_PUBLISH_STATES_HOST,
    CONF_SENSOR_TRIGGERS_HOSTIDS,
    CONF_SENSOR_TRIGGERS_INDIVIDUAL,
    CONF_SENSOR_TRIGGERS_NAME,
    CONF_SKIP_CREATION_PUBLISH_STATES_HOST,
    CONF_USE_API,
    CONF_USE_SENDER,
    CONF_USE_SENSORS,
    CONF_USE_TOKEN,
    DEFAULT_PUBLISH_STATES_HOST,
    DOMAIN,
    NEW_CONFIG,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import (
    CONF_PASSWORD,
    CONF_TOKEN,
    CONF_URL,
    CONF_USERNAME,
    STATE_ON,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.entityfilter import CONF_INCLUDE_ENTITIES

from .const import (
    MOCK_BAD_TOKEN,
    MOCK_GOOD_TOKEN,
    MOCK_PASSWORD,
    MOCK_PUBLISH_STATES_HOST,
    MOCK_URL,
    MOCK_USERNAME,
)


def get_default(schema, key):
    """Get default value for key in voluptuous schema."""

    for k in schema:
        if k == key:
            if k.default is None:
                return None
            return k.default()
    # Wanted key absent from schema
    raise KeyError("Key not found in voluptuous schema.")


async def test_async_step_user_abort(hass: HomeAssistant) -> None:
    """Test the step user config flow is aborted."""

    # Test that config via UI is not allowed if configuration.yaml is used (NEW_CONFIG=False)
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][NEW_CONFIG] = False
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "configuration_yaml_used"


async def test_async_step_user(hass: HomeAssistant) -> None:
    """Test the step user config flow."""

    # Test that the user form is served with no input.
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "user"
    assert result.get("errors") == {}

    # Test if neither Use API or Use Sender is selected
    result2 = await hass.config_entries.flow.async_configure(
        result.get("flow_id", ""),
        user_input={CONF_URL: MOCK_URL, CONF_USE_API: False, CONF_USE_SENDER: False},
    )
    assert result2.get("type") is FlowResultType.FORM
    assert result2.get("step_id") == "user"
    assert result2.get("errors") == {"base": "api_or_sender"}

    # Test if Use API is selected but cannot_connect error is rased by ZabbixAPI
    with patch(
        "homeassistant.components.zabbix.config_flow.ZabbixAPI",
        side_effect=ProcessingError("processing error"),
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result.get("flow_id", ""),
            user_input={CONF_URL: MOCK_URL, CONF_USE_API: True, CONF_USE_SENDER: True},
        )
        assert result3.get("type") is FlowResultType.FORM
        assert result3.get("step_id") == "user"
        assert result3.get("errors") == {"base": "cannot_connect"}

    # Test if Use API is selected and ZabbixAPI versions >=5.4
    with patch(
        "homeassistant.components.zabbix.config_flow.ZabbixAPI"
    ) as MockZabbixAPI:
        mock_instance = MockZabbixAPI.return_value
        mock_instance.version = 5.4
        result4 = await hass.config_entries.flow.async_configure(
            result.get("flow_id", ""),
            user_input={CONF_URL: MOCK_URL, CONF_USE_API: True, CONF_USE_SENDER: True},
        )
        assert result4.get("type") is FlowResultType.FORM
        assert result4.get("step_id") == "token_or_userpass"
        assert result4.get("errors") == {}

    # Test if Use API is selected and ZabbixAPI versions < 5.4
    # restart step_user flow as we left it already
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    with patch(
        "homeassistant.components.zabbix.config_flow.ZabbixAPI",
    ) as MockZabbixAPI:
        mock_instance = MockZabbixAPI.return_value
        mock_instance.version = 5.3
        result5 = await hass.config_entries.flow.async_configure(
            result.get("flow_id", ""),
            user_input={CONF_URL: MOCK_URL, CONF_USE_API: True, CONF_USE_SENDER: True},
        )
        assert result5.get("type") is FlowResultType.FORM
        assert result5.get("step_id") == "userpass"
        assert result5.get("errors") == {}

    # Test if Use API is not selected but Use Sender is selected
    # restart step_user flow as we left it already

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result6 = await hass.config_entries.flow.async_configure(
        result.get("flow_id", ""),
        user_input={CONF_URL: MOCK_URL, CONF_USE_API: False, CONF_USE_SENDER: True},
    )
    assert result6.get("type") is FlowResultType.FORM
    assert result6.get("step_id") == "publish_states_host_no_api"
    assert result6.get("errors") == {}


async def test_async_step_token_or_userpass(hass: HomeAssistant) -> None:
    """Test step token_or_userpass config flow."""

    # Test that the user form is served with no input.
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "token_or_userpass"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "token_or_userpass"
    assert result["errors"] == {}

    # Test if Use Token is True
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_USE_TOKEN: True},
    )
    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "token"
    assert result2["errors"] == {}

    # Test if Use Token is False
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "token_or_userpass"}
    )
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_USE_TOKEN: False},
    )
    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "userpass"
    assert result2["errors"] == {}


async def test_async_step_token(hass: HomeAssistant) -> None:
    """Test step token config flow."""

    # Test that the user form is served with no input.
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "token"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "token"
    assert result["errors"] == {}

    # Test if Token is not valid
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_TOKEN: MOCK_BAD_TOKEN},
    )
    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "token"
    assert result2["errors"] == {CONF_TOKEN: "token_length_invalid"}

    # Test is ZabbixAPI error on token step
    with (
        patch(
            "homeassistant.components.zabbix.config_flow.ZabbixAPI",
        ) as MockZabbixAPI,
    ):
        mock_instance_api = MockZabbixAPI.return_value
        mock_instance_api.check_auth = MagicMock(
            side_effect=APIRequestError("login error")
        )
        # To stay on next step only
        ZabbixConfigFlow.data = {CONF_USE_TOKEN: True}
        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_TOKEN: MOCK_GOOD_TOKEN},
        )
        assert result3["type"] is FlowResultType.FORM
        assert result3["step_id"] == "token"
        assert result3["errors"] == {"base": "invalid_auth"}

    # Test if no login error with token, and moved to other step
    with (
        patch(
            "homeassistant.components.zabbix.config_flow.ZabbixAPI",
        ) as MockZabbixAPI,
    ):
        # to stay in 'publish_states_host' only after token step
        ZabbixConfigFlow.data = {CONF_USE_SENDER: True, CONF_USE_TOKEN: True}
        mock_instance_api = MockZabbixAPI.return_value
        mock_instance_api.template.get = MagicMock(
            side_effect=APIRequestError("login error"),
            return_value=[],
        )

        result4 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_TOKEN: MOCK_GOOD_TOKEN},
        )
        assert result4["type"] is FlowResultType.FORM
        assert result4["step_id"] == "publish_states_host"
        assert result4["errors"] == {}


async def test_async_step_userpass(hass: HomeAssistant) -> None:
    """Test step userpass config flow."""

    # Test that the user form is served with no input.
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "userpass"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "userpass"
    assert result["errors"] == {}

    with (
        patch(
            "homeassistant.components.zabbix.config_flow.ZabbixAPI",
        ) as MockZabbixAPI,
    ):
        mock_instance_api = MockZabbixAPI.return_value
        mock_instance_api.check_auth = MagicMock(
            side_effect=APIRequestError("login error")
        )
        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_USERNAME: MOCK_USERNAME, CONF_PASSWORD: MOCK_PASSWORD},
        )
        assert result3["type"] is FlowResultType.FORM
        assert result3["step_id"] == "userpass"
        assert result3["errors"] == {"base": "invalid_auth"}

    with (
        patch(
            "homeassistant.components.zabbix.config_flow.ZabbixAPI",
        ) as MockZabbixAPI,
    ):
        mock_instance_api = MockZabbixAPI.return_value
        mock_instance_api.template.get = MagicMock(
            return_value=[], side_effect=APIRequestError("login error")
        )
        # to stay in 'publish_states_host' after token step
        ZabbixConfigFlow.data = {CONF_USE_SENDER: True}
        result4 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_USERNAME: MOCK_USERNAME, CONF_PASSWORD: MOCK_PASSWORD},
        )
        assert result4["type"] is FlowResultType.FORM
        assert result4["step_id"] == "publish_states_host"
        assert result4["errors"] == {}


async def test_async_step_publish_states_host(hass: HomeAssistant) -> None:
    """Test step publish_states_host config flow."""

    # Test that the user form is served with no input and if not using sender is forwarded to next step directly
    with (
        patch(
            "homeassistant.components.zabbix.config_flow.ZabbixAPI",
        ) as MockZabbixAPI,
    ):
        mock_instance_api = MockZabbixAPI.return_value
        mock_instance_api.check_auth = MagicMock(
            side_effect=APIRequestError("login error")
        )
        ZabbixConfigFlow.data = {CONF_USE_SENDER: False}
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "publish_states_host"}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "sensor_filter"
        assert result["errors"] == {"base": "no_permission_read"}

    # Test that the user form is served with no input and with login error from ZabbixAPI.
    ZabbixConfigFlow.data = {CONF_USE_SENDER: True}
    with (
        patch(
            "homeassistant.components.zabbix.config_flow.ZabbixAPI",
        ) as MockZabbixAPI,
    ):
        mock_instance_api = MockZabbixAPI.return_value
        mock_instance_api.check_auth = MagicMock(
            side_effect=APIRequestError("login error")
        )
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "publish_states_host"}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "publish_states_host"
        assert result["errors"] == {"base": "invalid_auth"}

    # Test that the user form is served with no input and with error from ZabbixAPI on template read
    ZabbixConfigFlow.data = {CONF_USE_SENDER: True}
    with (
        patch(
            "homeassistant.components.zabbix.config_flow.ZabbixAPI",
        ) as MockZabbixAPI,
    ):
        mock_instance_api = MockZabbixAPI.return_value
        mock_instance_api.template.get = MagicMock(
            side_effect=APIRequestError("login error")
        )
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "publish_states_host"}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "publish_states_host"
        assert result["errors"] == {}
        if result.get("data_schema") is not None:
            assert isinstance(result["data_schema"], vol.Schema)
            schema = result["data_schema"].schema
            assert (
                get_default(schema, CONF_PUBLISH_STATES_HOST)
                == DEFAULT_PUBLISH_STATES_HOST
            )
            assert get_default(schema, CONF_SKIP_CREATION_PUBLISH_STATES_HOST) is False

    # Test that the user form is served with no input and with no error from ZabbixAPI on template read
    ZabbixConfigFlow.data = {CONF_USE_SENDER: True}
    with (
        patch(
            "homeassistant.components.zabbix.config_flow.ZabbixAPI",
        ) as MockZabbixAPI,
    ):
        mock_instance_api = MockZabbixAPI.return_value
        mock_instance_api.template.get = MagicMock(
            return_value=[{"hosts": [{"host": MOCK_PUBLISH_STATES_HOST}]}]
        )
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "publish_states_host"}
        )
        assert isinstance(result, dict)
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "publish_states_host"
        assert result["errors"] == {}
        if result.get("data_schema") is not None:
            assert isinstance(result["data_schema"], vol.Schema)
            schema = result["data_schema"].schema
            assert (
                get_default(schema, CONF_PUBLISH_STATES_HOST)
                == MOCK_PUBLISH_STATES_HOST
            )
            assert get_default(schema, CONF_SKIP_CREATION_PUBLISH_STATES_HOST) is True

    # Test that the user form is served with input and skip creation public states host
    ZabbixConfigFlow.data = {CONF_USE_SENDER: True}
    with (
        patch(
            "homeassistant.components.zabbix.config_flow.ZabbixAPI",
        ) as MockZabbixAPI,
    ):
        mock_instance_api = MockZabbixAPI.return_value
        mock_instance_api.template.get = MagicMock(
            return_value=[{"hosts": [{"host": "zabbix_host"}]}]
        )
        result1 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_SKIP_CREATION_PUBLISH_STATES_HOST: True},
        )
        assert result1["type"] is FlowResultType.FORM
        assert result1["step_id"] == "include_exclude_filter"
        assert result1["errors"] == {}

    # Test that the user form is served with input and no skip creation public states host, but with host.get ZabbixAPI error
    ZabbixConfigFlow.data = {CONF_USE_SENDER: True}
    with (
        patch(
            "homeassistant.components.zabbix.config_flow.ZabbixAPI",
        ) as MockZabbixAPI,
    ):
        mock_instance_api = MockZabbixAPI.return_value
        mock_instance_api.host.get = MagicMock(
            side_effect=APIRequestError("login error")
        )
        mock_instance_api.template.get = MagicMock(
            return_value=[{"hosts": [{"host": MOCK_PUBLISH_STATES_HOST}]}]
        )
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "publish_states_host"}
        )
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_SKIP_CREATION_PUBLISH_STATES_HOST: False,
                CONF_PUBLISH_STATES_HOST: MOCK_PUBLISH_STATES_HOST,
            },
        )
        assert result2["type"] is FlowResultType.FORM
        assert result2["step_id"] == "publish_states_host"
        assert result2["errors"] == {"base": "no_permission_read"}

    # Test that the user form is served with input and no skip creation public states host, but without host.get ZabbixAPI error
    ZabbixConfigFlow.data = {CONF_USE_SENDER: True}
    with (
        patch(
            "homeassistant.components.zabbix.config_flow.ZabbixAPI",
        ) as MockZabbixAPI,
    ):
        mock_instance_api = MockZabbixAPI.return_value
        mock_instance_api.host.get = MagicMock(return_value=[{"host": "zabbix_host"}])
        mock_instance_api.template.get = MagicMock(
            return_value=[{"hosts": [{"host": MOCK_PUBLISH_STATES_HOST}]}]
        )
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "publish_states_host"}
        )
        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_SKIP_CREATION_PUBLISH_STATES_HOST: False,
                CONF_PUBLISH_STATES_HOST: MOCK_PUBLISH_STATES_HOST,
            },
        )
        assert result3["type"] is FlowResultType.FORM
        assert result3["step_id"] == "include_exclude_filter"
        assert result3["errors"] == {}

    # Test that the user form is served with input and no skip creation public states host, and try to create template but error
    ZabbixConfigFlow.data = {CONF_USE_SENDER: True}
    with (
        patch(
            "homeassistant.components.zabbix.config_flow.ZabbixAPI",
        ) as MockZabbixAPI,
        patch(
            "homeassistant.components.zabbix.config_flow.create_template",
            side_effect=APIRequestError("write error"),
        ),
    ):
        mock_instance_api = MockZabbixAPI.return_value
        mock_instance_api.host.get = MagicMock(side_effect=IndexError("index error"))
        mock_instance_api.template.get = MagicMock(
            return_value=[{"hosts": [{"host": "zabbix_host"}]}]
        )
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "publish_states_host"}
        )
        result4 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_SKIP_CREATION_PUBLISH_STATES_HOST: False,
                CONF_PUBLISH_STATES_HOST: MOCK_PUBLISH_STATES_HOST,
            },
        )
        assert result4["type"] is FlowResultType.FORM
        assert result4["step_id"] == "publish_states_host"
        assert result4["errors"] == {"base": "no_permission_write"}

    # Test that the user form is served with input and no skip creation public states host,
    # and try to create template and no error, but create hostname with error
    ZabbixConfigFlow.data = {CONF_USE_SENDER: True}
    with (
        patch(
            "homeassistant.components.zabbix.config_flow.ZabbixAPI",
        ) as MockZabbixAPI,
        patch(
            "homeassistant.components.zabbix.config_flow.create_template",
            return_value=11,
        ),
        patch(
            "homeassistant.components.zabbix.config_flow.create_hostname",
            side_effect=APIRequestError("write error"),
        ),
    ):
        mock_instance_api = MockZabbixAPI.return_value
        mock_instance_api.host.get = MagicMock(side_effect=IndexError("index error"))
        mock_instance_api.template.get = MagicMock(
            return_value=[{"hosts": [{"host": "zabbix_host"}]}]
        )
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "publish_states_host"}
        )
        result5 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_SKIP_CREATION_PUBLISH_STATES_HOST: False,
                CONF_PUBLISH_STATES_HOST: MOCK_PUBLISH_STATES_HOST,
            },
        )
        assert result5["type"] is FlowResultType.FORM
        assert result5["step_id"] == "publish_states_host"
        assert result5["errors"] == {"base": "no_permission_write"}


async def test_async_step_publish_states_host_no_api(hass: HomeAssistant) -> None:
    """Test step publish_states_host_no_api config flow."""

    # Test that the user form is served with no input
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "publish_states_host_no_api"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "publish_states_host_no_api"
    assert result["errors"] == {}

    result1 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_PUBLISH_STATES_HOST: MOCK_PUBLISH_STATES_HOST,
        },
    )
    assert result1["type"] is FlowResultType.FORM
    assert result1["step_id"] == "include_exclude_filter"
    assert result1["errors"] == {}


async def test_async_step_include_exclude_filter(hass: HomeAssistant) -> None:
    """Test step include_exclude_filter config flow."""

    # Test that the user form is served with no input
    # with patch("homeassistant.components.zabbix.config_flow.ZabbixConfigFlow.hass.states.async_all", return_value=):

    # create some dummy state, just for hass.states.async_all() call
    hass.states.async_set("switch.ceiling", STATE_ON)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "include_exclude_filter"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "include_exclude_filter"
    assert result["errors"] == {}

    # Test is on user input forward to next step is use api
    ZabbixConfigFlow.data = {
        CONF_USE_API: True,
        ALL_ZABBIX_HOSTS: [{"value": "", "label": ""}],
    }
    result1 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_INCLUDE_ENTITIES: [],
        },
    )
    assert result1["type"] is FlowResultType.FORM
    assert result1["step_id"] == "sensor_filter"
    assert result1["errors"] == {}

    # Test is on user input and no use api config_entery is created
    ZabbixConfigFlow.data = {CONF_USE_API: False}
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "include_exclude_filter"}
    )
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_INCLUDE_ENTITIES: [],
        },
    )
    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Zabbix integration"


async def test_async_step_sensor_filter(hass: HomeAssistant) -> None:
    """Test step sensor_filter config flow."""

    # Test that the user form is served with no input but with ZabbixAPI error
    ZabbixConfigFlow.data = {CONF_USE_SENSORS: False}
    with (
        patch(
            "homeassistant.components.zabbix.config_flow.ZabbixAPI",
        ) as MockZabbixAPI,
    ):
        mock_instance_api = MockZabbixAPI.return_value
        mock_instance_api.host.get = MagicMock(
            side_effect=APIRequestError("read error")
        )
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "sensor_filter"}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "sensor_filter"
        assert result["errors"] == {"base": "no_permission_read"}

    # Test that the user form is served with no input but with no ZabbixAPI error
    ZabbixConfigFlow.data = {CONF_USE_SENSORS: True}
    with (
        patch(
            "homeassistant.components.zabbix.config_flow.ZabbixAPI",
        ) as MockZabbixAPI,
    ):
        mock_instance_api = MockZabbixAPI.return_value
        mock_instance_api.host.get = MagicMock(
            return_value=[
                {"hostid": "11", "host": "first_zabbix_host"},
                {"hostid": "22", "host": "second_zabbix_host"},
            ]
        )
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "sensor_filter"}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "sensor_filter"
        assert result["errors"] == {}

    # Test on user input with individuals set, but no hostids provided
    ZabbixConfigFlow.data = {
        ALL_ZABBIX_HOSTS: [{"value": "", "label": ""}],
    }
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "sensor_filter"}
    )
    result1 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_USE_SENSORS: True, CONF_SENSOR_TRIGGERS_INDIVIDUAL: True},
    )
    assert result1["type"] is FlowResultType.FORM
    assert result1["step_id"] == "sensor_filter"
    assert result1["errors"] == {CONF_SENSOR_TRIGGERS_HOSTIDS: "need_hostids"}

    # Test on user input with individuals set, and hostids provided, but need to add another sensor
    ZabbixConfigFlow.data = {
        ALL_ZABBIX_HOSTS: [
            {"value": "11", "label": "dummy"},
            {"value": "22", "label": "dummy2"},
        ]
    }
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "sensor_filter"}
    )
    result1 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_USE_SENSORS: True,
            CONF_SENSOR_TRIGGERS_INDIVIDUAL: True,
            CONF_SENSOR_TRIGGERS_HOSTIDS: ["11"],
            CONF_SENSOR_TRIGGERS_NAME: "dummy_trigger_name",
            CONF_ADD_ANOTHER_SENSOR: True,
        },
    )
    assert result1["type"] is FlowResultType.FORM
    assert result1["step_id"] == "sensor_filter"
    assert result1["errors"] == {}

    # Test on user input with individuals set, and hostids provided, but no need to add another sensor
    ZabbixConfigFlow.data = {
        ALL_ZABBIX_HOSTS: [
            {"value": "11", "label": "dummy"},
            {"value": "22", "label": "dummy2"},
        ]
    }
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "sensor_filter"}
    )
    result1 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_USE_SENSORS: True,
            CONF_SENSOR_TRIGGERS_INDIVIDUAL: True,
            CONF_SENSOR_TRIGGERS_HOSTIDS: ["11"],
            CONF_SENSOR_TRIGGERS_NAME: "dummy_trigger_name",
            CONF_ADD_ANOTHER_SENSOR: False,
        },
    )
    assert result1["type"] is FlowResultType.CREATE_ENTRY
    assert result1["title"] == "Zabbix integration"


async def test_create_template(hass: HomeAssistant) -> None:
    """Test create_template."""

    # Test case when template already exists and no need to create
    with (
        patch(
            "homeassistant.components.zabbix.config_flow.ZabbixAPI",
        ) as MockZabbixAPI,
    ):
        mock_instance_api = MockZabbixAPI.return_value
        mock_instance_api.template.get = MagicMock(
            return_value=[
                {"templateid": "11"},
            ]
        )
        templateid = await create_template(mock_instance_api, hass)
        assert templateid == "11"

    # Test case when template is created
    with (
        patch(
            "homeassistant.components.zabbix.config_flow.ZabbixAPI",
        ) as MockZabbixAPI,
    ):
        mock_instance_api = MockZabbixAPI.return_value
        mock_instance_api.template.get = MagicMock(
            side_effect=IndexError("index not found")
        )
        mock_instance_api.template.create = MagicMock(
            return_value={"templateids": ["11"]}
        )
        mock_instance_api.discoveryrule.create = MagicMock(
            return_value={"itemids": ["11"]}
        )
        templateid = await create_template(mock_instance_api, hass)
        assert templateid == "11"
        mock_instance_api.template.create.assert_called_once()
        mock_instance_api.discoveryrule.create.assert_called_once()
        mock_instance_api.itemprototype.create.assert_called_once()


async def test_create_hostname(hass: HomeAssistant) -> None:
    """Test create_hostname."""

    # Test case when hostname already exists and no need to create
    with (
        patch(
            "homeassistant.components.zabbix.config_flow.ZabbixAPI",
        ) as MockZabbixAPI,
    ):
        mock_instance_api = MockZabbixAPI.return_value
        mock_instance_api.hostgroup.get = MagicMock(return_value=[{"groupid": "1"}])
        mock_instance_api.host.create = MagicMock(return_value={"hostids": ["1"]})
        hostid = await create_hostname(
            mock_instance_api, hass, {CONF_PUBLISH_STATES_HOST: "testhost"}, "55"
        )
        assert hostid == "1"

    # Test case when hostname is created
    with (
        patch(
            "homeassistant.components.zabbix.config_flow.ZabbixAPI",
        ) as MockZabbixAPI,
    ):
        mock_instance_api = MockZabbixAPI.return_value
        mock_instance_api.hostgroup.get = MagicMock(
            side_effect=IndexError("index not found")
        )
        mock_instance_api.hostgroup.create = MagicMock(return_value={"groupids": ["1"]})
        mock_instance_api.host.create = MagicMock(return_value={"hostids": ["1"]})
        hostid = await create_hostname(
            mock_instance_api, hass, {CONF_PUBLISH_STATES_HOST: "testhost"}, "55"
        )
        assert hostid == "1"
        mock_instance_api.hostgroup.create.assert_called_once()
