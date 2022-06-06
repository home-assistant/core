"""Test the Wallbox config flow."""
from http import HTTPStatus
from unittest.mock import Mock, patch

from requests.exceptions import HTTPError

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.wallbox import config_flow
from homeassistant.components.wallbox.const import DOMAIN
from homeassistant.core import HomeAssistant

from tests.components.wallbox import entry, setup_integration, test_response


async def test_show_set_form(hass: HomeAssistant) -> None:
    """Test that the setup form is served."""
    flow = config_flow.ConfigFlow()
    flow.hass = hass
    result = await flow.async_step_user(user_input=None)

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"


async def test_form_cannot_authenticate(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    with patch(
        "wallbox.Wallbox.authenticate",
        return_value=None,
        side_effect=HTTPError(
            Mock(status=HTTPStatus.FORBIDDEN),
            response=Mock(status_code=HTTPStatus.FORBIDDEN),
        ),
    ), patch(
        "wallbox.Wallbox.getChargerStatus",
        return_value=test_response,
        side_effect=HTTPError(
            Mock(status=HTTPStatus.FORBIDDEN),
            response=Mock(status_code=HTTPStatus.FORBIDDEN),
        ),
    ):

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "station": "12345",
                "username": "test-username",
                "password": "test-password",
            },
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "wallbox.Wallbox.authenticate",
        return_value=None,
        side_effect=HTTPError(
            Mock(status=HTTPStatus.NOT_FOUND),
            response=Mock(status_code=HTTPStatus.NOT_FOUND),
        ),
    ), patch(
        "wallbox.Wallbox.getChargerStatus",
        return_value=test_response,
        side_effect=HTTPError(
            Mock(status=HTTPStatus.NOT_FOUND),
            response=Mock(status_code=HTTPStatus.NOT_FOUND),
        ),
    ):

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "station": "12345",
                "username": "test-username",
                "password": "test-password",
            },
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_validate_input(hass: HomeAssistant) -> None:
    """Test we can validate input."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch("wallbox.Wallbox.authenticate", return_value=None,), patch(
        "wallbox.Wallbox.getChargerStatus",
        return_value=test_response,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "station": "12345",
                "username": "test-username",
                "password": "test-password",
            },
        )

    assert result2["title"] == "Wallbox Portal"
    assert result2["data"]["station"] == "12345"


async def test_form_reauth(hass: HomeAssistant) -> None:
    """Test we handle reauth flow."""
    await setup_integration(hass)
    assert entry.state == config_entries.ConfigEntryState.LOADED

    with patch("wallbox.Wallbox.authenticate", return_value=None,), patch(
        "wallbox.Wallbox.getChargerStatus",
        return_value=test_response,
    ):

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={
                "source": config_entries.SOURCE_REAUTH,
                "entry_id": entry.entry_id,
            },
        )

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "station": "12345",
                "username": "test-username",
                "password": "test-password",
            },
        )

    assert result2["type"] == "abort"
    assert result2["reason"] == "reauth_successful"

    await hass.config_entries.async_unload(entry.entry_id)


async def test_form_reauth_invalid(hass: HomeAssistant) -> None:
    """Test we handle reauth invalid flow."""
    await setup_integration(hass)
    assert entry.state == config_entries.ConfigEntryState.LOADED

    with patch("wallbox.Wallbox.authenticate", return_value=None,), patch(
        "wallbox.Wallbox.getChargerStatus",
        return_value=test_response,
    ):

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={
                "source": config_entries.SOURCE_REAUTH,
                "entry_id": entry.entry_id,
            },
        )

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "station": "12345678",
                "username": "test-username",
                "password": "test-password",
            },
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "reauth_invalid"}

    await hass.config_entries.async_unload(entry.entry_id)
