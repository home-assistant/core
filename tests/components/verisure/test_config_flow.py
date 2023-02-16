"""Test the Verisure config flow."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from verisure import Error as VerisureError, LoginError as VerisureLoginError

from homeassistant import config_entries
from homeassistant.components import dhcp
from homeassistant.components.verisure.const import (
    CONF_GIID,
    CONF_LOCK_CODE_DIGITS,
    CONF_LOCK_DEFAULT_CODE,
    DEFAULT_LOCK_CODE_DIGITS,
    DOMAIN,
)
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_full_user_flow_single_installation(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_verisure_config_flow: MagicMock,
) -> None:
    """Test a full user initiated configuration flow with a single installation."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result.get("step_id") == "user"
    assert result.get("type") == FlowResultType.FORM
    assert result.get("errors") == {}

    mock_verisure_config_flow.installations = [
        mock_verisure_config_flow.installations[0]
    ]

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "email": "verisure_my_pages@example.com",
            "password": "SuperS3cr3t!",
        },
    )
    await hass.async_block_till_done()

    assert result2.get("type") == FlowResultType.CREATE_ENTRY
    assert result2.get("title") == "ascending (12345th street)"
    assert result2.get("data") == {
        CONF_GIID: "12345",
        CONF_EMAIL: "verisure_my_pages@example.com",
        CONF_PASSWORD: "SuperS3cr3t!",
    }

    assert len(mock_verisure_config_flow.login.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_full_user_flow_multiple_installations(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_verisure_config_flow: MagicMock,
) -> None:
    """Test a full user initiated configuration flow with multiple installations."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result.get("step_id") == "user"
    assert result.get("type") == FlowResultType.FORM
    assert result.get("errors") == {}

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "email": "verisure_my_pages@example.com",
            "password": "SuperS3cr3t!",
        },
    )
    await hass.async_block_till_done()

    assert result2.get("step_id") == "installation"
    assert result2.get("type") == FlowResultType.FORM
    assert result2.get("errors") is None

    result3 = await hass.config_entries.flow.async_configure(
        result2["flow_id"], {"giid": "54321"}
    )
    await hass.async_block_till_done()

    assert result3.get("type") == FlowResultType.CREATE_ENTRY
    assert result3.get("title") == "descending (54321th street)"
    assert result3.get("data") == {
        CONF_GIID: "54321",
        CONF_EMAIL: "verisure_my_pages@example.com",
        CONF_PASSWORD: "SuperS3cr3t!",
    }

    assert len(mock_verisure_config_flow.login.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_full_user_flow_single_installation_with_mfa(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_verisure_config_flow: MagicMock,
) -> None:
    """Test a full user initiated flow with a single installation and mfa."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result.get("step_id") == "user"
    assert result.get("type") == FlowResultType.FORM
    assert result.get("errors") == {}

    mock_verisure_config_flow.login.side_effect = VerisureLoginError(
        "Multifactor authentication enabled, disable or create MFA cookie"
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "email": "verisure_my_pages@example.com",
            "password": "SuperS3cr3t!",
        },
    )
    await hass.async_block_till_done()

    assert result2.get("type") == FlowResultType.FORM
    assert result2.get("step_id") == "mfa"

    mock_verisure_config_flow.login.side_effect = None
    mock_verisure_config_flow.installations = [
        mock_verisure_config_flow.installations[0]
    ]

    result3 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "code": "123456",
        },
    )
    await hass.async_block_till_done()

    assert result3.get("type") == FlowResultType.CREATE_ENTRY
    assert result3.get("title") == "ascending (12345th street)"
    assert result3.get("data") == {
        CONF_GIID: "12345",
        CONF_EMAIL: "verisure_my_pages@example.com",
        CONF_PASSWORD: "SuperS3cr3t!",
    }

    assert len(mock_verisure_config_flow.login.mock_calls) == 2
    assert len(mock_verisure_config_flow.login_mfa.mock_calls) == 1
    assert len(mock_verisure_config_flow.mfa_validate.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_full_user_flow_multiple_installations_with_mfa(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_verisure_config_flow: MagicMock,
) -> None:
    """Test a full user initiated configuration flow with a single installation."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result.get("step_id") == "user"
    assert result.get("type") == FlowResultType.FORM
    assert result.get("errors") == {}

    mock_verisure_config_flow.login.side_effect = VerisureLoginError(
        "Multifactor authentication enabled, disable or create MFA cookie"
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "email": "verisure_my_pages@example.com",
            "password": "SuperS3cr3t!",
        },
    )
    await hass.async_block_till_done()

    assert result2.get("type") == FlowResultType.FORM
    assert result2.get("step_id") == "mfa"

    mock_verisure_config_flow.login.side_effect = None

    result3 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "code": "123456",
        },
    )
    await hass.async_block_till_done()

    assert result3.get("step_id") == "installation"
    assert result3.get("type") == FlowResultType.FORM
    assert result3.get("errors") is None

    result4 = await hass.config_entries.flow.async_configure(
        result3["flow_id"], {"giid": "54321"}
    )
    await hass.async_block_till_done()

    assert result4.get("type") == FlowResultType.CREATE_ENTRY
    assert result4.get("title") == "descending (54321th street)"
    assert result4.get("data") == {
        CONF_GIID: "54321",
        CONF_EMAIL: "verisure_my_pages@example.com",
        CONF_PASSWORD: "SuperS3cr3t!",
    }

    assert len(mock_verisure_config_flow.login.mock_calls) == 2
    assert len(mock_verisure_config_flow.login_mfa.mock_calls) == 1
    assert len(mock_verisure_config_flow.mfa_validate.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("side_effect", "error"),
    [
        (VerisureLoginError, "invalid_auth"),
        (VerisureError, "unknown"),
    ],
)
async def test_verisure_errors(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_verisure_config_flow: MagicMock,
    side_effect: Exception,
    error: str,
) -> None:
    """Test a flow with an invalid Verisure My Pages login."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_verisure_config_flow.login.side_effect = side_effect
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "email": "verisure_my_pages@example.com",
            "password": "SuperS3cr3t!",
        },
    )
    await hass.async_block_till_done()

    assert result2.get("type") == FlowResultType.FORM
    assert result2.get("step_id") == "user"
    assert result2.get("errors") == {"base": error}

    mock_verisure_config_flow.login.side_effect = VerisureLoginError(
        "Multifactor authentication enabled, disable or create MFA cookie"
    )
    mock_verisure_config_flow.login_mfa.side_effect = side_effect

    result3 = await hass.config_entries.flow.async_configure(
        result2["flow_id"],
        {
            "email": "verisure_my_pages@example.com",
            "password": "SuperS3cr3t!",
        },
    )
    await hass.async_block_till_done()

    mock_verisure_config_flow.login_mfa.side_effect = None

    assert result3.get("type") == FlowResultType.FORM
    assert result3.get("step_id") == "user"
    assert result3.get("errors") == {"base": "unknown_mfa"}

    result4 = await hass.config_entries.flow.async_configure(
        result3["flow_id"],
        {
            "email": "verisure_my_pages@example.com",
            "password": "SuperS3cr3t!",
        },
    )
    await hass.async_block_till_done()

    assert result4.get("type") == FlowResultType.FORM
    assert result4.get("step_id") == "mfa"

    mock_verisure_config_flow.mfa_validate.side_effect = side_effect

    result5 = await hass.config_entries.flow.async_configure(
        result4["flow_id"],
        {
            "code": "123456",
        },
    )
    assert result5.get("type") == FlowResultType.FORM
    assert result5.get("step_id") == "mfa"
    assert result5.get("errors") == {"base": error}

    mock_verisure_config_flow.installations = [
        mock_verisure_config_flow.installations[0]
    ]

    mock_verisure_config_flow.mfa_validate.side_effect = None
    mock_verisure_config_flow.login.side_effect = None

    result6 = await hass.config_entries.flow.async_configure(
        result5["flow_id"],
        {
            "code": "654321",
        },
    )
    await hass.async_block_till_done()

    assert result6.get("type") == FlowResultType.CREATE_ENTRY
    assert result6.get("title") == "ascending (12345th street)"
    assert result6.get("data") == {
        CONF_GIID: "12345",
        CONF_EMAIL: "verisure_my_pages@example.com",
        CONF_PASSWORD: "SuperS3cr3t!",
    }

    assert len(mock_verisure_config_flow.login.mock_calls) == 4
    assert len(mock_verisure_config_flow.login_mfa.mock_calls) == 2
    assert len(mock_verisure_config_flow.mfa_validate.mock_calls) == 2
    assert len(mock_setup_entry.mock_calls) == 1


