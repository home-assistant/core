"""Test the Verisure config flow."""
from __future__ import annotations

from unittest.mock import PropertyMock, patch

import pytest
from verisure import Error as VerisureError, LoginError as VerisureLoginError

from homeassistant import config_entries
from homeassistant.components.dhcp import MAC_ADDRESS
from homeassistant.components.verisure.const import (
    CONF_GIID,
    CONF_LOCK_CODE_DIGITS,
    CONF_LOCK_DEFAULT_CODE,
    DEFAULT_LOCK_CODE_DIGITS,
    DOMAIN,
)
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import (
    RESULT_TYPE_ABORT,
    RESULT_TYPE_CREATE_ENTRY,
    RESULT_TYPE_FORM,
)

from tests.common import MockConfigEntry

TEST_INSTALLATIONS = [
    {"giid": "12345", "alias": "ascending", "street": "12345th street"},
    {"giid": "54321", "alias": "descending", "street": "54321th street"},
]
TEST_INSTALLATION = [TEST_INSTALLATIONS[0]]


async def test_full_user_flow_single_installation(hass: HomeAssistant) -> None:
    """Test a full user initiated configuration flow with a single installation."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["step_id"] == "user"
    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.verisure.config_flow.Verisure",
    ) as mock_verisure, patch(
        "homeassistant.components.verisure.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.verisure.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        type(mock_verisure.return_value).installations = PropertyMock(
            return_value=TEST_INSTALLATION
        )
        mock_verisure.login.return_value = True

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "email": "verisure_my_pages@example.com",
                "password": "SuperS3cr3t!",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result2["title"] == "ascending (12345th street)"
    assert result2["data"] == {
        CONF_GIID: "12345",
        CONF_EMAIL: "verisure_my_pages@example.com",
        CONF_PASSWORD: "SuperS3cr3t!",
    }

    assert len(mock_verisure.mock_calls) == 2
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_full_user_flow_multiple_installations(hass: HomeAssistant) -> None:
    """Test a full user initiated configuration flow with multiple installations."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["step_id"] == "user"
    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.verisure.config_flow.Verisure",
    ) as mock_verisure:
        type(mock_verisure.return_value).installations = PropertyMock(
            return_value=TEST_INSTALLATIONS
        )
        mock_verisure.login.return_value = True

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "email": "verisure_my_pages@example.com",
                "password": "SuperS3cr3t!",
            },
        )
        await hass.async_block_till_done()

    assert result2["step_id"] == "installation"
    assert result2["type"] == RESULT_TYPE_FORM
    assert result2["errors"] is None

    with patch(
        "homeassistant.components.verisure.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.verisure.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"], {"giid": "54321"}
        )
        await hass.async_block_till_done()

    assert result3["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result3["title"] == "descending (54321th street)"
    assert result3["data"] == {
        CONF_GIID: "54321",
        CONF_EMAIL: "verisure_my_pages@example.com",
        CONF_PASSWORD: "SuperS3cr3t!",
    }

    assert len(mock_verisure.mock_calls) == 2
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_invalid_login(hass: HomeAssistant) -> None:
    """Test a flow with an invalid Verisure My Pages login."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.verisure.config_flow.Verisure.login",
        side_effect=VerisureLoginError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "email": "verisure_my_pages@example.com",
                "password": "SuperS3cr3t!",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == RESULT_TYPE_FORM
    assert result2["step_id"] == "user"
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_unknown_error(hass: HomeAssistant) -> None:
    """Test a flow with an invalid Verisure My Pages login."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.verisure.config_flow.Verisure.login",
        side_effect=VerisureError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "email": "verisure_my_pages@example.com",
                "password": "SuperS3cr3t!",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == RESULT_TYPE_FORM
    assert result2["step_id"] == "user"
    assert result2["errors"] == {"base": "unknown"}


async def test_dhcp(hass: HomeAssistant) -> None:
    """Test that DHCP discovery works."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        data={MAC_ADDRESS: "01:23:45:67:89:ab"},
        context={"source": config_entries.SOURCE_DHCP},
    )

    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "user"


async def test_reauth_flow(hass: HomeAssistant) -> None:
    """Test a reauthentication flow."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="12345",
        data={
            CONF_EMAIL: "verisure_my_pages@example.com",
            CONF_GIID: "12345",
            CONF_PASSWORD: "SuperS3cr3t!",
        },
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_REAUTH}, data={"entry": entry}
    )
    assert result["step_id"] == "reauth_confirm"
    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.verisure.config_flow.Verisure.login",
        return_value=True,
    ) as mock_verisure, patch(
        "homeassistant.components.verisure.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.verisure.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "email": "verisure_my_pages@example.com",
                "password": "correct horse battery staple",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == RESULT_TYPE_ABORT
    assert result2["reason"] == "reauth_successful"
    assert entry.data == {
        CONF_GIID: "12345",
        CONF_EMAIL: "verisure_my_pages@example.com",
        CONF_PASSWORD: "correct horse battery staple",
    }

    assert len(mock_verisure.mock_calls) == 1
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_reauth_flow_invalid_login(hass: HomeAssistant) -> None:
    """Test a reauthentication flow."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="12345",
        data={
            CONF_EMAIL: "verisure_my_pages@example.com",
            CONF_GIID: "12345",
            CONF_PASSWORD: "SuperS3cr3t!",
        },
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_REAUTH}, data={"entry": entry}
    )

    with patch(
        "homeassistant.components.verisure.config_flow.Verisure.login",
        side_effect=VerisureLoginError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "email": "verisure_my_pages@example.com",
                "password": "WrOngP4ssw0rd!",
            },
        )
        await hass.async_block_till_done()

    assert result2["step_id"] == "reauth_confirm"
    assert result2["type"] == RESULT_TYPE_FORM
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_reauth_flow_unknown_error(hass: HomeAssistant) -> None:
    """Test a reauthentication flow, with an unknown error happening."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="12345",
        data={
            CONF_EMAIL: "verisure_my_pages@example.com",
            CONF_GIID: "12345",
            CONF_PASSWORD: "SuperS3cr3t!",
        },
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_REAUTH}, data={"entry": entry}
    )

    with patch(
        "homeassistant.components.verisure.config_flow.Verisure.login",
        side_effect=VerisureError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "email": "verisure_my_pages@example.com",
                "password": "WrOngP4ssw0rd!",
            },
        )
        await hass.async_block_till_done()

    assert result2["step_id"] == "reauth_confirm"
    assert result2["type"] == RESULT_TYPE_FORM
    assert result2["errors"] == {"base": "unknown"}


