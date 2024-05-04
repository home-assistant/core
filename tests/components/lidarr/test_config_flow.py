"""Test Lidarr config flow."""

from homeassistant.components.lidarr.const import DEFAULT_NAME, DOMAIN
from homeassistant.config_entries import SOURCE_REAUTH, SOURCE_USER
from homeassistant.const import CONF_API_KEY, CONF_SOURCE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import CONF_DATA, MOCK_INPUT, ComponentSetup


async def test_flow_user_form(hass: HomeAssistant, connection) -> None:
    """Test that the user set up form is served."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_USER},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=MOCK_INPUT,
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == DEFAULT_NAME
    assert result["data"] == CONF_DATA


async def test_flow_user_invalid_auth(hass: HomeAssistant, invalid_auth) -> None:
    """Test invalid authentication."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_USER},
        data=CONF_DATA,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"]["base"] == "invalid_auth"


async def test_flow_user_cannot_connect(hass: HomeAssistant, cannot_connect) -> None:
    """Test connection error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_USER},
        data=CONF_DATA,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"]["base"] == "cannot_connect"


async def test_wrong_app(hass: HomeAssistant, wrong_app) -> None:
    """Test we show user form on wrong app."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_USER},
        data=MOCK_INPUT,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"]["base"] == "wrong_app"


async def test_zeroconf_failed(hass: HomeAssistant, zeroconf_failed) -> None:
    """Test we show user form on zeroconf failure."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_USER},
        data=MOCK_INPUT,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"]["base"] == "zeroconf_failed"


async def test_flow_user_unknown_error(hass: HomeAssistant, unknown) -> None:
    """Test unknown error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_USER},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=CONF_DATA,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"]["base"] == "unknown"


async def test_flow_reauth(
    hass: HomeAssistant, setup_integration: ComponentSetup, connection
) -> None:
    """Test reauth."""
    await setup_integration()
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            CONF_SOURCE: SOURCE_REAUTH,
            "entry_id": entry.entry_id,
            "unique_id": entry.unique_id,
        },
        data=CONF_DATA,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_API_KEY: "abc123"},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data[CONF_API_KEY] == "abc123"
