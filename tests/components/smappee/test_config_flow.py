"""Test the Smappee component config flow module."""
from homeassistant import data_entry_flow, setup
from homeassistant.components.smappee.const import (
    CONF_HOSTNAME,
    CONF_SERIALNUMBER,
    DOMAIN,
    ENV_CLOUD,
    ENV_LOCAL,
    TOKEN_URL,
)
from homeassistant.config_entries import SOURCE_USER, SOURCE_ZEROCONF
from homeassistant.const import CONF_CLIENT_ID, CONF_CLIENT_SECRET
from homeassistant.helpers import config_entry_oauth2_flow

from tests.async_mock import patch
from tests.common import MockConfigEntry

CLIENT_ID = "1234"
CLIENT_SECRET = "5678"


async def test_show_user_form(hass):
    """Test that the user set up form is served."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER},
    )

    assert result["step_id"] == "environment"
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM


async def test_show_user_host_form(hass):
    """Test that the host form is served after choosing the local option."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER},
    )
    assert result["step_id"] == "environment"
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"environment": ENV_LOCAL}
    )

    assert result["step_id"] == ENV_LOCAL
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM


async def test_show_zeroconf_connection_error_form(hass):
    """Test that the zeroconf confirmation form is served."""
    with patch("pysmappee.api.SmappeeLocalApi.logon", return_value=None):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_ZEROCONF},
            data={
                "host": "1.2.3.4",
                "port": 22,
                CONF_HOSTNAME: "Smappee1006000212.local.",
                "type": "_ssh._tcp.local.",
                "name": "Smappee1006000212._ssh._tcp.local.",
                "properties": {"_raw": {}},
            },
        )

        assert result["description_placeholders"] == {CONF_SERIALNUMBER: "1006000212"}
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "zeroconf_confirm"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"host": "1.2.3.4"}
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
        assert result["reason"] == "connection_error"
        assert len(hass.config_entries.async_entries(DOMAIN)) == 0


async def test_connection_error(hass):
    """Test we show user form on Smappee connection error."""
    with patch("pysmappee.api.SmappeeLocalApi.logon", return_value=None):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER},
        )
        assert result["step_id"] == "environment"
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"environment": ENV_LOCAL}
        )
        assert result["step_id"] == ENV_LOCAL
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"host": "1.2.3.4"}
        )
        assert result["reason"] == "connection_error"
        assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT


