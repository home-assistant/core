"""Test the Huisbaasje config flow."""

from collections.abc import Generator
from contextlib import contextmanager
from unittest.mock import patch

from energyflip import (
    EnergyFlipConnectionException,
    EnergyFlipException,
    EnergyFlipUnauthenticatedException,
)
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant import config_entries
from homeassistant.components.huisbaasje.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


@contextmanager
def _patch_success() -> Generator[None]:
    """Patch a successful login and entry setup."""
    with (
        patch("energyflip.EnergyFlip.authenticate", return_value=None),
        patch("energyflip.EnergyFlip.customer_overview", return_value=None),
        patch("energyflip.EnergyFlip.get_user_id", return_value="test-id"),
        patch(
            "homeassistant.components.huisbaasje.async_setup_entry",
            return_value=None,
        ),
    ):
        yield


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with (
        patch(
            "energyflip.EnergyFlip.authenticate", return_value=None
        ) as mock_authenticate,
        patch(
            "energyflip.EnergyFlip.customer_overview", return_value=None
        ) as mock_customer_overview,
        patch(
            "energyflip.EnergyFlip.get_user_id",
            return_value="test-id",
        ) as mock_get_user_id,
        patch(
            "homeassistant.components.huisbaasje.async_setup_entry",
            return_value=None,
        ) as mock_setup_entry,
    ):
        form_result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "username": "test-username",
                "password": "test-password",
            },
        )
        await hass.async_block_till_done()

    assert form_result["type"] is FlowResultType.CREATE_ENTRY
    assert form_result["title"] == "test-username"
    assert form_result["data"] == {
        "id": "test-id",
        "username": "test-username",
        "password": "test-password",
    }
    assert form_result["result"].unique_id == "test-id"
    assert len(mock_authenticate.mock_calls) == 1
    assert len(mock_customer_overview.mock_calls) == 1
    assert len(mock_get_user_id.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_invalid_auth(hass: HomeAssistant) -> None:
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "energyflip.EnergyFlip.authenticate",
        side_effect=EnergyFlipException,
    ):
        form_result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "username": "test-username",
                "password": "test-password",
            },
        )

    assert form_result["type"] is FlowResultType.FORM
    assert form_result["errors"] == {"base": "invalid_auth"}

    with _patch_success():
        form_result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "username": "test-username",
                "password": "test-password",
            },
        )
        await hass.async_block_till_done()

    assert form_result["type"] is FlowResultType.CREATE_ENTRY


async def test_form_authenticate_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error in authenticate."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "energyflip.EnergyFlip.authenticate",
        side_effect=EnergyFlipConnectionException,
    ):
        form_result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "username": "test-username",
                "password": "test-password",
            },
        )

    assert form_result["type"] is FlowResultType.FORM
    assert form_result["errors"] == {"base": "cannot_connect"}

    with _patch_success():
        form_result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "username": "test-username",
                "password": "test-password",
            },
        )
        await hass.async_block_till_done()

    assert form_result["type"] is FlowResultType.CREATE_ENTRY


async def test_form_authenticate_unknown_error(hass: HomeAssistant) -> None:
    """Test we handle an unknown error in authenticate."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "energyflip.EnergyFlip.authenticate",
        side_effect=Exception,
    ):
        form_result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "username": "test-username",
                "password": "test-password",
            },
        )

    assert form_result["type"] is FlowResultType.FORM
    assert form_result["errors"] == {"base": "unknown"}

    with _patch_success():
        form_result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "username": "test-username",
                "password": "test-password",
            },
        )
        await hass.async_block_till_done()

    assert form_result["type"] is FlowResultType.CREATE_ENTRY


async def test_form_customer_overview_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error in customer_overview."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with (
        patch("energyflip.EnergyFlip.authenticate", return_value=None),
        patch(
            "energyflip.EnergyFlip.customer_overview",
            side_effect=EnergyFlipConnectionException,
        ),
    ):
        form_result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "username": "test-username",
                "password": "test-password",
            },
        )

    assert form_result["type"] is FlowResultType.FORM
    assert form_result["errors"] == {"base": "cannot_connect"}

    with _patch_success():
        form_result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "username": "test-username",
                "password": "test-password",
            },
        )
        await hass.async_block_till_done()

    assert form_result["type"] is FlowResultType.CREATE_ENTRY


async def test_form_customer_overview_authentication_error(hass: HomeAssistant) -> None:
    """Test we handle an unknown error in customer_overview."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with (
        patch("energyflip.EnergyFlip.authenticate", return_value=None),
        patch(
            "energyflip.EnergyFlip.customer_overview",
            side_effect=EnergyFlipUnauthenticatedException,
        ),
    ):
        form_result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "username": "test-username",
                "password": "test-password",
            },
        )

    assert form_result["type"] is FlowResultType.FORM
    assert form_result["errors"] == {"base": "invalid_auth"}

    with _patch_success():
        form_result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "username": "test-username",
                "password": "test-password",
            },
        )
        await hass.async_block_till_done()

    assert form_result["type"] is FlowResultType.CREATE_ENTRY


