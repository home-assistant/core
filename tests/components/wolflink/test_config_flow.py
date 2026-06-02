"""Test the Wolf SmartSet Service config flow."""

from unittest.mock import patch

from httpcore import ConnectError
import pytest
from wolf_comm.models import Device
from wolf_comm.token_auth import InvalidAuth

from homeassistant import config_entries
from homeassistant.components.wolflink.const import (
    DEVICE_ID,
    DOMAIN,
    SUBENTRY_TYPE_DEVICE,
)
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

INPUT_CONFIG = {
    CONF_USERNAME: "test-username",
    CONF_PASSWORD: "test-password",
}

DEVICE = Device(1234, 5678, "test-device")
SECOND_DEVICE = Device(5678, 9999, "second-device")


async def test_show_form(hass: HomeAssistant) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"


async def test_create_entry_with_subentries(hass: HomeAssistant) -> None:
    """Test entry creation auto-adds one subentry per device on the account."""
    with (
        patch(
            "homeassistant.components.wolflink.config_flow.WolfClient.fetch_system_list",
            return_value=[DEVICE, SECOND_DEVICE],
        ),
        patch("homeassistant.components.wolflink.async_setup_entry", return_value=True),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}, data=INPUT_CONFIG
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "test-username"
    assert result["data"] == {
        CONF_USERNAME: "test-username",
        CONF_PASSWORD: "test-password",
    }

    entry = result["result"]
    assert entry.unique_id == "test-username"

    subentries = list(entry.subentries.values())
    assert len(subentries) == 2
    assert {s.unique_id for s in subentries} == {"1234", "5678"}
    assert {s.title for s in subentries} == {"test-device", "second-device"}
    assert all(
        s.subentry_type == SUBENTRY_TYPE_DEVICE and DEVICE_ID in s.data
        for s in subentries
    )


@pytest.mark.parametrize(
    ("side_effect", "expected_error"),
    [
        pytest.param(InvalidAuth, "invalid_auth", id="invalid_auth"),
        pytest.param(ConnectError("boom"), "cannot_connect", id="cannot_connect"),
        pytest.param(Exception("boom"), "unknown", id="unknown"),
    ],
)
async def test_user_flow_errors(
    hass: HomeAssistant, side_effect: Exception, expected_error: str
) -> None:
    """Test error handling in the user step keeps the form open with errors."""
    with patch(
        "homeassistant.components.wolflink.config_flow.WolfClient.fetch_system_list",
        side_effect=side_effect,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}, data=INPUT_CONFIG
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected_error}


async def test_no_devices_abort(hass: HomeAssistant) -> None:
    """Test we abort if the account has no devices."""
    with patch(
        "homeassistant.components.wolflink.config_flow.WolfClient.fetch_system_list",
        return_value=[],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}, data=INPUT_CONFIG
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices"


async def test_already_configured_aborts(hass: HomeAssistant) -> None:
    """Test entries with the same username can't be configured twice."""
    MockConfigEntry(
        domain=DOMAIN,
        unique_id="test-username",
        data={CONF_USERNAME: "test-username", CONF_PASSWORD: "test-password"},
        version=2,
        minor_version=2,
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}, data=INPUT_CONFIG
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def _make_hub_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Set up a hub entry already containing one device subentry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="test-username",
        data={CONF_USERNAME: "test-username", CONF_PASSWORD: "test-password"},
        version=2,
        minor_version=2,
        subentries_data=[
            {
                "data": {DEVICE_ID: 1234},
                "subentry_type": SUBENTRY_TYPE_DEVICE,
                "title": "test-device",
                "unique_id": "1234",
            }
        ],
    )
    entry.add_to_hass(hass)
    return entry


async def test_subentry_flow_adds_remaining_device(hass: HomeAssistant) -> None:
    """Test the subentry flow only offers devices not yet configured."""
    entry = await _make_hub_entry(hass)

    with patch(
        "homeassistant.components.wolflink.config_flow.WolfClient.fetch_system_list",
        return_value=[DEVICE, SECOND_DEVICE],
    ):
        result = await hass.config_entries.subentries.async_init(
            (entry.entry_id, SUBENTRY_TYPE_DEVICE),
            context={"source": config_entries.SOURCE_USER},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "device"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {DEVICE_ID: "5678"}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "second-device"
    assert result["data"] == {DEVICE_ID: 5678}
    assert result["unique_id"] == "5678"


async def test_subentry_flow_no_devices_to_add(hass: HomeAssistant) -> None:
    """Test the subentry flow aborts when every device is already configured."""
    entry = await _make_hub_entry(hass)

    with patch(
        "homeassistant.components.wolflink.config_flow.WolfClient.fetch_system_list",
        return_value=[DEVICE],
    ):
        result = await hass.config_entries.subentries.async_init(
            (entry.entry_id, SUBENTRY_TYPE_DEVICE),
            context={"source": config_entries.SOURCE_USER},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_to_add"


@pytest.mark.parametrize(
    ("side_effect", "expected_reason"),
    [
        pytest.param(InvalidAuth, "invalid_auth", id="invalid_auth"),
        pytest.param(ConnectError("boom"), "cannot_connect", id="cannot_connect"),
        pytest.param(Exception("boom"), "unknown", id="unknown"),
    ],
)
async def test_subentry_flow_errors_abort(
    hass: HomeAssistant, side_effect: Exception, expected_reason: str
) -> None:
    """Test the subentry flow aborts cleanly on connection errors."""
    entry = await _make_hub_entry(hass)

    with patch(
        "homeassistant.components.wolflink.config_flow.WolfClient.fetch_system_list",
        side_effect=side_effect,
    ):
        result = await hass.config_entries.subentries.async_init(
            (entry.entry_id, SUBENTRY_TYPE_DEVICE),
            context={"source": config_entries.SOURCE_USER},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == expected_reason
