"""Test the Synology SRM config flow."""
from synology_srm.http import SynologyError, SynologyHttpException

from homeassistant import config_entries, setup
from homeassistant.components.synology_srm.const import (
    DEFAULT_PORT,
    DEFAULT_SSL,
    DEFAULT_USERNAME,
    DEFAULT_VERIFY_SSL,
    DOMAIN,
)

from tests.async_mock import patch

SYNOLOGY_DEVICE_ID = "synology_irr436p_rt2600ac"

BAD_PASSWORD_EXCEPTION = SynologyError(400, "No such account or incorrect password")
NO_PERMISSION_EXCEPTION = SynologyError(
    105, "The logged in session does not have permission"
)


async def test_form(hass):
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.synology_srm.config_flow.fetch_srm_device_id",
        return_value=SYNOLOGY_DEVICE_ID,
    ), patch(
        "homeassistant.components.synology_srm.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.synology_srm.async_setup_entry", return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"host": "1.1.1.1", "password": "test-password"},
        )

    assert result2["type"] == "create_entry"
    assert result2["title"] == SYNOLOGY_DEVICE_ID
    assert result2["data"] == {
        "host": "1.1.1.1",
        "username": DEFAULT_USERNAME,
        "password": "test-password",
        "port": DEFAULT_PORT,
        "ssl": DEFAULT_SSL,
        "verify_ssl": DEFAULT_VERIFY_SSL,
    }
    await hass.async_block_till_done()
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_cannot_connect(hass):
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.synology_srm.config_flow.fetch_srm_device_id",
        side_effect=SynologyHttpException,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.1.1.1",
                "username": "test-username",
                "password": "test-password",
            },
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "cannot_connect"}

    with patch(
        "homeassistant.components.synology_srm.config_flow.fetch_srm_device_id",
        side_effect=NO_PERMISSION_EXCEPTION,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.1.1.1",
                "username": "test-username",
                "password": "test-password",
            },
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_invalid_auth(hass):
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.synology_srm.config_flow.fetch_srm_device_id",
        side_effect=BAD_PASSWORD_EXCEPTION,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.1.1.1",
                "username": "test-username",
                "password": "test-password",
            },
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_form_unknown_exception(hass):
    """Test we handle base exception error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.synology_srm.config_flow.fetch_srm_device_id",
        side_effect=Exception,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.1.1.1",
                "username": "test-username",
                "password": "test-password",
            },
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "unknown"}
