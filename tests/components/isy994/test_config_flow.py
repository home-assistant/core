"""Test the Universal Devices ISY/IoX config flow."""

import re
from unittest.mock import patch

from pyisy import ISYConnectionError, ISYInvalidAuthError
import pytest

from homeassistant import config_entries
from homeassistant.components import dhcp, ssdp
from homeassistant.components.isy994.const import (
    CONF_TLS_VER,
    DOMAIN,
    ISY_URL_POSTFIX,
    UDN_UUID_PREFIX,
)
from homeassistant.config_entries import SOURCE_DHCP, SOURCE_IGNORE, SOURCE_SSDP
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

MOCK_HOSTNAME = "1.1.1.1"
MOCK_USERNAME = "test-username"
MOCK_PASSWORD = "test-password"

# Don't use the integration defaults here to make sure they're being set correctly.
MOCK_TLS_VERSION = 1.2
MOCK_IGNORE_STRING = "{IGNOREME}"
MOCK_RESTORE_LIGHT_STATE = True
MOCK_SENSOR_STRING = "IMASENSOR"
MOCK_VARIABLE_SENSOR_STRING = "HomeAssistant."

MOCK_USER_INPUT = {
    CONF_HOST: f"http://{MOCK_HOSTNAME}",
    CONF_USERNAME: MOCK_USERNAME,
    CONF_PASSWORD: MOCK_PASSWORD,
    CONF_TLS_VER: MOCK_TLS_VERSION,
}
MOCK_IOX_USER_INPUT = {
    CONF_HOST: f"http://{MOCK_HOSTNAME}:8080",
    CONF_USERNAME: MOCK_USERNAME,
    CONF_PASSWORD: MOCK_PASSWORD,
    CONF_TLS_VER: MOCK_TLS_VERSION,
}

MOCK_DEVICE_NAME = "Name of the device"
MOCK_UUID = "ce:fb:72:31:b7:b9"
MOCK_MAC = "cefb7231b7b9"
MOCK_POLISY_MAC = "000db9123456"

MOCK_CONFIG_RESPONSE = """<?xml version="1.0" encoding="UTF-8"?>
<configuration>
    <app_full_version>5.0.16C</app_full_version>
    <platform>ISY-C-994</platform>
    <root>
        <id>ce:fb:72:31:b7:b9</id>
        <name>Name of the device</name>
    </root>
    <features>
        <feature>
            <id>21040</id>
            <desc>Networking Module</desc>
            <isInstalled>true</isInstalled>
            <isAvailable>true</isAvailable>
        </feature>
    </features>
</configuration>
"""

INTEGRATION = "homeassistant.components.isy994"
PATCH_CONNECTION = f"{INTEGRATION}.config_flow.Connection.test_connection"
PATCH_ASYNC_SETUP = f"{INTEGRATION}.async_setup"
PATCH_ASYNC_SETUP_ENTRY = f"{INTEGRATION}.async_setup_entry"


def _get_schema_default(schema, key_name):
    """Iterate schema to find a key."""
    for schema_key in schema:
        if schema_key == key_name:
            return schema_key.default()
    raise KeyError(f"{key_name} not found in schema")


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with (
        patch(PATCH_CONNECTION, return_value=MOCK_CONFIG_RESPONSE),
        patch(
            PATCH_ASYNC_SETUP_ENTRY,
            return_value=True,
        ) as mock_setup_entry,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            MOCK_USER_INPUT,
        )
        await hass.async_block_till_done()
    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == f"{MOCK_DEVICE_NAME} ({MOCK_HOSTNAME})"
    assert result2["result"].unique_id == MOCK_UUID
    assert result2["data"] == MOCK_USER_INPUT
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_invalid_host(hass: HomeAssistant) -> None:
    """Test we handle invalid host."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "host": MOCK_HOSTNAME,  # Test with missing protocol (http://)
            "username": MOCK_USERNAME,
            "password": MOCK_PASSWORD,
            "tls": MOCK_TLS_VERSION,
        },
    )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_host"}


async def test_form_invalid_auth(hass: HomeAssistant) -> None:
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    with patch(
        PATCH_CONNECTION,
        side_effect=ISYInvalidAuthError(),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            MOCK_USER_INPUT,
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {CONF_PASSWORD: "invalid_auth"}


async def test_form_unknown_exeption(hass: HomeAssistant) -> None:
    """Test we handle generic exceptions."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    with patch(
        PATCH_CONNECTION,
        side_effect=Exception,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            MOCK_USER_INPUT,
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "unknown"}


