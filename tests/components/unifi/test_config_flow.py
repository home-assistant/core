"""Test UniFi config flow."""

import socket
from unittest.mock import patch

import aiounifi

from homeassistant import config_entries, data_entry_flow, setup
from homeassistant.components.unifi.config_flow import async_discover_unifi
from homeassistant.components.unifi.const import (
    CONF_ALLOW_BANDWIDTH_SENSORS,
    CONF_ALLOW_UPTIME_SENSORS,
    CONF_BLOCK_CLIENT,
    CONF_CONTROLLER,
    CONF_DETECTION_TIME,
    CONF_DPI_RESTRICTIONS,
    CONF_IGNORE_WIRED_BUG,
    CONF_POE_CLIENTS,
    CONF_SITE_ID,
    CONF_SSID_FILTER,
    CONF_TRACK_CLIENTS,
    CONF_TRACK_DEVICES,
    CONF_TRACK_WIRED_CLIENTS,
    DOMAIN as UNIFI_DOMAIN,
)
from homeassistant.config_entries import SOURCE_REAUTH, SOURCE_USER
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    CONTENT_TYPE_JSON,
)

from .test_controller import setup_unifi_integration

from tests.common import MockConfigEntry

CLIENTS = [{"mac": "00:00:00:00:00:01"}]

DEVICES = [
    {
        "board_rev": 21,
        "device_id": "mock-id",
        "ip": "10.0.1.1",
        "last_seen": 0,
        "mac": "00:00:00:00:01:01",
        "model": "U7PG2",
        "name": "access_point",
        "state": 1,
        "type": "uap",
        "version": "4.0.80.10875",
        "wlan_overrides": [
            {
                "name": "SSID 3",
                "radio": "na",
                "radio_name": "wifi1",
                "wlan_id": "012345678910111213141516",
            },
            {
                "name": "",
                "radio": "na",
                "radio_name": "wifi1",
                "wlan_id": "012345678910111213141516",
            },
            {
                "radio": "na",
                "radio_name": "wifi1",
                "wlan_id": "012345678910111213141516",
            },
        ],
    }
]

WLANS = [
    {"name": "SSID 1"},
    {"name": "SSID 2", "name_combine_enabled": False, "name_combine_suffix": "_IOT"},
]

DPI_GROUPS = [
    {
        "_id": "5ba29dd8e3c58f026e9d7c4a",
        "name": "Default",
        "site_id": "5ba29dd4e3c58f026e9d7c38",
    },
]


