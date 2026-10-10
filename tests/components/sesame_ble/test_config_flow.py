"""Tests for the Sesame BLE config flow."""

from collections.abc import Generator
import json
import os
from pathlib import Path
import struct
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

from pysesame_ble import (
    COMPANY_ID,
    ProductModels,
    SesameAdData,
    SesameAuthenticationError,
    SesameConnectionError,
    SesameQRCode,
)
import pytest

from homeassistant import config_entries
from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.components.sesame_ble.config_flow import (
    SesameBLEConfigFlow,
    _decode_uploaded_qr,
)
from homeassistant.components.sesame_ble.const import (
    CONF_DEVICE_UUID,
    CONF_QR_URL,
    CONF_SECRET_KEY,
    DOMAIN,
)
from homeassistant.const import CONF_MODEL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType, InvalidData

from tests.common import MockConfigEntry
from tests.components.bluetooth import generate_advertisement_data, generate_ble_device

TEST_UUID = UUID("01234567-89ab-cdef-0123-456789abcdef")


@pytest.fixture(autouse=True)
def mock_setup_entry() -> Generator[AsyncMock]:
    """Mock async_setup_entry so config flow does not invoke full setup."""
    with patch(
        "homeassistant.components.sesame_ble.async_setup_entry", return_value=True
    ) as mock_setup:
        yield mock_setup


def make_bluetooth_service_info(
    address: str = "AA:BB:CC:DD:EE:FF",
    name: str = "Sesame Device",
    model_id: int = 5,
    is_registered: bool = True,
    device_uuid: UUID = TEST_UUID,
) -> BluetoothServiceInfoBleak:
    """Return Bluetooth service info for Sesame device."""
    mfg_data = struct.pack(
        "<HB16s", model_id, 1 if is_registered else 0, device_uuid.bytes
    )
    return BluetoothServiceInfoBleak(
        name=name,
        address=address,
        rssi=-60,
        manufacturer_data={COMPANY_ID: mfg_data},
        service_uuids=[],
        service_data={},
        source="local",
        device=generate_ble_device(address=address, name=name),
        advertisement=generate_advertisement_data(
            local_name=name,
            manufacturer_data={COMPANY_ID: mfg_data},
        ),
        time=0,
        connectable=True,
        tx_power=-127,
    )


@pytest.mark.asyncio
async def test_flow_menu_user_step(hass: HomeAssistant) -> None:
    """Tests that the initial user step presents a menu choice."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "user"
    assert result["menu_options"] == [
        "discover_unregistered",
        "import_qr",
        "manual",
    ]


@pytest.mark.asyncio
async def test_flow_manual_success(hass: HomeAssistant) -> None:
    """Tests that manual setup flow with valid inputs successfully creates a config entry."""
    service_info = make_bluetooth_service_info(
        address="AA:BB:CC:DD:EE:FF",
        model_id=5,  # SESAME5
        device_uuid=TEST_UUID,
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "manual"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "manual"

    with patch(
        "homeassistant.components.sesame_ble.config_flow.async_last_service_info",
        return_value=service_info,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "mac_address": "AA:BB:CC:DD:EE:FF",
                CONF_SECRET_KEY: "0123456789abcdef0123456789abcdef",
                CONF_MODEL: "SESAME5",
                CONF_DEVICE_UUID: str(TEST_UUID),
            },
        )
    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Sesame 5 (EE:FF)"
    assert result2["data"] == {
        "mac_address": "AA:BB:CC:DD:EE:FF",
        CONF_SECRET_KEY: "0123456789abcdef0123456789abcdef",
        CONF_MODEL: "SESAME5",
        CONF_DEVICE_UUID: str(TEST_UUID),
    }


@pytest.mark.asyncio
async def test_flow_manual_already_configured(hass: HomeAssistant) -> None:
    """Tests that manual setup flow aborts when the unique ID is already configured."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="aa:bb:cc:dd:ee:ff",
        data={
            "mac_address": "aa:bb:cc:dd:ee:ff",
            CONF_SECRET_KEY: "0123456789abcdef0123456789abcdef",
            CONF_MODEL: "SESAME5",
            CONF_DEVICE_UUID: str(TEST_UUID),
        },
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "manual"}
    )
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "mac_address": "AA:BB:CC:DD:EE:FF",
            CONF_SECRET_KEY: "0123456789abcdef0123456789abcdef",
            CONF_MODEL: "SESAME5",
            CONF_DEVICE_UUID: str(TEST_UUID),
        },
    )
    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "already_configured"


@pytest.mark.asyncio
async def test_flow_manual_invalid_mac(hass: HomeAssistant) -> None:
    """Tests that manual setup flow validates MAC address."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "manual"}
    )
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "mac_address": "invalid-mac-address",
            CONF_SECRET_KEY: "0123456789abcdef0123456789abcdef",
            CONF_MODEL: "SESAME5",
        },
    )
    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"]["mac_address"] == "invalid_mac"

    # Mixed separators (e.g. colon and hyphen mixed)
    result3 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "mac_address": "AA:BB-CC:DD-EE:FF",
            CONF_SECRET_KEY: "0123456789abcdef0123456789abcdef",
            CONF_MODEL: "SESAME5",
        },
    )
    assert result3["type"] is FlowResultType.FORM
    assert result3["errors"]["mac_address"] == "invalid_mac"


@pytest.mark.asyncio
async def test_flow_manual_with_cached_advertisement_saves_uuid(
    hass: HomeAssistant,
) -> None:
    """Tests manual setup flow stores CONF_DEVICE_UUID when advertisement is cached."""
    service_info = make_bluetooth_service_info(
        address="AA:BB:CC:DD:EE:FF",
        model_id=5,
        device_uuid=TEST_UUID,
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "manual"}
    )
    with patch(
        "homeassistant.components.sesame_ble.config_flow.async_last_service_info",
        return_value=service_info,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "mac_address": "AA:BB:CC:DD:EE:FF",
                CONF_SECRET_KEY: "0123456789abcdef0123456789abcdef",
                CONF_MODEL: "SESAME5",
            },
        )
    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["data"][CONF_DEVICE_UUID] == str(TEST_UUID)


@pytest.mark.asyncio
async def test_flow_manual_model_mismatch_with_advertisement(
    hass: HomeAssistant,
) -> None:
    """Tests that manual setup flags a mismatch when advertised model differs from user selection."""
    service_info = make_bluetooth_service_info(
        address="AA:BB:CC:DD:EE:FF",
        model_id=5,  # SESAME5
        device_uuid=TEST_UUID,
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "manual"}
    )
    with patch(
        "homeassistant.components.sesame_ble.config_flow.async_last_service_info",
        return_value=service_info,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "mac_address": "AA:BB:CC:DD:EE:FF",
                CONF_SECRET_KEY: "0123456789abcdef0123456789abcdef",
                CONF_MODEL: "SESAME6",
                CONF_DEVICE_UUID: str(TEST_UUID),
            },
        )
    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"][CONF_MODEL] == "device_mismatch"


@pytest.mark.asyncio
async def test_flow_manual_uuid_mismatch_with_advertisement(
    hass: HomeAssistant,
) -> None:
    """Tests that manual setup flags a mismatch when advertised UUID differs from user input."""
    service_info = make_bluetooth_service_info(
        address="AA:BB:CC:DD:EE:FF",
        model_id=5,
        device_uuid=TEST_UUID,
    )
    other_uuid = UUID("11111111-2222-3333-4444-555555555555")
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "manual"}
    )
    with patch(
        "homeassistant.components.sesame_ble.config_flow.async_last_service_info",
        return_value=service_info,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "mac_address": "AA:BB:CC:DD:EE:FF",
                CONF_SECRET_KEY: "0123456789abcdef0123456789abcdef",
                CONF_MODEL: "SESAME5",
                CONF_DEVICE_UUID: str(other_uuid),
            },
        )
    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"][CONF_DEVICE_UUID] == "device_mismatch"


@pytest.mark.asyncio
async def test_flow_manual_unsupported_model_advertisement(
    hass: HomeAssistant,
) -> None:
    """Tests that manual setup rejects a device advertising an unsupported lock model."""
    service_info = make_bluetooth_service_info(
        address="AA:BB:CC:DD:EE:FF",
        model_id=26,  # SESAME_TOUCH_2_PRO (not in SUPPORTED_LOCK_MODELS)
        device_uuid=TEST_UUID,
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "manual"}
    )
    with patch(
        "homeassistant.components.sesame_ble.config_flow.async_last_service_info",
        return_value=service_info,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "mac_address": "AA:BB:CC:DD:EE:FF",
                CONF_SECRET_KEY: "0123456789abcdef0123456789abcdef",
                CONF_MODEL: "SESAME5",
                CONF_DEVICE_UUID: str(TEST_UUID),
            },
        )
    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"][CONF_MODEL] == "unsupported_model"


@pytest.mark.asyncio
async def test_flow_manual_with_unregistered_device(hass: HomeAssistant) -> None:
    """Tests that manual setup flow routes to registration if the device is unregistered."""
    service_info = make_bluetooth_service_info(
        address="AA:BB:CC:DD:EE:FF",
        model_id=5,
        is_registered=False,
        device_uuid=TEST_UUID,
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "manual"}
    )
    with patch(
        "homeassistant.components.sesame_ble.config_flow.async_last_service_info",
        return_value=service_info,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "mac_address": "AA:BB:CC:DD:EE:FF",
                CONF_SECRET_KEY: "0123456789abcdef0123456789abcdef",
                CONF_MODEL: "SESAME5",
                CONF_DEVICE_UUID: str(TEST_UUID),
            },
        )
    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "bluetooth_register_confirm"


@pytest.mark.asyncio
async def test_flow_manual_unregistered_device_not_connectable(
    hass: HomeAssistant,
) -> None:
    """Tests that manual setup flags device_not_found if unregistered device has no connectable scanner."""
    service_info = make_bluetooth_service_info(
        address="AA:BB:CC:DD:EE:FF",
        model_id=5,
        is_registered=False,
        device_uuid=TEST_UUID,
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "manual"}
    )
    with patch(
        "homeassistant.components.sesame_ble.config_flow.async_last_service_info",
        side_effect=lambda _hass, _mac, connectable=False: (
            service_info if not connectable else None
        ),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "mac_address": "AA:BB:CC:DD:EE:FF",
                CONF_SECRET_KEY: "0123456789abcdef0123456789abcdef",
                CONF_MODEL: "SESAME5",
                CONF_DEVICE_UUID: str(TEST_UUID),
            },
        )
    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"]["mac_address"] == "device_not_found"


@pytest.mark.asyncio
async def test_flow_manual_invalid_key(hass: HomeAssistant) -> None:
    """Tests that manual setup flow displays errors when the secret key is invalid."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "manual"}
    )

    # 1. Invalid key (not hex)
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "mac_address": "AA:BB:CC:DD:EE:FF",
            CONF_SECRET_KEY: "invalidhexcharacters",
            CONF_MODEL: "SESAME5",
        },
    )
    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"][CONF_SECRET_KEY] == "invalid_secret_key"

    # 2. Invalid key (wrong length)
    result3 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "mac_address": "AA:BB:CC:DD:EE:FF",
            CONF_SECRET_KEY: "0123456789abcdef",
            CONF_MODEL: "SESAME5",
        },
    )
    assert result3["type"] is FlowResultType.FORM
    assert result3["errors"][CONF_SECRET_KEY] == "invalid_secret_key"


