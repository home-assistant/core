"""Test the nuki config flow."""

from unittest.mock import patch

from pynuki.bridge import InvalidCredentialsException
from requests.exceptions import RequestException

from homeassistant import config_entries
from homeassistant.components.nuki.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo

from .mock import DHCP_FORMATTED_MAC, HOST, MOCK_INFO, NAME, setup_nuki_integration


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with (
        patch(
            "homeassistant.components.nuki.config_flow.NukiBridge.info",
            return_value=MOCK_INFO,
        ),
        patch(
            "homeassistant.components.nuki.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "1.1.1.1",
                CONF_PORT: 8080,
                CONF_TOKEN: "test-token",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "BC614E"
    assert result2["data"] == {
        CONF_HOST: "1.1.1.1",
        CONF_PORT: 8080,
        CONF_TOKEN: "test-token",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_invalid_auth(hass: HomeAssistant) -> None:
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.nuki.config_flow.NukiBridge.info",
        side_effect=InvalidCredentialsException,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "1.1.1.1",
                CONF_PORT: 8080,
                CONF_TOKEN: "test-token",
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
        "homeassistant.components.nuki.config_flow.NukiBridge.info",
        side_effect=RequestException,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "1.1.1.1",
                CONF_PORT: 8080,
                CONF_TOKEN: "test-token",
            },
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_unknown_exception(hass: HomeAssistant) -> None:
    """Test we handle unknown exceptions."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.nuki.config_flow.NukiBridge.info",
        side_effect=Exception,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "1.1.1.1",
                CONF_PORT: 8080,
                CONF_TOKEN: "test-token",
            },
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "unknown"}


async def test_form_already_configured(hass: HomeAssistant) -> None:
    """Test we get the form."""
    await setup_nuki_integration(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.nuki.config_flow.NukiBridge.info",
        return_value=MOCK_INFO,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "1.1.1.1",
                CONF_PORT: 8080,
                CONF_TOKEN: "test-token",
            },
        )

        assert result2["type"] is FlowResultType.ABORT
        assert result2["reason"] == "already_configured"


async def test_dhcp_flow(hass: HomeAssistant) -> None:
    """Test that DHCP discovery for new bridge works."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        data=DhcpServiceInfo(hostname=NAME, ip=HOST, macaddress=DHCP_FORMATTED_MAC),
        context={"source": config_entries.SOURCE_DHCP},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == config_entries.SOURCE_USER

    with (
        patch(
            "homeassistant.components.nuki.config_flow.NukiBridge.info",
            return_value=MOCK_INFO,
        ),
        patch(
            "homeassistant.components.nuki.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "1.1.1.1",
                CONF_PORT: 8080,
                CONF_TOKEN: "test-token",
            },
        )

        assert result2["type"] is FlowResultType.CREATE_ENTRY
        assert result2["title"] == "BC614E"
        assert result2["data"] == {
            CONF_HOST: "1.1.1.1",
            CONF_PORT: 8080,
            CONF_TOKEN: "test-token",
        }

        await hass.async_block_till_done()
        assert len(mock_setup_entry.mock_calls) == 1


async def test_dhcp_flow_already_configured(hass: HomeAssistant) -> None:
    """Test that DHCP doesn't setup already configured devices."""
    await setup_nuki_integration(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        data=DhcpServiceInfo(hostname=NAME, ip=HOST, macaddress=DHCP_FORMATTED_MAC),
        context={"source": config_entries.SOURCE_DHCP},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reauth_success(hass: HomeAssistant) -> None:
    """Test starting a reauthentication flow."""
    entry = await setup_nuki_integration(hass)

    result = await entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    with (
        patch(
            "homeassistant.components.nuki.config_flow.NukiBridge.info",
            return_value=MOCK_INFO,
        ),
        patch(
            "homeassistant.components.nuki.async_setup_entry",
            return_value=True,
        ),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_TOKEN: "new-token"},
        )
        await hass.async_block_till_done()

        assert result2["type"] is FlowResultType.ABORT
        assert result2["reason"] == "reauth_successful"
        assert entry.data[CONF_TOKEN] == "new-token"


async def test_reauth_invalid_auth(hass: HomeAssistant) -> None:
    """Test starting a reauthentication flow with invalid auth."""
    entry = await setup_nuki_integration(hass)

    result = await entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    with patch(
        "homeassistant.components.nuki.config_flow.NukiBridge.info",
        side_effect=InvalidCredentialsException,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_TOKEN: "new-token"},
        )

        assert result2["type"] is FlowResultType.FORM
        assert result2["step_id"] == "reauth_confirm"
        assert result2["errors"] == {"base": "invalid_auth"}


async def test_reauth_cannot_connect(hass: HomeAssistant) -> None:
    """Test starting a reauthentication flow with cannot connect."""
    entry = await setup_nuki_integration(hass)

    result = await entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    with patch(
        "homeassistant.components.nuki.config_flow.NukiBridge.info",
        side_effect=RequestException,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_TOKEN: "new-token"},
        )

        assert result2["type"] is FlowResultType.FORM
        assert result2["step_id"] == "reauth_confirm"
        assert result2["errors"] == {"base": "cannot_connect"}


async def test_reauth_unknown_exception(hass: HomeAssistant) -> None:
    """Test starting a reauthentication flow with an unknown exception."""
    entry = await setup_nuki_integration(hass)

    result = await entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    with patch(
        "homeassistant.components.nuki.config_flow.NukiBridge.info",
        side_effect=Exception,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_TOKEN: "new-token"},
        )

        assert result2["type"] is FlowResultType.FORM
        assert result2["step_id"] == "reauth_confirm"
        assert result2["errors"] == {"base": "unknown"}
