"""Test the Powerwall config flow."""

from unittest.mock import MagicMock, patch

from homeassistant import config_entries
from homeassistant.components.powerwall.const import DOMAIN
from homeassistant.const import CONF_IP_ADDRESS, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .mocks import create_mock_powerwall_pw2, create_mock_powerwall_pw3

from tests.common import MockConfigEntry

VALID_CONFIG = {CONF_IP_ADDRESS: "192.168.1.100", CONF_PASSWORD: "test123"}


async def test_form_source_user_pw3(hass: HomeAssistant) -> None:
    """Test successful user flow with Powerwall 3."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    mock_pw = create_mock_powerwall_pw3()

    with (
        patch(
            "homeassistant.components.powerwall.config_flow.pypowerwall.Powerwall",
            return_value=mock_pw,
        ),
        patch(
            "homeassistant.components.powerwall.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            VALID_CONFIG,
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Powerwall 3 (192.168.1.100)"
    assert result2["data"] == VALID_CONFIG
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_source_user_pw2(hass: HomeAssistant) -> None:
    """Test successful user flow with Powerwall 2."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    mock_pw = create_mock_powerwall_pw2()

    with (
        patch(
            "homeassistant.components.powerwall.config_flow.pypowerwall.Powerwall",
            return_value=mock_pw,
        ),
        patch(
            "homeassistant.components.powerwall.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            VALID_CONFIG,
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "My Home"
    assert result2["data"] == VALID_CONFIG
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_pw = MagicMock()
    mock_pw.level.return_value = None  # Indicates connection failure

    with patch(
        "homeassistant.components.powerwall.config_flow.pypowerwall.Powerwall",
        return_value=mock_pw,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            VALID_CONFIG,
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_exception(hass: HomeAssistant) -> None:
    """Test we handle unexpected exception."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_pw = MagicMock()
    mock_pw.level.side_effect = Exception("Unexpected error")

    with patch(
        "homeassistant.components.powerwall.config_flow.pypowerwall.Powerwall",
        return_value=mock_pw,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            VALID_CONFIG,
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "unknown"}


async def test_form_invalid_auth(hass: HomeAssistant) -> None:
    """Test we handle invalid auth error."""
    from pypowerwall.local.exceptions import LoginError  # noqa: PLC0415

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.powerwall.config_flow.pypowerwall.Powerwall",
        side_effect=LoginError("Invalid Powerwall Login"),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            VALID_CONFIG,
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_already_configured(hass: HomeAssistant) -> None:
    """Test we abort when already configured."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=VALID_CONFIG,
        unique_id="192.168.1.100",
    )
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_pw = create_mock_powerwall_pw3()

    with patch(
        "homeassistant.components.powerwall.config_flow.pypowerwall.Powerwall",
        return_value=mock_pw,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            VALID_CONFIG,
        )

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "already_configured"


async def test_form_reauth(hass: HomeAssistant) -> None:
    """Test reauthentication flow."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=VALID_CONFIG,
        unique_id="192.168.1.100",
    )
    entry.add_to_hass(hass)

    result = await entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    mock_pw = create_mock_powerwall_pw3()

    with (
        patch(
            "homeassistant.components.powerwall.config_flow.pypowerwall.Powerwall",
            return_value=mock_pw,
        ),
        patch(
            "homeassistant.components.powerwall.async_setup_entry",
            return_value=True,
        ),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_PASSWORD: "new-password"},
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "reauth_successful"


async def test_form_reauth_cannot_connect(hass: HomeAssistant) -> None:
    """Test reauthentication with connection error."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=VALID_CONFIG,
        unique_id="192.168.1.100",
    )
    entry.add_to_hass(hass)

    result = await entry.start_reauth_flow(hass)

    mock_pw = MagicMock()
    mock_pw.level.return_value = None

    with patch(
        "homeassistant.components.powerwall.config_flow.pypowerwall.Powerwall",
        return_value=mock_pw,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_PASSWORD: "new-password"},
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}
