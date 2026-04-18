"""Tests for Specialized Turbo config flow."""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

from bleak import BleakError
import pytest

from homeassistant import config_entries
from homeassistant.components.specialized_turbo.const import CONF_PIN, DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import (
    MOCK_ADDRESS,
    MOCK_ADDRESS_FORMATTED,
    MOCK_NAME,
    MOCK_TCU1_ADDRESS,
    make_service_info,
    make_tcu1_service_info,
)

from tests.common import MockConfigEntry


@pytest.fixture(autouse=True)
def mock_setup_entry() -> Generator[None]:
    """Prevent actual entry setup during config flow tests."""
    with (
        patch(
            "homeassistant.components.specialized_turbo.async_setup_entry",
            return_value=True,
        ),
        patch(
            "homeassistant.components.specialized_turbo.async_unload_entry",
            return_value=True,
        ),
    ):
        yield


def _mock_connection_success() -> tuple[patch, patch]:
    """Return context managers for a successful BLE connection test."""
    mock_client = MagicMock()
    mock_client.disconnect = AsyncMock()
    return (
        patch(
            "homeassistant.components.specialized_turbo.config_flow.async_ble_device_from_address",
            return_value=MagicMock(),
        ),
        patch(
            "homeassistant.components.specialized_turbo.config_flow.establish_connection",
            new_callable=AsyncMock,
            return_value=mock_client,
        ),
    )


def _mock_connection_failure_no_device() -> tuple[patch, patch]:
    """Return context managers for a failed BLE connection (device not found)."""
    return (
        patch(
            "homeassistant.components.specialized_turbo.config_flow.async_ble_device_from_address",
            return_value=None,
        ),
        patch(
            "homeassistant.components.specialized_turbo.config_flow.establish_connection",
            new_callable=AsyncMock,
        ),
    )


def _mock_connection_failure_bleak_error() -> tuple[patch, patch]:
    """Return context managers for a failed BLE connection (BleakError)."""
    return (
        patch(
            "homeassistant.components.specialized_turbo.config_flow.async_ble_device_from_address",
            return_value=MagicMock(),
        ),
        patch(
            "homeassistant.components.specialized_turbo.config_flow.establish_connection",
            new_callable=AsyncMock,
            side_effect=BleakError("Connection failed"),
        ),
    )


def _mock_connection_failure_timeout() -> tuple[patch, patch]:
    """Return context managers for a failed BLE connection (TimeoutError)."""
    return (
        patch(
            "homeassistant.components.specialized_turbo.config_flow.async_ble_device_from_address",
            return_value=MagicMock(),
        ),
        patch(
            "homeassistant.components.specialized_turbo.config_flow.establish_connection",
            new_callable=AsyncMock,
            side_effect=TimeoutError,
        ),
    )


# --- Bluetooth Discovery ---


async def test_bluetooth_discovery(hass: HomeAssistant) -> None:
    """Test bluetooth discovery creates entry on successful connection."""
    service_info = make_service_info()

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=service_info,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"

    p1, p2 = _mock_connection_success()
    with p1, p2:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_PIN: "1234"},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == MOCK_NAME
    assert result["data"]["address"] == MOCK_ADDRESS
    assert result["data"][CONF_PIN] == "1234"


async def test_bluetooth_discovery_no_pin(hass: HomeAssistant) -> None:
    """Test bluetooth discovery without a PIN."""
    service_info = make_service_info()

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=service_info,
    )

    p1, p2 = _mock_connection_success()
    with p1, p2:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_PIN] is None


