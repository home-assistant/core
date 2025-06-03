"""Tests for the Elmax config flow."""

from ipaddress import IPv4Address, IPv6Address
from unittest.mock import patch

from elmax_api.exceptions import ElmaxBadLoginError, ElmaxBadPinError, ElmaxNetworkError
import pytest

from homeassistant import config_entries
from homeassistant.components.elmax.const import (
    CONF_ELMAX_MODE,
    CONF_ELMAX_MODE_CLOUD,
    CONF_ELMAX_MODE_DIRECT,
    CONF_ELMAX_MODE_DIRECT_HOST,
    CONF_ELMAX_MODE_DIRECT_PORT,
    CONF_ELMAX_MODE_DIRECT_SSL,
    CONF_ELMAX_MODE_DIRECT_SSL_CERT,
    CONF_ELMAX_PANEL_ID,
    CONF_ELMAX_PANEL_NAME,
    CONF_ELMAX_PANEL_PIN,
    CONF_ELMAX_PASSWORD,
    CONF_ELMAX_USERNAME,
    DOMAIN,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from . import (
    MOCK_DIRECT_CERT,
    MOCK_DIRECT_HOST,
    MOCK_DIRECT_HOST_CHANGED,
    MOCK_DIRECT_HOST_V6,
    MOCK_DIRECT_PORT,
    MOCK_DIRECT_SSL,
    MOCK_PANEL_ID,
    MOCK_PANEL_NAME,
    MOCK_PANEL_PIN,
    MOCK_PASSWORD,
    MOCK_USERNAME,
    MOCK_WRONG_PANEL_PIN,
)
from .conftest import MOCK_DIRECT_BASE_URI_V6

from tests.common import MockConfigEntry

MOCK_ZEROCONF_DISCOVERY_INFO = ZeroconfServiceInfo(
    ip_address=IPv4Address(address=MOCK_DIRECT_HOST),
    ip_addresses=[IPv4Address(address=MOCK_DIRECT_HOST)],
    hostname="VideoBox.local",
    name="VideoBox",
    port=443,
    properties={
        "idl": MOCK_PANEL_ID,
        "idr": MOCK_PANEL_ID,
        "v1": "PHANTOM64PRO_GSM 11.9.844",
        "v2": "4.9.13",
    },
    type="_elmax-ssl._tcp",
)
MOCK_ZEROCONF_DISCOVERY_INFO_V6 = ZeroconfServiceInfo(
    ip_address=IPv6Address(address=MOCK_DIRECT_HOST_V6),
    ip_addresses=[IPv6Address(address=MOCK_DIRECT_HOST_V6)],
    hostname="VideoBox.local",
    name="VideoBox",
    port=443,
    properties={
        "idl": MOCK_PANEL_ID,
        "idr": MOCK_PANEL_ID,
        "v1": "PHANTOM64PRO_GSM 11.9.844",
        "v2": "4.9.13",
    },
    type="_elmax-ssl._tcp",
)
MOCK_ZEROCONF_DISCOVERY_CHANGED_INFO = ZeroconfServiceInfo(
    ip_address=IPv4Address(address=MOCK_DIRECT_HOST_CHANGED),
    ip_addresses=[IPv4Address(address=MOCK_DIRECT_HOST_CHANGED)],
    hostname="VideoBox.local",
    name="VideoBox",
    port=443,
    properties={
        "idl": MOCK_PANEL_ID,
        "idr": MOCK_PANEL_ID,
        "v1": "PHANTOM64PRO_GSM 11.9.844",
        "v2": "4.9.13",
    },
    type="_elmax-ssl._tcp",
)
MOCK_ZEROCONF_DISCOVERY_INFO_NOT_SUPPORTED = ZeroconfServiceInfo(
    ip_address=IPv4Address(MOCK_DIRECT_HOST),
    ip_addresses=[IPv4Address(MOCK_DIRECT_HOST)],
    hostname="VideoBox.local",
    name="VideoBox",
    port=443,
    properties={
        "idl": MOCK_PANEL_ID,
        "idr": MOCK_PANEL_ID,
        "v1": "PHANTOM64PRO_GSM 11.9.844",
    },
    type="_elmax-ssl._tcp",
)
CONF_POLLING = "polling"


async def test_show_menu(hass: HomeAssistant) -> None:
    """Test that the form is served with no input."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "choose_mode"


async def test_direct_setup(hass: HomeAssistant) -> None:
    """Test the standard direct setup case."""
    show_form_result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    with patch(
        "homeassistant.components.elmax.async_setup_entry",
        return_value=True,
    ):
        set_mode_result = await hass.config_entries.flow.async_configure(
            show_form_result["flow_id"],
            {"next_step_id": CONF_ELMAX_MODE_DIRECT},
        )
        result = await hass.config_entries.flow.async_configure(
            set_mode_result["flow_id"],
            {
                CONF_ELMAX_MODE_DIRECT_HOST: MOCK_DIRECT_HOST,
                CONF_ELMAX_MODE_DIRECT_PORT: MOCK_DIRECT_PORT,
                CONF_ELMAX_MODE_DIRECT_SSL: MOCK_DIRECT_SSL,
                CONF_ELMAX_PANEL_PIN: MOCK_PANEL_PIN,
            },
        )
        await hass.async_block_till_done()
        assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_direct_show_form(hass: HomeAssistant) -> None:
    """Test the standard direct show form case."""
    show_form_result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    with patch(
        "homeassistant.components.elmax.async_setup_entry",
        return_value=True,
    ):
        set_mode_result = await hass.config_entries.flow.async_configure(
            show_form_result["flow_id"],
        )
        result = await hass.config_entries.flow.async_configure(
            set_mode_result["flow_id"], {"next_step_id": CONF_ELMAX_MODE_DIRECT}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == CONF_ELMAX_MODE_DIRECT
        assert result["errors"] is None


async def test_cloud_setup(hass: HomeAssistant) -> None:
    """Test the standard cloud setup case."""
    # Setup once.
    show_form_result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    with patch(
        "homeassistant.components.elmax.async_setup_entry",
        return_value=True,
    ):
        show_form_result = await hass.config_entries.flow.async_configure(
            show_form_result["flow_id"],
            {"next_step_id": CONF_ELMAX_MODE_CLOUD},
        )
        login_result = await hass.config_entries.flow.async_configure(
            show_form_result["flow_id"],
            {
                CONF_ELMAX_USERNAME: MOCK_USERNAME,
                CONF_ELMAX_PASSWORD: MOCK_PASSWORD,
            },
        )
        result = await hass.config_entries.flow.async_configure(
            login_result["flow_id"],
            {
                CONF_ELMAX_PANEL_NAME: MOCK_PANEL_NAME,
                CONF_ELMAX_PANEL_PIN: MOCK_PANEL_PIN,
            },
        )
        await hass.async_block_till_done()
        assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_zeroconf_form_setup_api_not_supported(hass: HomeAssistant) -> None:
    """Test the zeroconf setup case."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=MOCK_ZEROCONF_DISCOVERY_INFO_NOT_SUPPORTED,
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "not_supported"


async def test_zeroconf_discovery(hass: HomeAssistant) -> None:
    """Test discovery of Elmax local api panel."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=MOCK_ZEROCONF_DISCOVERY_INFO,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "zeroconf_setup"
    assert result["errors"] is None


async def test_zeroconf_discovery_ipv6(hass: HomeAssistant) -> None:
    """Test discovery of Elmax local api panel."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=MOCK_ZEROCONF_DISCOVERY_INFO_V6,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "zeroconf_setup"
    assert result["errors"] is None


async def test_zeroconf_setup_show_form(hass: HomeAssistant) -> None:
    """Test discovery shows a form when activated."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=MOCK_ZEROCONF_DISCOVERY_INFO,
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "zeroconf_setup"


async def test_zeroconf_setup(hass: HomeAssistant) -> None:
    """Test the successful creation of config entry via discovery flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=MOCK_ZEROCONF_DISCOVERY_INFO,
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_ELMAX_PANEL_PIN: MOCK_PANEL_PIN,
            CONF_ELMAX_MODE_DIRECT_SSL: MOCK_DIRECT_SSL,
        },
    )

    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.parametrize("base_uri", [MOCK_DIRECT_BASE_URI_V6])