@pytest.mark.asyncio
async def test_flow_manual_unsupported_model(hass: HomeAssistant) -> None:
    """Tests that manual setup rejects non-lock models."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "manual"}
    )
    with pytest.raises(InvalidData):
        await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "mac_address": "AA:BB:CC:DD:EE:FF",
                CONF_SECRET_KEY: "0123456789abcdef0123456789abcdef",
                CONF_MODEL: "SESAME_TOUCH_2_PRO",
            },
        )


@pytest.mark.asyncio
async def test_flow_manual_various_lock_models(hass: HomeAssistant) -> None:
    """Tests manual setup flow across different supported lock models."""
    models_to_test = [
        ("SESAME6", "Sesame 6 (55:66)", "11:22:33:44:55:66"),
        ("SESAME6_PRO", "Sesame 6 Pro (77:88)", "AA:BB:CC:66:77:88"),
        ("SESAME_BIKE2", "Sesame Bike 2 (99:88)", "11:22:33:44:99:88"),
    ]
    for model_name, expected_title, mac in models_to_test:
        service_info = make_bluetooth_service_info(
            address=mac,
            model_id=ProductModels[model_name].value,
            device_uuid=TEST_UUID,
        )
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"next_step_id": "manual"}
        )
        with patch(
            "homeassistant.components.sesame_ble.config_flow.async_last_service_info",
            return_value=service_info,
        ):
            result2 = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                {
                    "mac_address": mac,
                    CONF_SECRET_KEY: "0123456789abcdef0123456789abcdef",
                    CONF_MODEL: model_name,
                    CONF_DEVICE_UUID: str(TEST_UUID),
                },
            )
        assert result2["type"] is FlowResultType.CREATE_ENTRY
        assert result2["title"] == expected_title
        assert result2["data"]["mac_address"] == mac
        assert result2["data"][CONF_MODEL] == model_name
        assert result2["data"][CONF_DEVICE_UUID] == str(TEST_UUID)


@pytest.mark.asyncio
async def test_flow_manual_invalid_uuid(hass: HomeAssistant) -> None:
    """Tests that manual setup flow displays error when device UUID is invalid."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "manual"}
    )
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "mac_address": "AA:BB:CC:DD:EE:FF",
            CONF_SECRET_KEY: "0123456789abcdef0123456789abcdef",
            CONF_MODEL: "SESAME5",
            CONF_DEVICE_UUID: "not-a-valid-uuid",
        },
    )
    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"][CONF_DEVICE_UUID] == "invalid_device_uuid"


@pytest.mark.asyncio
async def test_flow_manual_missing_uuid_no_advertisement(hass: HomeAssistant) -> None:
    """Tests that manual setup flow requires device UUID if no advertisement is found."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "manual"}
    )
    with patch(
        "homeassistant.components.sesame_ble.config_flow.async_last_service_info",
        return_value=None,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "mac_address": "AA:BB:CC:DD:EE:FF",
                CONF_SECRET_KEY: "0123456789abcdef0123456789abcdef",
                CONF_MODEL: "SESAME5",
            },
        )
    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"][CONF_DEVICE_UUID] == "uuid_required"


@pytest.mark.asyncio
@patch("homeassistant.components.sesame_ble.config_flow.async_discovered_service_info")
async def test_flow_qr_code_with_discovered_mac(
    mock_discovered: MagicMock, hass: HomeAssistant
) -> None:
    """Tests that a valid QR URL flow auto-resolves the BLE MAC address if discovered."""
    secret_key = bytes(range(16))
    qr = SesameQRCode(
        device_name="My Lock",
        key_level=0,
        model_id=5,  # SESAME5
        device_uuid=TEST_UUID,
        secret_key=secret_key,
    )
    qr_url = qr.to_url()

    service_info = make_bluetooth_service_info(
        address="AA:BB:CC:DD:EE:FF",
        model_id=5,
        device_uuid=TEST_UUID,
    )
    mock_discovered.return_value = [service_info]

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "import_qr"}
    )
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_QR_URL: qr_url}
    )

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "My Lock"
    assert result2["data"] == {
        "mac_address": "AA:BB:CC:DD:EE:FF",
        CONF_SECRET_KEY: secret_key.hex(),
        CONF_MODEL: "SESAME5",
        CONF_DEVICE_UUID: str(TEST_UUID),
    }
    mock_discovered.assert_called_once_with(hass, connectable=True)


@pytest.mark.asyncio
@patch("homeassistant.components.sesame_ble.config_flow.async_discovered_service_info")
async def test_flow_qr_code_with_discovered_unregistered_device(
    mock_discovered: MagicMock, hass: HomeAssistant
) -> None:
    """Tests that a QR flow discovering an unregistered device routes to registration."""
    secret_key = bytes(range(16))
    qr = SesameQRCode(
        device_name="My Lock",
        key_level=0,
        model_id=5,
        device_uuid=TEST_UUID,
        secret_key=secret_key,
    )
    qr_url = qr.to_url()

    service_info = make_bluetooth_service_info(
        address="AA:BB:CC:DD:EE:FF",
        model_id=5,
        is_registered=False,
        device_uuid=TEST_UUID,
    )
    mock_discovered.return_value = [service_info]

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "import_qr"}
    )
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_QR_URL: qr_url}
    )

    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "bluetooth_register_confirm"

    with patch(
        "homeassistant.components.sesame_ble.config_flow.SesameDevice"
    ) as mock_device_class:
        mock_device = MagicMock()
        mock_device.connect = AsyncMock()
        mock_device.register = AsyncMock(
            return_value="0123456789abcdef0123456789abcdef"
        )
        mock_device.disconnect = AsyncMock()
        mock_device_class.return_value = mock_device

        result3 = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        assert result3["type"] is FlowResultType.CREATE_ENTRY
        assert result3["title"] == "Sesame 5 (EE:FF)"
        assert result3["data"]["mac_address"] == "AA:BB:CC:DD:EE:FF"


@pytest.mark.asyncio
async def test_flow_qr_code_unsupported_model(hass: HomeAssistant) -> None:
    """Tests that QR code import rejects non-lock models."""
    secret_key = bytes(range(16))
    qr = SesameQRCode(
        device_name="My Touch",
        key_level=0,
        model_id=26,  # SESAME_TOUCH_2_PRO (not a lock)
        device_uuid=TEST_UUID,
        secret_key=secret_key,
    )
    qr_url = qr.to_url()

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "import_qr"}
    )
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_QR_URL: qr_url}
    )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"]["base"] == "unsupported_model"


@pytest.mark.asyncio
@patch("homeassistant.components.sesame_ble.config_flow.async_discovered_service_info")
async def test_flow_qr_code_fallback_select_address(
    mock_discovered: MagicMock, hass: HomeAssistant
) -> None:
    """Tests that a valid QR URL flow falls back to selecting address if discovery doesn't find it."""
    secret_key = bytes(range(16))
    qr = SesameQRCode(
        device_name="My Lock",
        key_level=0,
        model_id=5,
        device_uuid=TEST_UUID,
        secret_key=secret_key,
    )
    qr_url = qr.to_url()

    # No discovered devices
    mock_discovered.return_value = []

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "import_qr"}
    )
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_QR_URL: qr_url}
    )

    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "select_address"

    # First submit without available BLE device -> device_not_found
    result_not_found = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"mac_address": "AA-BB-CC-DD-EE-FF"}
    )
    assert result_not_found["type"] is FlowResultType.FORM
    assert result_not_found["errors"]["mac_address"] == "device_not_found"

    # Now mock BLE device available and submit address
    mock_ble_device = MagicMock()
    with patch(
        "homeassistant.components.sesame_ble.config_flow.async_ble_device_from_address",
        return_value=mock_ble_device,
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"mac_address": "AA-BB-CC-DD-EE-FF"}
        )
    assert result3["type"] is FlowResultType.CREATE_ENTRY
    assert result3["title"] == "My Lock"
    assert result3["data"]["mac_address"] == "AA:BB:CC:DD:EE:FF"


@pytest.mark.asyncio
@patch("homeassistant.components.sesame_ble.config_flow.async_discovered_service_info")
async def test_flow_qr_code_fallback_auth_error(
    mock_discovered: MagicMock,
    mock_config_flow_sesame_device: MagicMock,
    hass: HomeAssistant,
) -> None:
    """Tests that select_address handles invalid secret key authentication error."""
    secret_key = bytes(range(16))
    qr = SesameQRCode(
        device_name="My Lock",
        key_level=0,
        model_id=5,
        device_uuid=TEST_UUID,
        secret_key=secret_key,
    )
    qr_url = qr.to_url()
    mock_discovered.return_value = []
    mock_config_flow_sesame_device.login.side_effect = SesameAuthenticationError(
        "Invalid key"
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "import_qr"}
    )
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_QR_URL: qr_url}
    )
    assert result2["type"] is FlowResultType.FORM

    mock_ble_device = MagicMock()
    with patch(
        "homeassistant.components.sesame_ble.config_flow.async_ble_device_from_address",
        return_value=mock_ble_device,
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"mac_address": "AA-BB-CC-DD-EE-FF"}
        )
    assert result3["type"] is FlowResultType.FORM
    assert result3["errors"]["base"] == "invalid_auth"


@pytest.mark.asyncio
@patch("homeassistant.components.sesame_ble.config_flow.async_discovered_service_info")
async def test_flow_qr_code_fallback_cannot_connect(
    mock_discovered: MagicMock,
    mock_config_flow_sesame_device: MagicMock,
    hass: HomeAssistant,
) -> None:
    """Tests that select_address handles connection error."""
    secret_key = bytes(range(16))
    qr = SesameQRCode(
        device_name="My Lock",
        key_level=0,
        model_id=5,
        device_uuid=TEST_UUID,
        secret_key=secret_key,
    )
    qr_url = qr.to_url()
    mock_discovered.return_value = []
    mock_config_flow_sesame_device.connect.side_effect = Exception("Connection timeout")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "import_qr"}
    )
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_QR_URL: qr_url}
    )
    assert result2["type"] is FlowResultType.FORM

    mock_ble_device = MagicMock()
    with patch(
        "homeassistant.components.sesame_ble.config_flow.async_ble_device_from_address",
        return_value=mock_ble_device,
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"mac_address": "AA-BB-CC-DD-EE-FF"}
        )
    assert result3["type"] is FlowResultType.FORM
    assert result3["errors"]["base"] == "cannot_connect"


@pytest.mark.asyncio
@patch("homeassistant.components.sesame_ble.config_flow.async_last_service_info")
@patch("homeassistant.components.sesame_ble.config_flow.async_discovered_service_info")
async def test_flow_qr_code_fallback_qr_device_mismatch(
    mock_discovered: MagicMock,
    mock_last_info: MagicMock,
    hass: HomeAssistant,
) -> None:
    """Tests that select_address detects when cached advertisement belongs to a different UUID."""
    secret_key = bytes(range(16))
    qr = SesameQRCode(
        device_name="My Lock",
        key_level=0,
        model_id=5,
        device_uuid=TEST_UUID,
        secret_key=secret_key,
    )
    qr_url = qr.to_url()

    mock_discovered.return_value = []
    # Cached service info has a different UUID
    other_uuid = UUID("99999999-9999-9999-9999-999999999999")
    mock_last_info.return_value = make_bluetooth_service_info(
        address="AA:BB:CC:DD:EE:FF",
        model_id=5,
        device_uuid=other_uuid,
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "import_qr"}
    )
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_QR_URL: qr_url}
    )
    assert result2["step_id"] == "select_address"

    result3 = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"mac_address": "AA:BB:CC:DD:EE:FF"}
    )
    assert result3["type"] is FlowResultType.FORM
    assert result3["errors"]["mac_address"] == "qr_device_mismatch"