async def test_flow_works(hass, aioclient_mock, mock_discovery):
    """Test config flow."""
    mock_discovery.return_value = "1"
    result = await hass.config_entries.flow.async_init(
        UNIFI_DOMAIN, context={"source": "user"}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"
    assert result["data_schema"]({CONF_USERNAME: "", CONF_PASSWORD: ""}) == {
        CONF_HOST: "unifi",
        CONF_USERNAME: "",
        CONF_PASSWORD: "",
        CONF_PORT: 443,
        CONF_VERIFY_SSL: False,
    }

    aioclient_mock.get("https://1.2.3.4:1234", status=302)

    aioclient_mock.post(
        "https://1.2.3.4:1234/api/login",
        json={"data": "login successful", "meta": {"rc": "ok"}},
        headers={"content-type": CONTENT_TYPE_JSON},
    )

    aioclient_mock.get(
        "https://1.2.3.4:1234/api/self/sites",
        json={
            "data": [
                {"desc": "Site name", "name": "site_id", "role": "admin", "_id": "1"}
            ],
            "meta": {"rc": "ok"},
        },
        headers={"content-type": CONTENT_TYPE_JSON},
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

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "Site name"
    assert result["data"] == {
        CONF_HOST: "1.2.3.4",
        CONF_USERNAME: "username",
        CONF_PASSWORD: "password",
        CONF_PORT: 1234,
        CONF_SITE_ID: "site_id",
        CONF_VERIFY_SSL: True,
        CONF_CONTROLLER: {
            CONF_HOST: "1.2.3.4",
            CONF_USERNAME: "username",
            CONF_PASSWORD: "password",
            CONF_PORT: 1234,
            CONF_SITE_ID: "site_id",
            CONF_VERIFY_SSL: True,
        },
    }


async def test_flow_works_negative_discovery(hass, aioclient_mock, mock_discovery):
    """Test config flow with a negative outcome of async_discovery_unifi."""
    result = await hass.config_entries.flow.async_init(
        UNIFI_DOMAIN, context={"source": "user"}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"
    assert result["data_schema"]({CONF_USERNAME: "", CONF_PASSWORD: ""}) == {
        CONF_HOST: "",
        CONF_USERNAME: "",
        CONF_PASSWORD: "",
        CONF_PORT: 443,
        CONF_VERIFY_SSL: False,
    }


async def test_flow_multiple_sites(hass, aioclient_mock):
    """Test config flow works when finding multiple sites."""
    result = await hass.config_entries.flow.async_init(
        UNIFI_DOMAIN, context={"source": "user"}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"

    aioclient_mock.get("https://1.2.3.4:1234", status=302)

    aioclient_mock.post(
        "https://1.2.3.4:1234/api/login",
        json={"data": "login successful", "meta": {"rc": "ok"}},
        headers={"content-type": CONTENT_TYPE_JSON},
    )

    aioclient_mock.get(
        "https://1.2.3.4:1234/api/self/sites",
        json={
            "data": [
                {"name": "default", "role": "admin", "desc": "site name", "_id": "1"},
                {"name": "site2", "role": "admin", "desc": "site2 name", "_id": "2"},
            ],
            "meta": {"rc": "ok"},
        },
        headers={"content-type": CONTENT_TYPE_JSON},
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

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "site"
    assert result["data_schema"]({"site": "1"})
    assert result["data_schema"]({"site": "2"})


async def test_flow_raise_already_configured(hass, aioclient_mock):
    """Test config flow aborts since a connected config entry already exists."""
    await setup_unifi_integration(hass, aioclient_mock)

    result = await hass.config_entries.flow.async_init(
        UNIFI_DOMAIN, context={"source": "user"}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"

    aioclient_mock.clear_requests()

    aioclient_mock.get("https://1.2.3.4:1234", status=302)

    aioclient_mock.post(
        "https://1.2.3.4:1234/api/login",
        json={"data": "login successful", "meta": {"rc": "ok"}},
        headers={"content-type": CONTENT_TYPE_JSON},
    )

    aioclient_mock.get(
        "https://1.2.3.4:1234/api/self/sites",
        json={
            "data": [
                {"desc": "Site name", "name": "site_id", "role": "admin", "_id": "1"}
            ],
            "meta": {"rc": "ok"},
        },
        headers={"content-type": CONTENT_TYPE_JSON},
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

    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"


async def test_flow_aborts_configuration_updated(hass, aioclient_mock):
    """Test config flow aborts since a connected config entry already exists."""
    entry = MockConfigEntry(
        domain=UNIFI_DOMAIN, data={"host": "1.2.3.4", "site": "office"}, unique_id="2"
    )
    entry.add_to_hass(hass)

    entry = MockConfigEntry(
        domain=UNIFI_DOMAIN, data={"host": "1.2.3.4", "site": "site_id"}, unique_id="1"
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        UNIFI_DOMAIN, context={"source": "user"}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"

    aioclient_mock.get("https://1.2.3.4:1234", status=302)

    aioclient_mock.post(
        "https://1.2.3.4:1234/api/login",
        json={"data": "login successful", "meta": {"rc": "ok"}},
        headers={"content-type": CONTENT_TYPE_JSON},
    )

    aioclient_mock.get(
        "https://1.2.3.4:1234/api/self/sites",
        json={
            "data": [
                {"desc": "Site name", "name": "site_id", "role": "admin", "_id": "1"}
            ],
            "meta": {"rc": "ok"},
        },
        headers={"content-type": CONTENT_TYPE_JSON},
    )

    with patch("homeassistant.components.unifi.async_setup_entry"):
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

    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "configuration_updated"


async def test_flow_fails_user_credentials_faulty(hass, aioclient_mock):
    """Test config flow."""
    result = await hass.config_entries.flow.async_init(
        UNIFI_DOMAIN, context={"source": "user"}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"

    aioclient_mock.get("https://1.2.3.4:1234", status=302)

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

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {"base": "faulty_credentials"}


async def test_flow_fails_controller_unavailable(hass, aioclient_mock):
    """Test config flow."""
    result = await hass.config_entries.flow.async_init(
        UNIFI_DOMAIN, context={"source": "user"}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"

    aioclient_mock.get("https://1.2.3.4:1234", status=302)

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

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {"base": "service_unavailable"}


async def test_reauth_flow_update_configuration(hass, aioclient_mock):
    """Verify reauth flow can update controller configuration."""
    config_entry = await setup_unifi_integration(hass, aioclient_mock)
    controller = hass.data[UNIFI_DOMAIN][config_entry.entry_id]
    controller.available = False

    result = await hass.config_entries.flow.async_init(
        UNIFI_DOMAIN,
        context={
            "source": SOURCE_REAUTH,
            "unique_id": config_entry.unique_id,
            "entry_id": config_entry.entry_id,
        },
        data=config_entry.data,
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == SOURCE_USER

    aioclient_mock.clear_requests()

    aioclient_mock.get("https://1.2.3.4:1234", status=302)

    aioclient_mock.post(
        "https://1.2.3.4:1234/api/login",
        json={"data": "login successful", "meta": {"rc": "ok"}},
        headers={"content-type": CONTENT_TYPE_JSON},
    )

    aioclient_mock.get(
        "https://1.2.3.4:1234/api/self/sites",
        json={
            "data": [
                {"desc": "Site name", "name": "site_id", "role": "admin", "_id": "1"}
            ],
            "meta": {"rc": "ok"},
        },
        headers={"content-type": CONTENT_TYPE_JSON},
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_HOST: "1.2.3.4",
            CONF_USERNAME: "new_name",
            CONF_PASSWORD: "new_pass",
            CONF_PORT: 1234,
            CONF_VERIFY_SSL: True,
        },
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "reauth_successful"
    assert config_entry.data[CONF_HOST] == "1.2.3.4"
    assert config_entry.data[CONF_USERNAME] == "new_name"
    assert config_entry.data[CONF_PASSWORD] == "new_pass"


async def test_advanced_option_flow(hass, aioclient_mock):
    """Test advanced config flow options."""
    config_entry = await setup_unifi_integration(
        hass,
        aioclient_mock,
        clients_response=CLIENTS,
        devices_response=DEVICES,
        wlans_response=WLANS,
        dpigroup_response=DPI_GROUPS,
        dpiapp_response=[],
    )

    result = await hass.config_entries.options.async_init(
        config_entry.entry_id, context={"show_advanced_options": True}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "device_tracker"
    assert set(
        result["data_schema"].schema[CONF_SSID_FILTER].options.keys()
    ).intersection(("SSID 1", "SSID 2", "SSID 2_IOT", "SSID 3"))

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_TRACK_CLIENTS: False,
            CONF_TRACK_WIRED_CLIENTS: False,
            CONF_TRACK_DEVICES: False,
            CONF_SSID_FILTER: ["SSID 1", "SSID 2_IOT", "SSID 3"],
            CONF_DETECTION_TIME: 100,
        },
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "client_control"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_BLOCK_CLIENT: [CLIENTS[0]["mac"]],
            CONF_POE_CLIENTS: False,
            CONF_DPI_RESTRICTIONS: False,
        },
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "statistics_sensors"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_ALLOW_BANDWIDTH_SENSORS: True,
            CONF_ALLOW_UPTIME_SENSORS: True,
        },
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["data"] == {
        CONF_TRACK_CLIENTS: False,
        CONF_TRACK_WIRED_CLIENTS: False,
        CONF_TRACK_DEVICES: False,
        CONF_SSID_FILTER: ["SSID 1", "SSID 2_IOT", "SSID 3"],
        CONF_DETECTION_TIME: 100,
        CONF_IGNORE_WIRED_BUG: False,
        CONF_POE_CLIENTS: False,
        CONF_DPI_RESTRICTIONS: False,
        CONF_BLOCK_CLIENT: [CLIENTS[0]["mac"]],
        CONF_ALLOW_BANDWIDTH_SENSORS: True,
        CONF_ALLOW_UPTIME_SENSORS: True,
    }


async def test_simple_option_flow(hass, aioclient_mock):
    """Test simple config flow options."""
    config_entry = await setup_unifi_integration(
        hass,
        aioclient_mock,
        clients_response=CLIENTS,
        wlans_response=WLANS,
        dpigroup_response=DPI_GROUPS,
        dpiapp_response=[],
    )

    result = await hass.config_entries.options.async_init(
        config_entry.entry_id, context={"show_advanced_options": False}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "simple_options"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_TRACK_CLIENTS: False,
            CONF_TRACK_DEVICES: False,
            CONF_BLOCK_CLIENT: [CLIENTS[0]["mac"]],
        },
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["data"] == {
        CONF_TRACK_CLIENTS: False,
        CONF_TRACK_DEVICES: False,
        CONF_BLOCK_CLIENT: [CLIENTS[0]["mac"]],
    }


async def test_form_ssdp(hass):
    """Test we get the form with ssdp source."""
    await setup.async_setup_component(hass, "persistent_notification", {})

    result = await hass.config_entries.flow.async_init(
        UNIFI_DOMAIN,
        context={"source": config_entries.SOURCE_SSDP},
        data={
            "friendlyName": "UniFi Dream Machine",
            "modelDescription": "UniFi Dream Machine Pro",
            "ssdp_location": "http://192.168.208.1:41417/rootDesc.xml",
            "serialNumber": "e0:63:da:20:14:a9",
        },
    )
    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["errors"] == {}
    context = next(
        flow["context"]
        for flow in hass.config_entries.flow.async_progress()
        if flow["flow_id"] == result["flow_id"]
    )
    assert context["title_placeholders"] == {
        "host": "192.168.208.1",
        "site": "default",
    }


async def test_form_ssdp_aborts_if_host_already_exists(hass):
    """Test we abort if the host is already configured."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    entry = MockConfigEntry(
        domain=UNIFI_DOMAIN,
        data={"host": "192.168.208.1", "site": "site_id"},
    )
    entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        UNIFI_DOMAIN,
        context={"source": config_entries.SOURCE_SSDP},
        data={
            "friendlyName": "UniFi Dream Machine",
            "modelDescription": "UniFi Dream Machine Pro",
            "ssdp_location": "http://192.168.208.1:41417/rootDesc.xml",
            "serialNumber": "e0:63:da:20:14:a9",
        },
    )
    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"


async def test_form_ssdp_aborts_if_serial_already_exists(hass):
    """Test we abort if the serial is already configured."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    entry = MockConfigEntry(
        domain=UNIFI_DOMAIN,
        data={"controller": {"host": "1.2.3.4", "site": "site_id"}},
        unique_id="e0:63:da:20:14:a9",
    )
    entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        UNIFI_DOMAIN,
        context={"source": config_entries.SOURCE_SSDP},
        data={
            "friendlyName": "UniFi Dream Machine",
            "modelDescription": "UniFi Dream Machine Pro",
            "ssdp_location": "http://192.168.208.1:41417/rootDesc.xml",
            "serialNumber": "e0:63:da:20:14:a9",
        },
    )
    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"


async def test_form_ssdp_gets_form_with_ignored_entry(hass):
    """Test we can still setup if there is an ignored entry."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    entry = MockConfigEntry(
        domain=UNIFI_DOMAIN,
        data={"not_controller_key": None},
        source=config_entries.SOURCE_IGNORE,
    )
    entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        UNIFI_DOMAIN,
        context={"source": config_entries.SOURCE_SSDP},
        data={
            "friendlyName": "UniFi Dream Machine New",
            "modelDescription": "UniFi Dream Machine Pro",
            "ssdp_location": "http://1.2.3.4:41417/rootDesc.xml",
            "serialNumber": "e0:63:da:20:14:a9",
        },
    )
    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["errors"] == {}
    context = next(
        flow["context"]
        for flow in hass.config_entries.flow.async_progress()
        if flow["flow_id"] == result["flow_id"]
    )
    assert context["title_placeholders"] == {
        "host": "1.2.3.4",
        "site": "default",
    }


async def test_discover_unifi_positive(hass):
    """Verify positive run of UniFi discovery."""
    with patch("socket.gethostbyname", return_value=True):
        assert await async_discover_unifi(hass)


async def test_discover_unifi_negative(hass):
    """Verify negative run of UniFi discovery."""
    with patch("socket.gethostbyname", side_effect=socket.gaierror):
        assert await async_discover_unifi(hass) is None