async def test_form_isy_connection_error(hass: HomeAssistant) -> None:
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    with patch(
        PATCH_CONNECTION,
        side_effect=ISYConnectionError(),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            MOCK_USER_INPUT,
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_isy_parse_response_error(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test we handle poorly formatted XML response from ISY."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    with patch(
        PATCH_CONNECTION,
        return_value=MOCK_CONFIG_RESPONSE.rsplit("\n", 3)[0],  # Test with invalid XML
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            MOCK_USER_INPUT,
        )

    assert result2["type"] is FlowResultType.FORM
    assert "ISY Could not parse response, poorly formatted XML." in caplog.text


async def test_form_no_name_in_response(hass: HomeAssistant) -> None:
    """Test we handle invalid response from ISY with name not set."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    with patch(
        PATCH_CONNECTION,
        return_value=re.sub(
            r"\<name\>.*\n", "", MOCK_CONFIG_RESPONSE
        ),  # Test with <name> line removed.
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            MOCK_USER_INPUT,
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_existing_config_entry(hass: HomeAssistant) -> None:
    """Test if config entry already exists."""
    MockConfigEntry(domain=DOMAIN, unique_id=MOCK_UUID).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with patch(PATCH_CONNECTION, return_value=MOCK_CONFIG_RESPONSE):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            MOCK_USER_INPUT,
        )
    assert result2["type"] is FlowResultType.ABORT


async def test_form_ssdp_already_configured(hass: HomeAssistant) -> None:
    """Test ssdp abort when the serial number is already configured."""

    MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: f"http://{MOCK_HOSTNAME}{ISY_URL_POSTFIX}"},
        unique_id=MOCK_UUID,
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_SSDP},
        data=ssdp.SsdpServiceInfo(
            ssdp_usn="mock_usn",
            ssdp_st="mock_st",
            ssdp_location=f"http://{MOCK_HOSTNAME}{ISY_URL_POSTFIX}",
            upnp={
                ssdp.ATTR_UPNP_FRIENDLY_NAME: "myisy",
                ssdp.ATTR_UPNP_UDN: f"{UDN_UUID_PREFIX}{MOCK_UUID}",
            },
        ),
    )
    assert result["type"] is FlowResultType.ABORT


async def test_form_ssdp(hass: HomeAssistant) -> None:
    """Test we can setup from ssdp."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_SSDP},
        data=ssdp.SsdpServiceInfo(
            ssdp_usn="mock_usn",
            ssdp_st="mock_st",
            ssdp_location=f"http://{MOCK_HOSTNAME}{ISY_URL_POSTFIX}",
            upnp={
                ssdp.ATTR_UPNP_FRIENDLY_NAME: "myisy",
                ssdp.ATTR_UPNP_UDN: f"{UDN_UUID_PREFIX}{MOCK_UUID}",
            },
        ),
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    with (
        patch(PATCH_CONNECTION, return_value=MOCK_CONFIG_RESPONSE),
        patch(
            PATCH_ASYNC_SETUP_ENTRY,
            return_value=True,
        ) as mock_setup_entry,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            MOCK_USER_INPUT,
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == f"{MOCK_DEVICE_NAME} ({MOCK_HOSTNAME})"
    assert result2["result"].unique_id == MOCK_UUID
    assert result2["data"] == MOCK_USER_INPUT
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_ssdp_existing_entry(hass: HomeAssistant) -> None:
    """Test we update the ip of an existing entry from ssdp."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: f"http://{MOCK_HOSTNAME}{ISY_URL_POSTFIX}"},
        unique_id=MOCK_UUID,
    )
    entry.add_to_hass(hass)

    with patch(PATCH_CONNECTION, return_value=MOCK_CONFIG_RESPONSE):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_SSDP},
            data=ssdp.SsdpServiceInfo(
                ssdp_usn="mock_usn",
                ssdp_st="mock_st",
                ssdp_location=f"http://3.3.3.3{ISY_URL_POSTFIX}",
                upnp={
                    ssdp.ATTR_UPNP_FRIENDLY_NAME: "myisy",
                    ssdp.ATTR_UPNP_UDN: f"{UDN_UUID_PREFIX}{MOCK_UUID}",
                },
            ),
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.data[CONF_HOST] == f"http://3.3.3.3:80{ISY_URL_POSTFIX}"


async def test_form_ssdp_existing_entry_with_no_port(hass: HomeAssistant) -> None:
    """Test we update the ip of an existing entry from ssdp with no port."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: f"http://{MOCK_HOSTNAME}:1443/{ISY_URL_POSTFIX}"},
        unique_id=MOCK_UUID,
    )
    entry.add_to_hass(hass)

    with patch(PATCH_CONNECTION, return_value=MOCK_CONFIG_RESPONSE):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_SSDP},
            data=ssdp.SsdpServiceInfo(
                ssdp_usn="mock_usn",
                ssdp_st="mock_st",
                ssdp_location=f"http://3.3.3.3/{ISY_URL_POSTFIX}",
                upnp={
                    ssdp.ATTR_UPNP_FRIENDLY_NAME: "myisy",
                    ssdp.ATTR_UPNP_UDN: f"{UDN_UUID_PREFIX}{MOCK_UUID}",
                },
            ),
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.data[CONF_HOST] == f"http://3.3.3.3:80/{ISY_URL_POSTFIX}"


