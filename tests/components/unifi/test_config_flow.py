"""Test UniFi config flow."""
import aiounifi
from asynctest import patch

from homeassistant.components import unifi
from homeassistant.components.unifi import config_flow
from homeassistant.components.unifi.const import CONF_CONTROLLER, CONF_SITE_ID
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)

from tests.common import MockConfigEntry


async def test_flow_works(hass, aioclient_mock, mock_discovery):
    """Test config flow."""
    mock_discovery.return_value = "1"
    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN, context={"source": "user"}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["data_schema"]({CONF_USERNAME: "", CONF_PASSWORD: ""}) == {
        CONF_HOST: "unifi",
        CONF_USERNAME: "",
        CONF_PASSWORD: "",
        CONF_PORT: 8443,
        CONF_VERIFY_SSL: False,
    }

    aioclient_mock.post(
        "https://1.2.3.4:1234/api/login",
        json={"data": "login successful", "meta": {"rc": "ok"}},
        headers={"content-type": "application/json"},
    )

    aioclient_mock.get(
        "https://1.2.3.4:1234/api/self/sites",
        json={
            "data": [{"desc": "Site name", "name": "site_id", "role": "admin"}],
            "meta": {"rc": "ok"},
        },
        headers={"content-type": "application/json"},
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_HOST: "1.2.3.4",
            CONF_USERNAME: "username",
            CONF_PASSWORD: "password",
            CONF_PORT: 1234,
            CONF_VERIFY_SSL: True,
        },
    )

    assert result["type"] == "create_entry"
    assert result["title"] == "Site name"
    assert result["data"] == {
        CONF_CONTROLLER: {
            CONF_HOST: "1.2.3.4",
            CONF_USERNAME: "username",
            CONF_PASSWORD: "password",
            CONF_PORT: 1234,
            CONF_SITE_ID: "site_id",
            CONF_VERIFY_SSL: True,
        }
    }


async def test_flow_works_multiple_sites(hass, aioclient_mock):
    """Test config flow works when finding multiple sites."""
    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN, context={"source": "user"}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"

    aioclient_mock.post(
        "https://1.2.3.4:1234/api/login",
        json={"data": "login successful", "meta": {"rc": "ok"}},
        headers={"content-type": "application/json"},
    )

    aioclient_mock.get(
        "https://1.2.3.4:1234/api/self/sites",
        json={
            "data": [
                {"name": "default", "role": "admin", "desc": "site name"},
                {"name": "site2", "role": "admin", "desc": "site2 name"},
            ],
            "meta": {"rc": "ok"},
        },
        headers={"content-type": "application/json"},
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_HOST: "1.2.3.4",
            CONF_USERNAME: "username",
            CONF_PASSWORD: "password",
            CONF_PORT: 1234,
            CONF_VERIFY_SSL: True,
        },
    )

    assert result["type"] == "form"
    assert result["step_id"] == "site"
    assert result["data_schema"]({"site": "site name"})
    assert result["data_schema"]({"site": "site2 name"})


async def test_flow_fails_site_already_configured(hass, aioclient_mock):
    """Test config flow."""
    entry = MockConfigEntry(
        domain=unifi.DOMAIN, data={"controller": {"host": "1.2.3.4", "site": "site_id"}}
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN, context={"source": "user"}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"

    aioclient_mock.post(
        "https://1.2.3.4:1234/api/login",
        json={"data": "login successful", "meta": {"rc": "ok"}},
        headers={"content-type": "application/json"},
    )

    aioclient_mock.get(
        "https://1.2.3.4:1234/api/self/sites",
        json={
            "data": [{"desc": "Site name", "name": "site_id", "role": "admin"}],
            "meta": {"rc": "ok"},
        },
        headers={"content-type": "application/json"},
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_HOST: "1.2.3.4",
            CONF_USERNAME: "username",
            CONF_PASSWORD: "password",
            CONF_PORT: 1234,
            CONF_VERIFY_SSL: True,
        },
    )

    assert result["type"] == "abort"


async def test_flow_fails_user_credentials_faulty(hass, aioclient_mock):
    """Test config flow."""
    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN, context={"source": "user"}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"

    with patch("aiounifi.Controller.login", side_effect=aiounifi.errors.Unauthorized):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_HOST: "1.2.3.4",
                CONF_USERNAME: "username",
                CONF_PASSWORD: "password",
                CONF_PORT: 1234,
                CONF_VERIFY_SSL: True,
            },
        )

    assert result["type"] == "form"
    assert result["errors"] == {"base": "faulty_credentials"}


async def test_flow_fails_controller_unavailable(hass, aioclient_mock):
    """Test config flow."""
    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN, context={"source": "user"}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"

    with patch("aiounifi.Controller.login", side_effect=aiounifi.errors.RequestError):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_HOST: "1.2.3.4",
                CONF_USERNAME: "username",
                CONF_PASSWORD: "password",
                CONF_PORT: 1234,
                CONF_VERIFY_SSL: True,
            },
        )

    assert result["type"] == "form"
    assert result["errors"] == {"base": "service_unavailable"}


async def test_flow_fails_unknown_problem(hass, aioclient_mock):
    """Test config flow."""
    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN, context={"source": "user"}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"

    with patch("aiounifi.Controller.login", side_effect=Exception):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_HOST: "1.2.3.4",
                CONF_USERNAME: "username",
                CONF_PASSWORD: "password",
                CONF_PORT: 1234,
                CONF_VERIFY_SSL: True,
            },
        )

    assert result["type"] == "abort"


async def test_option_flow(hass):
    """Test config flow options."""
    entry = MockConfigEntry(domain=config_flow.DOMAIN, data={}, options=None)
    hass.config_entries._entries.append(entry)

    flow = await hass.config_entries.options.async_create_flow(
        entry.entry_id, context={"source": "test"}, data=None
    )

    result = await flow.async_step_init()
    assert result["type"] == "form"
    assert result["step_id"] == "device_tracker"

    result = await flow.async_step_device_tracker(
        user_input={
            config_flow.CONF_TRACK_CLIENTS: False,
            config_flow.CONF_TRACK_WIRED_CLIENTS: False,
            config_flow.CONF_TRACK_DEVICES: False,
            config_flow.CONF_DETECTION_TIME: 100,
        }
    )
    assert result["type"] == "form"
    assert result["step_id"] == "statistics_sensors"

    result = await flow.async_step_statistics_sensors(
        user_input={config_flow.CONF_ALLOW_BANDWIDTH_SENSORS: True}
    )
    assert result["type"] == "create_entry"
    assert result["data"] == {
        config_flow.CONF_TRACK_CLIENTS: False,
        config_flow.CONF_TRACK_WIRED_CLIENTS: False,
        config_flow.CONF_TRACK_DEVICES: False,
        config_flow.CONF_DETECTION_TIME: 100,
        config_flow.CONF_ALLOW_BANDWIDTH_SENSORS: True,
    }
