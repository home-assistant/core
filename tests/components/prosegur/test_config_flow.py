"""Test the Prosegur Alarm config flow."""

from collections.abc import Generator
from contextlib import contextmanager
from unittest.mock import patch

import pytest

from homeassistant import config_entries
from homeassistant.components.prosegur.config_flow import CannotConnect, InvalidAuth
from homeassistant.components.prosegur.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


@contextmanager
def _patch_success(contracts: list[dict[str, str]]) -> Generator[None]:
    """Patch a successful login and entry setup."""
    with (
        patch(
            "homeassistant.components.prosegur.config_flow.Installation.list",
            return_value=contracts,
        ),
        patch(
            "homeassistant.components.prosegur.async_setup_entry",
            return_value=True,
        ),
    ):
        yield


async def test_form(hass: HomeAssistant, mock_list_contracts) -> None:
    """Test we get the form."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with (
        patch(
            "homeassistant.components.prosegur.config_flow.Installation.list",
            return_value=mock_list_contracts,
        ) as mock_retrieve,
        patch(
            "homeassistant.components.prosegur.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "username": "test-username",
                "password": "test-password",
                "country": "PT",
            },
        )
        await hass.async_block_till_done()

        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {"contract": "123"},
        )
        await hass.async_block_till_done()

    assert result3["type"] is FlowResultType.CREATE_ENTRY
    assert result3["title"] == "Contract 123"
    assert result3["data"] == {
        "contract": "123",
        "username": "test-username",
        "password": "test-password",
        "country": "PT",
    }
    assert result3["result"].unique_id == "123"
    assert len(mock_setup_entry.mock_calls) == 1

    assert len(mock_retrieve.mock_calls) == 1


async def test_form_invalid_auth(
    hass: HomeAssistant, mock_list_contracts: list[dict[str, str]]
) -> None:
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "pyprosegur.installation.Installation.list",
        side_effect=ConnectionRefusedError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "username": "test-username",
                "password": "test-password",
                "country": "PT",
            },
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_auth"}

    with _patch_success(mock_list_contracts):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {
                "username": "test-username",
                "password": "test-password",
                "country": "PT",
            },
        )
        result4 = await hass.config_entries.flow.async_configure(
            result3["flow_id"],
            {"contract": "123"},
        )

    assert result4["type"] is FlowResultType.CREATE_ENTRY


async def test_form_cannot_connect(
    hass: HomeAssistant, mock_list_contracts: list[dict[str, str]]
) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.prosegur.config_flow.Installation.list",
        side_effect=ConnectionError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "username": "test-username",
                "password": "test-password",
                "country": "PT",
            },
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}

    with _patch_success(mock_list_contracts):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {
                "username": "test-username",
                "password": "test-password",
                "country": "PT",
            },
        )
        result4 = await hass.config_entries.flow.async_configure(
            result3["flow_id"],
            {"contract": "123"},
        )

    assert result4["type"] is FlowResultType.CREATE_ENTRY


async def test_form_unknown_exception(
    hass: HomeAssistant, mock_list_contracts: list[dict[str, str]]
) -> None:
    """Test we handle unknown exceptions."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "pyprosegur.installation.Installation",
        side_effect=ValueError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "username": "test-username",
                "password": "test-password",
                "country": "PT",
            },
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "unknown"}

    with _patch_success(mock_list_contracts):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {
                "username": "test-username",
                "password": "test-password",
                "country": "PT",
            },
        )
        result4 = await hass.config_entries.flow.async_configure(
            result3["flow_id"],
            {"contract": "123"},
        )

    assert result4["type"] is FlowResultType.CREATE_ENTRY


async def test_reauth_flow(hass: HomeAssistant, mock_list_contracts) -> None:
    """Test a reauthentication flow."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="12345",
        data={
            "username": "test-username",
            "password": "test-password",
            "country": "PT",
        },
    )
    entry.add_to_hass(hass)

    result = await entry.start_reauth_flow(hass)
    assert result["step_id"] == "reauth_confirm"
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with (
        patch(
            "homeassistant.components.prosegur.config_flow.Installation.list",
            return_value=mock_list_contracts,
        ) as mock_installation,
        patch(
            "homeassistant.components.prosegur.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "username": "test-username",
                "password": "new_password",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "reauth_successful"
    assert entry.data == {
        "country": "PT",
        "username": "test-username",
        "password": "new_password",
    }

    assert len(mock_installation.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("exception", "base_error"),
    [
        (CannotConnect, "cannot_connect"),
        (InvalidAuth, "invalid_auth"),
        (Exception, "unknown"),
    ],
)
async def test_reauth_flow_error(
    hass: HomeAssistant,
    exception: type[Exception],
    base_error: str,
    mock_list_contracts: list[dict[str, str]],
) -> None:
    """Test a reauthentication flow with errors."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="12345",
        data={
            "username": "test-username",
            "password": "test-password",
            "country": "PT",
        },
    )
    entry.add_to_hass(hass)

    result = await entry.start_reauth_flow(hass)

    with patch(
        "homeassistant.components.prosegur.config_flow.Installation.list",
        side_effect=exception,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "username": "test-username",
                "password": "new_password",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"]["base"] == base_error

    with _patch_success(mock_list_contracts):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {
                "username": "test-username",
                "password": "new_password",
            },
        )

    assert result3["type"] is FlowResultType.ABORT
    assert result3["reason"] == "reauth_successful"