async def test_zeroconf_wrong_mdns(hass):
    """Test we abort if unsupported mDNS name is discovered."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data={
            "host": "1.2.3.4",
            "port": 22,
            CONF_HOSTNAME: "example.local.",
            "type": "_ssh._tcp.local.",
            "name": "example._ssh._tcp.local.",
            "properties": {"_raw": {}},
        },
    )

    assert result["reason"] == "invalid_mdns"
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT


async def test_full_user_wrong_mdns(hass):
    """Test we abort user flow if unsupported mDNS name got resolved."""
    with patch("pysmappee.api.SmappeeLocalApi.logon", return_value={}), patch(
        "pysmappee.api.SmappeeLocalApi.load_advanced_config",
        return_value=[{"key": "mdnsHostName", "value": "Smappee2006000212"}],
    ), patch(
        "pysmappee.api.SmappeeLocalApi.load_command_control_config", return_value=[]
    ), patch(
        "pysmappee.api.SmappeeLocalApi.load_instantaneous",
        return_value=[{"key": "phase0ActivePower", "value": 0}],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER},
        )
        assert result["step_id"] == "environment"
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"environment": ENV_LOCAL}
        )
        assert result["step_id"] == ENV_LOCAL
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"host": "1.2.3.4"}
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
        assert result["reason"] == "invalid_mdns"


async def test_user_device_exists_abort(hass):
    """Test we abort user flow if Smappee device already configured."""
    with patch("pysmappee.api.SmappeeLocalApi.logon", return_value={}), patch(
        "pysmappee.api.SmappeeLocalApi.load_advanced_config",
        return_value=[{"key": "mdnsHostName", "value": "Smappee1006000212"}],
    ), patch(
        "pysmappee.api.SmappeeLocalApi.load_command_control_config", return_value=[]
    ), patch(
        "pysmappee.api.SmappeeLocalApi.load_instantaneous",
        return_value=[{"key": "phase0ActivePower", "value": 0}],
    ):
        config_entry = MockConfigEntry(
            domain=DOMAIN,
            data={"host": "1.2.3.4"},
            unique_id="1006000212",
            source=SOURCE_USER,
        )
        config_entry.add_to_hass(hass)
        assert len(hass.config_entries.async_entries(DOMAIN)) == 1

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER},
        )
        assert result["step_id"] == "environment"
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"environment": ENV_LOCAL}
        )
        assert result["step_id"] == ENV_LOCAL
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"host": "1.2.3.4"}
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
        assert result["reason"] == "already_configured"
        assert len(hass.config_entries.async_entries(DOMAIN)) == 1


async def test_zeroconf_device_exists_abort(hass):
    """Test we abort zeroconf flow if Smappee device already configured."""
    with patch("pysmappee.api.SmappeeLocalApi.logon", return_value={}), patch(
        "pysmappee.api.SmappeeLocalApi.load_advanced_config",
        return_value=[{"key": "mdnsHostName", "value": "Smappee1006000212"}],
    ), patch(
        "pysmappee.api.SmappeeLocalApi.load_command_control_config", return_value=[]
    ), patch(
        "pysmappee.api.SmappeeLocalApi.load_instantaneous",
        return_value=[{"key": "phase0ActivePower", "value": 0}],
    ):
        config_entry = MockConfigEntry(
            domain=DOMAIN,
            data={"host": "1.2.3.4"},
            unique_id="1006000212",
            source=SOURCE_USER,
        )
        config_entry.add_to_hass(hass)

        assert len(hass.config_entries.async_entries(DOMAIN)) == 1

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_ZEROCONF},
            data={
                "host": "1.2.3.4",
                "port": 22,
                CONF_HOSTNAME: "Smappee1006000212.local.",
                "type": "_ssh._tcp.local.",
                "name": "Smappee1006000212._ssh._tcp.local.",
                "properties": {"_raw": {}},
            },
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
        assert result["reason"] == "already_configured"
        assert len(hass.config_entries.async_entries(DOMAIN)) == 1


async def test_cloud_device_exists_abort(hass):
    """Test we abort cloud flow if Smappee Cloud device already configured."""
    config_entry = MockConfigEntry(
        domain=DOMAIN, unique_id="smappeeCloud", source=SOURCE_USER,
    )
    config_entry.add_to_hass(hass)

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER},
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured_device"
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1


async def test_zeroconf_abort_if_cloud_device_exists(hass):
    """Test we abort zeroconf flow if Smappee Cloud device already configured."""
    config_entry = MockConfigEntry(
        domain=DOMAIN, unique_id="smappeeCloud", source=SOURCE_USER,
    )
    config_entry.add_to_hass(hass)

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data={
            "host": "1.2.3.4",
            "port": 22,
            CONF_HOSTNAME: "Smappee1006000212.local.",
            "type": "_ssh._tcp.local.",
            "name": "Smappee1006000212._ssh._tcp.local.",
            "properties": {"_raw": {}},
        },
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured_device"
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1


async def test_zeroconf_confirm_abort_if_cloud_device_exists(hass):
    """Test we abort zeroconf confirm flow if Smappee Cloud device already configured."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data={
            "host": "1.2.3.4",
            "port": 22,
            CONF_HOSTNAME: "Smappee1006000212.local.",
            "type": "_ssh._tcp.local.",
            "name": "Smappee1006000212._ssh._tcp.local.",
            "properties": {"_raw": {}},
        },
    )

    config_entry = MockConfigEntry(
        domain=DOMAIN, unique_id="smappeeCloud", source=SOURCE_USER,
    )
    config_entry.add_to_hass(hass)

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured_device"
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1