@pytest.mark.asyncio
async def test_flow_select_address_with_unregistered_device(
    hass: HomeAssistant,
) -> None:
    """Tests that selecting an address for an unregistered device routes to registration."""
    secret_key = bytes(range(16))
    qr = SesameQRCode(
        device_name="My Lock",
        key_level=0,
        model_id=5,
        device_uuid=TEST_UUID,
        secret_key=secret_key,
    )
    qr_url = qr.to_url()

    service_info = make_bluetooth_service_info(
        address="AA:BB:CC:DD:EE:FF",
        model_id=5,
        is_registered=False,
        device_uuid=TEST_UUID,
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "import_qr"}
    )
    with patch(
        "homeassistant.components.sesame_ble.config_flow.async_discovered_service_info",
        return_value=[],
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_QR_URL: qr_url}
        )
    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "select_address"

    with patch(
        "homeassistant.components.sesame_ble.config_flow.async_last_service_info",
        return_value=service_info,
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"mac_address": "AA:BB:CC:DD:EE:FF"}
        )
    assert result3["type"] is FlowResultType.FORM
    assert result3["step_id"] == "bluetooth_register_confirm"


@pytest.mark.asyncio
@patch("homeassistant.components.sesame_ble.config_flow.async_discovered_service_info")
async def test_flow_qr_code_fallback_invalid_mac(
    mock_discovered: MagicMock, hass: HomeAssistant
) -> None:
    """Tests that select_address rejects invalid MAC."""
    secret_key = bytes(range(16))
    qr = SesameQRCode(
        device_name="My Lock",
        key_level=0,
        model_id=5,
        device_uuid=TEST_UUID,
        secret_key=secret_key,
    )
    qr_url = qr.to_url()
    mock_discovered.return_value = []

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "import_qr"}
    )
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_QR_URL: qr_url}
    )
    assert result2["step_id"] == "select_address"

    result3 = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"mac_address": "invalid-mac"}
    )
    assert result3["type"] is FlowResultType.FORM
    assert result3["errors"]["mac_address"] == "invalid_mac"


@pytest.mark.asyncio
async def test_flow_qr_code_invalid_url(hass: HomeAssistant) -> None:
    """Tests that an invalid QR URL displays an error form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "import_qr"}
    )
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_QR_URL: "invalid_url_without_ssm_prefix"}
    )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"]["base"] == "invalid_qr_code"


@pytest.mark.asyncio
@patch("homeassistant.components.sesame_ble.config_flow.async_discovered_service_info")
@patch("homeassistant.components.sesame_ble.config_flow.decode_qr_image")
async def test_flow_qr_image_success(
    mock_decode: MagicMock, mock_discovered: MagicMock, hass: HomeAssistant
) -> None:
    """Tests that a valid QR image upload flow successfully creates a config entry."""
    secret_key = bytes(range(16))
    qr = SesameQRCode(
        device_name="My Lock",
        key_level=0,
        model_id=5,
        device_uuid=TEST_UUID,
        secret_key=secret_key,
    )
    mock_decode.return_value = [qr.to_url()]
    service_info = make_bluetooth_service_info(
        address="AA:BB:CC:DD:EE:FF",
        model_id=5,
        device_uuid=TEST_UUID,
    )
    mock_discovered.return_value = [service_info]

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "import_qr"}
    )
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"qr_code_image": str(TEST_UUID)}
    )

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "My Lock"
    assert result2["data"]["mac_address"] == "AA:BB:CC:DD:EE:FF"


@pytest.mark.asyncio
@patch("homeassistant.components.sesame_ble.config_flow.decode_qr_image")
async def test_flow_qr_image_no_qr(mock_decode: MagicMock, hass: HomeAssistant) -> None:
    """Tests that an image upload containing no QR code displays an error form."""
    mock_decode.return_value = []

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "import_qr"}
    )
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"qr_code_image": str(TEST_UUID)}
    )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"]["base"] == "invalid_qr_code"


@pytest.mark.asyncio
@patch("homeassistant.components.sesame_ble.config_flow.decode_qr_image")
async def test_flow_qr_image_invalid_url(
    mock_decode: MagicMock, hass: HomeAssistant
) -> None:
    """Tests that an image upload containing a non-ssm QR code URL displays an error form."""
    mock_decode.return_value = ["https://example.com/not-ssm"]

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "import_qr"}
    )
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"qr_code_image": str(TEST_UUID)}
    )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"]["base"] == "invalid_qr_code"


@pytest.mark.asyncio
@patch("homeassistant.components.sesame_ble.config_flow.process_uploaded_file")
async def test_flow_qr_image_exception(
    mock_process: MagicMock, hass: HomeAssistant
) -> None:
    """Tests that an exception during the file processing phase displays an error form."""
    mock_process.side_effect = Exception("File could not be opened")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "import_qr"}
    )
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"qr_code_image": str(TEST_UUID)}
    )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"]["base"] == "invalid_qr_code"


@pytest.mark.asyncio
@patch("homeassistant.components.sesame_ble.config_flow.async_discovered_service_info")
async def test_discover_unregistered_no_devices(
    mock_discovered: MagicMock, hass: HomeAssistant
) -> None:
    """Tests step_discover_unregistered when no unregistered Sesame devices are found."""
    mock_discovered.return_value = []

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "discover_unregistered"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == "no_unregistered_devices"


@pytest.mark.asyncio
@patch("homeassistant.components.sesame_ble.config_flow.async_discovered_service_info")
async def test_discover_unregistered_retry_empty_submission(
    mock_discovered: MagicMock, hass: HomeAssistant
) -> None:
    """Tests that submitting the empty retry form re-runs discovery without raising KeyError."""
    mock_discovered.return_value = []

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "discover_unregistered"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == "no_unregistered_devices"

    # User submits retry with empty dictionary
    service_info = make_bluetooth_service_info(
        address="AA:BB:CC:DD:EE:FF",
        model_id=5,
        is_registered=False,
        device_uuid=TEST_UUID,
    )
    mock_discovered.return_value = [service_info]

    result2 = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result2["type"] is FlowResultType.FORM
    assert "mac_address" in result2["data_schema"].schema


@pytest.mark.asyncio
@patch("homeassistant.components.sesame_ble.config_flow.async_discovered_service_info")
async def test_discover_unregistered_success(
    mock_discovered: MagicMock, hass: HomeAssistant
) -> None:
    """Tests successful BLE enrollment of discovered unregistered device."""
    service_info = make_bluetooth_service_info(
        address="AA:BB:CC:DD:EE:FF",
        model_id=5,
        is_registered=False,
        device_uuid=TEST_UUID,
    )
    mock_discovered.return_value = [service_info]

    with patch(
        "homeassistant.components.sesame_ble.config_flow.SesameDevice"
    ) as mock_device_class:
        mock_device = MagicMock()
        mock_device.connect = AsyncMock()
        mock_device.register = AsyncMock(
            return_value="0123456789abcdef0123456789abcdef"
        )
        mock_device.disconnect = AsyncMock()
        mock_device_class.return_value = mock_device

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"next_step_id": "discover_unregistered"}
        )
        assert result["type"] is FlowResultType.FORM

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"mac_address": "AA:BB:CC:DD:EE:FF"}
        )

        assert result2["type"] is FlowResultType.CREATE_ENTRY
        assert result2["title"] == "Sesame 5 (EE:FF)"
        assert result2["data"] == {
            "mac_address": "AA:BB:CC:DD:EE:FF",
            CONF_SECRET_KEY: "0123456789abcdef0123456789abcdef",
            CONF_MODEL: "SESAME5",
            CONF_DEVICE_UUID: str(TEST_UUID),
        }


@pytest.mark.asyncio
@patch("homeassistant.components.sesame_ble.config_flow.async_discovered_service_info")
async def test_discover_unregistered_device_not_found_preserved(
    mock_discovered: MagicMock, hass: HomeAssistant
) -> None:
    """Tests that device_not_found error is preserved when rediscovery finds no devices."""
    service_info = make_bluetooth_service_info(
        address="AA:BB:CC:DD:EE:FF",
        model_id=5,
        is_registered=False,
        device_uuid=TEST_UUID,
    )
    # First call returns device to build the form
    mock_discovered.return_value = [service_info]

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "discover_unregistered"}
    )
    assert result["type"] is FlowResultType.FORM

    # Before submitting, device stops advertising
    mock_discovered.return_value = []
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"mac_address": "AA:BB:CC:DD:EE:FF"}
    )
    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"]["base"] == "device_not_found"


@pytest.mark.asyncio
@patch("homeassistant.components.sesame_ble.config_flow.async_discovered_service_info")
async def test_discover_unregistered_registration_failed_preserved(
    mock_discovered: MagicMock, hass: HomeAssistant
) -> None:
    """Tests that registration_failed error is preserved when rediscovery finds no devices."""
    service_info = make_bluetooth_service_info(
        address="AA:BB:CC:DD:EE:FF",
        model_id=5,
        is_registered=False,
        device_uuid=TEST_UUID,
    )
    mock_discovered.return_value = [service_info]

    with patch(
        "homeassistant.components.sesame_ble.config_flow.SesameDevice"
    ) as mock_device_class:
        mock_device = MagicMock()
        mock_device.connect = AsyncMock()
        mock_device.register = AsyncMock(
            side_effect=Exception("Registration handshake failed")
        )
        mock_device.disconnect = AsyncMock()
        mock_device_class.return_value = mock_device

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"next_step_id": "discover_unregistered"}
        )

        # On submit, device fails and subsequent rediscovery finds no devices
        mock_discovered.side_effect = [[service_info], []]
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"mac_address": "AA:BB:CC:DD:EE:FF"}
        )
        assert result2["type"] is FlowResultType.FORM
        assert result2["errors"]["base"] == "registration_failed"


@pytest.mark.asyncio
async def test_bluetooth_step_routing_registered(hass: HomeAssistant) -> None:
    """Tests routing in async_step_bluetooth when device is already registered."""
    service_info = make_bluetooth_service_info(
        address="AA:BB:CC:DD:EE:FF",
        model_id=5,
        is_registered=True,
        device_uuid=TEST_UUID,
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=service_info,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_SECRET_KEY: "0123456789abcdef0123456789abcdef"}
    )
    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Sesame 5 (EE:FF)"
    assert result2["data"]["mac_address"] == "AA:BB:CC:DD:EE:FF"


@pytest.mark.asyncio
async def test_bluetooth_step_routing_unregistered(hass: HomeAssistant) -> None:
    """Tests routing in async_step_bluetooth when device is unregistered."""
    service_info = make_bluetooth_service_info(
        address="AA:BB:CC:DD:EE:FF",
        model_id=5,
        is_registered=False,
        device_uuid=TEST_UUID,
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=service_info,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "bluetooth_register_confirm"

    with patch(
        "homeassistant.components.sesame_ble.config_flow.SesameDevice"
    ) as mock_device_class:
        mock_device = MagicMock()
        mock_device.connect = AsyncMock()
        mock_device.register = AsyncMock(
            return_value="0123456789abcdef0123456789abcdef"
        )
        mock_device.disconnect = AsyncMock()
        mock_device_class.return_value = mock_device

        result2 = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        assert result2["type"] is FlowResultType.CREATE_ENTRY
        assert result2["title"] == "Sesame 5 (EE:FF)"
        assert result2["data"]["mac_address"] == "AA:BB:CC:DD:EE:FF"


@pytest.mark.asyncio
async def test_bluetooth_step_unsupported_model(hass: HomeAssistant) -> None:
    """Tests that bluetooth discovery aborts for non-lock models."""
    service_info = make_bluetooth_service_info(
        address="AA:BB:CC:DD:EE:FF",
        model_id=26,  # SESAME_TOUCH_2_PRO
        is_registered=True,
        device_uuid=TEST_UUID,
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=service_info,
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "not_sesame"


@pytest.mark.asyncio
async def test_bluetooth_step_already_configured(hass: HomeAssistant) -> None:
    """Tests that bluetooth discovery aborts when unique id is already configured."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="aa:bb:cc:dd:ee:ff",
        data={
            "mac_address": "aa:bb:cc:dd:ee:ff",
            CONF_SECRET_KEY: "0123456789abcdef0123456789abcdef",
            CONF_MODEL: "SESAME5",
        },
    )
    entry.add_to_hass(hass)

    service_info = make_bluetooth_service_info(
        address="AA:BB:CC:DD:EE:FF",
        model_id=5,
        is_registered=True,
        device_uuid=TEST_UUID,
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=service_info,
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.asyncio
async def test_bluetooth_confirm_invalid_hex_key(hass: HomeAssistant) -> None:
    """Tests validation error when an invalid hex string is entered in bluetooth confirm."""
    service_info = make_bluetooth_service_info(
        address="AA:BB:CC:DD:EE:FF",
        model_id=21,  # SESAME6_PRO
        is_registered=True,
        device_uuid=TEST_UUID,
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=service_info,
    )
    assert result["step_id"] == "bluetooth_confirm"

    # Too short
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_SECRET_KEY: "1234abcd"}
    )
    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"][CONF_SECRET_KEY] == "invalid_secret_key"

    # Non-hex characters
    result3 = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_SECRET_KEY: "zzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzz"}
    )
    assert result3["type"] is FlowResultType.FORM
    assert result3["errors"][CONF_SECRET_KEY] == "invalid_secret_key"