async def test_zeroconf_ipv6_setup(hass: HomeAssistant) -> None:
    """Test the successful creation of config entry via discovery flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=MOCK_ZEROCONF_DISCOVERY_INFO_V6,
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_ELMAX_PANEL_PIN: MOCK_PANEL_PIN,
            CONF_ELMAX_MODE_DIRECT_SSL: MOCK_DIRECT_SSL,
        },
    )

    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_zeroconf_already_configured(hass: HomeAssistant) -> None:
    """Ensure local discovery aborts when same panel is already added to ha."""
    MockConfigEntry(
        domain=DOMAIN,
        title=f"Elmax Direct ({MOCK_PANEL_ID})",
        data={
            CONF_ELMAX_MODE: CONF_ELMAX_MODE_DIRECT,
            CONF_ELMAX_MODE_DIRECT_HOST: MOCK_DIRECT_HOST,
            CONF_ELMAX_MODE_DIRECT_PORT: MOCK_DIRECT_PORT,
            CONF_ELMAX_MODE_DIRECT_SSL: MOCK_DIRECT_SSL,
            CONF_ELMAX_PANEL_PIN: MOCK_PANEL_PIN,
            CONF_ELMAX_PANEL_ID: MOCK_PANEL_ID,
            CONF_ELMAX_MODE_DIRECT_SSL_CERT: MOCK_DIRECT_CERT,
        },
        unique_id=MOCK_PANEL_ID,
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=MOCK_ZEROCONF_DISCOVERY_INFO,
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_zeroconf_panel_changed_ip(hass: HomeAssistant) -> None:
    """Ensure local discovery updates the panel data when a the panel changes its IP."""
    # Simulate an entry already exists for ip MOCK_DIRECT_HOST.
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title=f"Elmax Direct ({MOCK_PANEL_ID})",
        data={
            CONF_ELMAX_MODE: CONF_ELMAX_MODE_DIRECT,
            CONF_ELMAX_MODE_DIRECT_HOST: MOCK_DIRECT_HOST,
            CONF_ELMAX_MODE_DIRECT_PORT: MOCK_DIRECT_PORT,
            CONF_ELMAX_MODE_DIRECT_SSL: MOCK_DIRECT_SSL,
            CONF_ELMAX_PANEL_PIN: MOCK_PANEL_PIN,
            CONF_ELMAX_PANEL_ID: MOCK_PANEL_ID,
            CONF_ELMAX_MODE_DIRECT_SSL_CERT: MOCK_DIRECT_CERT,
        },
        unique_id=MOCK_PANEL_ID,
    )
    config_entry.add_to_hass(hass)

    # Simulate a MDNS discovery finds the same panel with a different IP (MOCK_ZEROCONF_DISCOVERY_CHANGED_INFO).
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=MOCK_ZEROCONF_DISCOVERY_CHANGED_INFO,
    )

    # Expect we abort the configuration as "already configured"
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"

    # Expect the panel ip has been updated.
    assert (
        hass.config_entries.async_get_entry(config_entry.entry_id).data[
            CONF_ELMAX_MODE_DIRECT_HOST
        ]
        == MOCK_ZEROCONF_DISCOVERY_CHANGED_INFO.host
    )


async def test_one_config_allowed_cloud(hass: HomeAssistant) -> None:
    """Test that only one Elmax configuration is allowed for each panel."""
    MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_ELMAX_PANEL_ID: MOCK_PANEL_ID,
            CONF_ELMAX_USERNAME: MOCK_USERNAME,
            CONF_ELMAX_PASSWORD: MOCK_PASSWORD,
            CONF_ELMAX_PANEL_PIN: MOCK_PANEL_PIN,
        },
        unique_id=MOCK_PANEL_ID,
    ).add_to_hass(hass)

    # Attempt to add another instance of the integration for the very same panel, it must fail.
    show_form_result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    user_result = await hass.config_entries.flow.async_configure(
        show_form_result["flow_id"],
        {"next_step_id": CONF_ELMAX_MODE_CLOUD},
    )
    login_result = await hass.config_entries.flow.async_configure(
        user_result["flow_id"],
        {
            CONF_ELMAX_USERNAME: MOCK_USERNAME,
            CONF_ELMAX_PASSWORD: MOCK_PASSWORD,
        },
    )
    result = await hass.config_entries.flow.async_configure(
        login_result["flow_id"],
        {
            CONF_ELMAX_PANEL_NAME: MOCK_PANEL_NAME,
            CONF_ELMAX_PANEL_PIN: MOCK_PANEL_PIN,
        },
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_cloud_invalid_credentials(hass: HomeAssistant) -> None:
    """Test that invalid credentials throws an error."""
    with patch(
        "elmax_api.http.Elmax.login",
        side_effect=ElmaxBadLoginError(),
    ):
        show_form_result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        show_form_result = await hass.config_entries.flow.async_configure(
            show_form_result["flow_id"],
            {"next_step_id": CONF_ELMAX_MODE_CLOUD},
        )
        login_result = await hass.config_entries.flow.async_configure(
            show_form_result["flow_id"],
            {
                CONF_ELMAX_USERNAME: "wrong_user_name@email.com",
                CONF_ELMAX_PASSWORD: "incorrect_password",
            },
        )
        assert login_result["step_id"] == CONF_ELMAX_MODE_CLOUD
        assert login_result["type"] is FlowResultType.FORM
        assert login_result["errors"] == {"base": "invalid_auth"}


async def test_cloud_connection_error(hass: HomeAssistant) -> None:
    """Test other than invalid credentials throws an error."""
    with patch(
        "elmax_api.http.Elmax.login",
        side_effect=ElmaxNetworkError(),
    ):
        show_form_result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        show_form_result = await hass.config_entries.flow.async_configure(
            show_form_result["flow_id"],
            {"next_step_id": CONF_ELMAX_MODE_CLOUD},
        )
        login_result = await hass.config_entries.flow.async_configure(
            show_form_result["flow_id"],
            {
                CONF_ELMAX_USERNAME: MOCK_USERNAME,
                CONF_ELMAX_PASSWORD: MOCK_PASSWORD,
            },
        )
        assert login_result["step_id"] == CONF_ELMAX_MODE_CLOUD
        assert login_result["type"] is FlowResultType.FORM
        assert login_result["errors"] == {"base": "network_error"}


async def test_direct_connection_error(hass: HomeAssistant) -> None:
    """Test network error while dealing with direct panel APIs."""
    with patch(
        "elmax_api.http.ElmaxLocal.login",
        side_effect=ElmaxNetworkError(),
    ):
        show_form_result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        set_mode_result = await hass.config_entries.flow.async_configure(
            show_form_result["flow_id"],
            {"next_step_id": CONF_ELMAX_MODE_DIRECT},
        )
        result = await hass.config_entries.flow.async_configure(
            set_mode_result["flow_id"],
            {
                CONF_ELMAX_MODE_DIRECT_HOST: MOCK_DIRECT_HOST,
                CONF_ELMAX_MODE_DIRECT_PORT: MOCK_DIRECT_PORT,
                CONF_ELMAX_MODE_DIRECT_SSL: MOCK_DIRECT_SSL,
                CONF_ELMAX_PANEL_PIN: MOCK_PANEL_PIN,
            },
        )
        assert result["step_id"] == CONF_ELMAX_MODE_DIRECT
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"base": "network_error"}


async def test_direct_wrong_panel_code(hass: HomeAssistant) -> None:
    """Test wrong code being specified while dealing with direct panel APIs."""
    with patch(
        "elmax_api.http.ElmaxLocal.login",
        side_effect=ElmaxBadLoginError(),
    ):
        show_form_result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        set_mode_result = await hass.config_entries.flow.async_configure(
            show_form_result["flow_id"],
            {"next_step_id": CONF_ELMAX_MODE_DIRECT},
        )
        result = await hass.config_entries.flow.async_configure(
            set_mode_result["flow_id"],
            {
                CONF_ELMAX_MODE_DIRECT_HOST: MOCK_DIRECT_HOST,
                CONF_ELMAX_MODE_DIRECT_PORT: MOCK_DIRECT_PORT,
                CONF_ELMAX_MODE_DIRECT_SSL: MOCK_DIRECT_SSL,
                CONF_ELMAX_PANEL_PIN: MOCK_WRONG_PANEL_PIN,
            },
        )
        assert result["step_id"] == CONF_ELMAX_MODE_DIRECT
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"base": "invalid_auth"}


async def test_unhandled_error(hass: HomeAssistant) -> None:
    """Test unhandled exceptions."""
    with patch(
        "elmax_api.http.Elmax.get_panel_status",
        side_effect=Exception(),
    ):
        show_form_result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        show_form_result = await hass.config_entries.flow.async_configure(
            show_form_result["flow_id"],
            {"next_step_id": CONF_ELMAX_MODE_CLOUD},
        )
        login_result = await hass.config_entries.flow.async_configure(
            show_form_result["flow_id"],
            {
                CONF_ELMAX_USERNAME: MOCK_USERNAME,
                CONF_ELMAX_PASSWORD: MOCK_PASSWORD,
            },
        )
        result = await hass.config_entries.flow.async_configure(
            login_result["flow_id"],
            {
                CONF_ELMAX_PANEL_NAME: MOCK_PANEL_NAME,
                CONF_ELMAX_PANEL_PIN: MOCK_PANEL_PIN,
            },
        )
        assert result["step_id"] == "panels"
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"base": "unknown"}


async def test_invalid_pin(hass: HomeAssistant) -> None:
    """Test error is thrown when a wrong pin is used to pair a panel."""
    # Simulate bad pin response.
    with patch(
        "elmax_api.http.Elmax.get_panel_status",
        side_effect=ElmaxBadPinError(),
    ):
        show_form_result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        show_form_result = await hass.config_entries.flow.async_configure(
            show_form_result["flow_id"],
            {"next_step_id": CONF_ELMAX_MODE_CLOUD},
        )
        login_result = await hass.config_entries.flow.async_configure(
            show_form_result["flow_id"],
            {
                CONF_ELMAX_USERNAME: MOCK_USERNAME,
                CONF_ELMAX_PASSWORD: MOCK_PASSWORD,
            },
        )
        result = await hass.config_entries.flow.async_configure(
            login_result["flow_id"],
            {
                CONF_ELMAX_PANEL_NAME: MOCK_PANEL_NAME,
                CONF_ELMAX_PANEL_PIN: MOCK_PANEL_PIN,
            },
        )
        assert result["step_id"] == "panels"
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"base": "invalid_pin"}


async def test_no_online_panel(hass: HomeAssistant) -> None:
    """Test no-online panel is available."""
    # Simulate low-level api returns no panels.
    with patch(
        "elmax_api.http.Elmax.list_control_panels",
        return_value=[],
    ):
        show_form_result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        show_form_result = await hass.config_entries.flow.async_configure(
            show_form_result["flow_id"],
            {"next_step_id": CONF_ELMAX_MODE_CLOUD},
        )
        login_result = await hass.config_entries.flow.async_configure(
            show_form_result["flow_id"],
            {
                CONF_ELMAX_USERNAME: MOCK_USERNAME,
                CONF_ELMAX_PASSWORD: MOCK_PASSWORD,
            },
        )
        assert login_result["step_id"] == CONF_ELMAX_MODE_CLOUD
        assert login_result["type"] is FlowResultType.FORM
        assert login_result["errors"] == {"base": "no_panel_online"}


async def test_show_reauth(hass: HomeAssistant) -> None:
    """Test that the reauth form shows."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_ELMAX_PANEL_ID: MOCK_PANEL_ID,
            CONF_ELMAX_USERNAME: MOCK_USERNAME,
            CONF_ELMAX_PASSWORD: MOCK_PASSWORD,
            CONF_ELMAX_PANEL_PIN: MOCK_PANEL_PIN,
        },
        unique_id=MOCK_PANEL_ID,
    )
    entry.add_to_hass(hass)

    result = await entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"


