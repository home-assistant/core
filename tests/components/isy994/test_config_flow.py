"""Test the Universal Devices ISY994 config flow."""

from unittest.mock import patch

from homeassistant import config_entries, data_entry_flow, setup
from homeassistant.components import ssdp
from homeassistant.components.isy994.config_flow import CannotConnect
from homeassistant.components.isy994.const import (
    CONF_IGNORE_STRING,
    CONF_RESTORE_LIGHT_STATE,
    CONF_SENSOR_STRING,
    CONF_TLS_VER,
    CONF_VAR_SENSOR_STRING,
    DOMAIN,
    ISY_URL_POSTFIX,
    UDN_UUID_PREFIX,
)
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_SSDP
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

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
MOCK_IMPORT_WITH_SSL = {
    CONF_HOST: f"https://{MOCK_HOSTNAME}",
    CONF_USERNAME: MOCK_USERNAME,
    CONF_PASSWORD: MOCK_PASSWORD,
    CONF_TLS_VER: MOCK_TLS_VERSION,
}
MOCK_IMPORT_BASIC_CONFIG = {
    CONF_HOST: f"http://{MOCK_HOSTNAME}",
    CONF_USERNAME: MOCK_USERNAME,
    CONF_PASSWORD: MOCK_PASSWORD,
}
MOCK_IMPORT_FULL_CONFIG = {
    CONF_HOST: f"http://{MOCK_HOSTNAME}",
    CONF_USERNAME: MOCK_USERNAME,
    CONF_PASSWORD: MOCK_PASSWORD,
    CONF_IGNORE_STRING: MOCK_IGNORE_STRING,
    CONF_RESTORE_LIGHT_STATE: MOCK_RESTORE_LIGHT_STATE,
    CONF_SENSOR_STRING: MOCK_SENSOR_STRING,
    CONF_TLS_VER: MOCK_TLS_VERSION,
    CONF_VAR_SENSOR_STRING: MOCK_VARIABLE_SENSOR_STRING,
}

MOCK_DEVICE_NAME = "Name of the device"
MOCK_UUID = "CE:FB:72:31:B7:B9"
MOCK_VALIDATED_RESPONSE = {"name": MOCK_DEVICE_NAME, "uuid": MOCK_UUID}

PATCH_CONFIGURATION = "homeassistant.components.isy994.config_flow.Configuration"
PATCH_CONNECTION = "homeassistant.components.isy994.config_flow.Connection"
PATCH_ASYNC_SETUP = "homeassistant.components.isy994.async_setup"
PATCH_ASYNC_SETUP_ENTRY = "homeassistant.components.isy994.async_setup_entry"


