"""Test the devolo_home_control config flow."""

from homeassistant import config_entries
from homeassistant.components.devolo_home_control.const import DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .const import (
    DISCOVERY_INFO,
    DISCOVERY_INFO_WRONG_DEVICE,
    DISCOVERY_INFO_WRONG_DEVOLO_DEVICE,
)
from .mocks import MydevoloMock

from tests.common import MockConfigEntry


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["step_id"] == "user"
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_USERNAME: "test-username", CONF_PASSWORD: "test-password"},
    )
    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "devolo Home Control"
    assert result2["data"] == {
        CONF_USERNAME: "test-username",
        CONF_PASSWORD: "test-password",
    }


async def test_form_invalid_credentials_user(
    hass: HomeAssistant, mydevolo: MydevoloMock
) -> None:
    """Test if we get the error message on invalid credentials."""
    mydevolo.valid_credentials = False
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_USERNAME: "test-username", CONF_PASSWORD: "wrong-password"},
    )
    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_auth"}

    mydevolo.valid_credentials = True
    result3 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_USERNAME: "test-username", CONF_PASSWORD: "correct-password"},
    )
    assert result3["type"] is FlowResultType.CREATE_ENTRY
    assert result3["data"] == {
        CONF_USERNAME: "test-username",
        CONF_PASSWORD: "correct-password",
    }


async def test_form_already_configured(hass: HomeAssistant) -> None:
    """Test if we get the error message on already configured."""
    MockConfigEntry(domain=DOMAIN, unique_id="123456", data={}).add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data={CONF_USERNAME: "test-username", CONF_PASSWORD: "test-password"},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_form_zeroconf(hass: HomeAssistant) -> None:
    """Test that the zeroconf confirmation form is served."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=DISCOVERY_INFO,
    )
    assert result["step_id"] == "zeroconf_confirm"
    assert result["type"] is FlowResultType.FORM

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_USERNAME: "test-username", CONF_PASSWORD: "test-password"},
    )
    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "devolo Home Control"
    assert result2["data"] == {
        CONF_USERNAME: "test-username",
        CONF_PASSWORD: "test-password",
    }


async def test_form_invalid_credentials_zeroconf(
    hass: HomeAssistant, mydevolo: MydevoloMock
) -> None:
    """Test if we get the error message on invalid credentials."""
    mydevolo.valid_credentials = False
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=DISCOVERY_INFO,
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_USERNAME: "test-username", CONF_PASSWORD: "test-password"},
    )
    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_auth"}

    mydevolo.valid_credentials = True
    result3 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_USERNAME: "test-username", CONF_PASSWORD: "correct-password"},
    )
    assert result3["type"] is FlowResultType.CREATE_ENTRY


async def test_zeroconf_wrong_device(hass: HomeAssistant) -> None:
    """Test that the zeroconf ignores wrong devices."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=DISCOVERY_INFO_WRONG_DEVOLO_DEVICE,
    )
    assert result["reason"] == "Not a devolo Home Control gateway."
    assert result["type"] is FlowResultType.ABORT

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=DISCOVERY_INFO_WRONG_DEVICE,
    )

    assert result["reason"] == "Not a devolo Home Control gateway."
    assert result["type"] is FlowResultType.ABORT


async def test_form_reauth(hass: HomeAssistant) -> None:
    """Test that the reauth confirmation form is served."""
    mock_config = MockConfigEntry(
        domain=DOMAIN,
        unique_id="123456",
        data={
            CONF_USERNAME: "test-username",
            CONF_PASSWORD: "test-password",
        },
    )
    mock_config.add_to_hass(hass)
    result = await mock_config.start_reauth_flow(hass)
    assert result["step_id"] == "reauth_confirm"
    assert result["type"] is FlowResultType.FORM

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_USERNAME: "test-username-new", CONF_PASSWORD: "test-password-new"},
    )
    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "reauth_successful"


async def test_form_invalid_credentials_reauth(
    hass: HomeAssistant, mydevolo: MydevoloMock
) -> None:
    """Test if we get the error message on invalid credentials."""
    mydevolo.valid_credentials = False
    mock_config = MockConfigEntry(
        domain=DOMAIN,
        unique_id="123456",
        data={
            CONF_USERNAME: "test-username",
            CONF_PASSWORD: "test-password",
        },
    )
    mock_config.add_to_hass(hass)
    result = await mock_config.start_reauth_flow(hass)

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_USERNAME: "test-username", CONF_PASSWORD: "wrong-password"},
    )
    assert result2["errors"] == {"base": "invalid_auth"}
    assert result2["type"] is FlowResultType.FORM

    mydevolo.valid_credentials = True
    result3 = await hass.config_entries.flow.async_configure(
        result2["flow_id"],
        {CONF_USERNAME: "test-username-new", CONF_PASSWORD: "correct-password"},
    )
    assert result3["reason"] == "reauth_successful"
    assert result3["type"] is FlowResultType.ABORT


async def test_form_uuid_change_reauth(hass: HomeAssistant) -> None:
    """Test that the reauth confirmation form is served."""
    mock_config = MockConfigEntry(
        domain=DOMAIN,
        unique_id="123457",
        data={
            CONF_USERNAME: "test-username",
            CONF_PASSWORD: "test-password",
        },
    )
    mock_config.add_to_hass(hass)
    result = await mock_config.start_reauth_flow(hass)
    assert result["step_id"] == "reauth_confirm"
    assert result["type"] is FlowResultType.FORM

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_USERNAME: "test-username-new", CONF_PASSWORD: "test-password-new"},
    )
    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "reauth_failed"}
