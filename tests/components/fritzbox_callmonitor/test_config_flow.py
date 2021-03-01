"""Tests for fritzbox_callmonitor config flow."""
from unittest.mock import PropertyMock

from fritzconnection.core.exceptions import FritzConnectionException, FritzSecurityError
from requests.exceptions import ConnectionError as RequestsConnectionError

from homeassistant.components.fritzbox_callmonitor.config_flow import (
    RESULT_INSUFFICIENT_PERMISSIONS,
    RESULT_INVALID_AUTH,
    RESULT_MALFORMED_PREFIXES,
    RESULT_NO_DEVIES_FOUND,
)
from homeassistant.components.fritzbox_callmonitor.const import (
    CONF_PHONEBOOK,
    CONF_PREFIXES,
    DOMAIN,
    FRITZ_ATTR_NAME,
    FRITZ_ATTR_SERIAL_NUMBER,
    SERIAL_NUMBER,
)
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import (
    RESULT_TYPE_ABORT,
    RESULT_TYPE_CREATE_ENTRY,
    RESULT_TYPE_FORM,
)

from tests.common import MockConfigEntry, patch

MOCK_HOST = "fake_host"
MOCK_PORT = 1234
MOCK_USERNAME = "fake_username"
MOCK_PASSWORD = "fake_password"
MOCK_PHONEBOOK_NAME_1 = "fake_phonebook_name_1"
MOCK_PHONEBOOK_NAME_2 = "fake_phonebook_name_2"
MOCK_PHONEBOOK_ID = 0
MOCK_SERIAL_NUMBER = "fake_serial_number"
MOCK_NAME = "fake_call_monitor_name"

MOCK_USER_DATA = {
    CONF_HOST: MOCK_HOST,
    CONF_PORT: MOCK_PORT,
    CONF_PASSWORD: MOCK_PASSWORD,
    CONF_USERNAME: MOCK_USERNAME,
}
MOCK_CONFIG_ENTRY = {
    CONF_HOST: MOCK_HOST,
    CONF_PORT: MOCK_PORT,
    CONF_PASSWORD: MOCK_PASSWORD,
    CONF_USERNAME: MOCK_USERNAME,
    CONF_PREFIXES: None,
    CONF_PHONEBOOK: MOCK_PHONEBOOK_ID,
    SERIAL_NUMBER: MOCK_SERIAL_NUMBER,
}
MOCK_YAML_CONFIG = {
    CONF_HOST: MOCK_HOST,
    CONF_PORT: MOCK_PORT,
    CONF_PASSWORD: MOCK_PASSWORD,
    CONF_USERNAME: MOCK_USERNAME,
    CONF_PHONEBOOK: MOCK_PHONEBOOK_ID,
    CONF_NAME: MOCK_NAME,
}
MOCK_DEVICE_INFO = {FRITZ_ATTR_SERIAL_NUMBER: MOCK_SERIAL_NUMBER}
MOCK_PHONEBOOK_INFO_1 = {FRITZ_ATTR_NAME: MOCK_PHONEBOOK_NAME_1}
MOCK_PHONEBOOK_INFO_2 = {FRITZ_ATTR_NAME: MOCK_PHONEBOOK_NAME_2}
MOCK_UNIQUE_ID = f"{MOCK_SERIAL_NUMBER}-{MOCK_PHONEBOOK_ID}"


async def test_yaml_import(hass: HomeAssistant) -> None:
    """Test configuration.yaml import."""

    with patch(
        "homeassistant.components.fritzbox_callmonitor.base.FritzPhonebook.__init__",
        return_value=None,
    ), patch(
        "homeassistant.components.fritzbox_callmonitor.base.FritzPhonebook.phonebook_ids",
        new_callable=PropertyMock,
        return_value=[0],
    ), patch(
        "homeassistant.components.fritzbox_callmonitor.base.FritzPhonebook.phonebook_info",
        return_value=MOCK_PHONEBOOK_INFO_1,
    ), patch(
        "homeassistant.components.fritzbox_callmonitor.base.FritzPhonebook.modelname",
        return_value=MOCK_PHONEBOOK_NAME_1,
    ), patch(
        "homeassistant.components.fritzbox_callmonitor.config_flow.FritzConnection.__init__",
        return_value=None,
    ), patch(
        "homeassistant.components.fritzbox_callmonitor.config_flow.FritzConnection.call_action",
        return_value=MOCK_DEVICE_INFO,
    ), patch(
        "homeassistant.components.fritzbox_callmonitor.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data=MOCK_YAML_CONFIG,
        )

        assert result["type"] == RESULT_TYPE_CREATE_ENTRY
        assert result["title"] == MOCK_NAME
        assert result["data"] == MOCK_CONFIG_ENTRY
        assert len(mock_setup_entry.mock_calls) == 1