async def test_dhcp(hass: HomeAssistant) -> None:
    """Test that DHCP discovery works."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        data=dhcp.DhcpServiceInfo(
            ip="1.2.3.4", macaddress="01:23:45:67:89:ab", hostname="mock_hostname"
        ),
        context={"source": config_entries.SOURCE_DHCP},
    )

    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == "user"


async def test_reauth_flow(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_verisure_config_flow: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a reauthentication flow."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "unique_id": mock_config_entry.unique_id,
            "entry_id": mock_config_entry.entry_id,
        },
        data=mock_config_entry.data,
    )
    assert result.get("step_id") == "reauth_confirm"
    assert result.get("type") == FlowResultType.FORM
    assert result.get("errors") == {}

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "email": "verisure_my_pages@example.com",
            "password": "correct horse battery staple",
        },
    )
    await hass.async_block_till_done()

    assert result2.get("type") == FlowResultType.ABORT
    assert result2.get("reason") == "reauth_successful"
    assert mock_config_entry.data == {
        CONF_GIID: "12345",
        CONF_EMAIL: "verisure_my_pages@example.com",
        CONF_PASSWORD: "correct horse battery staple",
    }

    assert len(mock_verisure_config_flow.login.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_reauth_flow_with_mfa(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_verisure_config_flow: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a reauthentication flow."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "unique_id": mock_config_entry.unique_id,
            "entry_id": mock_config_entry.entry_id,
        },
        data=mock_config_entry.data,
    )
    assert result.get("step_id") == "reauth_confirm"
    assert result.get("type") == FlowResultType.FORM
    assert result.get("errors") == {}

    mock_verisure_config_flow.login.side_effect = VerisureLoginError(
        "Multifactor authentication enabled, disable or create MFA cookie"
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "email": "verisure_my_pages@example.com",
            "password": "correct horse battery staple!",
        },
    )
    await hass.async_block_till_done()

    assert result2.get("type") == FlowResultType.FORM
    assert result2.get("step_id") == "reauth_mfa"

    mock_verisure_config_flow.login.side_effect = None

    result3 = await hass.config_entries.flow.async_configure(
        result2["flow_id"],
        {
            "code": "123456",
        },
    )
    await hass.async_block_till_done()

    assert result3.get("type") == FlowResultType.ABORT
    assert result3.get("reason") == "reauth_successful"
    assert mock_config_entry.data == {
        CONF_GIID: "12345",
        CONF_EMAIL: "verisure_my_pages@example.com",
        CONF_PASSWORD: "correct horse battery staple!",
    }

    assert len(mock_verisure_config_flow.login.mock_calls) == 2
    assert len(mock_verisure_config_flow.login_mfa.mock_calls) == 1
    assert len(mock_verisure_config_flow.mfa_validate.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("side_effect", "error"),
    [
        (VerisureLoginError, "invalid_auth"),
        (VerisureError, "unknown"),
    ],
)
async def test_reauth_flow_errors(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_verisure_config_flow: MagicMock,
    mock_config_entry: MockConfigEntry,
    side_effect: Exception,
    error: str,
) -> None:
    """Test a reauthentication flow."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "unique_id": mock_config_entry.unique_id,
            "entry_id": mock_config_entry.entry_id,
        },
        data=mock_config_entry.data,
    )

    mock_verisure_config_flow.login.side_effect = side_effect
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "email": "verisure_my_pages@example.com",
            "password": "WrOngP4ssw0rd!",
        },
    )
    await hass.async_block_till_done()

    assert result2.get("step_id") == "reauth_confirm"
    assert result2.get("type") == FlowResultType.FORM
    assert result2.get("errors") == {"base": error}

    mock_verisure_config_flow.login.side_effect = VerisureLoginError(
        "Multifactor authentication enabled, disable or create MFA cookie"
    )
    mock_verisure_config_flow.login_mfa.side_effect = side_effect

    result3 = await hass.config_entries.flow.async_configure(
        result2["flow_id"],
        {
            "email": "verisure_my_pages@example.com",
            "password": "SuperS3cr3t!",
        },
    )
    await hass.async_block_till_done()

    assert result3.get("type") == FlowResultType.FORM
    assert result3.get("step_id") == "reauth_confirm"
    assert result3.get("errors") == {"base": "unknown_mfa"}

    mock_verisure_config_flow.login_mfa.side_effect = None

    result4 = await hass.config_entries.flow.async_configure(
        result3["flow_id"],
        {
            "email": "verisure_my_pages@example.com",
            "password": "SuperS3cr3t!",
        },
    )
    await hass.async_block_till_done()

    assert result4.get("type") == FlowResultType.FORM
    assert result4.get("step_id") == "reauth_mfa"

    mock_verisure_config_flow.mfa_validate.side_effect = side_effect

    result5 = await hass.config_entries.flow.async_configure(
        result4["flow_id"],
        {
            "code": "123456",
        },
    )
    assert result5.get("type") == FlowResultType.FORM
    assert result5.get("step_id") == "reauth_mfa"
    assert result5.get("errors") == {"base": error}

    mock_verisure_config_flow.mfa_validate.side_effect = None
    mock_verisure_config_flow.login.side_effect = None
    mock_verisure_config_flow.installations = [
        mock_verisure_config_flow.installations[0]
    ]

    await hass.config_entries.flow.async_configure(
        result5["flow_id"],
        {
            "code": "654321",
        },
    )
    await hass.async_block_till_done()

    assert mock_config_entry.data == {
        CONF_GIID: "12345",
        CONF_EMAIL: "verisure_my_pages@example.com",
        CONF_PASSWORD: "SuperS3cr3t!",
    }

    assert len(mock_verisure_config_flow.login.mock_calls) == 4
    assert len(mock_verisure_config_flow.login_mfa.mock_calls) == 2
    assert len(mock_verisure_config_flow.mfa_validate.mock_calls) == 2
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("input", "output"),
    [
        (
            {
                CONF_LOCK_CODE_DIGITS: 5,
                CONF_LOCK_DEFAULT_CODE: "12345",
            },
            {
                CONF_LOCK_CODE_DIGITS: 5,
                CONF_LOCK_DEFAULT_CODE: "12345",
            },
        ),
        (
            {
                CONF_LOCK_DEFAULT_CODE: "",
            },
            {
                CONF_LOCK_DEFAULT_CODE: "",
                CONF_LOCK_CODE_DIGITS: DEFAULT_LOCK_CODE_DIGITS,
            },
        ),
    ],
)
async def test_options_flow(
    hass: HomeAssistant, input: dict[str, int | str], output: dict[str, int | str]
) -> None:
    """Test options config flow."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="12345",
        data={},
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.verisure.async_setup_entry",
        return_value=True,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input=input,
    )

    assert result.get("type") == FlowResultType.CREATE_ENTRY
    assert result.get("data") == output


async def test_options_flow_code_format_mismatch(hass: HomeAssistant) -> None:
    """Test options config flow with a code format mismatch."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="12345",
        data={},
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.verisure.async_setup_entry",
        return_value=True,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == "init"
    assert result.get("errors") == {}

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_LOCK_CODE_DIGITS: 5,
            CONF_LOCK_DEFAULT_CODE: "123",
        },
    )

    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == "init"
    assert result.get("errors") == {"base": "code_format_mismatch"}