async def test_form_ssdp_existing_entry_with_alternate_port(
    hass: HomeAssistant,
) -> None:
    """Test we update the ip of an existing entry from ssdp with an alternate port."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: f"http://{MOCK_HOSTNAME}:1443/{ISY_URL_POSTFIX}"},
        unique_id=MOCK_UUID,
    )
    entry.add_to_hass(hass)

    with patch(PATCH_CONNECTION, return_value=MOCK_CONFIG_RESPONSE):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_SSDP},
            data=ssdp.SsdpServiceInfo(
                ssdp_usn="mock_usn",
                ssdp_st="mock_st",
                ssdp_location=f"http://3.3.3.3:1443/{ISY_URL_POSTFIX}",
                upnp={
                    ssdp.ATTR_UPNP_FRIENDLY_NAME: "myisy",
                    ssdp.ATTR_UPNP_UDN: f"{UDN_UUID_PREFIX}{MOCK_UUID}",
                },
            ),
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.data[CONF_HOST] == f"http://3.3.3.3:1443/{ISY_URL_POSTFIX}"


async def test_form_ssdp_existing_entry_no_port_https(hass: HomeAssistant) -> None:
    """Test we update the ip of an existing entry from ssdp with no port and https."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: f"https://{MOCK_HOSTNAME}/{ISY_URL_POSTFIX}"},
        unique_id=MOCK_UUID,
    )
    entry.add_to_hass(hass)

    with patch(PATCH_CONNECTION, return_value=MOCK_CONFIG_RESPONSE):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_SSDP},
            data=ssdp.SsdpServiceInfo(
                ssdp_usn="mock_usn",
                ssdp_st="mock_st",
                ssdp_location=f"https://3.3.3.3/{ISY_URL_POSTFIX}",
                upnp={
                    ssdp.ATTR_UPNP_FRIENDLY_NAME: "myisy",
                    ssdp.ATTR_UPNP_UDN: f"{UDN_UUID_PREFIX}{MOCK_UUID}",
                },
            ),
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.data[CONF_HOST] == f"https://3.3.3.3:443/{ISY_URL_POSTFIX}"