@pytest.mark.asyncio
async def test_bluetooth_confirm_success_qr_url(hass: HomeAssistant) -> None:
    """Tests providing a QR code URL in the bluetooth confirm dialog."""
    service_info = make_bluetooth_service_info(
        address="AA:BB:CC:DD:EE:FF",
        model_id=21,
        is_registered=True,
        device_uuid=TEST_UUID,
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=service_info,
    )

    qr = SesameQRCode(
        device_name="Test Sesame Lock",
        key_level=0,
        model_id=21,
        device_uuid=TEST_UUID,
        secret_key=bytes.fromhex("00112233445566778899aabbccddeeff"),
    )
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_QR_URL: qr.to_url()}
    )
    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Test Sesame Lock"
    assert result2["data"]["mac_address"] == "AA:BB:CC:DD:EE:FF"
    assert result2["data"][CONF_SECRET_KEY] == "00112233445566778899aabbccddeeff"


@pytest.mark.asyncio
async def test_bluetooth_confirm_pasting_ssm_in_secret_key_field(
    hass: HomeAssistant,
) -> None:
    """Tests pasting an ssm:// URL directly into the secret_key field."""
    service_info = make_bluetooth_service_info(
        address="AA:BB:CC:DD:EE:FF",
        model_id=21,
        is_registered=True,
        device_uuid=TEST_UUID,
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=service_info,
    )

    qr = SesameQRCode(
        device_name="Test Sesame Lock",
        key_level=0,
        model_id=21,
        device_uuid=TEST_UUID,
        secret_key=bytes.fromhex("00112233445566778899aabbccddeeff"),
    )
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_SECRET_KEY: qr.to_url()}
    )
    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Test Sesame Lock"
    assert result2["data"]["mac_address"] == "AA:BB:CC:DD:EE:FF"
    assert result2["data"][CONF_SECRET_KEY] == "00112233445566778899aabbccddeeff"


@pytest.mark.asyncio
@patch("homeassistant.components.sesame_ble.config_flow.decode_qr_image")
async def test_bluetooth_confirm_qr_image_upload(
    mock_decode: MagicMock,
    hass: HomeAssistant,
) -> None:
    """Tests uploading a QR code image in the bluetooth confirm dialog."""
    service_info = make_bluetooth_service_info(
        address="AA:BB:CC:DD:EE:FF",
        model_id=21,
        is_registered=True,
        device_uuid=TEST_UUID,
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=service_info,
    )

    qr = SesameQRCode(
        device_name="Test Sesame Lock",
        key_level=0,
        model_id=21,
        device_uuid=TEST_UUID,
        secret_key=bytes.fromhex("00112233445566778899aabbccddeeff"),
    )
    mock_decode.return_value = [qr.to_url()]

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"qr_code_image": str(TEST_UUID)}
    )
    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Test Sesame Lock"
    assert result2["data"]["mac_address"] == "AA:BB:CC:DD:EE:FF"


@pytest.mark.asyncio
async def test_bluetooth_confirm_empty_input(hass: HomeAssistant) -> None:
    """Tests error when submitting bluetooth confirm form with no key or QR code."""
    service_info = make_bluetooth_service_info(
        address="AA:BB:CC:DD:EE:FF",
        model_id=5,
        is_registered=True,
        device_uuid=TEST_UUID,
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=service_info,
    )
    result2 = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"][CONF_SECRET_KEY] == "invalid_secret_key"


@pytest.mark.asyncio
async def test_bluetooth_confirm_qr_device_mismatch(hass: HomeAssistant) -> None:
    """Tests that uploading a QR code for a different device UUID triggers qr_device_mismatch error."""
    service_info = make_bluetooth_service_info(
        address="AA:BB:CC:DD:EE:FF",
        model_id=21,
        is_registered=True,
        device_uuid=TEST_UUID,
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=service_info,
    )

    other_uuid = UUID("11111111-2222-3333-4444-555555555555")
    qr = SesameQRCode(
        device_name="Different Sesame Lock",
        key_level=0,
        model_id=21,
        device_uuid=other_uuid,
        secret_key=bytes.fromhex("00112233445566778899aabbccddeeff"),
    )
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_QR_URL: qr.to_url()}
    )
    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"]["base"] == "qr_device_mismatch"


@pytest.mark.asyncio
async def test_bluetooth_confirm_authentication_failure(
    hass: HomeAssistant, mock_config_flow_sesame_device: MagicMock
) -> None:
    """Tests error when entered secret key fails authentication against discovered device."""
    service_info = make_bluetooth_service_info(
        address="AA:BB:CC:DD:EE:FF",
        model_id=21,
        is_registered=True,
        device_uuid=TEST_UUID,
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=service_info,
    )

    mock_config_flow_sesame_device.login.side_effect = SesameAuthenticationError(
        "Invalid auth"
    )
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_SECRET_KEY: "0123456789abcdef0123456789abcdef"}
    )
    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"][CONF_SECRET_KEY] == "invalid_auth"


@pytest.mark.asyncio
async def test_bluetooth_confirm_connection_failure(
    hass: HomeAssistant, mock_config_flow_sesame_device: MagicMock
) -> None:
    """Tests error when connecting to discovered device times out or fails."""
    service_info = make_bluetooth_service_info(
        address="AA:BB:CC:DD:EE:FF",
        model_id=21,
        is_registered=True,
        device_uuid=TEST_UUID,
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=service_info,
    )

    mock_config_flow_sesame_device.connect.side_effect = SesameConnectionError(
        "Timeout"
    )
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_SECRET_KEY: "0123456789abcdef0123456789abcdef"}
    )
    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"]["base"] == "cannot_connect"


