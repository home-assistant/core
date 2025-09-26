"""Test the Sure Petcare config flow."""

from unittest.mock import NonCallableMagicMock, patch

from surepy.exceptions import SurePetcareAuthenticationError, SurePetcareError

from homeassistant import config_entries
from homeassistant.components.surepetcare.const import DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_TOKEN, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

INPUT_DATA = {
    "username": "test-username",
    "password": "test-password",
}


async def test_form(hass: HomeAssistant, surepetcare: NonCallableMagicMock) -> None:
    """Test we get the form."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert not result["errors"]

    with patch(
        "homeassistant.components.surepetcare.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "username": "test-username",
                "password": "test-password",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Sure Petcare"
    assert result2["data"] == {
        "username": "test-username",
        "password": "test-password",
        "token": "token",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_invalid_auth(hass: HomeAssistant) -> None:
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.surepetcare.config_flow.surepy.client.SureAPIClient.get_token",
        side_effect=SurePetcareAuthenticationError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "username": "test-username",
                "password": "test-password",
            },
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.surepetcare.config_flow.surepy.client.SureAPIClient.get_token",
        side_effect=SurePetcareError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "username": "test-username",
                "password": "test-password",
            },
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_unknown_error(hass: HomeAssistant) -> None:
    """Test we handle unknown error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.surepetcare.config_flow.surepy.client.SureAPIClient.get_token",
        side_effect=Exception,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "username": "test-username",
                "password": "test-password",
            },
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "unknown"}


async def test_flow_entry_already_exists(
    hass: HomeAssistant, surepetcare: NonCallableMagicMock
) -> None:
    """Test user input for config_entry that already exists."""
    first_entry = MockConfigEntry(
        domain="surepetcare",
        data={
            "username": "test-username",
            "password": "test-password",
        },
        unique_id="test-username",
    )
    first_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.surepetcare.async_setup_entry",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={
                "username": "test-username",
                "password": "test-password",
            },
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reauthentication(
    hass: HomeAssistant, surepetcare: NonCallableMagicMock
) -> None:
    """Test surepetcare reauthentication."""
    old_entry = MockConfigEntry(
        domain="surepetcare",
        data={
            CONF_USERNAME: "test-username",
            CONF_PASSWORD: "test-password",
            CONF_TOKEN: "token",
        },
        unique_id="test-username",
    )
    old_entry.add_to_hass(hass)

    result = await old_entry.start_reauth_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}
    assert result["step_id"] == "reauth_confirm"

    surepetcare.get_token.return_value = "token2"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"password": "test-password2"},
    )
    await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "reauth_successful"

    assert old_entry.data == {
        CONF_USERNAME: "test-username",
        CONF_PASSWORD: "test-password2",
        CONF_TOKEN: "token2",
    }


async def test_reauthentication_failure(hass: HomeAssistant) -> None:
    """Test surepetcare reauthentication failure."""
    old_entry = MockConfigEntry(
        domain="surepetcare",
        data=INPUT_DATA,
        unique_id="USERID",
    )
    old_entry.add_to_hass(hass)

    result = await old_entry.start_reauth_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}
    assert result["step_id"] == "reauth_confirm"

    with patch(
        "homeassistant.components.surepetcare.config_flow.surepy.client.SureAPIClient.get_token",
        side_effect=SurePetcareAuthenticationError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"password": "test-password"},
        )
        await hass.async_block_till_done()

    assert result2["step_id"] == "reauth_confirm"
    assert result["type"] is FlowResultType.FORM
    assert result2["errors"]["base"] == "invalid_auth"


async def test_reauthentication_cannot_connect(hass: HomeAssistant) -> None:
    """Test surepetcare reauthentication failure."""
    old_entry = MockConfigEntry(
        domain="surepetcare",
        data=INPUT_DATA,
        unique_id="USERID",
    )
    old_entry.add_to_hass(hass)

    result = await old_entry.start_reauth_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}
    assert result["step_id"] == "reauth_confirm"

    with patch(
        "homeassistant.components.surepetcare.config_flow.surepy.client.SureAPIClient.get_token",
        side_effect=SurePetcareError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"password": "test-password"},
        )
        await hass.async_block_till_done()

    assert result2["step_id"] == "reauth_confirm"
    assert result["type"] is FlowResultType.FORM
    assert result2["errors"]["base"] == "cannot_connect"


async def test_reauthentication_unknown_failure(hass: HomeAssistant) -> None:
    """Test surepetcare reauthentication failure."""
    old_entry = MockConfigEntry(
        domain="surepetcare",
        data=INPUT_DATA,
        unique_id="USERID",
    )
    old_entry.add_to_hass(hass)

    result = await old_entry.start_reauth_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}
    assert result["step_id"] == "reauth_confirm"

    with patch(
        "homeassistant.components.surepetcare.config_flow.surepy.client.SureAPIClient.get_token",
        side_effect=Exception,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"password": "test-password"},
        )
        await hass.async_block_till_done()

    assert result2["step_id"] == "reauth_confirm"
    assert result["type"] is FlowResultType.FORM
    assert result2["errors"]["base"] == "unknown"