@pytest.mark.parametrize(
    "input,output",
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
        "homeassistant.components.verisure.async_setup", return_value=True
    ), patch(
        "homeassistant.components.verisure.async_setup_entry",
        return_value=True,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input=input,
    )

    assert result["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result["data"] == output


async def test_options_flow_code_format_mismatch(hass: HomeAssistant) -> None:
    """Test options config flow with a code format mismatch."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="12345",
        data={},
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.verisure.async_setup", return_value=True
    ), patch(
        "homeassistant.components.verisure.async_setup_entry",
        return_value=True,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "init"
    assert result["errors"] == {}

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_LOCK_CODE_DIGITS: 5,
            CONF_LOCK_DEFAULT_CODE: "123",
        },
    )

    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "init"
    assert result["errors"] == {"base": "code_format_mismatch"}


#
# Below this line are tests that can be removed once the YAML configuration
# has been removed from this integration.
#
@pytest.mark.parametrize(
    "giid,installations",
    [
        ("12345", TEST_INSTALLATION),
        ("12345", TEST_INSTALLATIONS),
        (None, TEST_INSTALLATION),
    ],
)
async def test_imports(
    hass: HomeAssistant, giid: str | None, installations: dict[str, str]
) -> None:
    """Test a YAML import with/without known giid on single/multiple installations."""
    with patch(
        "homeassistant.components.verisure.config_flow.Verisure",
    ) as mock_verisure, patch(
        "homeassistant.components.verisure.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.verisure.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        type(mock_verisure.return_value).installations = PropertyMock(
            return_value=installations
        )
        mock_verisure.login.return_value = True

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={
                CONF_EMAIL: "verisure_my_pages@example.com",
                CONF_GIID: giid,
                CONF_LOCK_CODE_DIGITS: 10,
                CONF_LOCK_DEFAULT_CODE: "123456",
                CONF_PASSWORD: "SuperS3cr3t!",
            },
        )

    assert result["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "ascending (12345th street)"
    assert result["data"] == {
        CONF_EMAIL: "verisure_my_pages@example.com",
        CONF_GIID: "12345",
        CONF_LOCK_CODE_DIGITS: 10,
        CONF_LOCK_DEFAULT_CODE: "123456",
        CONF_PASSWORD: "SuperS3cr3t!",
    }

    assert len(mock_verisure.mock_calls) == 2
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_imports_invalid_login(hass: HomeAssistant) -> None:
    """Test a YAML import that results in a invalid login."""
    with patch(
        "homeassistant.components.verisure.config_flow.Verisure.login",
        side_effect=VerisureLoginError,
    ):

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={
                CONF_EMAIL: "verisure_my_pages@example.com",
                CONF_GIID: None,
                CONF_LOCK_CODE_DIGITS: None,
                CONF_LOCK_DEFAULT_CODE: None,
                CONF_PASSWORD: "SuperS3cr3t!",
            },
        )

    assert result["step_id"] == "user"
    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] == {"base": "invalid_auth"}

    with patch(
        "homeassistant.components.verisure.config_flow.Verisure",
    ) as mock_verisure, patch(
        "homeassistant.components.verisure.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.verisure.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        type(mock_verisure.return_value).installations = PropertyMock(
            return_value=TEST_INSTALLATION
        )
        mock_verisure.login.return_value = True

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "email": "verisure_my_pages@example.com",
                "password": "SuperS3cr3t!",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result2["title"] == "ascending (12345th street)"
    assert result2["data"] == {
        CONF_GIID: "12345",
        CONF_EMAIL: "verisure_my_pages@example.com",
        CONF_PASSWORD: "SuperS3cr3t!",
    }

    assert len(mock_verisure.mock_calls) == 2
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_imports_needs_user_installation_choice(hass: HomeAssistant) -> None:
    """Test a YAML import that needs to use to decide on the installation."""
    with patch(
        "homeassistant.components.verisure.config_flow.Verisure",
    ) as mock_verisure:
        type(mock_verisure.return_value).installations = PropertyMock(
            return_value=TEST_INSTALLATIONS
        )
        mock_verisure.login.return_value = True

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={
                CONF_EMAIL: "verisure_my_pages@example.com",
                CONF_GIID: None,
                CONF_LOCK_CODE_DIGITS: None,
                CONF_LOCK_DEFAULT_CODE: None,
                CONF_PASSWORD: "SuperS3cr3t!",
            },
        )

    assert result["step_id"] == "installation"
    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] is None

    with patch(
        "homeassistant.components.verisure.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.verisure.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"giid": "12345"}
        )
        await hass.async_block_till_done()

    assert result2["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result2["title"] == "ascending (12345th street)"
    assert result2["data"] == {
        CONF_GIID: "12345",
        CONF_EMAIL: "verisure_my_pages@example.com",
        CONF_PASSWORD: "SuperS3cr3t!",
    }

    assert len(mock_verisure.mock_calls) == 2
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize("giid", ["12345", None])
async def test_import_already_exists(hass: HomeAssistant, giid: str | None) -> None:
    """Test that import flow aborts if exists."""
    MockConfigEntry(domain=DOMAIN, data={}, unique_id="12345").add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data={
            CONF_EMAIL: "verisure_my_pages@example.com",
            CONF_PASSWORD: "SuperS3cr3t!",
            CONF_GIID: giid,
        },
    )

    assert result["type"] == RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"