@pytest.mark.asyncio
@patch("homeassistant.components.sesame_ble.config_flow.async_last_service_info")
async def test_bluetooth_confirm_auto_switches_when_device_reset(
    mock_last_service_info: MagicMock,
    hass: HomeAssistant,
) -> None:
    """Tests that opening bluetooth_confirm auto-detects a reset device from latest broadcast and switches to register confirm."""
    service_info = make_bluetooth_service_info(
        address="DE:34:B7:06:2E:56",
        model_id=21,
        is_registered=True,
        device_uuid=TEST_UUID,
    )
    # Latest advertisement in HA cache indicates device was reset (is_registered = False)
    mock_last_service_info.return_value = make_bluetooth_service_info(
        address="DE:34:B7:06:2E:56",
        model_id=21,
        is_registered=False,
        device_uuid=TEST_UUID,
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=service_info,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "bluetooth_register_confirm"


@pytest.mark.asyncio
@patch("homeassistant.components.sesame_ble.config_flow.async_last_service_info")
async def test_bluetooth_register_confirm_auto_switches_when_device_registered(
    mock_last_service_info: MagicMock,
    hass: HomeAssistant,
) -> None:
    """Tests that opening bluetooth_register_confirm auto-detects a paired device and switches to confirm."""
    service_info = make_bluetooth_service_info(
        address="DE:34:B7:06:2E:56",
        model_id=21,
        is_registered=False,
        device_uuid=TEST_UUID,
    )
    # Latest advertisement in HA cache indicates device was paired/registered
    mock_last_service_info.return_value = make_bluetooth_service_info(
        address="DE:34:B7:06:2E:56",
        model_id=21,
        is_registered=True,
        device_uuid=TEST_UUID,
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=service_info,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"


@pytest.mark.asyncio
@patch("homeassistant.components.sesame_ble.config_flow.async_last_service_info")
async def test_bluetooth_register_confirm_switches_on_submit_if_registered(
    mock_last_service_info: MagicMock,
    hass: HomeAssistant,
) -> None:
    """Tests that submitting bluetooth_register_confirm switches to confirm if device became registered."""
    service_info = make_bluetooth_service_info(
        address="DE:34:B7:06:2E:56",
        model_id=21,
        is_registered=False,
        device_uuid=TEST_UUID,
    )
    reg_service_info = make_bluetooth_service_info(
        address="DE:34:B7:06:2E:56",
        model_id=21,
        is_registered=True,
        device_uuid=TEST_UUID,
    )
    # When step opens, device is still unregistered (or not in cache)
    call_count = 0

    def mock_info(*args: object, **kwargs: object) -> BluetoothServiceInfoBleak | None:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return None
        return reg_service_info

    mock_last_service_info.side_effect = mock_info

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=service_info,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "bluetooth_register_confirm"

    result2 = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "bluetooth_confirm"


def test_parse_qr_urls() -> None:
    """Tests parsing QR code URLs."""
    qr_orig = SesameQRCode(
        device_name="Test Sesame Lock",
        key_level=0,
        model_id=21,
        device_uuid=UUID("12345678-1234-5678-1234-567812345678"),
        secret_key=bytes.fromhex("00112233445566778899aabbccddeeff"),
    )
    url = qr_orig.to_url()
    qr_parsed = SesameQRCode.from_url(url)
    assert qr_parsed.device_name == "Test Sesame Lock"
    assert qr_parsed.model_id == 21
    assert str(qr_parsed.device_uuid) == "12345678-1234-5678-1234-567812345678"
    assert qr_parsed.secret_key.hex() == "00112233445566778899aabbccddeeff"


def test_translations_completeness() -> None:
    """Verifies strings.json exists, is valid JSON, and has matching keys."""
    comp_dir = Path(__file__).parents[3] / "homeassistant" / "components" / "sesame_ble"
    strings_path = str(comp_dir / "strings.json")

    assert os.path.exists(strings_path), "strings.json is missing!"
    with open(strings_path, encoding="utf-8") as f:
        strings_data = json.load(f)

    assert "config" in strings_data
    config_data = strings_data["config"]
    assert "step" in config_data
    assert "error" in config_data
    assert "abort" in config_data

    expected_errors = [
        "device_mismatch",
        "device_not_found",
        "invalid_device_uuid",
        "invalid_mac",
        "invalid_mfg_data",
        "invalid_qr_code",
        "invalid_secret_key",
        "no_devices_found",
        "no_unregistered_devices",
        "qr_device_mismatch",
        "registration_failed",
        "unsupported_model",
        "uuid_required",
    ]
    for err in expected_errors:
        assert err in config_data["error"], (
            f"Error '{err}' is not defined in strings.json!"
        )

    expected_aborts = ["already_configured", "not_sesame", "invalid_mfg_data"]
    for abrt in expected_aborts:
        assert abrt in config_data["abort"], (
            f"Abort reason '{abrt}' is not defined in strings.json!"
        )


@pytest.mark.asyncio
async def test_flow_qr_code_empty_submission(hass: HomeAssistant) -> None:
    """Tests that submitting an empty form in QR import displays an error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "import_qr"}
    )
    result2 = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"]["base"] == "invalid_qr_code"


@pytest.mark.asyncio
async def test_manual_flow_whitespace_mac_stripped(hass: HomeAssistant) -> None:
    """Tests that manual setup strips whitespace from MAC address."""
    service_info = make_bluetooth_service_info(
        address="AA:BB:CC:DD:EE:FF",
        model_id=5,  # SESAME5
        device_uuid=TEST_UUID,
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "manual"}
    )

    with patch(
        "homeassistant.components.sesame_ble.config_flow.async_last_service_info",
        return_value=service_info,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "mac_address": "  AA:BB:CC:DD:EE:FF  ",
                CONF_SECRET_KEY: "0123456789abcdef0123456789abcdef",
                CONF_MODEL: "SESAME5",
                CONF_DEVICE_UUID: str(TEST_UUID),
            },
        )

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["data"]["mac_address"] == "AA:BB:CC:DD:EE:FF"
    assert result2["result"].unique_id == "aa:bb:cc:dd:ee:ff"


@pytest.mark.asyncio
async def test_manual_flow_device_not_found(hass: HomeAssistant) -> None:
    """Tests error when manual MAC address is not found in Bluetooth cache."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "manual"}
    )

    with (
        patch(
            "homeassistant.components.sesame_ble.config_flow.async_last_service_info",
            return_value=None,
        ),
        patch(
            "homeassistant.components.sesame_ble.config_flow.async_ble_device_from_address",
            return_value=None,
        ),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "mac_address": "AA:BB:CC:DD:EE:FF",
                CONF_SECRET_KEY: "0123456789abcdef0123456789abcdef",
                CONF_MODEL: "SESAME5",
                CONF_DEVICE_UUID: str(TEST_UUID),
            },
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"]["mac_address"] == "device_not_found"


@pytest.mark.asyncio
async def test_manual_flow_auth_failure(
    hass: HomeAssistant, mock_config_flow_sesame_device: MagicMock
) -> None:
    """Tests error when manual secret key fails authentication against device."""
    service_info = make_bluetooth_service_info(
        address="AA:BB:CC:DD:EE:FF",
        model_id=5,
        device_uuid=TEST_UUID,
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "manual"}
    )

    mock_config_flow_sesame_device.login.side_effect = SesameAuthenticationError(
        "Invalid key"
    )

    with patch(
        "homeassistant.components.sesame_ble.config_flow.async_last_service_info",
        return_value=service_info,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "mac_address": "AA:BB:CC:DD:EE:FF",
                CONF_SECRET_KEY: "0123456789abcdef0123456789abcdef",
                CONF_MODEL: "SESAME5",
                CONF_DEVICE_UUID: str(TEST_UUID),
            },
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"][CONF_SECRET_KEY] == "invalid_auth"


@pytest.mark.asyncio
async def test_manual_flow_connection_failure(
    hass: HomeAssistant, mock_config_flow_sesame_device: MagicMock
) -> None:
    """Tests error when connecting to device during manual setup fails."""
    service_info = make_bluetooth_service_info(
        address="AA:BB:CC:DD:EE:FF",
        model_id=5,
        device_uuid=TEST_UUID,
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "manual"}
    )

    mock_config_flow_sesame_device.connect.side_effect = SesameConnectionError(
        "Connection timed out"
    )

    with patch(
        "homeassistant.components.sesame_ble.config_flow.async_last_service_info",
        return_value=service_info,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "mac_address": "AA:BB:CC:DD:EE:FF",
                CONF_SECRET_KEY: "0123456789abcdef0123456789abcdef",
                CONF_MODEL: "SESAME5",
                CONF_DEVICE_UUID: str(TEST_UUID),
            },
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"]["base"] == "cannot_connect"


@pytest.mark.asyncio
@patch("homeassistant.components.sesame_ble.config_flow.async_discovered_service_info")
async def test_flow_qr_code_with_discovered_mac_unsupported_model(
    mock_discovered: MagicMock, hass: HomeAssistant
) -> None:
    """Tests that QR discovery errors when discovered device has an unsupported model."""
    secret_key = bytes(range(16))
    qr = SesameQRCode(
        device_name="My Lock",
        key_level=0,
        model_id=5,  # SESAME5
        device_uuid=TEST_UUID,
        secret_key=secret_key,
    )
    qr_url = qr.to_url()

    # Discovered advertisement has matching UUID but unsupported model (SESAME_BOT1 = 1)
    service_info = make_bluetooth_service_info(
        address="AA:BB:CC:DD:EE:FF",
        model_id=1,
        device_uuid=TEST_UUID,
    )
    mock_discovered.return_value = [service_info]

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "import_qr"}
    )
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_QR_URL: qr_url}
    )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"]["base"] == "unsupported_model"


@pytest.mark.asyncio
@patch("homeassistant.components.sesame_ble.config_flow.async_discovered_service_info")
async def test_flow_qr_code_with_discovered_mac_model_mismatch(
    mock_discovered: MagicMock, hass: HomeAssistant
) -> None:
    """Tests that QR discovery errors when discovered device model contradicts QR model."""
    secret_key = bytes(range(16))
    qr = SesameQRCode(
        device_name="My Lock",
        key_level=0,
        model_id=5,  # SESAME5
        device_uuid=TEST_UUID,
        secret_key=secret_key,
    )
    qr_url = qr.to_url()

    # Discovered advertisement has matching UUID but different supported model (SESAME5_PRO = 7)
    service_info = make_bluetooth_service_info(
        address="AA:BB:CC:DD:EE:FF",
        model_id=7,
        device_uuid=TEST_UUID,
    )
    mock_discovered.return_value = [service_info]

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "import_qr"}
    )
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_QR_URL: qr_url}
    )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"]["base"] == "qr_device_mismatch"


@pytest.mark.asyncio
@patch("homeassistant.components.sesame_ble.config_flow.async_last_service_info")
@patch("homeassistant.components.sesame_ble.config_flow.async_discovered_service_info")
async def test_flow_select_address_model_mismatch(
    mock_discovered: MagicMock,
    mock_last_info: MagicMock,
    hass: HomeAssistant,
) -> None:
    """Tests that select_address errors when advertisement model contradicts QR code."""
    secret_key = bytes(range(16))
    qr = SesameQRCode(
        device_name="My Lock",
        key_level=0,
        model_id=5,  # SESAME5
        device_uuid=TEST_UUID,
        secret_key=secret_key,
    )
    qr_url = qr.to_url()

    mock_discovered.return_value = []
    # Mock service info with matching UUID but different model (SESAME5_PRO = 7)
    mock_last_info.return_value = make_bluetooth_service_info(
        address="AA:BB:CC:DD:EE:FF",
        model_id=7,
        device_uuid=TEST_UUID,
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "import_qr"}
    )
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_QR_URL: qr_url}
    )
    assert result2["step_id"] == "select_address"

    result3 = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"mac_address": "AA:BB:CC:DD:EE:FF"}
    )
    assert result3["type"] is FlowResultType.FORM
    assert result3["errors"]["mac_address"] == "qr_device_mismatch"


@pytest.mark.asyncio
@patch("homeassistant.components.sesame_ble.config_flow.async_last_service_info")
@patch("homeassistant.components.sesame_ble.config_flow.async_discovered_service_info")
async def test_flow_select_address_unsupported_model(
    mock_discovered: MagicMock,
    mock_last_info: MagicMock,
    hass: HomeAssistant,
) -> None:
    """Tests that select_address errors when advertisement model is unsupported."""
    secret_key = bytes(range(16))
    qr = SesameQRCode(
        device_name="My Lock",
        key_level=0,
        model_id=5,  # SESAME5
        device_uuid=TEST_UUID,
        secret_key=secret_key,
    )
    qr_url = qr.to_url()

    mock_discovered.return_value = []
    # Mock service info with matching UUID but unsupported model (SESAME_BOT1 = 1)
    mock_last_info.return_value = make_bluetooth_service_info(
        address="AA:BB:CC:DD:EE:FF",
        model_id=1,
        device_uuid=TEST_UUID,
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "import_qr"}
    )
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_QR_URL: qr_url}
    )
    assert result2["step_id"] == "select_address"

    result3 = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"mac_address": "AA:BB:CC:DD:EE:FF"}
    )
    assert result3["type"] is FlowResultType.FORM
    assert result3["errors"]["mac_address"] == "unsupported_model"


@pytest.mark.asyncio
async def test_flow_bluetooth_confirm_qr_model_mismatch(hass: HomeAssistant) -> None:
    """Tests that bluetooth_confirm errors when QR code model contradicts discovered model."""
    service_info = make_bluetooth_service_info(
        address="AA:BB:CC:DD:EE:FF",
        model_id=5,  # SESAME5
        is_registered=True,
        device_uuid=TEST_UUID,
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=service_info,
    )

    secret_key = bytes(range(16))
    qr = SesameQRCode(
        device_name="My Lock",
        key_level=0,
        model_id=7,  # SESAME5_PRO contradicts SESAME5
        device_uuid=TEST_UUID,
        secret_key=secret_key,
    )
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_QR_URL: qr.to_url()}
    )
    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"]["base"] == "qr_device_mismatch"


