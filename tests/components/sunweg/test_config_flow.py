"""Tests for the Sun WEG server config flow."""

from unittest.mock import patch

from sunweg.api import APIHelper, SunWegApiError

from homeassistant import config_entries
from homeassistant.components.sunweg.const import CONF_PLANT_ID, DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .common import SUNWEG_MOCK_ENTRY, SUNWEG_USER_INPUT

from tests.common import MockConfigEntry


async def test_show_authenticate_form(hass: HomeAssistant) -> None:
    """Test that the setup form is served."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"


async def test_incorrect_login(hass: HomeAssistant) -> None:
    """Test that it shows the appropriate error when an incorrect username/password/server is entered."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch.object(APIHelper, "authenticate", return_value=False):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], SUNWEG_USER_INPUT
        )

    assert result["type"] is FlowResultType.FORM
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

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "timeout_connect"}


async def test_reauth(hass: HomeAssistant, plant_fixture, inverter_fixture) -> None:
    """Test reauth flow."""
    mock_entry = SUNWEG_MOCK_ENTRY
    mock_entry.add_to_hass(hass)

    entries = hass.config_entries.async_entries()
    assert len(entries) == 1
    assert entries[0].data[CONF_USERNAME] == SUNWEG_MOCK_ENTRY.data[CONF_USERNAME]
    assert entries[0].data[CONF_PASSWORD] == SUNWEG_MOCK_ENTRY.data[CONF_PASSWORD]

    result = await mock_entry.start_reauth_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    with patch.object(APIHelper, "authenticate", return_value=False):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=SUNWEG_USER_INPUT,
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == {"base": "invalid_auth"}

    with patch.object(
        APIHelper, "authenticate", side_effect=SunWegApiError("Internal Server Error")
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=SUNWEG_USER_INPUT,
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == {"base": "timeout_connect"}

    with (
        patch.object(APIHelper, "authenticate", return_value=True),
        patch.object(APIHelper, "listPlants", return_value=[plant_fixture]),
        patch.object(APIHelper, "plant", return_value=plant_fixture),
        patch.object(APIHelper, "inverter", return_value=inverter_fixture),
        patch.object(APIHelper, "complete_inverter"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=SUNWEG_USER_INPUT,
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"

    entries = hass.config_entries.async_entries()

    assert len(entries) == 1
    assert entries[0].data[CONF_USERNAME] == SUNWEG_USER_INPUT[CONF_USERNAME]
    assert entries[0].data[CONF_PASSWORD] == SUNWEG_USER_INPUT[CONF_PASSWORD]


async def test_no_plants_on_account(hass: HomeAssistant) -> None:
    """Test registering an integration with wrong auth then with no plants available."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch.object(APIHelper, "authenticate", return_value=False):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], SUNWEG_USER_INPUT
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "invalid_auth"}

    with (
        patch.object(APIHelper, "authenticate", return_value=True),
        patch.object(APIHelper, "listPlants", return_value=[]),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], SUNWEG_USER_INPUT
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_plants"


async def test_multiple_plant_ids(hass: HomeAssistant, plant_fixture) -> None:
    """Test registering an integration and finishing flow with an selected plant_id."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with (
        patch.object(APIHelper, "authenticate", return_value=True),
        patch.object(
            APIHelper, "listPlants", return_value=[plant_fixture, plant_fixture]
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], SUNWEG_USER_INPUT
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "plant"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_PLANT_ID: 123456}
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_USERNAME] == SUNWEG_USER_INPUT[CONF_USERNAME]
    assert result["data"][CONF_PASSWORD] == SUNWEG_USER_INPUT[CONF_PASSWORD]
    assert result["data"][CONF_PLANT_ID] == 123456


async def test_one_plant_on_account(hass: HomeAssistant, plant_fixture) -> None:
    """Test registering an integration and finishing flow with current plant_id."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with (
        patch.object(APIHelper, "authenticate", return_value=True),
        patch.object(
            APIHelper,
            "listPlants",
            return_value=[plant_fixture],
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], SUNWEG_USER_INPUT
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
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

    with (
        patch.object(APIHelper, "authenticate", return_value=True),
        patch.object(
            APIHelper,
            "listPlants",
            return_value=[plant_fixture],
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], SUNWEG_USER_INPUT
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
