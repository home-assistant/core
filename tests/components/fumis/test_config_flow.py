"""Tests for the Fumis config flow."""

from unittest.mock import MagicMock

from fumis import FumisAuthenticationError, FumisConnectionError, FumisStoveOfflineError
import pytest

from homeassistant.components.fumis.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_MAC, CONF_PIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


@pytest.mark.usefixtures("mock_fumis")
async def test_full_user_flow(hass: HomeAssistant) -> None:
    """Test the full user flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_MAC: "AABBCCDDEEFF",
            CONF_PIN: "1234",
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Clou Duo"
    assert result["data"] == {
        CONF_MAC: "AABBCCDDEEFF",
        CONF_PIN: "1234",
    }
    assert result["result"].unique_id == "aa:bb:cc:dd:ee:ff"


@pytest.mark.parametrize(
    ("side_effect", "expected_error"),
    [
        (FumisAuthenticationError, {CONF_PIN: "invalid_auth"}),
        (FumisStoveOfflineError, {"base": "device_offline"}),
        (FumisConnectionError, {"base": "cannot_connect"}),
        (Exception, {"base": "unknown"}),
    ],
)
async def test_user_flow_errors(
    hass: HomeAssistant,
    mock_fumis: MagicMock,
    side_effect: type[Exception],
    expected_error: dict[str, str],
) -> None:
    """Test the user flow with errors."""
    mock_fumis.update_info.side_effect = side_effect

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_MAC: "AABBCCDDEEFF",
            CONF_PIN: "1234",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == expected_error

    mock_fumis.update_info.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_MAC: "AABBCCDDEEFF",
            CONF_PIN: "1234",
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.parametrize(
    "mac_input",
    [
        "aa:bb:cc:dd:ee:ff",
        "AA:BB:CC:DD:EE:FF",
        "aa-bb-cc-dd-ee-ff",
        "aabbccddeeff",
    ],
)
@pytest.mark.usefixtures("mock_fumis")
async def test_user_flow_mac_normalization(
    hass: HomeAssistant,
    mac_input: str,
) -> None:
    """Test the MAC address is normalized regardless of input format."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_MAC: mac_input,
            CONF_PIN: "1234",
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_MAC] == "AABBCCDDEEFF"
    assert result["result"].unique_id == "aa:bb:cc:dd:ee:ff"


@pytest.mark.usefixtures("mock_fumis")
async def test_user_flow_already_configured(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the user flow when the device is already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_MAC: "aa:bb:cc:dd:ee:ff",
            CONF_PIN: "1234",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