@pytest.mark.asyncio
async def test_is_valid_mac_address_empty(hass: HomeAssistant) -> None:
    """Tests _is_valid_mac_address returns False for empty/None mac."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "manual"}
    )
    # Submit with empty mac
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "mac_address": "",
            CONF_SECRET_KEY: "0123456789abcdef0123456789abcdef",
            CONF_MODEL: "SESAME5",
            CONF_DEVICE_UUID: str(TEST_UUID),
        },
    )
    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"]["mac_address"] == "invalid_mac"


@pytest.mark.asyncio
async def test_decode_uploaded_qr_unavailable(hass: HomeAssistant) -> None:
    """Tests _decode_uploaded_qr returns None when QR not available."""
    with patch(
        "homeassistant.components.sesame_ble.config_flow._QRCODE_AVAILABLE",
        False,
    ):
        result = _decode_uploaded_qr(hass, "some-file-id")
        assert result is None


@pytest.mark.asyncio
@patch("homeassistant.components.sesame_ble.config_flow.async_last_service_info")
@patch("homeassistant.components.sesame_ble.config_flow.async_discovered_service_info")
async def test_discover_unregistered_invalid_mfg_data(
    mock_discovered: MagicMock,
    mock_last_info: MagicMock,
    hass: HomeAssistant,
) -> None:
    """Tests discover_unregistered with invalid manufacturer data."""
    # Device with Sesame COMPANY_ID but too-short data to decode
    bad_service_info = BluetoothServiceInfoBleak(
        name="Bad Device",
        address="AA:BB:CC:DD:EE:FF",
        rssi=-60,
        manufacturer_data={COMPANY_ID: b"\x00"},
        service_uuids=[],
        service_data={},
        source="local",
        device=generate_ble_device(address="AA:BB:CC:DD:EE:FF", name="Bad"),
        advertisement=generate_advertisement_data(
            local_name="Bad",
            manufacturer_data={COMPANY_ID: b"\x00"},
        ),
        time=0,
        connectable=True,
        tx_power=-127,
    )
    # First call for discover form shows an unregistered device
    unreg_service_info = make_bluetooth_service_info(
        model_id=5, is_registered=False, device_uuid=TEST_UUID
    )
    mock_discovered.side_effect = [[unreg_service_info], []]
    # When user selects the device, async_last_service_info returns the bad service info
    mock_last_info.return_value = bad_service_info

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "discover_unregistered"}
    )
    assert result["step_id"] == "discover_unregistered"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"mac_address": "AA:BB:CC:DD:EE:FF"}
    )
    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"]["base"] == "invalid_mfg_data"


@pytest.mark.asyncio
@patch("homeassistant.components.sesame_ble.config_flow.async_last_service_info")
@patch("homeassistant.components.sesame_ble.config_flow.async_discovered_service_info")
async def test_discover_unregistered_unsupported_model_in_adv(
    mock_discovered: MagicMock,
    mock_last_info: MagicMock,
    hass: HomeAssistant,
) -> None:
    """Tests discover_unregistered with unsupported model in advertisement."""
    # Model ID 1 is SESAME_BOT1, not a supported lock
    bot_service_info = make_bluetooth_service_info(
        model_id=1,
        is_registered=False,
        device_uuid=TEST_UUID,
    )
    # First call: show an unregistered device
    unreg_service_info = make_bluetooth_service_info(
        model_id=5, is_registered=False, device_uuid=TEST_UUID
    )
    mock_discovered.side_effect = [[unreg_service_info], []]
    # When user selects, last_info returns a bot model
    mock_last_info.return_value = bot_service_info

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "discover_unregistered"}
    )
    assert result["step_id"] == "discover_unregistered"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"mac_address": "AA:BB:CC:DD:EE:FF"}
    )
    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"]["base"] == "unsupported_model"


@pytest.mark.asyncio
@patch("homeassistant.components.sesame_ble.config_flow.async_last_service_info")
@patch("homeassistant.components.sesame_ble.config_flow.async_discovered_service_info")
async def test_discover_unregistered_became_registered(
    mock_discovered: MagicMock,
    mock_last_info: MagicMock,
    hass: HomeAssistant,
) -> None:
    """Tests discover_unregistered routes to bluetooth_confirm if lock became registered."""
    unreg_service_info = make_bluetooth_service_info(
        model_id=5, is_registered=False, device_uuid=TEST_UUID
    )
    reg_service_info = make_bluetooth_service_info(
        model_id=5, is_registered=True, device_uuid=TEST_UUID
    )
    mock_discovered.side_effect = [[unreg_service_info], []]
    mock_last_info.return_value = reg_service_info

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "discover_unregistered"}
    )
    assert result["step_id"] == "discover_unregistered"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"mac_address": "AA:BB:CC:DD:EE:FF"}
    )
    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "bluetooth_confirm"


@pytest.mark.asyncio
@patch("homeassistant.components.sesame_ble.config_flow.async_discovered_service_info")
async def test_discover_unregistered_decode_error(
    mock_discovered: MagicMock,
    hass: HomeAssistant,
) -> None:
    """Tests discover_unregistered skips devices with decode errors."""
    bad_service_info = BluetoothServiceInfoBleak(
        name="Bad",
        address="AA:BB:CC:DD:EE:FF",
        rssi=-60,
        manufacturer_data={COMPANY_ID: b"\x00"},
        service_uuids=[],
        service_data={},
        source="local",
        device=generate_ble_device(address="AA:BB:CC:DD:EE:FF", name="Bad"),
        advertisement=generate_advertisement_data(
            local_name="Bad",
            manufacturer_data={COMPANY_ID: b"\x00"},
        ),
        time=0,
        connectable=True,
        tx_power=-127,
    )
    mock_discovered.return_value = [bad_service_info]

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "discover_unregistered"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == "no_unregistered_devices"


@pytest.mark.asyncio
@patch("homeassistant.components.sesame_ble.config_flow.async_discovered_service_info")
async def test_import_qr_invalid_adv_model(
    mock_discovered: MagicMock,
    hass: HomeAssistant,
) -> None:
    """Tests import_qr when discovered device has ValueError on ProductModels."""
    secret_key = bytes(range(16))
    qr = SesameQRCode(
        device_name="Lock",
        key_level=0,
        model_id=5,
        device_uuid=TEST_UUID,
        secret_key=secret_key,
    )
    # Device with matching UUID but invalid model ID
    mfg_data = struct.pack("<HB16s", 255, 1, TEST_UUID.bytes)
    bad_service_info = BluetoothServiceInfoBleak(
        name="Bad",
        address="AA:BB:CC:DD:EE:FF",
        rssi=-60,
        manufacturer_data={COMPANY_ID: mfg_data},
        service_uuids=[],
        service_data={},
        source="local",
        device=generate_ble_device(address="AA:BB:CC:DD:EE:FF", name="Bad"),
        advertisement=generate_advertisement_data(
            local_name="Bad",
            manufacturer_data={COMPANY_ID: mfg_data},
        ),
        time=0,
        connectable=True,
        tx_power=-127,
    )
    mock_discovered.return_value = [bad_service_info]

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "import_qr"}
    )
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_QR_URL: qr.to_url()}
    )
    # Device has matching UUID but invalid model → unsupported_model error on import_qr
    assert result2["step_id"] == "import_qr"
    assert result2["errors"]["base"] == "unsupported_model"


@pytest.mark.asyncio
@patch("homeassistant.components.sesame_ble.config_flow.async_last_service_info")
@patch(
    "homeassistant.components.sesame_ble.config_flow.async_ble_device_from_address",
)
async def test_manual_no_advertisement_synthesizes_adv_data(
    mock_ble_device: MagicMock,
    mock_last_info: MagicMock,
    hass: HomeAssistant,
) -> None:
    """Tests manual entry without cached adv data synthesizes SesameAdData."""
    mock_last_info.return_value = None
    mock_device = MagicMock()
    mock_ble_device.return_value = mock_device

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "manual"}
    )
    with patch(
        "homeassistant.components.sesame_ble.config_flow.SesameBLEConfigFlow._async_validate_bluetooth_key",
        return_value=None,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "mac_address": "AA:BB:CC:DD:EE:FF",
                CONF_SECRET_KEY: "0123456789abcdef0123456789abcdef",
                CONF_MODEL: "SESAME5",
                CONF_DEVICE_UUID: str(TEST_UUID),
            },
        )
    assert result2["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.asyncio
async def test_select_address_without_qr_info(hass: HomeAssistant) -> None:
    """Tests select_address aborts when qr_code_info is missing."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    # Directly access the flow and call select_address without qr_code_info
    flow = hass.config_entries.flow._progress.get(result["flow_id"])
    assert flow is not None
    flow_result = await flow.async_step_select_address()
    assert flow_result["type"] is FlowResultType.ABORT
    assert flow_result["reason"] == "unknown"


@pytest.mark.asyncio
@patch("homeassistant.components.sesame_ble.config_flow.async_last_service_info")
@patch("homeassistant.components.sesame_ble.config_flow.async_discovered_service_info")
async def test_select_address_invalid_model_in_adv(
    mock_discovered: MagicMock,
    mock_last_info: MagicMock,
    hass: HomeAssistant,
) -> None:
    """Tests select_address when advertisement has invalid ProductModel."""
    secret_key = bytes(range(16))
    qr = SesameQRCode(
        device_name="My Lock",
        key_level=0,
        model_id=5,
        device_uuid=TEST_UUID,
        secret_key=secret_key,
    )

    mock_discovered.return_value = []
    # Matching UUID but invalid model ID (255 -> ValueError in ProductModels)
    mfg_data = struct.pack("<HB16s", 255, 1, TEST_UUID.bytes)

    bad_service_info = BluetoothServiceInfoBleak(
        name="Bad",
        address="AA:BB:CC:DD:EE:FF",
        rssi=-60,
        manufacturer_data={COMPANY_ID: mfg_data},
        service_uuids=[],
        service_data={},
        source="local",
        device=generate_ble_device(address="AA:BB:CC:DD:EE:FF", name="Bad"),
        advertisement=generate_advertisement_data(
            local_name="Bad",
            manufacturer_data={COMPANY_ID: mfg_data},
        ),
        time=0,
        connectable=True,
        tx_power=-127,
    )
    mock_last_info.return_value = bad_service_info

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "import_qr"}
    )
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_QR_URL: qr.to_url()}
    )
    assert result2["step_id"] == "select_address"

    result3 = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"mac_address": "AA:BB:CC:DD:EE:FF"}
    )
    assert result3["type"] is FlowResultType.FORM
    assert result3["errors"]["mac_address"] == "unsupported_model"