async def test_form_dhcp(hass: HomeAssistant) -> None:
    """Test we can setup from dhcp."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_DHCP},
        data=dhcp.DhcpServiceInfo(
            ip="1.2.3.4",
            hostname="isy994-ems",
            macaddress=MOCK_MAC,
        ),
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    with (
        patch(PATCH_CONNECTION, return_value=MOCK_CONFIG_RESPONSE),
        patch(
            PATCH_ASYNC_SETUP_ENTRY,
            return_value=True,
        ) as mock_setup_entry,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            MOCK_USER_INPUT,
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == f"{MOCK_DEVICE_NAME} ({MOCK_HOSTNAME})"
    assert result2["result"].unique_id == MOCK_UUID
    assert result2["data"] == MOCK_USER_INPUT
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_dhcp_with_polisy(hass: HomeAssistant) -> None:
    """Test we can setup from dhcp with polisy."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_DHCP},
        data=dhcp.DhcpServiceInfo(
            ip="1.2.3.4",
            hostname="polisy",
            macaddress=MOCK_POLISY_MAC,
        ),
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}
    assert (
        _get_schema_default(result["data_schema"].schema, CONF_HOST)
        == "http://1.2.3.4:8080"
    )

    with (
        patch(PATCH_CONNECTION, return_value=MOCK_CONFIG_RESPONSE),
        patch(
            PATCH_ASYNC_SETUP_ENTRY,
            return_value=True,
        ) as mock_setup_entry,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            MOCK_IOX_USER_INPUT,
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == f"{MOCK_DEVICE_NAME} ({MOCK_HOSTNAME})"
    assert result2["result"].unique_id == MOCK_UUID
    assert result2["data"] == MOCK_IOX_USER_INPUT
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_dhcp_with_eisy(hass: HomeAssistant) -> None:
    """Test we can setup from dhcp with eisy."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_DHCP},
        data=dhcp.DhcpServiceInfo(
            ip="1.2.3.4",
            hostname="eisy",
            macaddress=MOCK_MAC,
        ),
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}
    assert (
        _get_schema_default(result["data_schema"].schema, CONF_HOST)
        == "http://1.2.3.4:8080"
    )

    with (
        patch(PATCH_CONNECTION, return_value=MOCK_CONFIG_RESPONSE),
        patch(
            PATCH_ASYNC_SETUP_ENTRY,
            return_value=True,
        ) as mock_setup_entry,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            MOCK_IOX_USER_INPUT,
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == f"{MOCK_DEVICE_NAME} ({MOCK_HOSTNAME})"
    assert result2["result"].unique_id == MOCK_UUID
    assert result2["data"] == MOCK_IOX_USER_INPUT
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_dhcp_existing_entry(hass: HomeAssistant) -> None:
    """Test we update the ip of an existing entry from dhcp."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: f"http://{MOCK_HOSTNAME}{ISY_URL_POSTFIX}"},
        unique_id=MOCK_UUID,
    )
    entry.add_to_hass(hass)

    with patch(PATCH_CONNECTION, return_value=MOCK_CONFIG_RESPONSE):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_DHCP},
            data=dhcp.DhcpServiceInfo(
                ip="1.2.3.4",
                hostname="isy994-ems",
                macaddress=MOCK_MAC,
            ),
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.data[CONF_HOST] == f"http://1.2.3.4{ISY_URL_POSTFIX}"


async def test_form_dhcp_existing_entry_preserves_port(hass: HomeAssistant) -> None:
    """Test we update the ip of an existing entry from dhcp preserves port."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_USERNAME: "bob",
            CONF_HOST: f"http://{MOCK_HOSTNAME}:1443{ISY_URL_POSTFIX}",
        },
        unique_id=MOCK_UUID,
    )
    entry.add_to_hass(hass)

    with patch(PATCH_CONNECTION, return_value=MOCK_CONFIG_RESPONSE):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_DHCP},
            data=dhcp.DhcpServiceInfo(
                ip="1.2.3.4",
                hostname="isy994-ems",
                macaddress=MOCK_MAC,
            ),
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.data[CONF_HOST] == f"http://1.2.3.4:1443{ISY_URL_POSTFIX}"
    assert entry.data[CONF_USERNAME] == "bob"


async def test_form_dhcp_existing_ignored_entry(hass: HomeAssistant) -> None:
    """Test we handled an ignored entry from dhcp."""

    entry = MockConfigEntry(
        domain=DOMAIN, data={}, unique_id=MOCK_UUID, source=SOURCE_IGNORE
    )
    entry.add_to_hass(hass)

    with patch(PATCH_CONNECTION, return_value=MOCK_CONFIG_RESPONSE):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_DHCP},
            data=dhcp.DhcpServiceInfo(
                ip="1.2.3.4",
                hostname="isy994-ems",
                macaddress=MOCK_MAC,
            ),
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reauth(hass: HomeAssistant) -> None:
    """Test we can reauth."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_USERNAME: "bob",
            CONF_HOST: f"http://{MOCK_HOSTNAME}:1443{ISY_URL_POSTFIX}",
        },
        unique_id=MOCK_UUID,
    )
    entry.add_to_hass(hass)

    result = await entry.start_reauth_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    with patch(
        PATCH_CONNECTION,
        side_effect=ISYInvalidAuthError(),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "test-password",
            },
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"password": "invalid_auth"}

    with patch(
        PATCH_CONNECTION,
        side_effect=ISYConnectionError(),
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "test-password",
            },
        )

    assert result3["type"] is FlowResultType.FORM
    assert result3["errors"] == {"base": "cannot_connect"}

    with (
        patch(PATCH_CONNECTION, return_value=MOCK_CONFIG_RESPONSE),
        patch(
            "homeassistant.components.isy994.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result4 = await hass.config_entries.flow.async_configure(
            result3["flow_id"],
            {
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "test-password",
            },
        )
        await hass.async_block_till_done()

    assert mock_setup_entry.called
    assert result4["type"] is FlowResultType.ABORT
    assert result4["reason"] == "reauth_successful"
