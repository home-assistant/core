"""Define tests for the Awair config flow."""

from unittest.mock import patch

from python_awair.exceptions import AuthError, AwairError

from homeassistant import data_entry_flow
from homeassistant.components.awair.const import DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.const import CONF_ACCESS_TOKEN

from .const import CONFIG, DEVICES_FIXTURE, NO_DEVICES_FIXTURE, UNIQUE_ID, USER_FIXTURE

from tests.common import MockConfigEntry


async def test_show_form(hass):
    """Test that the form is served with no input."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == SOURCE_USER


async def test_invalid_access_token(hass):
    """Test that errors are shown when the access token is invalid."""

    with patch("python_awair.AwairClient.query", side_effect=AuthError()):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=CONFIG
        )

        assert result["errors"] == {CONF_ACCESS_TOKEN: "invalid_access_token"}


async def test_unexpected_api_error(hass):
    """Test that we abort on generic errors."""

    with patch("python_awair.AwairClient.query", side_effect=AwairError()):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=CONFIG
        )

        assert result["type"] == "abort"
        assert result["reason"] == "unknown"


async def test_duplicate_error(hass):
    """Test that errors are shown when adding a duplicate config."""

    with patch(
        "python_awair.AwairClient.query", side_effect=[USER_FIXTURE, DEVICES_FIXTURE]
    ), patch(
        "homeassistant.components.awair.sensor.async_setup_entry",
        return_value=True,
    ):
        MockConfigEntry(domain=DOMAIN, unique_id=UNIQUE_ID, data=CONFIG).add_to_hass(
            hass
        )

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=CONFIG
        )

        assert result["type"] == "abort"
        assert result["reason"] == "already_configured"


async def test_no_devices_error(hass):
    """Test that errors are shown when the API returns no devices."""

    with patch(
        "python_awair.AwairClient.query", side_effect=[USER_FIXTURE, NO_DEVICES_FIXTURE]
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=CONFIG
        )

        assert result["type"] == "abort"
        assert result["reason"] == "no_devices_found"


async def test_import(hass):
    """Test config.yaml import."""

    with patch(
        "python_awair.AwairClient.query", side_effect=[USER_FIXTURE, DEVICES_FIXTURE]
    ), patch(
        "homeassistant.components.awair.sensor.async_setup_entry",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data={CONF_ACCESS_TOKEN: CONFIG[CONF_ACCESS_TOKEN]},
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert result["title"] == "foo@bar.com (32406)"
        assert result["data"][CONF_ACCESS_TOKEN] == CONFIG[CONF_ACCESS_TOKEN]
        assert result["result"].unique_id == UNIQUE_ID


async def test_import_aborts_on_api_error(hass):
    """Test config.yaml imports on api error."""

    with patch("python_awair.AwairClient.query", side_effect=AwairError()):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data={CONF_ACCESS_TOKEN: CONFIG[CONF_ACCESS_TOKEN]},
        )

        assert result["type"] == "abort"
        assert result["reason"] == "unknown"


async def test_import_aborts_if_configured(hass):
    """Test config import doesn't re-import unnecessarily."""

    with patch(
        "python_awair.AwairClient.query", side_effect=[USER_FIXTURE, DEVICES_FIXTURE]
    ), patch(
        "homeassistant.components.awair.sensor.async_setup_entry",
        return_value=True,
    ):
        MockConfigEntry(domain=DOMAIN, unique_id=UNIQUE_ID, data=CONFIG).add_to_hass(
            hass
        )

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data={CONF_ACCESS_TOKEN: CONFIG[CONF_ACCESS_TOKEN]},
        )

        assert result["type"] == "abort"
        assert result["reason"] == "already_setup"


async def test_reauth(hass):
    """Test reauth flow."""
    with patch(
        "python_awair.AwairClient.query", side_effect=[USER_FIXTURE, DEVICES_FIXTURE]
    ), patch(
        "homeassistant.components.awair.sensor.async_setup_entry",
        return_value=True,
    ):
        mock_config = MockConfigEntry(domain=DOMAIN, unique_id=UNIQUE_ID, data=CONFIG)
        mock_config.add_to_hass(hass)
        hass.config_entries.async_update_entry(
            mock_config, data={**CONFIG, CONF_ACCESS_TOKEN: "blah"}
        )

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "reauth", "unique_id": UNIQUE_ID},
            data=CONFIG,
        )

        assert result["type"] == "abort"
        assert result["reason"] == "reauth_successful"

    with patch("python_awair.AwairClient.query", side_effect=AuthError()):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "reauth", "unique_id": UNIQUE_ID},
            data=CONFIG,
        )

        assert result["errors"] == {CONF_ACCESS_TOKEN: "invalid_access_token"}

    with patch("python_awair.AwairClient.query", side_effect=AwairError()):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "reauth", "unique_id": UNIQUE_ID},
            data=CONFIG,
        )

        assert result["type"] == "abort"
        assert result["reason"] == "unknown"


async def test_create_entry(hass):
    """Test overall flow."""

    with patch(
        "python_awair.AwairClient.query", side_effect=[USER_FIXTURE, DEVICES_FIXTURE]
    ), patch(
        "homeassistant.components.awair.sensor.async_setup_entry",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=CONFIG
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert result["title"] == "foo@bar.com (32406)"
        assert result["data"][CONF_ACCESS_TOKEN] == CONFIG[CONF_ACCESS_TOKEN]
        assert result["result"].unique_id == UNIQUE_ID
