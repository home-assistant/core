"""Test the ConnectedCars config flow."""
from unittest.mock import AsyncMock, patch

from connectedcars.client import ConnectedCarsClient

from homeassistant import config_entries, setup
from homeassistant.components.connectedcars.config_flow import (
    CannotGetEmail,
    CannotGetVin,
    ConnectedcarsApiHandler,
    InvalidAuth,
)
from homeassistant.components.connectedcars.const import CONF_NAMESPACE, DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME


def _get_mock_cc_client(
    get_async_query_data={
        "data": {
            "viewer": {
                "email": "test@email.tld",
                "vehicles": [{"vehicle": {"vin": "test-vin"}}],
            }
        }
    }
):
    mock = AsyncMock(ConnectedCarsClient)
    mock.async_query.return_value = get_async_query_data

    return mock


async def test_form(hass):
    """Test we get the form."""
    await setup.async_setup_component(hass, DOMAIN, {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["errors"] == {}


async def test_setup(hass):
    """Test setup results in a create_entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    cc_client = _get_mock_cc_client()

    with patch(
        "homeassistant.components.connectedcars.config_flow.ConnectedCarsClient",
        return_value=cc_client,
    ), patch(
        "homeassistant.components.connectedcars.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        test_result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_NAMESPACE: "test-namespace",
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "test-password",
            },
        )
        await hass.async_block_till_done()

    assert test_result["type"] == "create_entry"
    assert test_result["data"] == {
        CONF_NAMESPACE: "test-namespace",
        CONF_USERNAME: "test-username",
        CONF_PASSWORD: "test-password",
    }

    assert len(mock_setup_entry.mock_calls) == 1


async def test_full_user_flow_implementation(hass) -> None:
    """Test the full manual user flow from start to finish."""
    cc_client = _get_mock_cc_client()

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["step_id"] == "user"
    assert result["type"] == "form"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_NAMESPACE: "test-namespace",
            CONF_USERNAME: "test-username",
            CONF_PASSWORD: "test-password",
        },
    )

    with patch(
        "homeassistant.components.connectedcars.config_flow.ConnectedCarsClient",
        return_value=cc_client,
    ), patch(
        "homeassistant.components.connectedcars.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        test_result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_NAMESPACE: "test-namespace",
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "test-password",
            },
        )
        await hass.async_block_till_done()

    assert test_result["data"][CONF_NAMESPACE] == "test-namespace"
    assert test_result["data"][CONF_USERNAME] == "test-username"
    assert test_result["data"][CONF_PASSWORD] == "test-password"
    assert test_result["title"] == "test@email.tld - test-vin"
    assert test_result["type"] == "create_entry"

    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_invalid_auth(hass):
    """Test we handle invalid auth."""
    cc_client = _get_mock_cc_client()

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.connectedcars.config_flow.ConnectedCarsClient",
        return_value=cc_client,
    ), patch(
        "homeassistant.components.connectedcars.config_flow.ConnectedcarsApiHandler.authenticate",
        side_effect=InvalidAuth,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_NAMESPACE: "test-namespace",
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "test-password",
            },
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_form_cannot_get_vin(hass):
    """Test we handle error of noy getting vin."""
    cc_client = _get_mock_cc_client()

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.connectedcars.config_flow.ConnectedCarsClient",
        return_value=cc_client,
    ), patch(
        "homeassistant.components.connectedcars.config_flow.ConnectedcarsApiHandler.get_vin",
        side_effect=CannotGetVin,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_NAMESPACE: "test-namespace",
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "test-password",
            },
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "cannot_get_vin"}


async def test_form_cannot_get_email(hass):
    """Test we handle error of noy getting vin."""
    cc_client = _get_mock_cc_client()

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.connectedcars.config_flow.ConnectedCarsClient",
        return_value=cc_client,
    ), patch(
        "homeassistant.components.connectedcars.config_flow.ConnectedcarsApiHandler.get_email",
        side_effect=CannotGetEmail,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_NAMESPACE: "test-namespace",
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "test-password",
            },
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "cannot_get_email"}


async def test_form_unknown_error(hass):
    """Test we handle error of noy getting vin."""
    cc_client = _get_mock_cc_client()

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.connectedcars.config_flow.ConnectedCarsClient",
        return_value=cc_client,
    ), patch(
        "homeassistant.components.connectedcars.config_flow.ConnectedcarsApiHandler.authenticate",
        side_effect=Exception,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_NAMESPACE: "test-namespace",
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "test-password",
            },
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "unknown"}


async def test_connectedcars_api_handler_get_email_empty_user_data():
    """Test we handle error of noy getting vin."""
    cc_client = _get_mock_cc_client()

    ccapih = ConnectedcarsApiHandler("test-namespace")
    ccapih.client = cc_client
    ccapih.user_data = None
    result = await ConnectedcarsApiHandler.get_email(ccapih)

    assert result == "test@email.tld"