async def test_bluetooth_discovery_already_configured(hass: HomeAssistant) -> None:
    """Test bluetooth discovery aborts when device is already configured."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"address": MOCK_ADDRESS},
        unique_id=MOCK_ADDRESS_FORMATTED,
    )
    entry.add_to_hass(hass)

    service_info = make_service_info()
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=service_info,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_bluetooth_confirm_cannot_connect_no_device(
    hass: HomeAssistant,
) -> None:
    """Test bluetooth confirm shows error when device is not found."""
    service_info = make_service_info()

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=service_info,
    )

    p1, p2 = _mock_connection_failure_no_device()
    with p1, p2:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_PIN: "1234"},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_bluetooth_confirm_cannot_connect_bleak_error(
    hass: HomeAssistant,
) -> None:
    """Test bluetooth confirm shows error on BleakError."""
    service_info = make_service_info()

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=service_info,
    )

    p1, p2 = _mock_connection_failure_bleak_error()
    with p1, p2:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_PIN: "1234"},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_bluetooth_confirm_cannot_connect_timeout(
    hass: HomeAssistant,
) -> None:
    """Test bluetooth confirm shows error on TimeoutError."""
    service_info = make_service_info()

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=service_info,
    )

    p1, p2 = _mock_connection_failure_timeout()
    with p1, p2:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_PIN: "1234"},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_bluetooth_confirm_recover_from_error(hass: HomeAssistant) -> None:
    """Test that after a connection error, user can retry successfully."""
    service_info = make_service_info()

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=service_info,
    )

    # First attempt fails
    p1, p2 = _mock_connection_failure_no_device()
    with p1, p2:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_PIN: "1234"},
        )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    # Retry succeeds
    p1, p2 = _mock_connection_success()
    with p1, p2:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_PIN: "1234"},
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY


# --- User Flow ---


async def test_user_flow(hass: HomeAssistant) -> None:
    """Test user-initiated flow with discovered devices."""
    service_info = make_service_info()

    with patch(
        "homeassistant.components.specialized_turbo.config_flow.async_discovered_service_info",
        return_value=[service_info],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    p1, p2 = _mock_connection_success()
    with p1, p2:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"address": MOCK_ADDRESS, CONF_PIN: "5678"},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"]["address"] == MOCK_ADDRESS
    assert result["data"][CONF_PIN] == "5678"


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
    """Test user flow filters out already configured devices."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"address": MOCK_ADDRESS},
        unique_id=MOCK_ADDRESS_FORMATTED,
    )
    entry.add_to_hass(hass)

    service_info = make_service_info()
    with patch(
        "homeassistant.components.specialized_turbo.config_flow.async_discovered_service_info",
        return_value=[service_info],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"


async def test_user_flow_cannot_connect(hass: HomeAssistant) -> None:
    """Test user flow shows error when connection fails."""
    service_info = make_service_info()

    with patch(
        "homeassistant.components.specialized_turbo.config_flow.async_discovered_service_info",
        return_value=[service_info],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )

    p1, p2 = _mock_connection_failure_bleak_error()
    with (
        p1,
        p2,
        patch(
            "homeassistant.components.specialized_turbo.config_flow.async_discovered_service_info",
            return_value=[service_info],
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"address": MOCK_ADDRESS, CONF_PIN: "1234"},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_user_flow_non_specialized_device_filtered(
    hass: HomeAssistant,
) -> None:
    """Test that non-Specialized devices are filtered out of discovery."""
    non_specialized = make_service_info(
        name="Other Device",
        address="AA:BB:CC:DD:EE:FF",
        manufacturer_data={},
    )

    with patch(
        "homeassistant.components.specialized_turbo.config_flow.async_discovered_service_info",
        return_value=[non_specialized],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"


# --- TCU1 Flows ---


async def test_bluetooth_discovery_tcu1(hass: HomeAssistant) -> None:
    """Test bluetooth discovery for a TCU1 Levo (Simplo manufacturer ID)."""
    service_info = make_tcu1_service_info()

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=service_info,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"

    p1, p2 = _mock_connection_success()
    with p1, p2:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"]["address"] == MOCK_TCU1_ADDRESS


async def test_user_flow_discovers_tcu1(hass: HomeAssistant) -> None:
    """Test user flow discovers TCU1 bikes alongside TCX."""
    tcu1_info = make_tcu1_service_info()
    tcx_info = make_service_info()

    with patch(
        "homeassistant.components.specialized_turbo.config_flow.async_discovered_service_info",
        return_value=[tcu1_info, tcx_info],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
