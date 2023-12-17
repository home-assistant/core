"""Configuration flow tests for the Tailwind integration."""
from unittest.mock import MagicMock

from gotailwind import (
    TailwindAuthenticationError,
    TailwindConnectionError,
    TailwindUnsupportedFirmwareVersionError,
)
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.tailwind.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


@pytest.mark.usefixtures("mock_tailwind")
async def test_user_flow(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the full happy path user flow from start to finish."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == "user"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_HOST: "127.0.0.1",
            CONF_TOKEN: "987654",
        },
    )

    assert result2.get("type") == FlowResultType.CREATE_ENTRY
    assert result2 == snapshot


@pytest.mark.parametrize(
    ("side_effect", "expected_error"),
    [
        (TailwindConnectionError, {CONF_HOST: "cannot_connect"}),
        (TailwindAuthenticationError, {CONF_TOKEN: "invalid_auth"}),
        (Exception, {"base": "unknown"}),
    ],
)
async def test_user_flow_errors(
    hass: HomeAssistant,
    mock_tailwind: MagicMock,
    side_effect: Exception,
    expected_error: dict[str, str],
) -> None:
    """Test we show user form on a connection error."""
    mock_tailwind.status.side_effect = side_effect

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={
            CONF_HOST: "127.0.0.1",
            CONF_TOKEN: "987654",
        },
    )

    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == "user"
    assert result.get("errors") == expected_error

    mock_tailwind.status.side_effect = None
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_HOST: "127.0.0.2",
            CONF_TOKEN: "123456",
        },
    )
    assert result2.get("type") == FlowResultType.CREATE_ENTRY


async def test_unsupported_firmware_version(
    hass: HomeAssistant, mock_tailwind: MagicMock
) -> None:
    """Test configuration flow aborts when the firmware version is not supported."""
    mock_tailwind.status.side_effect = TailwindUnsupportedFirmwareVersionError
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={
            CONF_HOST: "127.0.0.1",
            CONF_TOKEN: "987654",
        },
    )

    assert result.get("type") == FlowResultType.ABORT
    assert result.get("reason") == "unsupported_firmware"
