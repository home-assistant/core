"""Tests for the Redfish config flow."""

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant import config_entries
from homeassistant.components.redfish.const import CONF_BASE_URL, DOMAIN
from homeassistant.components.redfish.coordinator import RedfishAuthError, RedfishError
from homeassistant.components.redfish.models import RedfishSystem
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

USER_INPUT = {
    CONF_BASE_URL: "https://bmc.example/",
    CONF_USERNAME: "user",
    CONF_PASSWORD: "password",
    CONF_VERIFY_SSL: False,
}

SYSTEM = RedfishSystem(
    odata_id="/redfish/v1/Systems/1",
    system_id="1",
    name="Server",
    uuid="uuid-1",
    manufacturer="Acme",
    model="Model 1",
    serial_number="serial",
    power_state="On",
    reset_target="/redfish/v1/Systems/1/Actions/ComputerSystem.Reset",
    reset_types=frozenset({"On", "GracefulShutdown"}),
)


async def test_user_form_defaults_certificate_verification_off(
    hass: HomeAssistant,
) -> None:
    """Test certificate verification defaults off for self-signed BMCs."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert (
        result["data_schema"](
            {
                CONF_BASE_URL: "https://bmc.example",
                CONF_USERNAME: "user",
                CONF_PASSWORD: "password",
            }
        )[CONF_VERIFY_SSL]
        is False
    )


@pytest.mark.parametrize("verify_ssl", [False, True])
async def test_user_flow(hass: HomeAssistant, verify_ssl: bool) -> None:
    """Test successful setup validates systems and normalizes the URL."""
    user_input = {**USER_INPUT, CONF_VERIFY_SSL: verify_ssl}
    with (
        patch(
            "homeassistant.components.redfish.config_flow.async_get_clientsession"
        ) as get_clientsession,
        patch(
            "homeassistant.components.redfish.config_flow.RedfishClient.async_get_systems",
            return_value={"1": SYSTEM},
        ) as get_systems,
        patch(
            "homeassistant.components.redfish.async_setup_entry",
            new=AsyncMock(return_value=True),
        ) as setup_entry,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data=user_input,
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Server"
    assert result["data"] == {
        **user_input,
        CONF_BASE_URL: "https://bmc.example",
    }
    assert result["result"].unique_id == "https://bmc.example"
    get_systems.assert_awaited_once_with()
    get_clientsession.assert_called_once_with(hass, verify_ssl=verify_ssl)
    setup_entry.assert_awaited_once()


@pytest.mark.parametrize(
    ("side_effect", "systems", "expected_error"),
    [
        (RedfishAuthError(), None, "invalid_auth"),
        (RedfishError(), None, "cannot_connect"),
        (RuntimeError(), None, "unknown"),
        (None, {}, "no_systems"),
    ],
)
async def test_user_flow_errors(
    hass: HomeAssistant,
    side_effect: Exception | None,
    systems: dict[str, RedfishSystem] | None,
    expected_error: str,
) -> None:
    """Test authentication, connection, and no-system errors."""
    with patch(
        "homeassistant.components.redfish.config_flow.RedfishClient.async_get_systems",
        side_effect=side_effect,
        return_value=systems,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data=USER_INPUT,
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": expected_error}


@pytest.mark.parametrize(
    "url",
    [
        "bmc.example",
        "http://bmc.example",
        "ftp://bmc.example",
        "https://user:password@bmc.example",
        "https://bmc.example/path",
        "https://bmc.example?query=value",
        "https://bmc.example#fragment",
    ],
)
async def test_user_flow_rejects_invalid_base_url(
    hass: HomeAssistant, url: str
) -> None:
    """Test setup rejects unsafe or non-base URLs before connecting."""
    with patch(
        "homeassistant.components.redfish.config_flow.RedfishClient.async_get_systems"
    ) as get_systems:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={**USER_INPUT, CONF_BASE_URL: url},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_BASE_URL: "invalid_url"}
    get_systems.assert_not_called()


@pytest.mark.parametrize(
    "base_url",
    [
        pytest.param("https://bmc.example/", id="trailing-slash"),
        pytest.param("https://bmc.example:443", id="default-port"),
    ],
)
async def test_user_flow_already_configured(hass: HomeAssistant, base_url: str) -> None:
    """Test duplicate normalized base URLs are rejected."""
    MockConfigEntry(
        domain=DOMAIN,
        unique_id="https://bmc.example",
        data=USER_INPUT,
    ).add_to_hass(hass)

    with patch(
        "homeassistant.components.redfish.config_flow.RedfishClient.async_get_systems",
        return_value={"1": SYSTEM},
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={**USER_INPUT, CONF_BASE_URL: base_url},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_user_flow_rejects_invalid_basic_auth_username(
    hass: HomeAssistant,
) -> None:
    """Test an invalid HTTP Basic username returns an authentication error."""
    with patch(
        "homeassistant.components.redfish.config_flow.RedfishClient.async_get_systems"
    ) as get_systems:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={**USER_INPUT, CONF_USERNAME: "invalid:user"},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}
    get_systems.assert_not_called()
