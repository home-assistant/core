"""Test the Hikvision config flow."""

from unittest.mock import MagicMock

import pytest
from pytest_homeassistant.common import MockConfigEntry
import requests

from homeassistant.components.hikvision.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import setup_integration
from .conftest import (
    TEST_DEVICE_ID,
    TEST_DEVICE_NAME,
    TEST_HOST,
    TEST_PASSWORD,
    TEST_PORT,
    TEST_USERNAME,
)


@pytest.mark.usefixtures("mock_setup_entry")
async def test_form(hass: HomeAssistant, mock_hikcamera: MagicMock) -> None:
    """Test we get the form and can create entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: TEST_HOST,
            CONF_PORT: TEST_PORT,
            CONF_USERNAME: TEST_USERNAME,
            CONF_PASSWORD: TEST_PASSWORD,
            CONF_SSL: False,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_DEVICE_NAME
    assert result["result"].unique_id == TEST_DEVICE_ID
    assert result["data"] == {
        CONF_HOST: TEST_HOST,
        CONF_PORT: TEST_PORT,
        CONF_USERNAME: TEST_USERNAME,
        CONF_PASSWORD: TEST_PASSWORD,
        CONF_SSL: False,
        CONF_VERIFY_SSL: True,
    }

    # Certificate verification defaults to on; it is unused over plain HTTP
    mock_hikcamera.assert_called_once_with(
        f"http://{TEST_HOST}", TEST_PORT, TEST_USERNAME, TEST_PASSWORD, True
    )


@pytest.mark.usefixtures("mock_setup_entry")
async def test_form_cannot_connect(
    hass: HomeAssistant, mock_hikcamera: MagicMock
) -> None:
    """Test we handle cannot connect error and can recover."""
    mock_hikcamera.return_value.get_id = None

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: TEST_HOST,
            CONF_PORT: TEST_PORT,
            CONF_USERNAME: TEST_USERNAME,
            CONF_PASSWORD: TEST_PASSWORD,
            CONF_SSL: False,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    # Recover from error
    mock_hikcamera.return_value.get_id = TEST_DEVICE_ID

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: TEST_HOST,
            CONF_PORT: TEST_PORT,
            CONF_USERNAME: TEST_USERNAME,
            CONF_PASSWORD: TEST_PASSWORD,
            CONF_SSL: False,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == TEST_DEVICE_ID


@pytest.mark.usefixtures("mock_setup_entry")
async def test_form_exception(hass: HomeAssistant, mock_hikcamera: MagicMock) -> None:
    """Test we handle exception during connection and can recover."""
    mock_hikcamera.side_effect = requests.exceptions.RequestException(
        "Connection failed"
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: TEST_HOST,
            CONF_PORT: TEST_PORT,
            CONF_USERNAME: TEST_USERNAME,
            CONF_PASSWORD: TEST_PASSWORD,
            CONF_SSL: False,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    # Recover from error
    mock_hikcamera.side_effect = None
    mock_hikcamera.return_value.get_id = TEST_DEVICE_ID
    mock_hikcamera.return_value.get_name = TEST_DEVICE_NAME

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: TEST_HOST,
            CONF_PORT: TEST_PORT,
            CONF_USERNAME: TEST_USERNAME,
            CONF_PASSWORD: TEST_PASSWORD,
            CONF_SSL: False,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == TEST_DEVICE_ID


@pytest.mark.usefixtures("mock_setup_entry")
async def test_form_unknown_exception(
    hass: HomeAssistant, mock_hikcamera: MagicMock
) -> None:
    """Test we handle unknown exception during connection and can recover."""
    mock_hikcamera.side_effect = Exception("Unexpected error")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: TEST_HOST,
            CONF_PORT: TEST_PORT,
            CONF_USERNAME: TEST_USERNAME,
            CONF_PASSWORD: TEST_PASSWORD,
            CONF_SSL: False,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}

    # Recover from error
    mock_hikcamera.side_effect = None
    mock_hikcamera.return_value.get_id = TEST_DEVICE_ID
    mock_hikcamera.return_value.get_name = TEST_DEVICE_NAME

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: TEST_HOST,
            CONF_PORT: TEST_PORT,
            CONF_USERNAME: TEST_USERNAME,
            CONF_PASSWORD: TEST_PASSWORD,
            CONF_SSL: False,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == TEST_DEVICE_ID


@pytest.mark.usefixtures("mock_setup_entry")
async def test_form_already_configured(
    hass: HomeAssistant, mock_hikcamera: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test we handle already configured devices."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: TEST_HOST,
            CONF_PORT: TEST_PORT,
            CONF_USERNAME: TEST_USERNAME,
            CONF_PASSWORD: TEST_PASSWORD,
            CONF_SSL: False,
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    ("form", "verify_ssl"),
    [
        pytest.param({}, True, id="verified_by_default"),
        pytest.param({CONF_VERIFY_SSL: True}, True, id="verified"),
        pytest.param({CONF_VERIFY_SSL: False}, False, id="unverified"),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_form_with_ssl(
    hass: HomeAssistant,
    mock_hikcamera: MagicMock,
    form: dict[str, bool],
    verify_ssl: bool,
) -> None:
    """Test the user flow passes HTTPS and the certificate choice to HikCamera."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: TEST_HOST,
            CONF_PORT: TEST_PORT,
            CONF_USERNAME: TEST_USERNAME,
            CONF_PASSWORD: TEST_PASSWORD,
            CONF_SSL: True,
            **form,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_SSL] is True
    assert result["data"][CONF_VERIFY_SSL] is verify_ssl
    assert result["result"].unique_id == TEST_DEVICE_ID
    mock_hikcamera.assert_called_once_with(
        f"https://{TEST_HOST}", TEST_PORT, TEST_USERNAME, TEST_PASSWORD, verify_ssl
    )


