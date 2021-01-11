"""Test the devolo_home_control config flow."""
from unittest.mock import patch

from homeassistant import config_entries, data_entry_flow, setup
from homeassistant.components.devolo_home_control.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER

from tests.common import MockConfigEntry


async def test_form(hass):
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.devolo_home_control.async_setup",
        return_value=True,
    ) as mock_setup, patch(
        "homeassistant.components.devolo_home_control.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry, patch(
        "homeassistant.components.devolo_home_control.config_flow.Mydevolo.credentials_valid",
        return_value=True,
    ), patch(
        "homeassistant.components.devolo_home_control.config_flow.Mydevolo.uuid",
        return_value="123456",
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"username": "test-username", "password": "test-password"},
        )
        await hass.async_block_till_done()

    assert result2["type"] == "create_entry"
    assert result2["title"] == "devolo Home Control"
    assert result2["data"] == {
        "username": "test-username",
        "password": "test-password",
        "mydevolo_url": "https://www.mydevolo.com",
    }

    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_invalid_credentials(hass):
    """Test if we get the error message on invalid credentials."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.devolo_home_control.config_flow.Mydevolo.credentials_valid",
        return_value=False,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"username": "test-username", "password": "test-password"},
        )

        assert result["errors"] == {"base": "invalid_auth"}


async def test_form_already_configured(hass):
    """Test if we get the error message on already configured."""
    with patch(
        "homeassistant.components.devolo_home_control.config_flow.Mydevolo.uuid",
        return_value="123456",
    ), patch(
        "homeassistant.components.devolo_home_control.config_flow.Mydevolo.credentials_valid",
        return_value=True,
    ):
        MockConfigEntry(domain=DOMAIN, unique_id="123456", data={}).add_to_hass(hass)
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data={"username": "test-username", "password": "test-password"},
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
        assert result["reason"] == "already_configured"


async def test_form_advanced_options(hass):
    """Test if we get the advanced options if user has enabled it."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user", "show_advanced_options": True}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.devolo_home_control.async_setup",
        return_value=True,
    ) as mock_setup, patch(
        "homeassistant.components.devolo_home_control.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry, patch(
        "homeassistant.components.devolo_home_control.config_flow.Mydevolo.credentials_valid",
        return_value=True,
    ), patch(
        "homeassistant.components.devolo_home_control.config_flow.Mydevolo.uuid",
        return_value="123456",
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "username": "test-username",
                "password": "test-password",
                "mydevolo_url": "https://test_mydevolo_url.test",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == "create_entry"
    assert result2["title"] == "devolo Home Control"
    assert result2["data"] == {
        "username": "test-username",
        "password": "test-password",
        "mydevolo_url": "https://test_mydevolo_url.test",
    }

    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1