async def test_reauth_flow(hass: HomeAssistant) -> None:
    """Test that the reauth flow works."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_ELMAX_PANEL_ID: MOCK_PANEL_ID,
            CONF_ELMAX_USERNAME: MOCK_USERNAME,
            CONF_ELMAX_PASSWORD: MOCK_PASSWORD,
            CONF_ELMAX_PANEL_PIN: MOCK_PANEL_PIN,
        },
        unique_id=MOCK_PANEL_ID,
    )
    entry.add_to_hass(hass)

    # Trigger reauth
    reauth_result = await entry.start_reauth_flow(hass)
    with patch(
        "homeassistant.components.elmax.async_setup_entry",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_configure(
            reauth_result["flow_id"],
            {
                CONF_ELMAX_PANEL_PIN: MOCK_PANEL_PIN,
                CONF_ELMAX_USERNAME: MOCK_USERNAME,
                CONF_ELMAX_PASSWORD: MOCK_PASSWORD,
            },
        )
        assert result["type"] is FlowResultType.ABORT
        await hass.async_block_till_done()
        assert result["reason"] == "reauth_successful"


async def test_reauth_panel_disappeared(hass: HomeAssistant) -> None:
    """Test that the case where panel is no longer associated with the user."""
    # Simulate a first setup
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_ELMAX_PANEL_ID: MOCK_PANEL_ID,
            CONF_ELMAX_USERNAME: MOCK_USERNAME,
            CONF_ELMAX_PASSWORD: MOCK_PASSWORD,
            CONF_ELMAX_PANEL_PIN: MOCK_PANEL_PIN,
        },
        unique_id=MOCK_PANEL_ID,
    )
    entry.add_to_hass(hass)

    # Trigger reauth
    reauth_result = await entry.start_reauth_flow(hass)
    with patch(
        "elmax_api.http.Elmax.list_control_panels",
        return_value=[],
    ):
        result = await hass.config_entries.flow.async_configure(
            reauth_result["flow_id"],
            {
                CONF_ELMAX_PANEL_PIN: MOCK_PANEL_PIN,
                CONF_ELMAX_USERNAME: MOCK_USERNAME,
                CONF_ELMAX_PASSWORD: MOCK_PASSWORD,
            },
        )
        assert result["step_id"] == "reauth_confirm"
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"base": "reauth_panel_disappeared"}


async def test_reauth_invalid_pin(hass: HomeAssistant) -> None:
    """Test that the case where panel is no longer associated with the user."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_ELMAX_PANEL_ID: MOCK_PANEL_ID,
            CONF_ELMAX_USERNAME: MOCK_USERNAME,
            CONF_ELMAX_PASSWORD: MOCK_PASSWORD,
            CONF_ELMAX_PANEL_PIN: MOCK_PANEL_PIN,
        },
        unique_id=MOCK_PANEL_ID,
    )
    entry.add_to_hass(hass)

    # Trigger reauth
    reauth_result = await entry.start_reauth_flow(hass)
    with patch(
        "elmax_api.http.Elmax.get_panel_status",
        side_effect=ElmaxBadPinError(),
    ):
        result = await hass.config_entries.flow.async_configure(
            reauth_result["flow_id"],
            {
                CONF_ELMAX_PANEL_PIN: MOCK_PANEL_PIN,
                CONF_ELMAX_USERNAME: MOCK_USERNAME,
                CONF_ELMAX_PASSWORD: MOCK_PASSWORD,
            },
        )
        assert result["step_id"] == "reauth_confirm"
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"base": "invalid_pin"}


async def test_reauth_bad_login(hass: HomeAssistant) -> None:
    """Test bad login attempt at reauth time."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_ELMAX_PANEL_ID: MOCK_PANEL_ID,
            CONF_ELMAX_USERNAME: MOCK_USERNAME,
            CONF_ELMAX_PASSWORD: MOCK_PASSWORD,
            CONF_ELMAX_PANEL_PIN: MOCK_PANEL_PIN,
        },
        unique_id=MOCK_PANEL_ID,
    )
    entry.add_to_hass(hass)

    # Trigger reauth
    reauth_result = await entry.start_reauth_flow(hass)
    with patch(
        "elmax_api.http.Elmax.login",
        side_effect=ElmaxBadLoginError(),
    ):
        result = await hass.config_entries.flow.async_configure(
            reauth_result["flow_id"],
            {
                CONF_ELMAX_PANEL_PIN: MOCK_PANEL_PIN,
                CONF_ELMAX_USERNAME: MOCK_USERNAME,
                CONF_ELMAX_PASSWORD: MOCK_PASSWORD,
            },
        )
        assert result["step_id"] == "reauth_confirm"
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"base": "invalid_auth"}