async def test_form_customer_overview_unknown_error(hass: HomeAssistant) -> None:
    """Test we handle an unknown error in customer_overview."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with (
        patch("energyflip.EnergyFlip.authenticate", return_value=None),
        patch(
            "energyflip.EnergyFlip.customer_overview",
            side_effect=Exception,
        ),
    ):
        form_result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "username": "test-username",
                "password": "test-password",
            },
        )

    assert form_result["type"] is FlowResultType.FORM
    assert form_result["errors"] == {"base": "unknown"}

    with _patch_success():
        form_result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "username": "test-username",
                "password": "test-password",
            },
        )
        await hass.async_block_till_done()

    assert form_result["type"] is FlowResultType.CREATE_ENTRY


async def test_form_entry_exists(hass: HomeAssistant) -> None:
    """Test we handle an already existing entry."""
    MockConfigEntry(
        unique_id="test-id",
        domain=DOMAIN,
        data={
            "id": "test-id",
            "username": "test-username",
            "password": "test-password",
        },
        title="test-username",
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with (
        patch("energyflip.EnergyFlip.authenticate", return_value=None),
        patch("energyflip.EnergyFlip.customer_overview", return_value=None),
        patch(
            "energyflip.EnergyFlip.get_user_id",
            return_value="test-id",
        ),
        patch(
            "homeassistant.components.huisbaasje.async_setup_entry",
            return_value=None,
        ),
    ):
        form_result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "username": "test-username",
                "password": "test-password",
            },
        )

    assert form_result["type"] is FlowResultType.ABORT
    assert form_result["reason"] == "already_configured"


def _mock_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Add an entry for the test-id account."""
    entry = MockConfigEntry(
        unique_id="test-id",
        domain=DOMAIN,
        data={
            "id": "test-id",
            "username": "test-username",
            "password": "old-password",
        },
        title="test-username",
    )
    entry.add_to_hass(hass)
    return entry


async def test_reauth(hass: HomeAssistant) -> None:
    """Test a successful reauthentication."""
    entry = _mock_entry(hass)

    result = await entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    with (
        patch("energyflip.EnergyFlip.authenticate", return_value=None),
        patch("energyflip.EnergyFlip.customer_overview", return_value=None),
        patch("energyflip.EnergyFlip.get_user_id", return_value="test-id"),
        patch(
            "homeassistant.components.huisbaasje.async_setup_entry",
            return_value=None,
        ) as mock_setup_entry,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"password": "new-password"}
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data == {
        "id": "test-id",
        "username": "test-username",
        "password": "new-password",
    }
    assert len(mock_setup_entry.mock_calls) == 1
    assert entry.state is ConfigEntryState.LOADED


@pytest.mark.parametrize(
    ("side_effect", "error"),
    [
        pytest.param(
            EnergyFlipConnectionException, "cannot_connect", id="cannot_connect"
        ),
        pytest.param(EnergyFlipException, "invalid_auth", id="invalid_auth"),
        pytest.param(
            EnergyFlipUnauthenticatedException,
            "invalid_auth",
            id="unauthenticated",
        ),
        pytest.param(Exception, "unknown", id="unknown"),
    ],
)
async def test_reauth_errors(
    hass: HomeAssistant, side_effect: type[Exception], error: str
) -> None:
    """Test errors during reauthentication and a successful retry."""
    entry = _mock_entry(hass)

    result = await entry.start_reauth_flow(hass)

    with patch("energyflip.EnergyFlip.authenticate", side_effect=side_effect):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"password": "new-password"}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == {"base": error}

    with _patch_success():
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"password": "new-password"}
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data["password"] == "new-password"


async def test_reauth_wrong_account(hass: HomeAssistant) -> None:
    """Test reauthentication with credentials of another account."""
    entry = _mock_entry(hass)

    result = await entry.start_reauth_flow(hass)

    with (
        patch("energyflip.EnergyFlip.authenticate", return_value=None),
        patch("energyflip.EnergyFlip.customer_overview", return_value=None),
        patch("energyflip.EnergyFlip.get_user_id", return_value="other-id"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"password": "new-password"}
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "wrong_account"
    assert entry.data["password"] == "old-password"
