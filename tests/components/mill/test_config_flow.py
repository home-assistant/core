"""Tests for Mill config flow."""
from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.components.mill.const import CLOUD, CONNECTION_TYPE, DOMAIN, LOCAL
from homeassistant.const import CONF_IP_ADDRESS, CONF_PASSWORD, CONF_USERNAME
from homeassistant.data_entry_flow import RESULT_TYPE_FORM

from tests.common import MockConfigEntry


async def test_show_config_form(hass):
    """Test show configuration form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "user"


async def test_create_entry(hass):
    """Test create entry from user input."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] is None

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONNECTION_TYPE: CLOUD,
        },
    )
    assert result2["type"] == RESULT_TYPE_FORM

    with patch("mill.Mill.connect", return_value=True):
        result = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {
                CONF_USERNAME: "user",
                CONF_PASSWORD: "pswd",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] == "create_entry"
    assert result["title"] == "user"
    assert result["data"] == {
        CONF_USERNAME: "user",
        CONF_PASSWORD: "pswd",
        CONNECTION_TYPE: CLOUD,
    }


async def test_flow_entry_already_exists(hass):
    """Test user input for config_entry that already exists."""

    test_data = {
        CONF_USERNAME: "user",
        CONF_PASSWORD: "pswd",
    }

    first_entry = MockConfigEntry(
        domain="mill",
        data=test_data,
        unique_id=test_data[CONF_USERNAME],
    )
    first_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] is None

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONNECTION_TYPE: CLOUD,
        },
    )
    assert result2["type"] == RESULT_TYPE_FORM

    with patch("mill.Mill.connect", return_value=True):
        result = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            test_data,
        )
        await hass.async_block_till_done()

    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"


async def test_connection_error(hass):
    """Test connection error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] is None

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONNECTION_TYPE: CLOUD,
        },
    )
    assert result2["type"] == RESULT_TYPE_FORM

    with patch("mill.Mill.connect", return_value=False):
        result = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {
                CONF_USERNAME: "user",
                CONF_PASSWORD: "pswd",
            },
        )

    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_local_create_entry(hass):
    """Test create entry from user input."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] is None

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONNECTION_TYPE: LOCAL,
        },
    )
    assert result2["type"] == RESULT_TYPE_FORM

    test_data = {
        CONF_IP_ADDRESS: "192.168.1.59",
    }

    with patch(
        "mill_local.Mill.connect",
        return_value={
            "name": "panel heater gen. 3",
            "version": "0x210927",
            "operation_key": "",
            "status": "ok",
        },
    ):
        result = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            test_data,
        )

    test_data[CONNECTION_TYPE] = LOCAL
    assert result["type"] == "create_entry"
    assert result["title"] == test_data[CONF_IP_ADDRESS]
    assert result["data"] == test_data


async def test_local_flow_entry_already_exists(hass):
    """Test user input for config_entry that already exists."""

    test_data = {
        CONF_IP_ADDRESS: "192.168.1.59",
    }

    first_entry = MockConfigEntry(
        domain="mill",
        data=test_data,
        unique_id=test_data[CONF_IP_ADDRESS],
    )
    first_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] is None

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONNECTION_TYPE: LOCAL,
        },
    )
    assert result2["type"] == RESULT_TYPE_FORM

    test_data = {
        CONF_IP_ADDRESS: "192.168.1.59",
    }

    with patch(
        "mill_local.Mill.connect",
        return_value={
            "name": "panel heater gen. 3",
            "version": "0x210927",
            "operation_key": "",
            "status": "ok",
        },
    ):
        result = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            test_data,
        )

    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"


async def test_local_connection_error(hass):
    """Test connection error."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] is None

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONNECTION_TYPE: LOCAL,
        },
    )
    assert result2["type"] == RESULT_TYPE_FORM

    test_data = {
        CONF_IP_ADDRESS: "192.168.1.59",
    }

    with patch(
        "mill_local.Mill.connect",
        return_value=None,
    ):
        result = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            test_data,
        )

    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] == {"base": "cannot_connect"}