async def test_setup_one_phonebook(hass: HomeAssistant) -> None:
    """Test setting up manually."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "user"

    with patch(
        "homeassistant.components.fritzbox_callmonitor.base.FritzPhonebook.__init__",
        return_value=None,
    ), patch(
        "homeassistant.components.fritzbox_callmonitor.base.FritzPhonebook.phonebook_ids",
        new_callable=PropertyMock,
        return_value=[0],
    ), patch(
        "homeassistant.components.fritzbox_callmonitor.base.FritzPhonebook.phonebook_info",
        return_value=MOCK_PHONEBOOK_INFO_1,
    ), patch(
        "homeassistant.components.fritzbox_callmonitor.base.FritzPhonebook.modelname",
        return_value=MOCK_PHONEBOOK_NAME_1,
    ), patch(
        "homeassistant.components.fritzbox_callmonitor.config_flow.FritzConnection.__init__",
        return_value=None,
    ), patch(
        "homeassistant.components.fritzbox_callmonitor.config_flow.FritzConnection.call_action",
        return_value=MOCK_DEVICE_INFO,
    ), patch(
        "homeassistant.components.fritzbox_callmonitor.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=MOCK_USER_DATA
        )

    assert result["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == MOCK_PHONEBOOK_NAME_1
    assert result["data"] == MOCK_CONFIG_ENTRY
    assert len(mock_setup_entry.mock_calls) == 1


async def test_setup_multiple_phonebooks(hass: HomeAssistant) -> None:
    """Test setting up manually."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "user"

    with patch(
        "homeassistant.components.fritzbox_callmonitor.base.FritzPhonebook.__init__",
        return_value=None,
    ), patch(
        "homeassistant.components.fritzbox_callmonitor.base.FritzPhonebook.phonebook_ids",
        new_callable=PropertyMock,
        return_value=[0, 1],
    ), patch(
        "homeassistant.components.fritzbox_callmonitor.config_flow.FritzConnection.__init__",
        return_value=None,
    ), patch(
        "homeassistant.components.fritzbox_callmonitor.config_flow.FritzConnection.call_action",
        return_value=MOCK_DEVICE_INFO,
    ), patch(
        "homeassistant.components.fritzbox_callmonitor.base.FritzPhonebook.phonebook_info",
        side_effect=[MOCK_PHONEBOOK_INFO_1, MOCK_PHONEBOOK_INFO_2],
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=MOCK_USER_DATA
        )

    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "phonebook"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.fritzbox_callmonitor.base.FritzPhonebook.modelname",
        return_value=MOCK_PHONEBOOK_NAME_1,
    ), patch(
        "homeassistant.components.fritzbox_callmonitor.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_PHONEBOOK: MOCK_PHONEBOOK_NAME_2},
        )

    assert result["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == MOCK_PHONEBOOK_NAME_2
    assert result["data"] == {
        CONF_HOST: MOCK_HOST,
        CONF_PORT: MOCK_PORT,
        CONF_PASSWORD: MOCK_PASSWORD,
        CONF_USERNAME: MOCK_USERNAME,
        CONF_PREFIXES: None,
        CONF_PHONEBOOK: 1,
        SERIAL_NUMBER: MOCK_SERIAL_NUMBER,
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_setup_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle cannot connect."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    with patch(
        "homeassistant.components.fritzbox_callmonitor.base.FritzPhonebook.__init__",
        side_effect=RequestsConnectionError,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=MOCK_USER_DATA
        )

    assert result["type"] == RESULT_TYPE_ABORT
    assert result["reason"] == RESULT_NO_DEVIES_FOUND


async def test_setup_insufficient_permissions(hass: HomeAssistant) -> None:
    """Test we handle insufficient permissions."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    with patch(
        "homeassistant.components.fritzbox_callmonitor.base.FritzPhonebook.__init__",
        side_effect=FritzSecurityError,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=MOCK_USER_DATA
        )

    assert result["type"] == RESULT_TYPE_ABORT
    assert result["reason"] == RESULT_INSUFFICIENT_PERMISSIONS


async def test_setup_invalid_auth(hass: HomeAssistant) -> None:
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    with patch(
        "homeassistant.components.fritzbox_callmonitor.base.FritzPhonebook.__init__",
        side_effect=FritzConnectionException,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=MOCK_USER_DATA
        )

    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] == {"base": RESULT_INVALID_AUTH}


async def test_options_flow_correct_prefixes(hass: HomeAssistant) -> None:
    """Test config flow options."""

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=MOCK_UNIQUE_ID,
        data=MOCK_CONFIG_ENTRY,
        options={CONF_PREFIXES: None},
    )
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.fritzbox_callmonitor.async_setup_entry",
        return_value=True,
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        result = await hass.config_entries.options.async_init(config_entry.entry_id)

        assert result["type"] == RESULT_TYPE_FORM
        assert result["step_id"] == "init"

        result = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input={CONF_PREFIXES: "+49, 491234"}
        )

        assert result["type"] == RESULT_TYPE_CREATE_ENTRY
        assert config_entry.options == {CONF_PREFIXES: ["+49", "491234"]}


async def test_options_flow_incorrect_prefixes(hass: HomeAssistant) -> None:
    """Test config flow options."""

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=MOCK_UNIQUE_ID,
        data=MOCK_CONFIG_ENTRY,
        options={CONF_PREFIXES: None},
    )
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.fritzbox_callmonitor.async_setup_entry",
        return_value=True,
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        result = await hass.config_entries.options.async_init(config_entry.entry_id)

        assert result["type"] == RESULT_TYPE_FORM
        assert result["step_id"] == "init"

        result = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input={CONF_PREFIXES: ""}
        )

        assert result["type"] == RESULT_TYPE_FORM
        assert result["errors"] == {"base": RESULT_MALFORMED_PREFIXES}


async def test_options_flow_no_prefixes(hass: HomeAssistant) -> None:
    """Test config flow options."""

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=MOCK_UNIQUE_ID,
        data=MOCK_CONFIG_ENTRY,
        options={CONF_PREFIXES: None},
    )
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.fritzbox_callmonitor.async_setup_entry",
        return_value=True,
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        result = await hass.config_entries.options.async_init(config_entry.entry_id)

        assert result["type"] == RESULT_TYPE_FORM
        assert result["step_id"] == "init"

        result = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input={}
        )

        assert result["type"] == RESULT_TYPE_CREATE_ENTRY
        assert config_entry.options == {CONF_PREFIXES: None}
