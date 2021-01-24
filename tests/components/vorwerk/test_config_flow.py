"""Test vorwerk config flow."""
from unittest.mock import MagicMock, patch

from requests.models import HTTPError

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.vorwerk.const import (
    VORWERK_DOMAIN,
    VORWERK_ROBOT_ENDPOINT,
    VORWERK_ROBOT_NAME,
    VORWERK_ROBOT_SECRET,
    VORWERK_ROBOT_SERIAL,
    VORWERK_ROBOT_TRAITS,
    VORWERK_ROBOTS,
)
from homeassistant.const import CONF_CODE, CONF_EMAIL, CONF_TOKEN
from homeassistant.helpers.typing import HomeAssistantType

from tests.common import MockConfigEntry


def _create_mocked_vorwerk_session():
    mocked_vorwerk_session = MagicMock()
    return mocked_vorwerk_session


def _patch_config_flow_vorwerksession(mocked_vorwerk_session):
    return patch(
        "homeassistant.components.vorwerk.authsession.VorwerkSession",
        return_value=mocked_vorwerk_session,
    )


def _patch_setup():
    return patch(
        "homeassistant.components.vorwerk.async_setup_entry",
        return_value=True,
    )


def _flow_next(hass, flow_id):
    return next(
        flow
        for flow in hass.config_entries.flow.async_progress()
        if flow["flow_id"] == flow_id
    )


async def test_import_abort_if_already_setup(hass: HomeAssistantType):
    """Test we abort if Vorwerk configuration is already setup."""
    entry = MockConfigEntry(
        domain=VORWERK_DOMAIN,
        unique_id="from configuration",
        data={VORWERK_ROBOTS: {}},
    )
    entry.add_to_hass(hass)

    # Should fail
    data = [
        {
            VORWERK_ROBOT_NAME: "Mein VR",
            VORWERK_ROBOT_SERIAL: "S3R14L",
            VORWERK_ROBOT_SECRET: "S3CR3+",
            VORWERK_ROBOT_ENDPOINT: "http://nucleo_url",
        }
    ]
    result = await hass.config_entries.flow.async_init(
        VORWERK_DOMAIN, context={"source": config_entries.SOURCE_IMPORT}, data=data
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"
    # Check that the robots are updated in the config entry
    assert dict(entry.data) == {VORWERK_ROBOTS: data}


async def test_import_success(hass: HomeAssistantType):
    """Test Vorwerk setup from configuration.yaml."""
    data = [
        {
            VORWERK_ROBOT_NAME: "Mein VR",
            VORWERK_ROBOT_SERIAL: "S3R14L",
            VORWERK_ROBOT_SECRET: "S3CR3+",
            VORWERK_ROBOT_ENDPOINT: "http://nucleo_url",
        }
    ]
    # Should success
    result = await hass.config_entries.flow.async_init(
        VORWERK_DOMAIN, context={"source": config_entries.SOURCE_IMPORT}, data=data
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "from configuration"
    assert result["result"].unique_id == "from configuration"
    assert result["result"].data == {VORWERK_ROBOTS: data}
    assert result["data"] == {VORWERK_ROBOTS: data}


async def test_user_full(hass: HomeAssistantType):
    """Test user initialized flow."""
    mock_session = _create_mocked_vorwerk_session()
    mock_session.token = {
        "id_token": "id_token",
        "refresh_token": "refresh_token",
    }
    mock_session.get.return_value.json.return_value = [
        {
            "name": "Mein VR",
            "serial": "S3R14L",
            "secret_key": "S3CR3+",
            "traits": ["trait1", "trait2"],
            "nucleo_url": "https://example.com",
        }
    ]
    email = "testuser@example.com"
    result_data = {
        CONF_TOKEN: mock_session.token,
        CONF_EMAIL: email,
        VORWERK_ROBOTS: [
            {
                VORWERK_ROBOT_NAME: "Mein VR",
                VORWERK_ROBOT_SERIAL: "S3R14L",
                VORWERK_ROBOT_SECRET: "S3CR3+",
                VORWERK_ROBOT_TRAITS: ["trait1", "trait2"],
                VORWERK_ROBOT_ENDPOINT: "https://example.com",
            }
        ],
    }
    with _patch_config_flow_vorwerksession(mock_session), _patch_setup():
        result = await hass.config_entries.flow.async_init(
            VORWERK_DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "user"
        assert not result["errors"]
        _flow_next(hass, result["flow_id"])

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_EMAIL: email},
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "code"
        mock_session.send_email_otp.assert_called_once_with(email)
        _flow_next(hass, result["flow_id"])

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_CODE: "123456"},
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert result["title"] == email
        assert result["result"].unique_id == email
        assert dict(result["result"].data) == result_data
        mock_session.fetch_token_passwordless.assert_called_once_with(email, "123456")
        mock_session.get.assert_called_once_with("users/me/robots")


async def test_user_code_invalid_2nd_try(hass: HomeAssistantType):
    """Test user initialized flow."""
    mock_session = _create_mocked_vorwerk_session()
    mock_session.token = {
        "id_token": "id_token",
        "refresh_token": "refresh_token",
    }
    mock_session.fetch_token_passwordless.side_effect = [HTTPError(), None]
    mock_session.get.return_value.json.return_value = [
        {
            "name": "Mein VR",
            "serial": "S3R14L",
            "secret_key": "S3CR3+",
            "traits": ["trait1", "trait2"],
            "nucleo_url": "https://example.com",
        }
    ]
    email = "testuser@example.com"
    result_data = {
        CONF_TOKEN: mock_session.token,
        CONF_EMAIL: email,
        VORWERK_ROBOTS: [
            {
                VORWERK_ROBOT_NAME: "Mein VR",
                VORWERK_ROBOT_SERIAL: "S3R14L",
                VORWERK_ROBOT_SECRET: "S3CR3+",
                VORWERK_ROBOT_TRAITS: ["trait1", "trait2"],
                VORWERK_ROBOT_ENDPOINT: "https://example.com",
            }
        ],
    }
    with _patch_config_flow_vorwerksession(mock_session), _patch_setup():

        result = await hass.config_entries.flow.async_init(
            VORWERK_DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "user"
        assert not result["errors"]
        _flow_next(hass, result["flow_id"])

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_EMAIL: email},
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "code"
        assert not result["errors"]
        mock_session.send_email_otp.assert_called_once_with(email)
        mock_session.reset_mock()
        _flow_next(hass, result["flow_id"])

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_CODE: "123456"},
        )
        mock_session.fetch_token_passwordless.assert_called_once_with(email, "123456")
        mock_session.get.assert_not_called()
        mock_session.send_email_otp.assert_called_once_with(email)
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "code"
        assert result["errors"] == {"base": "invalid_auth"}
        _flow_next(hass, result["flow_id"])

        mock_session.reset_mock()
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_CODE: "123456"},
        )
        mock_session.send_email_otp.assert_not_called()
        mock_session.fetch_token_passwordless.assert_called_once_with(email, "123456")
        mock_session.get.assert_called_once_with("users/me/robots")
        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert result["title"] == email
        assert result["result"].unique_id == email
        assert dict(result["result"].data) == result_data
