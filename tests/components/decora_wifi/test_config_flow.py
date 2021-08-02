"""Test the decora_wifi Config Flow."""

from unittest.mock import patch

from homeassistant import config_entries, data_entry_flow, setup
from homeassistant.components.decora_wifi.common import (
    DecoraWifiCommFailed,
    DecoraWifiLoginFailed,
    DecoraWifiPlatform,
    decorawifisessions,
)
from homeassistant.components.decora_wifi.const import CONF_TITLE, DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

from tests.common import MockConfigEntry
from tests.components.decora_wifi.common import MockDecoraWifiPlatform

USERNAME = "username@home-assisant.com"
UPDATED_USERNAME = "updated_username@home-assitant.com"
PASSWORD = "test-password"
UPDATED_PASSWORD = "updated-password"
INCORRECT_PASSWORD = "incoreect-password"
SCAN_INTERVAL = 120
UPDATED_SCAN_INTERVAL = 60


async def test_import_flow(hass):
    """Check import flow."""

    with patch.object(
        DecoraWifiPlatform,
        "async_setup_decora_wifi",
        MockDecoraWifiPlatform.async_setup_decora_wifi,
    ), patch.dict(decorawifisessions) as mock_decorawifisessions, patch(
        "homeassistant.components.decora_wifi.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.decora_wifi.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD},
        )
        assert isinstance(mock_decorawifisessions[USERNAME], MockDecoraWifiPlatform)

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == f"{CONF_TITLE} - {USERNAME}"
    assert result["data"] == {
        CONF_USERNAME: USERNAME,
        CONF_PASSWORD: PASSWORD,
    }
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_user_flow(hass):
    """Test the user flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert not result["errors"]

    with patch.object(
        DecoraWifiPlatform,
        "async_setup_decora_wifi",
        MockDecoraWifiPlatform.async_setup_decora_wifi,
    ), patch.dict(decorawifisessions) as mock_decorawifisessions, patch(
        "homeassistant.components.decora_wifi.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.decora_wifi.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD},
        )
        await hass.async_block_till_done()
        assert isinstance(mock_decorawifisessions[USERNAME], MockDecoraWifiPlatform)

    assert result2["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result2["title"] == f"{CONF_TITLE} - {USERNAME}"
    assert result2["data"] == {
        CONF_USERNAME: USERNAME,
        CONF_PASSWORD: PASSWORD,
    }

    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1


async def test_reauth_flow(hass):
    """Test the reauth flow."""

    await setup.async_setup_component(hass, "persistent_notification", {})
    mock_config = MockConfigEntry(
        domain=DOMAIN,
        unique_id=USERNAME,
        data={
            CONF_USERNAME: USERNAME,
            CONF_PASSWORD: INCORRECT_PASSWORD,
        },
    )
    mock_config.add_to_hass(hass)

    with patch(
        "homeassistant.components.decora_wifi.config_flow.DecoraWifiPlatform.async_setup_decora_wifi",
        side_effect=DecoraWifiLoginFailed(),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={
                "source": config_entries.SOURCE_REAUTH,
                "unique_id": mock_config.unique_id,
            },
            data=mock_config.data,
        )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {"base": "invalid_auth"}

    with patch.object(
        DecoraWifiPlatform,
        "async_setup_decora_wifi",
        MockDecoraWifiPlatform.async_setup_decora_wifi,
    ), patch.dict(decorawifisessions) as mock_decorawifisessions:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: USERNAME,
                CONF_PASSWORD: UPDATED_PASSWORD,
            },
        )
        assert isinstance(mock_decorawifisessions[USERNAME], MockDecoraWifiPlatform)
    await hass.async_block_till_done()

    assert mock_config.data.get("username") == USERNAME
    assert mock_config.data.get("password") == UPDATED_PASSWORD
    assert result2["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result2["reason"] == "reauth_successful"
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1


async def test_abort_if_existing_entry(hass):
    """Check flow abort when an entry already exist."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=USERNAME,
        data={CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD},
    )
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data={
            CONF_USERNAME: USERNAME,
            CONF_PASSWORD: PASSWORD,
        },
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"


async def test_user_flow_invalid_username(hass):
    """Test user flow with invalid username."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert not result["errors"]

    with patch(
        "homeassistant.components.decora_wifi.config_flow.DecoraWifiPlatform.async_setup_decora_wifi",
        side_effect=DecoraWifiLoginFailed(),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD},
        )

    assert result2["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result2["step_id"] == "user"
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_user_flow_invalid_password(hass):
    """Test user flow with invalid password."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert not result["errors"]

    with patch(
        "homeassistant.components.decora_wifi.config_flow.DecoraWifiPlatform.async_setup_decora_wifi",
        side_effect=DecoraWifiLoginFailed(),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD},
        )

    assert result2["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result2["step_id"] == "user"
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_user_flow_no_internet_connection(hass):
    """Test user flow with no internet connection."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert not result["errors"]

    with patch(
        "homeassistant.components.decora_wifi.config_flow.DecoraWifiPlatform.async_setup_decora_wifi",
        side_effect=DecoraWifiCommFailed(),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD},
        )

    assert result2["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result2["step_id"] == "user"
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_reauth_flow_no_internet_connection(hass):
    """Test reauth flow with no internet connection."""

    await setup.async_setup_component(hass, "persistent_notification", {})
    mock_config = MockConfigEntry(
        domain=DOMAIN,
        unique_id=USERNAME,
        data={
            CONF_USERNAME: USERNAME,
            CONF_PASSWORD: INCORRECT_PASSWORD,
        },
    )
    mock_config.add_to_hass(hass)

    with patch(
        "homeassistant.components.decora_wifi.config_flow.DecoraWifiPlatform.async_setup_decora_wifi",
        side_effect=DecoraWifiCommFailed(),
    ):
        result2 = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={
                "source": config_entries.SOURCE_REAUTH,
                "unique_id": mock_config.unique_id,
            },
            data=mock_config.data,
        )

    assert result2["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result2["step_id"] == "reauth"
    assert result2["errors"] == {"base": "cannot_connect"}