@pytest.mark.asyncio
@patch("homeassistant.components.sesame_ble.config_flow.async_last_service_info")
@patch("homeassistant.components.sesame_ble.config_flow.async_discovered_service_info")
async def test_select_address_unregistered_not_connectable(
    mock_discovered: MagicMock,
    mock_last_info: MagicMock,
    hass: HomeAssistant,
) -> None:
    """Tests select_address when unregistered device is not connectable."""
    secret_key = bytes(range(16))
    qr = SesameQRCode(
        device_name="My Lock",
        key_level=0,
        model_id=5,
        device_uuid=TEST_UUID,
        secret_key=secret_key,
    )

    mock_discovered.return_value = []
    # Service info with unregistered device
    unreg_service_info = make_bluetooth_service_info(
        model_id=5,
        is_registered=False,
        device_uuid=TEST_UUID,
    )

    def side_effect(
        hass: HomeAssistant, mac: str, connectable: bool = True
    ) -> BluetoothServiceInfoBleak | None:
        if connectable:
            return None  # not connectable
        return unreg_service_info

    mock_last_info.side_effect = side_effect

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "import_qr"}
    )
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_QR_URL: qr.to_url()}
    )
    assert result2["step_id"] == "select_address"

    result3 = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"mac_address": "AA:BB:CC:DD:EE:FF"}
    )
    assert result3["type"] is FlowResultType.FORM
    assert result3["errors"]["mac_address"] == "device_not_found"


@pytest.mark.asyncio
@patch("homeassistant.components.sesame_ble.config_flow.async_last_service_info")
@patch("homeassistant.components.sesame_ble.config_flow.async_discovered_service_info")
@patch(
    "homeassistant.components.sesame_ble.config_flow.async_ble_device_from_address",
)
async def test_select_address_no_adv_synthesizes_data(
    mock_ble_device: MagicMock,
    mock_discovered: MagicMock,
    mock_last_info: MagicMock,
    hass: HomeAssistant,
) -> None:
    """Tests select_address with no adv data synthesizes SesameAdData."""
    secret_key = bytes(range(16))
    qr = SesameQRCode(
        device_name="My Lock",
        key_level=0,
        model_id=5,
        device_uuid=TEST_UUID,
        secret_key=secret_key,
    )

    mock_discovered.return_value = []
    mock_last_info.return_value = None
    mock_device = MagicMock()
    mock_ble_device.return_value = mock_device

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "import_qr"}
    )
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_QR_URL: qr.to_url()}
    )
    assert result2["step_id"] == "select_address"

    with patch(
        "homeassistant.components.sesame_ble.config_flow.SesameBLEConfigFlow._async_validate_bluetooth_key",
        return_value=None,
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"mac_address": "AA:BB:CC:DD:EE:FF"}
        )
    assert result3["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.asyncio
@patch("homeassistant.components.sesame_ble.config_flow.async_discovered_service_info")
@patch("homeassistant.components.sesame_ble.config_flow.async_last_service_info")
async def test_select_address_discovered_options_shown(
    mock_last_info: MagicMock,
    mock_discovered: MagicMock,
    hass: HomeAssistant,
) -> None:
    """Tests select_address shows discovered options matching QR UUID."""
    secret_key = bytes(range(16))
    qr = SesameQRCode(
        device_name="My Lock",
        key_level=0,
        model_id=5,
        device_uuid=TEST_UUID,
        secret_key=secret_key,
    )

    matching_service_info = make_bluetooth_service_info(
        model_id=5,
        device_uuid=TEST_UUID,
    )
    mock_last_info.return_value = None
    # First call (import_qr): no devices
    # Second call (select_address show form): return matching device
    mock_discovered.side_effect = [[], [matching_service_info]]

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "import_qr"}
    )
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_QR_URL: qr.to_url()}
    )
    assert result2["step_id"] == "select_address"
    assert result2["type"] is FlowResultType.FORM


@pytest.mark.asyncio
async def test_bluetooth_step_no_mfg_data(hass: HomeAssistant) -> None:
    """Tests bluetooth discovery aborts when no Sesame mfg data."""
    service_info = BluetoothServiceInfoBleak(
        name="Other",
        address="AA:BB:CC:DD:EE:FF",
        rssi=-60,
        manufacturer_data={},  # No Sesame mfg data
        service_uuids=[],
        service_data={},
        source="local",
        device=generate_ble_device(address="AA:BB:CC:DD:EE:FF", name="Other"),
        advertisement=generate_advertisement_data(
            local_name="Other",
            manufacturer_data={},
        ),
        time=0,
        connectable=True,
        tx_power=-127,
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=service_info,
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "not_sesame"


@pytest.mark.asyncio
async def test_bluetooth_step_invalid_decode(hass: HomeAssistant) -> None:
    """Tests bluetooth discovery aborts on decode error."""
    service_info = BluetoothServiceInfoBleak(
        name="Bad",
        address="AA:BB:CC:DD:EE:FF",
        rssi=-60,
        manufacturer_data={COMPANY_ID: b"\x00"},
        service_uuids=[],
        service_data={},
        source="local",
        device=generate_ble_device(address="AA:BB:CC:DD:EE:FF", name="Bad"),
        advertisement=generate_advertisement_data(
            local_name="Bad",
            manufacturer_data={COMPANY_ID: b"\x00"},
        ),
        time=0,
        connectable=True,
        tx_power=-127,
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=service_info,
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "invalid_mfg_data"


@pytest.mark.asyncio
async def test_resolve_device_model_fallback_paths(hass: HomeAssistant) -> None:
    """Tests _resolve_device_model fallback through QR, service info, and default."""
    flow = SesameBLEConfigFlow()
    flow.hass = hass
    flow._sesame_adv_data = None
    flow._mac_address = None

    # No adv data, no QR info, no MAC => default to SESAME5
    result = flow._resolve_device_model(None)
    assert result == "SESAME5"

    # With QR info
    qr_info = SesameQRCode(
        device_name="Lock",
        key_level=0,
        model_id=7,  # SESAME5_PRO
        device_uuid=TEST_UUID,
        secret_key=bytes(16),
    )
    result = flow._resolve_device_model(qr_info)
    assert result == "SESAME5_PRO"

    # With mac but no service info
    flow._mac_address = "aa:bb:cc:dd:ee:ff"
    with (
        patch(
            "homeassistant.components.sesame_ble.config_flow.async_last_service_info",
            return_value=None,
        ),
        patch(
            "homeassistant.components.sesame_ble.config_flow.async_discovered_service_info",
            return_value=[],
        ),
    ):
        result = flow._resolve_device_model(None)
        assert result == "SESAME5"  # default

    # With mac and matching service info
    service_info = make_bluetooth_service_info(
        address="aa:bb:cc:dd:ee:ff",
        model_id=5,
        device_uuid=TEST_UUID,
    )
    with (
        patch(
            "homeassistant.components.sesame_ble.config_flow.async_last_service_info",
            return_value=None,
        ),
        patch(
            "homeassistant.components.sesame_ble.config_flow.async_discovered_service_info",
            return_value=[service_info],
        ),
    ):
        result = flow._resolve_device_model(None)
        assert result == "SESAME5"


@pytest.mark.asyncio
@patch(
    "homeassistant.components.sesame_ble.config_flow._decode_uploaded_qr",
    return_value=None,
)
async def test_bluetooth_confirm_qr_decode_failure(
    mock_decode: MagicMock,
    hass: HomeAssistant,
) -> None:
    """Tests bluetooth_confirm with failed QR decode from image."""
    service_info = make_bluetooth_service_info(
        address="AA:BB:CC:DD:EE:FF",
        model_id=5,
        is_registered=True,
        device_uuid=TEST_UUID,
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=service_info,
    )
    assert result["step_id"] == "bluetooth_confirm"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"qr_code_image": str(TEST_UUID)}
    )
    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"]["base"] == "invalid_qr_code"


@pytest.mark.asyncio
async def test_bluetooth_confirm_invalid_qr_url(hass: HomeAssistant) -> None:
    """Tests bluetooth_confirm with invalid QR URL."""
    service_info = make_bluetooth_service_info(
        address="AA:BB:CC:DD:EE:FF",
        model_id=5,
        is_registered=True,
        device_uuid=TEST_UUID,
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=service_info,
    )
    assert result["step_id"] == "bluetooth_confirm"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_QR_URL: "https://invalid.example.com/not-a-sesame-url"}
    )
    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"]["base"] == "invalid_qr_code"


@pytest.mark.asyncio
async def test_bluetooth_confirm_device_became_unregistered_during_auth(
    hass: HomeAssistant,
) -> None:
    """Tests bluetooth_confirm routes to register_confirm when device becomes unregistered during auth."""
    service_info = make_bluetooth_service_info(
        address="AA:BB:CC:DD:EE:FF",
        model_id=5,
        is_registered=True,
        device_uuid=TEST_UUID,
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=service_info,
    )
    assert result["step_id"] == "bluetooth_confirm"

    # Now the device becomes unregistered during auth
    unreg_service_info = make_bluetooth_service_info(
        address="AA:BB:CC:DD:EE:FF",
        model_id=5,
        is_registered=False,
        device_uuid=TEST_UUID,
    )
    secret_key = bytes(range(16))
    with patch(
        "homeassistant.components.sesame_ble.config_flow.async_last_service_info",
        return_value=unreg_service_info,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_SECRET_KEY: secret_key.hex()}
        )
    assert result2["step_id"] == "bluetooth_register_confirm"


@pytest.mark.asyncio
async def test_bluetooth_confirm_device_not_found(hass: HomeAssistant) -> None:
    """Tests bluetooth_confirm errors when device can't be reached."""
    service_info = make_bluetooth_service_info(
        address="AA:BB:CC:DD:EE:FF",
        model_id=5,
        is_registered=True,
        device_uuid=TEST_UUID,
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=service_info,
    )

    secret_key = bytes(range(16))
    with (
        patch(
            "homeassistant.components.sesame_ble.config_flow.async_last_service_info",
            return_value=None,
        ),
        patch(
            "homeassistant.components.sesame_ble.config_flow.async_ble_device_from_address",
            return_value=None,
        ),
    ):
        # Need to clear _discovery_info to hit the fallback path
        flow = hass.config_entries.flow._progress.get(result["flow_id"])
        assert flow is not None
        flow._discovery_info = None
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_SECRET_KEY: secret_key.hex()}
        )
    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"]["base"] == "device_not_found"


@pytest.mark.asyncio
async def test_bluetooth_confirm_uuid_from_qr_fallback(
    hass: HomeAssistant,
) -> None:
    """Tests bluetooth_confirm uses QR UUID when adv_data is None."""
    service_info = make_bluetooth_service_info(
        address="AA:BB:CC:DD:EE:FF",
        model_id=5,
        is_registered=True,
        device_uuid=TEST_UUID,
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=service_info,
    )

    secret_key = bytes(range(16))
    qr = SesameQRCode(
        device_name="My Lock",
        key_level=0,
        model_id=5,
        device_uuid=TEST_UUID,
        secret_key=secret_key,
    )

    with (
        patch(
            "homeassistant.components.sesame_ble.config_flow.async_last_service_info",
            return_value=service_info,
        ),
        patch(
            "homeassistant.components.sesame_ble.config_flow.SesameBLEConfigFlow._async_validate_bluetooth_key",
            return_value=None,
        ),
    ):
        # Clear adv_data so QR fallback is used for UUID
        flow = hass.config_entries.flow._progress.get(result["flow_id"])
        assert flow is not None
        flow._sesame_adv_data = None
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_QR_URL: qr.to_url()}
        )
    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["data"][CONF_DEVICE_UUID] == str(TEST_UUID)
    assert result2["title"] == "My Lock"


