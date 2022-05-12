"""Test the Aladdin Connect config flow."""
from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.components.aladdin_connect.config_flow import InvalidAuth
from homeassistant.components.aladdin_connect.const import DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import (
    RESULT_TYPE_ABORT,
    RESULT_TYPE_CREATE_ENTRY,
    RESULT_TYPE_FORM,
)

from tests.common import MockConfigEntry


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] is None

    with patch(
        "homeassistant.components.aladdin_connect.config_flow.AladdinConnectClient.login",
        return_value=True,
    ), patch(
        "homeassistant.components.aladdin_connect.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "test-password",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result2["title"] == "Aladdin Connect"
    assert result2["data"] == {
        CONF_USERNAME: "test-username",
        CONF_PASSWORD: "test-password",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_invalid_auth(hass: HomeAssistant) -> None:
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.aladdin_connect.config_flow.AladdinConnectClient.login",
        side_effect=InvalidAuth,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "test-password",
            },
        )

    assert result2["type"] == RESULT_TYPE_FORM
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.aladdin_connect.config_flow.AladdinConnectClient.login",
        side_effect=ConnectionError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "test-password",
            },
        )

    assert result2["type"] == RESULT_TYPE_FORM
    assert result2["errors"] == {"base": "cannot_connect"}

    with patch(
        "homeassistant.components.aladdin_connect.config_flow.AladdinConnectClient.login",
        side_effect=TypeError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "test-password",
            },
        )

    assert result2["type"] == RESULT_TYPE_FORM
    assert result2["errors"] == {"base": "cannot_connect"}

    with patch(
        "homeassistant.components.aladdin_connect.config_flow.AladdinConnectClient.login",
        return_value=False,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "test-password",
            },
        )

    assert result2["type"] == RESULT_TYPE_FORM
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_form_already_configured(hass):
    """Test we handle already configured error."""
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_USERNAME: "test-username", CONF_PASSWORD: "test-password"},
        unique_id="test-username",
    )
    mock_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["step_id"] == config_entries.SOURCE_USER

    with patch(
        "homeassistant.components.aladdin_connect.config_flow.AladdinConnectClient.login",
        return_value=True,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "test-password",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == "abort"
    assert result2["reason"] == "already_configured"


async def test_import_flow_success(hass: HomeAssistant) -> None:
    """Test a successful import of yaml."""

    with patch(
        "homeassistant.components.aladdin_connect.cover.async_setup_platform",
        return_value=True,
    ), patch(
        "homeassistant.components.aladdin_connect.config_flow.AladdinConnectClient.login",
        return_value=True,
    ), patch(
        "homeassistant.components.aladdin_connect.cover.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={
                CONF_USERNAME: "test-user",
                CONF_PASSWORD: "test-password",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result2["title"] == "Aladdin Connect"
    assert result2["data"] == {
        CONF_USERNAME: "test-user",
        CONF_PASSWORD: "test-password",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_reauth_flow(hass: HomeAssistant) -> None:
    """Test a successful reauth flow."""

    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        data={"username": "test-username", "password": "test-password"},
        unique_id="test-username",
    )
    mock_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "unique_id": mock_entry.unique_id,
            "entry_id": mock_entry.entry_id,
        },
        data={"username": "test-username", "password": "new-password"},
    )

    assert result["step_id"] == "reauth_confirm"
    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.aladdin_connect.cover.async_setup_platform",
        return_value=True,
    ), patch(
        "homeassistant.components.aladdin_connect.config_flow.AladdinConnectClient.login",
        return_value=True,
    ), patch(
        "homeassistant.components.aladdin_connect.cover.async_setup_entry",
        return_value=True,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_PASSWORD: "new-password"},
        )
        await hass.async_block_till_done()

    assert result2["type"] == RESULT_TYPE_ABORT
    assert result2["reason"] == "reauth_successful"
    assert mock_entry.data == {
        CONF_USERNAME: "test-username",
        CONF_PASSWORD: "new-password",
    }


async def test_reauth_flow_auth_error(hass: HomeAssistant) -> None:
    """Test a successful reauth flow."""

    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        data={"username": "test-username", "password": "test-password"},
        unique_id="test-username",
    )
    mock_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "unique_id": mock_entry.unique_id,
            "entry_id": mock_entry.entry_id,
        },
        data={"username": "test-username", "password": "new-password"},
    )

    assert result["step_id"] == "reauth_confirm"
    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.aladdin_connect.cover.async_setup_platform",
        return_value=True,
    ), patch(
        "homeassistant.components.aladdin_connect.config_flow.AladdinConnectClient.login",
        return_value=False,
    ), patch(
        "homeassistant.components.aladdin_connect.cover.async_setup_entry",
        return_value=True,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_PASSWORD: "new-password"},
        )
        await hass.async_block_till_done()

    assert result2["type"] == RESULT_TYPE_FORM
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_reauth_flow_other_error(hass: HomeAssistant) -> None:
    """Test an unsuccessful reauth flow."""

    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        data={"username": "test-username", "password": "test-password"},
        unique_id="test-username",
    )
    mock_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "unique_id": mock_entry.unique_id,
            "entry_id": mock_entry.entry_id,
        },
        data={"username": "test-username", "password": "new-password"},
    )

    assert result["step_id"] == "reauth_confirm"
    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.aladdin_connect.cover.async_setup_platform",
        return_value=True,
    ), patch(
        "homeassistant.components.aladdin_connect.config_flow.AladdinConnectClient.login",
        side_effect=ValueError,
    ), patch(
        "homeassistant.components.aladdin_connect.cover.async_setup_entry",
        return_value=True,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_PASSWORD: "new-password"},
        )
        await hass.async_block_till_done()

    assert result2["type"] == RESULT_TYPE_FORM
    assert result2["errors"] == {"base": "cannot_connect"}