async def test_form(hass: HomeAssistant):
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {}

    with patch(PATCH_CONFIGURATION) as mock_config_class, patch(
        PATCH_CONNECTION
    ) as mock_connection_class, patch(
        PATCH_ASYNC_SETUP, return_value=True
    ) as mock_setup, patch(
        PATCH_ASYNC_SETUP_ENTRY,
        return_value=True,
    ) as mock_setup_entry:
        isy_conn = mock_connection_class.return_value
        isy_conn.get_config.return_value = None
        mock_config_class.return_value = MOCK_VALIDATED_RESPONSE
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            MOCK_USER_INPUT,
        )
        await hass.async_block_till_done()
    assert result2["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result2["title"] == f"{MOCK_DEVICE_NAME} ({MOCK_HOSTNAME})"
    assert result2["result"].unique_id == MOCK_UUID
    assert result2["data"] == MOCK_USER_INPUT
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_invalid_host(hass: HomeAssistant):
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

    assert result2["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result2["errors"] == {"base": "invalid_host"}


async def test_form_invalid_auth(hass: HomeAssistant):
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    with patch(PATCH_CONFIGURATION), patch(
        PATCH_CONNECTION,
        side_effect=ValueError("PyISY could not connect to the ISY."),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            MOCK_USER_INPUT,
        )

    assert result2["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_form_cannot_connect(hass: HomeAssistant):
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    with patch(PATCH_CONFIGURATION), patch(
        PATCH_CONNECTION,
        side_effect=CannotConnect,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            MOCK_USER_INPUT,
        )

    assert result2["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_existing_config_entry(hass: HomeAssistant):
    """Test if config entry already exists."""
    MockConfigEntry(domain=DOMAIN, unique_id=MOCK_UUID).add_to_hass(hass)
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {}

    with patch(PATCH_CONFIGURATION) as mock_config_class, patch(
        PATCH_CONNECTION
    ) as mock_connection_class:
        isy_conn = mock_connection_class.return_value
        isy_conn.get_config.return_value = None
        mock_config_class.return_value = MOCK_VALIDATED_RESPONSE
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            MOCK_USER_INPUT,
        )
    assert result2["type"] == data_entry_flow.RESULT_TYPE_ABORT


async def test_import_flow_some_fields(hass: HomeAssistant) -> None:
    """Test import config flow with just the basic fields."""
    with patch(PATCH_CONFIGURATION) as mock_config_class, patch(
        PATCH_CONNECTION
    ) as mock_connection_class, patch(PATCH_ASYNC_SETUP, return_value=True), patch(
        PATCH_ASYNC_SETUP_ENTRY,
        return_value=True,
    ):
        isy_conn = mock_connection_class.return_value
        isy_conn.get_config.return_value = None
        mock_config_class.return_value = MOCK_VALIDATED_RESPONSE
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data=MOCK_IMPORT_BASIC_CONFIG,
        )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["data"][CONF_HOST] == f"http://{MOCK_HOSTNAME}"
    assert result["data"][CONF_USERNAME] == MOCK_USERNAME
    assert result["data"][CONF_PASSWORD] == MOCK_PASSWORD


async def test_import_flow_with_https(hass: HomeAssistant) -> None:
    """Test import config with https."""

    with patch(PATCH_CONFIGURATION) as mock_config_class, patch(
        PATCH_CONNECTION
    ) as mock_connection_class, patch(PATCH_ASYNC_SETUP, return_value=True), patch(
        PATCH_ASYNC_SETUP_ENTRY,
        return_value=True,
    ):
        isy_conn = mock_connection_class.return_value
        isy_conn.get_config.return_value = None
        mock_config_class.return_value = MOCK_VALIDATED_RESPONSE
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data=MOCK_IMPORT_WITH_SSL,
        )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["data"][CONF_HOST] == f"https://{MOCK_HOSTNAME}"
    assert result["data"][CONF_USERNAME] == MOCK_USERNAME
    assert result["data"][CONF_PASSWORD] == MOCK_PASSWORD


async def test_import_flow_all_fields(hass: HomeAssistant) -> None:
    """Test import config flow with all fields."""
    with patch(PATCH_CONFIGURATION) as mock_config_class, patch(
        PATCH_CONNECTION
    ) as mock_connection_class, patch(PATCH_ASYNC_SETUP, return_value=True), patch(
        PATCH_ASYNC_SETUP_ENTRY,
        return_value=True,
    ):
        isy_conn = mock_connection_class.return_value
        isy_conn.get_config.return_value = None
        mock_config_class.return_value = MOCK_VALIDATED_RESPONSE
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data=MOCK_IMPORT_FULL_CONFIG,
        )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["data"][CONF_HOST] == f"http://{MOCK_HOSTNAME}"
    assert result["data"][CONF_USERNAME] == MOCK_USERNAME
    assert result["data"][CONF_PASSWORD] == MOCK_PASSWORD
    assert result["data"][CONF_IGNORE_STRING] == MOCK_IGNORE_STRING
    assert result["data"][CONF_RESTORE_LIGHT_STATE] == MOCK_RESTORE_LIGHT_STATE
    assert result["data"][CONF_SENSOR_STRING] == MOCK_SENSOR_STRING
    assert result["data"][CONF_VAR_SENSOR_STRING] == MOCK_VARIABLE_SENSOR_STRING
    assert result["data"][CONF_TLS_VER] == MOCK_TLS_VERSION


async def test_form_ssdp_already_configured(hass: HomeAssistant) -> None:
    """Test ssdp abort when the serial number is already configured."""
    await setup.async_setup_component(hass, "persistent_notification", {})

    MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: f"http://{MOCK_HOSTNAME}{ISY_URL_POSTFIX}"},
        unique_id=MOCK_UUID,
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_SSDP},
        data={
            ssdp.ATTR_SSDP_LOCATION: f"http://{MOCK_HOSTNAME}{ISY_URL_POSTFIX}",
            ssdp.ATTR_UPNP_FRIENDLY_NAME: "myisy",
            ssdp.ATTR_UPNP_UDN: f"{UDN_UUID_PREFIX}{MOCK_UUID}",
        },
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT


async def test_form_ssdp(hass: HomeAssistant):
    """Test we can setup from ssdp."""
    await setup.async_setup_component(hass, "persistent_notification", {})

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_SSDP},
        data={
            ssdp.ATTR_SSDP_LOCATION: f"http://{MOCK_HOSTNAME}{ISY_URL_POSTFIX}",
            ssdp.ATTR_UPNP_FRIENDLY_NAME: "myisy",
            ssdp.ATTR_UPNP_UDN: f"{UDN_UUID_PREFIX}{MOCK_UUID}",
        },
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    with patch(PATCH_CONFIGURATION) as mock_config_class, patch(
        PATCH_CONNECTION
    ) as mock_connection_class, patch(
        PATCH_ASYNC_SETUP, return_value=True
    ) as mock_setup, patch(
        PATCH_ASYNC_SETUP_ENTRY,
        return_value=True,
    ) as mock_setup_entry:
        isy_conn = mock_connection_class.return_value
        isy_conn.get_config.return_value = None
        mock_config_class.return_value = MOCK_VALIDATED_RESPONSE
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            MOCK_USER_INPUT,
        )
        await hass.async_block_till_done()

    assert result2["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result2["title"] == f"{MOCK_DEVICE_NAME} ({MOCK_HOSTNAME})"
    assert result2["result"].unique_id == MOCK_UUID
    assert result2["data"] == MOCK_USER_INPUT
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1
