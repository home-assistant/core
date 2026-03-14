"""Tests for Specialized Turbo config flow."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from homeassistant import config_entries
from homeassistant.components.specialized_turbo.const import CONF_PIN, DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import (
    MOCK_ADDRESS,
    MOCK_ADDRESS_FORMATTED,
    MOCK_NAME,
    MOCK_SERVICE_INFO,
    NOT_SPECIALIZED_SERVICE_INFO,
    mock_connection_failure_bleak_error,
    mock_connection_failure_no_device,
    mock_connection_failure_timeout,
    mock_connection_success,
)

from tests.common import MockConfigEntry

# --- Bluetooth Discovery ---


async def test_bluetooth_discovery(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test bluetooth discovery creates entry on successful connection."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=MOCK_SERVICE_INFO,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"

    p1, p2 = mock_connection_success()
    with p1, p2:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_PIN: 1234},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == MOCK_NAME
    assert result["data"]["address"] == MOCK_ADDRESS
    assert result["data"][CONF_PIN] == 1234


async def test_bluetooth_discovery_no_pin(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test bluetooth discovery without a PIN."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=MOCK_SERVICE_INFO,
    )

    p1, p2 = mock_connection_success()
    with p1, p2:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_PIN] is None


async def test_bluetooth_discovery_already_configured(
    hass: HomeAssistant,
) -> None:
    """Test bluetooth discovery aborts when device is already configured."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"address": MOCK_ADDRESS},
        unique_id=MOCK_ADDRESS_FORMATTED,
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=MOCK_SERVICE_INFO,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_bluetooth_confirm_cannot_connect_no_device(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test bluetooth confirm shows error when device is not found."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=MOCK_SERVICE_INFO,
    )

    p1, p2 = mock_connection_failure_no_device()
    with p1, p2:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_PIN: 1234},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_bluetooth_confirm_cannot_connect_bleak_error(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test bluetooth confirm shows error on BleakError."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=MOCK_SERVICE_INFO,
    )

    p1, p2 = mock_connection_failure_bleak_error()
    with p1, p2:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_PIN: 1234},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_bluetooth_confirm_cannot_connect_timeout(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test bluetooth confirm shows error on TimeoutError."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=MOCK_SERVICE_INFO,
    )

    p1, p2 = mock_connection_failure_timeout()
    with p1, p2:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_PIN: 1234},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_bluetooth_confirm_recover_from_error(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test that after a connection error, user can retry successfully."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=MOCK_SERVICE_INFO,
    )

    # First attempt fails
    p1, p2 = mock_connection_failure_no_device()
    with p1, p2:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_PIN: 1234},
        )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    # Retry succeeds
    p1, p2 = mock_connection_success()
    with p1, p2:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_PIN: 1234},
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY


# --- User Flow ---


async def test_user_flow(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test user-initiated flow with discovered devices."""
    with patch(
        "homeassistant.components.specialized_turbo.config_flow.async_discovered_service_info",
        return_value=[MOCK_SERVICE_INFO],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    p1, p2 = mock_connection_success()
    with p1, p2:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"address": MOCK_ADDRESS, CONF_PIN: 5678},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"]["address"] == MOCK_ADDRESS
    assert result["data"][CONF_PIN] == 5678


async def test_user_flow_no_devices(hass: HomeAssistant) -> None:
    """Test user flow aborts when no devices are found."""
    with patch(
        "homeassistant.components.specialized_turbo.config_flow.async_discovered_service_info",
        return_value=[],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"


async def test_user_flow_already_configured(hass: HomeAssistant) -> None:
    """Test user flow aborts when selecting an already configured device."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"address": MOCK_ADDRESS},
        unique_id=MOCK_ADDRESS_FORMATTED,
    )
    entry.add_to_hass(hass)

    # Discover the already-configured address so it appears in the form
    with patch(
        "homeassistant.components.specialized_turbo.config_flow.async_discovered_service_info",
        return_value=[MOCK_SERVICE_INFO],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )

    assert result["type"] is FlowResultType.FORM

    # Submit the already-configured address
    p1, p2 = mock_connection_success()
    with p1, p2:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"address": MOCK_ADDRESS, CONF_PIN: 1234},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_user_flow_cannot_connect(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test user flow shows error when connection fails."""
    with patch(
        "homeassistant.components.specialized_turbo.config_flow.async_discovered_service_info",
        return_value=[MOCK_SERVICE_INFO],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )

    p1, p2 = mock_connection_failure_bleak_error()
    with (
        p1,
        p2,
        patch(
            "homeassistant.components.specialized_turbo.config_flow.async_discovered_service_info",
            return_value=[MOCK_SERVICE_INFO],
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"address": MOCK_ADDRESS, CONF_PIN: 1234},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_user_flow_non_specialized_device_filtered(
    hass: HomeAssistant,
) -> None:
    """Test that non-Specialized devices are filtered out of discovery."""
    with patch(
        "homeassistant.components.specialized_turbo.config_flow.async_discovered_service_info",
        return_value=[NOT_SPECIALIZED_SERVICE_INFO],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"


# --- Reconfigure Flow ---


async def test_reconfigure_flow(hass: HomeAssistant) -> None:
    """Test reconfigure flow updates the PIN."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"address": MOCK_ADDRESS, CONF_PIN: 1234},
        unique_id=MOCK_ADDRESS_FORMATTED,
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "entry_id": entry.entry_id,
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_PIN: 9999},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data[CONF_PIN] == 9999


async def test_reconfigure_flow_remove_pin(hass: HomeAssistant) -> None:
    """Test reconfigure flow can remove the PIN."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"address": MOCK_ADDRESS, CONF_PIN: 1234},
        unique_id=MOCK_ADDRESS_FORMATTED,
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "entry_id": entry.entry_id,
        },
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data[CONF_PIN] is None
