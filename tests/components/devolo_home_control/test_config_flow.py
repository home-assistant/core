"""Test the devolo_home_control config flow."""
from unittest.mock import patch

import pytest

from homeassistant import config_entries, data_entry_flow, setup
from homeassistant.components.devolo_home_control.const import DEFAULT_MYDEVOLO, DOMAIN

from .const import (
    DISCOVERY_INFO,
    DISCOVERY_INFO_WRONG_DEVICE,
    DISCOVERY_INFO_WRONG_DEVOLO_DEVICE,
)

from tests.common import MockConfigEntry


async def test_form(hass):
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["step_id"] == "user"
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {}

    await _setup(hass, result)


@pytest.mark.credentials_invalid
async def test_form_invalid_credentials_user(hass):
    """Test if we get the error message on invalid credentials."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["step_id"] == "user"
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"username": "test-username", "password": "test-password"},
    )

    assert result["errors"] == {"base": "invalid_auth"}


async def test_form_already_configured(hass):
    """Test if we get the error message on already configured."""
    with patch(
        "homeassistant.components.devolo_home_control.Mydevolo.uuid",
        return_value="123456",
    ):
        MockConfigEntry(domain=DOMAIN, unique_id="123456", data={}).add_to_hass(hass)
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={"username": "test-username", "password": "test-password"},
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
        assert result["reason"] == "already_configured"


async def test_form_advanced_options(hass):
    """Test if we get the advanced options if user has enabled it."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER, "show_advanced_options": True},
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.devolo_home_control.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry, patch(
        "homeassistant.components.devolo_home_control.Mydevolo.uuid",
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

    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_zeroconf(hass):
    """Test that the zeroconf confirmation form is served."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=DISCOVERY_INFO,
    )

    assert result["step_id"] == "zeroconf_confirm"
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM

    await _setup(hass, result)


@pytest.mark.credentials_invalid
async def test_form_invalid_credentials_zeroconf(hass):
    """Test if we get the error message on invalid credentials."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=DISCOVERY_INFO,
    )

    assert result["step_id"] == "zeroconf_confirm"
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"username": "test-username", "password": "test-password"},
    )

    assert result["errors"] == {"base": "invalid_auth"}


async def test_zeroconf_wrong_device(hass):
    """Test that the zeroconf ignores wrong devices."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=DISCOVERY_INFO_WRONG_DEVOLO_DEVICE,
    )

    assert result["reason"] == "Not a devolo Home Control gateway."
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=DISCOVERY_INFO_WRONG_DEVICE,
    )

    assert result["reason"] == "Not a devolo Home Control gateway."
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT


async def test_form_reauth(hass):
    """Test that the reauth confirmation form is served."""
    mock_config = MockConfigEntry(domain=DOMAIN, unique_id="123456", data={})
    mock_config.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": mock_config.entry_id,
        },
        data={"username": "test-username", "password": "test-password"},
    )

    assert result["step_id"] == "reauth_confirm"
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM

    with patch(
        "homeassistant.components.devolo_home_control.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry, patch(
        "homeassistant.components.devolo_home_control.Mydevolo.uuid",
        return_value="123456",
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"username": "test-username-new", "password": "test-password-new"},
        )
        await hass.async_block_till_done()

    assert result2["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.credentials_invalid
async def test_form_invalid_credentials_reauth(hass):
    """Test if we get the error message on invalid credentials."""
    mock_config = MockConfigEntry(domain=DOMAIN, unique_id="123456", data={})
    mock_config.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": mock_config.entry_id,
        },
        data={"username": "test-username", "password": "test-password"},
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"username": "test-username", "password": "test-password"},
    )

    assert result["errors"] == {"base": "invalid_auth"}


async def test_form_uuid_change_reauth(hass):
    """Test that the reauth confirmation form is served."""
    mock_config = MockConfigEntry(domain=DOMAIN, unique_id="123456", data={})
    mock_config.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": mock_config.entry_id,
        },
        data={"username": "test-username", "password": "test-password"},
    )

    assert result["step_id"] == "reauth_confirm"
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM

    with patch(
        "homeassistant.components.devolo_home_control.async_setup_entry",
        return_value=True,
    ), patch(
        "homeassistant.components.devolo_home_control.Mydevolo.uuid",
        return_value="789123",
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"username": "test-username-new", "password": "test-password-new"},
        )
        await hass.async_block_till_done()

    assert result2["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result2["errors"] == {"base": "reauth_failed"}


async def _setup(hass, result):
    """Finish configuration steps."""
    with patch(
        "homeassistant.components.devolo_home_control.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry, patch(
        "homeassistant.components.devolo_home_control.Mydevolo.uuid",
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
        "mydevolo_url": DEFAULT_MYDEVOLO,
    }

    assert len(mock_setup_entry.mock_calls) == 1
