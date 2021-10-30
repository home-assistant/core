"""Define tests for the QNAP QSW config flow."""

from unittest.mock import patch

from qnap_qsw.homeassistant import LoginError
import requests_mock

from homeassistant import data_entry_flow
from homeassistant.components.qnap_qsw.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER, ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME

from .util import CONFIG, qnap_qsw_requests_mock

from tests.common import MockConfigEntry


async def test_form(hass):
    """Test that the form is served with valid input."""

    with patch(
        "homeassistant.components.qnap_qsw.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry, requests_mock.mock() as _m:
        qnap_qsw_requests_mock(_m)

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == SOURCE_USER
        assert result["errors"] == {}

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], CONFIG
        )

        await hass.async_block_till_done()

        conf_entries = hass.config_entries.async_entries(DOMAIN)
        entry = conf_entries[0]
        assert entry.state is ConfigEntryState.LOADED

        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert result["title"] == "QSW-M408-4C 1234567890"
        assert result["data"][CONF_HOST] == CONFIG[CONF_HOST]
        assert result["data"][CONF_PASSWORD] == CONFIG[CONF_PASSWORD]
        assert result["data"][CONF_USERNAME] == CONFIG[CONF_USERNAME]

        assert len(mock_setup_entry.mock_calls) == 1


async def test_form_duplicated_id(hass):
    """Test setting up duplicated entry."""

    with requests_mock.mock() as _m:
        qnap_qsw_requests_mock(_m)

        entry = MockConfigEntry(domain=DOMAIN, unique_id="1234567890", data=CONFIG)
        entry.add_to_hass(hass)

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=CONFIG
        )

        assert result["type"] == "abort"
        assert result["reason"] == "already_configured"


async def test_connection_error(hass):
    """Test connection to host error."""

    with patch(
        "homeassistant.components.qnap_qsw.config_flow.QSHA.login",
        side_effect=ConnectionError(),
    ), requests_mock.mock() as _m:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=CONFIG
        )

        assert result["errors"] == {"base": "cannot_connect"}

    with patch(
        "homeassistant.components.qnap_qsw.config_flow.QSHA.update_firmware_update_check",
        side_effect=ConnectionError(),
    ), requests_mock.mock() as _m:
        qnap_qsw_requests_mock(_m)

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == SOURCE_USER
        assert result["errors"] == {}

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], CONFIG
        )

        await hass.async_block_till_done()

        conf_entries = hass.config_entries.async_entries(DOMAIN)
        entry = conf_entries[0]
        assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_login_error(hass):
    """Test login error."""

    with patch(
        "homeassistant.components.qnap_qsw.config_flow.QSHA.login",
        side_effect=LoginError("login error"),
    ), requests_mock.mock() as _m:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=CONFIG
        )

        assert result["errors"] == {"base": "invalid_auth"}

    with patch(
        "homeassistant.components.qnap_qsw.config_flow.QSHA.update_firmware_update_check",
        side_effect=LoginError("login error"),
    ), requests_mock.mock() as _m:
        qnap_qsw_requests_mock(_m)

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == SOURCE_USER
        assert result["errors"] == {}

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], CONFIG
        )

        await hass.async_block_till_done()

        conf_entries = hass.config_entries.async_entries(DOMAIN)
        entry = conf_entries[0]
        assert entry.state is ConfigEntryState.SETUP_RETRY