@pytest.mark.usefixtures("mock_setup_entry")
async def test_form_invalid_auth(
    hass: HomeAssistant, mock_hikcamera: MagicMock
) -> None:
    """Test a rejected password is reported as such, and the user can recover."""
    mock_hikcamera.return_value.get_id = None
    mock_hikcamera.return_value.auth_failed = True

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    user_input = {
        CONF_HOST: TEST_HOST,
        CONF_PORT: TEST_PORT,
        CONF_USERNAME: TEST_USERNAME,
        CONF_PASSWORD: TEST_PASSWORD,
        CONF_SSL: False,
    }
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}

    mock_hikcamera.return_value.get_id = TEST_DEVICE_ID
    mock_hikcamera.return_value.auth_failed = False

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == TEST_DEVICE_ID


async def test_reauth_flow(
    hass: HomeAssistant,
    mock_hikcamera: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the stored credentials can be replaced."""
    await setup_integration(hass, mock_config_entry)

    result = await mock_config_entry.start_reauth_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["description_placeholders"] == {"name": mock_config_entry.title}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_USERNAME: "new-user", CONF_PASSWORD: "new-password"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data[CONF_USERNAME] == "new-user"
    assert mock_config_entry.data[CONF_PASSWORD] == "new-password"
    # The rest of the entry is unchanged.
    assert mock_config_entry.data[CONF_HOST] == TEST_HOST
    assert mock_config_entry.data[CONF_PORT] == TEST_PORT
    # The new credentials are what the device was asked to accept.
    assert mock_hikcamera.call_args.args[2:4] == ("new-user", "new-password")


async def test_reauth_flow_keeps_the_certificate_setting(
    hass: HomeAssistant,
    mock_hikcamera: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reauthentication connects the way the entry was set up."""
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry,
        data={**mock_config_entry.data, CONF_SSL: True, CONF_VERIFY_SSL: False},
    )
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    result = await mock_config_entry.start_reauth_flow(hass)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_USERNAME: "new-user", CONF_PASSWORD: "new-password"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    mock_hikcamera.assert_called_with(
        f"https://{TEST_HOST}", TEST_PORT, "new-user", "new-password", False
    )


@pytest.mark.parametrize(
    ("get_id", "auth_failed", "side_effect", "error"),
    [
        (None, True, None, "invalid_auth"),
        (None, False, None, "cannot_connect"),
        (TEST_DEVICE_ID, False, requests.exceptions.ConnectionError, "cannot_connect"),
        (TEST_DEVICE_ID, False, RuntimeError, "unknown"),
    ],
)
async def test_reauth_flow_errors(
    hass: HomeAssistant,
    mock_hikcamera: MagicMock,
    mock_config_entry: MockConfigEntry,
    get_id: str | None,
    auth_failed: bool,
    side_effect: type[Exception] | None,
    error: str,
) -> None:
    """Test reauthentication reports why the credentials were not accepted."""
    await setup_integration(hass, mock_config_entry)
    result = await mock_config_entry.start_reauth_flow(hass)
    user_input = {CONF_USERNAME: TEST_USERNAME, CONF_PASSWORD: "wrong"}

    mock_hikcamera.return_value.get_id = get_id
    mock_hikcamera.return_value.auth_failed = auth_failed
    mock_hikcamera.side_effect = side_effect
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == {"base": error}

    # Recover from the error
    mock_hikcamera.return_value.get_id = TEST_DEVICE_ID
    mock_hikcamera.return_value.auth_failed = False
    mock_hikcamera.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_USERNAME: TEST_USERNAME, CONF_PASSWORD: "right"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data[CONF_PASSWORD] == "right"


async def test_reauth_flow_wrong_device(
    hass: HomeAssistant,
    mock_hikcamera: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the credentials cannot be used to switch to another device."""
    await setup_integration(hass, mock_config_entry)
    result = await mock_config_entry.start_reauth_flow(hass)

    mock_hikcamera.return_value.get_id = "another-device"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_USERNAME: TEST_USERNAME, CONF_PASSWORD: TEST_PASSWORD},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "wrong_device"
    assert mock_config_entry.data[CONF_PASSWORD] == TEST_PASSWORD