async def test_abort_cloud_flow_if_local_device_exists(hass):
    """Test we abort the cloud flow if a Smappee local device already configured."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={"host": "1.2.3.4"},
        unique_id="1006000212",
        source=SOURCE_USER,
    )
    config_entry.add_to_hass(hass)

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"environment": ENV_CLOUD}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured_local_device"
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1


async def test_full_user_flow(hass, aiohttp_client, aioclient_mock, current_request):
    """Check full flow."""
    assert await setup.async_setup_component(
        hass,
        DOMAIN,
        {
            DOMAIN: {CONF_CLIENT_ID: CLIENT_ID, CONF_CLIENT_SECRET: CLIENT_SECRET},
            "http": {"base_url": "https://example.com"},
        },
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"environment": ENV_CLOUD}
    )
    state = config_entry_oauth2_flow._encode_jwt(hass, {"flow_id": result["flow_id"]})

    client = await aiohttp_client(hass.http.app)
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == 200
    assert resp.headers["content-type"] == "text/html; charset=utf-8"

    aioclient_mock.post(
        TOKEN_URL["PRODUCTION"],
        json={
            "refresh_token": "mock-refresh-token",
            "access_token": "mock-access-token",
            "type": "Bearer",
            "expires_in": 60,
        },
    )

    with patch(
        "homeassistant.components.smappee.async_setup_entry", return_value=True
    ) as mock_setup:
        await hass.config_entries.flow.async_configure(result["flow_id"])

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert len(mock_setup.mock_calls) == 1


async def test_full_zeroconf_flow(hass):
    """Test the full zeroconf flow."""
    with patch("pysmappee.api.SmappeeLocalApi.logon", return_value={}), patch(
        "pysmappee.api.SmappeeLocalApi.load_advanced_config",
        return_value=[{"key": "mdnsHostName", "value": "Smappee1006000212"}],
    ), patch(
        "pysmappee.api.SmappeeLocalApi.load_command_control_config", return_value=[]
    ), patch(
        "pysmappee.api.SmappeeLocalApi.load_instantaneous",
        return_value=[{"key": "phase0ActivePower", "value": 0}],
    ), patch(
        "homeassistant.components.smappee.async_setup_entry", return_value=True
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_ZEROCONF},
            data={
                "host": "1.2.3.4",
                "port": 22,
                CONF_HOSTNAME: "Smappee1006000212.local.",
                "type": "_ssh._tcp.local.",
                "name": "Smappee1006000212._ssh._tcp.local.",
                "properties": {"_raw": {}},
            },
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "zeroconf_confirm"
        assert result["description_placeholders"] == {CONF_SERIALNUMBER: "1006000212"}

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"host": "1.2.3.4"}
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert result["title"] == "smappee1006000212"
        assert len(hass.config_entries.async_entries(DOMAIN)) == 1

        entry = hass.config_entries.async_entries(DOMAIN)[0]
        assert entry.unique_id == "1006000212"


async def test_full_user_local_flow(hass):
    """Test the full zeroconf flow."""
    with patch("pysmappee.api.SmappeeLocalApi.logon", return_value={}), patch(
        "pysmappee.api.SmappeeLocalApi.load_advanced_config",
        return_value=[{"key": "mdnsHostName", "value": "Smappee1006000212"}],
    ), patch(
        "pysmappee.api.SmappeeLocalApi.load_command_control_config", return_value=[]
    ), patch(
        "pysmappee.api.SmappeeLocalApi.load_instantaneous",
        return_value=[{"key": "phase0ActivePower", "value": 0}],
    ), patch(
        "homeassistant.components.smappee.async_setup_entry", return_value=True
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER},
        )
        assert result["step_id"] == "environment"
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["description_placeholders"] is None

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"environment": ENV_LOCAL},
        )
        assert result["step_id"] == ENV_LOCAL
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"host": "1.2.3.4"}
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert result["title"] == "smappee1006000212"
        assert len(hass.config_entries.async_entries(DOMAIN)) == 1

        entry = hass.config_entries.async_entries(DOMAIN)[0]
        assert entry.unique_id == "1006000212"
