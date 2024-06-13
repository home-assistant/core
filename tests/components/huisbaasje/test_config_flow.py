"""Test the Huisbaasje config flow."""

from unittest.mock import patch

from energyflip import (
    EnergyFlipConnectionException,
    EnergyFlipException,
    EnergyFlipUnauthenticatedException,
)

from homeassistant import config_entries
from homeassistant.components.huisbaasje.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


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
            return_value=True,
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
            return_value=True,
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