@pytest.mark.asyncio
async def test_bluetooth_register_confirm_without_discovery_info(
    hass: HomeAssistant,
) -> None:
    """Tests register_confirm redirects to user step when discovery_info is missing."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    flow = hass.config_entries.flow._progress.get(result["flow_id"])
    assert flow is not None
    flow._discovery_info = None
    flow._sesame_adv_data = None
    flow_result = await flow.async_step_bluetooth_register_confirm()
    assert flow_result["step_id"] == "user"


@pytest.mark.asyncio
async def test_bluetooth_register_confirm_registration_failure(
    hass: HomeAssistant,
) -> None:
    """Tests register_confirm handles registration failure."""
    service_info = make_bluetooth_service_info(
        address="AA:BB:CC:DD:EE:FF",
        model_id=5,
        is_registered=False,
        device_uuid=TEST_UUID,
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=service_info,
    )
    assert result["step_id"] == "bluetooth_register_confirm"

    with patch(
        "homeassistant.components.sesame_ble.config_flow.SesameDevice"
    ) as mock_device_class:
        mock_device = AsyncMock()
        mock_device.connect = AsyncMock(side_effect=Exception("Connection refused"))
        mock_device.disconnect = AsyncMock()
        mock_device_class.return_value = mock_device

        result2 = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"]["base"] == "registration_failed"


@pytest.mark.asyncio
@patch("homeassistant.components.sesame_ble.config_flow.async_last_service_info")
async def test_manual_adv_decode_exception_in_validation(
    mock_last_info: MagicMock,
    hass: HomeAssistant,
) -> None:
    """Tests manual entry when SesameAdData.decode raises ValueError."""
    service_info = make_bluetooth_service_info(
        model_id=5,
        device_uuid=TEST_UUID,
    )
    mock_last_info.return_value = service_info

    with patch(
        "homeassistant.components.sesame_ble.config_flow.SesameAdData.decode",
        side_effect=ValueError("corrupt data"),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"next_step_id": "manual"}
        )
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "mac_address": "AA:BB:CC:DD:EE:FF",
                CONF_SECRET_KEY: "0123456789abcdef0123456789abcdef",
                CONF_MODEL: "SESAME5",
                CONF_DEVICE_UUID: str(TEST_UUID),
            },
        )
    # Should pass through the decode error and proceed without adv_data (creates entry)
    assert result2["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.asyncio
@patch("homeassistant.components.sesame_ble.config_flow.async_last_service_info")
async def test_manual_adv_unknown_product_model(
    mock_last_info: MagicMock,
    hass: HomeAssistant,
) -> None:
    """Tests manual entry when ProductModels() raises ValueError."""
    service_info = make_bluetooth_service_info(
        model_id=5,
        device_uuid=TEST_UUID,
    )
    mock_last_info.return_value = service_info

    # Mock decode to return adv data with an invalid model id
    fake_adv = SesameAdData(model_id=255, is_registered=True, device_uuid=TEST_UUID)
    with patch(
        "homeassistant.components.sesame_ble.config_flow.SesameAdData.decode",
        return_value=fake_adv,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"next_step_id": "manual"}
        )
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "mac_address": "AA:BB:CC:DD:EE:FF",
                CONF_SECRET_KEY: "0123456789abcdef0123456789abcdef",
                CONF_MODEL: "SESAME5",
                CONF_DEVICE_UUID: str(TEST_UUID),
            },
        )
    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"][CONF_MODEL] == "unsupported_model"


@pytest.mark.asyncio
@patch("homeassistant.components.sesame_ble.config_flow.async_last_service_info")
async def test_manual_last_info_hit_discover_service(
    mock_last_info: MagicMock,
    hass: HomeAssistant,
) -> None:
    """Tests manual validation when async_last_service_info hits."""
    service_info = make_bluetooth_service_info(
        model_id=5,
        device_uuid=TEST_UUID,
    )
    mock_last_info.return_value = service_info

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "manual"}
    )
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "mac_address": "AA:BB:CC:DD:EE:FF",
            CONF_SECRET_KEY: "0123456789abcdef0123456789abcdef",
            CONF_MODEL: "SESAME5",
            CONF_DEVICE_UUID: str(TEST_UUID),
        },
    )
    assert result2["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.asyncio
@patch("homeassistant.components.sesame_ble.config_flow.async_last_service_info")
@patch("homeassistant.components.sesame_ble.config_flow.async_discovered_service_info")
async def test_discover_unregistered_missing_mfg_data_in_discovered(
    mock_discovered: MagicMock,
    mock_last_info: MagicMock,
    hass: HomeAssistant,
) -> None:
    """Tests discover_unregistered when discovered device lacks Sesame mfg data."""
    unreg_service_info = make_bluetooth_service_info(
        model_id=5, is_registered=False, device_uuid=TEST_UUID
    )
    bad_service_info = BluetoothServiceInfoBleak(
        name="Bad Device",
        address="AA:BB:CC:DD:EE:FF",
        rssi=-60,
        manufacturer_data={},
        service_uuids=[],
        service_data={},
        source="local",
        device=generate_ble_device(address="AA:BB:CC:DD:EE:FF", name="Bad"),
        advertisement=generate_advertisement_data(
            local_name="Bad",
            manufacturer_data={},
        ),
        time=0,
        connectable=True,
        tx_power=-127,
    )
    mock_last_info.return_value = None
    mock_discovered.side_effect = [[unreg_service_info], [bad_service_info], []]

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "discover_unregistered"}
    )
    assert result["step_id"] == "discover_unregistered"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"mac_address": "AA:BB:CC:DD:EE:FF"}
    )
    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"]["base"] == "invalid_mfg_data"


@pytest.mark.asyncio
@patch("homeassistant.components.sesame_ble.config_flow.async_last_service_info")
@patch("homeassistant.components.sesame_ble.config_flow.async_discovered_service_info")
@patch(
    "homeassistant.components.sesame_ble.config_flow.async_ble_device_from_address",
)
async def test_select_address_with_registered_adv_data(
    mock_ble_device: MagicMock,
    mock_discovered: MagicMock,
    mock_last_info: MagicMock,
    hass: HomeAssistant,
) -> None:
    """Tests select_address with matching registered adv data."""
    secret_key = bytes(range(16))
    qr = SesameQRCode(
        device_name="My Lock",
        key_level=0,
        model_id=5,
        device_uuid=TEST_UUID,
        secret_key=secret_key,
    )

    mock_discovered.return_value = []
    reg_service_info = make_bluetooth_service_info(
        model_id=5, is_registered=True, device_uuid=TEST_UUID
    )
    mock_last_info.return_value = reg_service_info
    mock_device = MagicMock()
    mock_ble_device.return_value = mock_device

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "import_qr"}
    )
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_QR_URL: qr.to_url()}
    )
    assert result2["step_id"] == "select_address"

    with patch(
        "homeassistant.components.sesame_ble.config_flow.SesameBLEConfigFlow._async_validate_bluetooth_key",
        return_value=None,
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"mac_address": "AA:BB:CC:DD:EE:FF"}
        )
    assert result3["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.asyncio
@patch("homeassistant.components.sesame_ble.config_flow.async_discovered_service_info")
async def test_import_qr_discovered_auth_failure(
    mock_discovered: MagicMock,
    hass: HomeAssistant,
) -> None:
    """Tests import_qr when discovered device fails authentication."""
    secret_key = bytes(range(16))
    qr = SesameQRCode(
        device_name="My Lock",
        key_level=0,
        model_id=5,
        device_uuid=TEST_UUID,
        secret_key=secret_key,
    )

    service_info = make_bluetooth_service_info(
        address="AA:BB:CC:DD:EE:FF",
        model_id=5,
        device_uuid=TEST_UUID,
    )
    mock_discovered.return_value = [service_info]

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "import_qr"}
    )

    with patch(
        "homeassistant.components.sesame_ble.config_flow.SesameBLEConfigFlow._async_validate_bluetooth_key",
        return_value="invalid_auth",
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_QR_URL: qr.to_url()}
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "import_qr"
    assert result2["errors"]["base"] == "invalid_auth"


@pytest.mark.asyncio
@patch("homeassistant.components.sesame_ble.config_flow.async_discovered_service_info")
async def test_import_qr_discovered_cannot_connect(
    mock_discovered: MagicMock,
    hass: HomeAssistant,
) -> None:
    """Tests import_qr when discovered device cannot connect."""
    secret_key = bytes(range(16))
    qr = SesameQRCode(
        device_name="My Lock",
        key_level=0,
        model_id=5,
        device_uuid=TEST_UUID,
        secret_key=secret_key,
    )

    service_info = make_bluetooth_service_info(
        address="AA:BB:CC:DD:EE:FF",
        model_id=5,
        device_uuid=TEST_UUID,
    )
    mock_discovered.return_value = [service_info]

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "import_qr"}
    )

    with patch(
        "homeassistant.components.sesame_ble.config_flow.SesameBLEConfigFlow._async_validate_bluetooth_key",
        return_value="cannot_connect",
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_QR_URL: qr.to_url()}
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "import_qr"
    assert result2["errors"]["base"] == "cannot_connect"


@pytest.mark.asyncio
async def test_bluetooth_register_confirm_device_not_found(
    hass: HomeAssistant,
) -> None:
    """Tests register_confirm handles connectable device not found."""
    service_info = make_bluetooth_service_info(
        address="AA:BB:CC:DD:EE:FF",
        model_id=5,
        is_registered=False,
        device_uuid=TEST_UUID,
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=service_info,
    )
    assert result["step_id"] == "bluetooth_register_confirm"

    flow = hass.config_entries.flow._progress.get(result["flow_id"])
    assert flow is not None
    flow._discovery_info.device = None

    with (
        patch(
            "homeassistant.components.sesame_ble.config_flow.async_last_service_info",
            return_value=None,
        ),
        patch(
            "homeassistant.components.sesame_ble.config_flow.async_ble_device_from_address",
            return_value=None,
        ),
    ):
        result2 = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"]["base"] == "device_not_found"


@pytest.mark.asyncio
async def test_bluetooth_register_confirm_uses_current_connectable_device(
    hass: HomeAssistant,
) -> None:
    """Tests register_confirm resolves current connectable device by address."""
    service_info = make_bluetooth_service_info(
        address="AA:BB:CC:DD:EE:FF",
        model_id=5,
        is_registered=False,
        device_uuid=TEST_UUID,
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=service_info,
    )
    assert result["step_id"] == "bluetooth_register_confirm"

    flow = hass.config_entries.flow._progress.get(result["flow_id"])
    assert flow is not None

    fresh_device = generate_ble_device("AA:BB:CC:DD:EE:FF", "Fresh Scanner Device")
    with (
        patch(
            "homeassistant.components.sesame_ble.config_flow.async_last_service_info",
            return_value=None,
        ),
        patch(
            "homeassistant.components.sesame_ble.config_flow.async_ble_device_from_address",
            return_value=fresh_device,
        ),
        patch(
            "homeassistant.components.sesame_ble.config_flow.SesameDevice"
        ) as mock_device_class,
    ):
        mock_device = MagicMock()
        mock_device.connect = AsyncMock()
        mock_device.register = AsyncMock(
            return_value="0123456789abcdef0123456789abcdef"
        )
        mock_device.disconnect = AsyncMock()
        mock_device_class.return_value = mock_device

        result2 = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    mock_device_class.assert_called_once_with(fresh_device, flow._sesame_adv_data)
