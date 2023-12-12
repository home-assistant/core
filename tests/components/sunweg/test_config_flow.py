"""Tests for the Sun WEG server config flow."""
from datetime import datetime
from unittest.mock import patch

import pytest
from sunweg.api import APIHelper, LoginError, SunWegApiError
from sunweg.plant import Plant

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.sunweg.const import CONF_PLANT_ID, DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from .common import SUNWEG_USER_INPUT

from tests.common import MockConfigEntry


@pytest.fixture
def plant_fixture() -> Plant:
    """Define Plant fixture."""
    return Plant(
        123456,
        "Plant #123",
        29.5,
        0.5,
        0,
        12.786912,
        24.0,
        "kWh",
        332.2,
        0.012296,
        datetime(2023, 2, 16, 14, 22, 37),
    )


async def test_show_authenticate_form(hass: HomeAssistant) -> None:
    """Test that the setup form is served."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"


async def test_incorrect_login(hass: HomeAssistant) -> None:
    """Test that it shows the appropriate error when an incorrect username/password/server is entered."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch.object(
        APIHelper, "authenticate", side_effect=SunWegApiError("Failed Auth")
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], SUNWEG_USER_INPUT
        )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "invalid_auth"}


async def test_authentication_expired(hass: HomeAssistant) -> None:
    """Test when the authentication information is expired."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch.object(APIHelper, "authenticate", side_effect=LoginError("Failed Auth")):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], SUNWEG_USER_INPUT
        )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "invalid_auth"}


async def test_server_unavailable(hass: HomeAssistant) -> None:
    """Test when the SunWEG server don't respond."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch.object(
        APIHelper, "authenticate", side_effect=SunWegApiError("Internal Server Error")
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], SUNWEG_USER_INPUT
        )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "invalid_auth"}


async def test_no_plants_on_account(hass: HomeAssistant) -> None:
    """Test registering an integration with wrong auth then with no plants available."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch.object(
        APIHelper, "authenticate", side_effect=SunWegApiError("Failed Auth")
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], SUNWEG_USER_INPUT
        )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "invalid_auth"}

    with patch.object(APIHelper, "authenticate", return_value=True), patch.object(
        APIHelper, "listPlants", return_value=[]
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], SUNWEG_USER_INPUT
        )

    assert result["type"] == "abort"
    assert result["reason"] == "no_plants"


async def test_multiple_plant_ids(hass: HomeAssistant, plant_fixture) -> None:
    """Test registering an integration and finishing flow with an selected plant_id."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    user_input = SUNWEG_USER_INPUT.copy()
    plant_list = [plant_fixture, plant_fixture]

    with patch.object(APIHelper, "authenticate", return_value=True), patch.object(
        APIHelper, "listPlants", return_value=plant_list
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input
        )
        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "plant"

        user_input = {CONF_PLANT_ID: 123456}
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input
        )
        await hass.async_block_till_done()

    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_USERNAME] == SUNWEG_USER_INPUT[CONF_USERNAME]
    assert result["data"][CONF_PASSWORD] == SUNWEG_USER_INPUT[CONF_PASSWORD]
    assert result["data"][CONF_PLANT_ID] == 123456


async def test_one_plant_on_account(hass: HomeAssistant, plant_fixture) -> None:
    """Test registering an integration and finishing flow with current plant_id."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    user_input = SUNWEG_USER_INPUT.copy()

    with patch.object(APIHelper, "authenticate", return_value=True), patch.object(
        APIHelper,
        "listPlants",
        return_value=[plant_fixture],
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input
        )

    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_USERNAME] == SUNWEG_USER_INPUT[CONF_USERNAME]
    assert result["data"][CONF_PASSWORD] == SUNWEG_USER_INPUT[CONF_PASSWORD]
    assert result["data"][CONF_PLANT_ID] == 123456


async def test_existing_plant_configured(hass: HomeAssistant, plant_fixture) -> None:
    """Test entering an existing plant_id."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id=123456)
    entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    user_input = SUNWEG_USER_INPUT.copy()

    with patch.object(APIHelper, "authenticate", return_value=True), patch.object(
        APIHelper,
        "listPlants",
        return_value=[plant_fixture],
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input
        )

    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"
