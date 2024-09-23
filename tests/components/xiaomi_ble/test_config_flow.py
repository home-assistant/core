"""Test the Xiaomi config flow."""

from unittest.mock import patch

from xiaomi_ble import XiaomiBluetoothDeviceData as DeviceData

from homeassistant import config_entries
from homeassistant.components.bluetooth import BluetoothChange
from homeassistant.components.xiaomi_ble.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import (
    JTYJGD03MI_SERVICE_INFO,
    LYWSDCGQ_SERVICE_INFO,
    MISSING_PAYLOAD_ENCRYPTED,
    MMC_T201_1_SERVICE_INFO,
    NOT_SENSOR_PUSH_SERVICE_INFO,
    YLKG07YL_SERVICE_INFO,
    make_advertisement,
)

from tests.common import MockConfigEntry


async def test_async_step_bluetooth_valid_device(hass: HomeAssistant) -> None:
    """Test discovery via bluetooth with a valid device."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=MMC_T201_1_SERVICE_INFO,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"
    with patch(
        "homeassistant.components.xiaomi_ble.async_setup_entry", return_value=True
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )
    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Baby Thermometer 6FC1 (MMC-T201-1)"
    assert result2["data"] == {}
    assert result2["result"].unique_id == "00:81:F9:DD:6F:C1"


async def test_async_step_bluetooth_valid_device_but_missing_payload(
    hass: HomeAssistant,
) -> None:
    """Test discovery via bluetooth with a valid device but missing payload."""
    with patch(
        "homeassistant.components.xiaomi_ble.config_flow.async_process_advertisements",
        side_effect=TimeoutError(),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_BLUETOOTH},
            data=MISSING_PAYLOAD_ENCRYPTED,
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirm_slow"

    with patch(
        "homeassistant.components.xiaomi_ble.async_setup_entry", return_value=True
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )
    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Temperature/Humidity Sensor 5384 (LYWSD03MMC)"
    assert result2["data"] == {}
    assert result2["result"].unique_id == "A4:C1:38:56:53:84"


async def test_async_step_bluetooth_valid_device_but_missing_payload_then_full(
    hass: HomeAssistant,
) -> None:
    """Test discovering a valid device. Payload is too short, but later we get full one."""

    async def _async_process_advertisements(
        _hass, _callback, _matcher, _mode, _timeout
    ):
        service_info = make_advertisement(
            "A4:C1:38:56:53:84",
            b"XX\xe4\x16,\x84SV8\xc1\xa4+n\xf2\xe9\x12\x00\x00l\x88M\x9e",
        )
        assert _callback(service_info)
        return service_info

    with patch(
        "homeassistant.components.xiaomi_ble.config_flow.async_process_advertisements",
        _async_process_advertisements,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_BLUETOOTH},
            data=MISSING_PAYLOAD_ENCRYPTED,
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "get_encryption_key_4_5"

    with patch(
        "homeassistant.components.xiaomi_ble.async_setup_entry", return_value=True
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"bindkey": "a115210eed7a88e50ad52662e732a9fb"},
        )

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["data"] == {"bindkey": "a115210eed7a88e50ad52662e732a9fb"}
    assert result2["result"].unique_id == "A4:C1:38:56:53:84"


async def test_async_step_bluetooth_during_onboarding(hass: HomeAssistant) -> None:
    """Test discovery via bluetooth during onboarding."""
    with (
        patch(
            "homeassistant.components.xiaomi_ble.async_setup_entry", return_value=True
        ) as mock_setup_entry,
        patch(
            "homeassistant.components.onboarding.async_is_onboarded",
            return_value=False,
        ) as mock_onboarding,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_BLUETOOTH},
            data=MMC_T201_1_SERVICE_INFO,
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Baby Thermometer 6FC1 (MMC-T201-1)"
    assert result["data"] == {}
    assert result["result"].unique_id == "00:81:F9:DD:6F:C1"
    assert len(mock_setup_entry.mock_calls) == 1
    assert len(mock_onboarding.mock_calls) == 1


async def test_async_step_bluetooth_valid_device_legacy_encryption(
    hass: HomeAssistant,
) -> None:
    """Test discovery via bluetooth with a valid device, with legacy encryption."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=YLKG07YL_SERVICE_INFO,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "get_encryption_key_legacy"

    with patch(
        "homeassistant.components.xiaomi_ble.async_setup_entry", return_value=True
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"bindkey": "b853075158487ca39a5b5ea9"},
        )
    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Dimmer Switch 988B (YLKG07YL/YLKG08YL)"
    assert result2["data"] == {"bindkey": "b853075158487ca39a5b5ea9"}
    assert result2["result"].unique_id == "F8:24:41:C5:98:8B"


async def test_async_step_bluetooth_valid_device_legacy_encryption_wrong_key(
    hass: HomeAssistant,
) -> None:
    """Test discovery via bluetooth with a valid device, with legacy encryption and invalid key."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=YLKG07YL_SERVICE_INFO,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "get_encryption_key_legacy"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"bindkey": "aaaaaaaaaaaaaaaaaaaaaaaa"},
    )
    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "get_encryption_key_legacy"
    assert result2["errors"]["bindkey"] == "decryption_failed"

    # Test can finish flow
    with patch(
        "homeassistant.components.xiaomi_ble.async_setup_entry", return_value=True
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"bindkey": "b853075158487ca39a5b5ea9"},
        )
    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Dimmer Switch 988B (YLKG07YL/YLKG08YL)"
    assert result2["data"] == {"bindkey": "b853075158487ca39a5b5ea9"}
    assert result2["result"].unique_id == "F8:24:41:C5:98:8B"


async def test_async_step_bluetooth_valid_device_legacy_encryption_wrong_key_length(
    hass: HomeAssistant,
) -> None:
    """Test discovery via bluetooth with a valid device, with legacy encryption and wrong key length."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=YLKG07YL_SERVICE_INFO,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "get_encryption_key_legacy"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"bindkey": "aaaaaaaaaaaaaaaaaaaaaaa"},
    )
    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "get_encryption_key_legacy"
    assert result2["errors"]["bindkey"] == "expected_24_characters"

    # Test can finish flow
    with patch(
        "homeassistant.components.xiaomi_ble.async_setup_entry", return_value=True
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"bindkey": "b853075158487ca39a5b5ea9"},
        )
    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Dimmer Switch 988B (YLKG07YL/YLKG08YL)"
    assert result2["data"] == {"bindkey": "b853075158487ca39a5b5ea9"}
    assert result2["result"].unique_id == "F8:24:41:C5:98:8B"


async def test_async_step_bluetooth_valid_device_v4_encryption(
    hass: HomeAssistant,
) -> None:
    """Test discovery via bluetooth with a valid device, with v4 encryption."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=JTYJGD03MI_SERVICE_INFO,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "get_encryption_key_4_5"

    with patch(
        "homeassistant.components.xiaomi_ble.async_setup_entry", return_value=True
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"bindkey": "5b51a7c91cde6707c9ef18dfda143a58"},
        )

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Smoke Detector 9CBC (JTYJGD03MI)"
    assert result2["data"] == {"bindkey": "5b51a7c91cde6707c9ef18dfda143a58"}
    assert result2["result"].unique_id == "54:EF:44:E3:9C:BC"


async def test_async_step_bluetooth_valid_device_v4_encryption_wrong_key(
    hass: HomeAssistant,
) -> None:
    """Test discovery via bluetooth with a valid device, with v4 encryption and wrong key."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=JTYJGD03MI_SERVICE_INFO,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "get_encryption_key_4_5"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"bindkey": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"},
    )

    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "get_encryption_key_4_5"
    assert result2["errors"]["bindkey"] == "decryption_failed"

    # Test can finish flow
    with patch(
        "homeassistant.components.xiaomi_ble.async_setup_entry", return_value=True
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"bindkey": "5b51a7c91cde6707c9ef18dfda143a58"},
        )

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Smoke Detector 9CBC (JTYJGD03MI)"
    assert result2["data"] == {"bindkey": "5b51a7c91cde6707c9ef18dfda143a58"}
    assert result2["result"].unique_id == "54:EF:44:E3:9C:BC"


async def test_async_step_bluetooth_valid_device_v4_encryption_wrong_key_length(
    hass: HomeAssistant,
) -> None:
    """Test discovery via bluetooth with a valid device, with v4 encryption and wrong key length."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=JTYJGD03MI_SERVICE_INFO,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "get_encryption_key_4_5"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"bindkey": "5b51a7c91cde6707c9ef18fda143a58"},
    )

    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "get_encryption_key_4_5"
    assert result2["errors"]["bindkey"] == "expected_32_characters"

    # Test can finish flow
    with patch(
        "homeassistant.components.xiaomi_ble.async_setup_entry", return_value=True
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"bindkey": "5b51a7c91cde6707c9ef18dfda143a58"},
        )

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Smoke Detector 9CBC (JTYJGD03MI)"
    assert result2["data"] == {"bindkey": "5b51a7c91cde6707c9ef18dfda143a58"}
    assert result2["result"].unique_id == "54:EF:44:E3:9C:BC"


async def test_async_step_bluetooth_not_xiaomi(hass: HomeAssistant) -> None:
    """Test discovery via bluetooth not xiaomi."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=NOT_SENSOR_PUSH_SERVICE_INFO,
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "not_supported"


async def test_async_step_user_no_devices_found(hass: HomeAssistant) -> None:
    """Test setup from service info cache with no devices found."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"


async def test_async_step_user_no_devices_found_2(hass: HomeAssistant) -> None:
    """Test setup from service info cache with no devices found.

    This variant tests with a non-Xiaomi device known to us.
    """
    with patch(
        "homeassistant.components.xiaomi_ble.config_flow.async_discovered_service_info",
        return_value=[NOT_SENSOR_PUSH_SERVICE_INFO],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "no_devices_found"


async def test_async_step_user_with_found_devices(hass: HomeAssistant) -> None:
    """Test setup from service info cache with devices found."""
    with patch(
        "homeassistant.components.xiaomi_ble.config_flow.async_discovered_service_info",
        return_value=[LYWSDCGQ_SERVICE_INFO],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    with patch(
        "homeassistant.components.xiaomi_ble.async_setup_entry", return_value=True
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"address": "58:2D:34:35:93:21"},
        )
    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Temperature/Humidity Sensor 9321 (LYWSDCGQ)"
    assert result2["data"] == {}
    assert result2["result"].unique_id == "58:2D:34:35:93:21"


async def test_async_step_user_short_payload(hass: HomeAssistant) -> None:
    """Test setup from service info cache with devices found but short payloads."""
    with patch(
        "homeassistant.components.xiaomi_ble.config_flow.async_discovered_service_info",
        return_value=[MISSING_PAYLOAD_ENCRYPTED],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    with patch(
        "homeassistant.components.xiaomi_ble.config_flow.async_process_advertisements",
        side_effect=TimeoutError(),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"address": "A4:C1:38:56:53:84"},
        )
    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "confirm_slow"

    with patch(
        "homeassistant.components.xiaomi_ble.async_setup_entry", return_value=True
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )
    assert result3["type"] is FlowResultType.CREATE_ENTRY
    assert result3["title"] == "Temperature/Humidity Sensor 5384 (LYWSD03MMC)"
    assert result3["data"] == {}
    assert result3["result"].unique_id == "A4:C1:38:56:53:84"


async def test_async_step_user_short_payload_then_full(hass: HomeAssistant) -> None:
    """Test setup from service info cache with devices found."""
    with patch(
        "homeassistant.components.xiaomi_ble.config_flow.async_discovered_service_info",
        return_value=[MISSING_PAYLOAD_ENCRYPTED],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    async def _async_process_advertisements(
        _hass, _callback, _matcher, _mode, _timeout
    ):
        service_info = make_advertisement(
            "A4:C1:38:56:53:84",
            b"XX\xe4\x16,\x84SV8\xc1\xa4+n\xf2\xe9\x12\x00\x00l\x88M\x9e",
        )
        assert _callback(service_info)
        return service_info

    with patch(
        "homeassistant.components.xiaomi_ble.config_flow.async_process_advertisements",
        _async_process_advertisements,
    ):
        result1 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"address": "A4:C1:38:56:53:84"},
        )
    assert result1["type"] is FlowResultType.FORM
    assert result1["step_id"] == "get_encryption_key_4_5"

    with patch(
        "homeassistant.components.xiaomi_ble.async_setup_entry", return_value=True
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"bindkey": "a115210eed7a88e50ad52662e732a9fb"},
        )

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Temperature/Humidity Sensor 5384 (LYWSD03MMC)"
    assert result2["data"] == {"bindkey": "a115210eed7a88e50ad52662e732a9fb"}


async def test_async_step_user_with_found_devices_v4_encryption(
    hass: HomeAssistant,
) -> None:
    """Test setup from service info cache with devices found, with v4 encryption."""
    with patch(
        "homeassistant.components.xiaomi_ble.config_flow.async_discovered_service_info",
        return_value=[JTYJGD03MI_SERVICE_INFO],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result1 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"address": "54:EF:44:E3:9C:BC"},
    )
    assert result1["type"] is FlowResultType.FORM
    assert result1["step_id"] == "get_encryption_key_4_5"

    with patch(
        "homeassistant.components.xiaomi_ble.async_setup_entry", return_value=True
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"bindkey": "5b51a7c91cde6707c9ef18dfda143a58"},
        )

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Smoke Detector 9CBC (JTYJGD03MI)"
    assert result2["data"] == {"bindkey": "5b51a7c91cde6707c9ef18dfda143a58"}
    assert result2["result"].unique_id == "54:EF:44:E3:9C:BC"


async def test_async_step_user_with_found_devices_v4_encryption_wrong_key(
    hass: HomeAssistant,
) -> None:
    """Test setup from service info cache with devices found, with v4 encryption and wrong key."""
    # Get a list of devices
    with patch(
        "homeassistant.components.xiaomi_ble.config_flow.async_discovered_service_info",
        return_value=[JTYJGD03MI_SERVICE_INFO],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    # Pick a device
    result1 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"address": "54:EF:44:E3:9C:BC"},
    )
    assert result1["type"] is FlowResultType.FORM
    assert result1["step_id"] == "get_encryption_key_4_5"

    # Try an incorrect key
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"bindkey": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"},
    )
    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "get_encryption_key_4_5"
    assert result2["errors"]["bindkey"] == "decryption_failed"

    # Check can still finish flow
    with patch(
        "homeassistant.components.xiaomi_ble.async_setup_entry", return_value=True
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"bindkey": "5b51a7c91cde6707c9ef18dfda143a58"},
        )

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Smoke Detector 9CBC (JTYJGD03MI)"
    assert result2["data"] == {"bindkey": "5b51a7c91cde6707c9ef18dfda143a58"}
    assert result2["result"].unique_id == "54:EF:44:E3:9C:BC"


async def test_async_step_user_with_found_devices_v4_encryption_wrong_key_length(
    hass: HomeAssistant,
) -> None:
    """Test setup from service info cache with devices found, with v4 encryption and wrong key length."""
    # Get a list of devices
    with patch(
        "homeassistant.components.xiaomi_ble.config_flow.async_discovered_service_info",
        return_value=[JTYJGD03MI_SERVICE_INFO],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    # Select a single device
    result1 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"address": "54:EF:44:E3:9C:BC"},
    )
    assert result1["type"] is FlowResultType.FORM
    assert result1["step_id"] == "get_encryption_key_4_5"

    # Try an incorrect key
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"bindkey": "5b51a7c91cde6707c9ef1dfda143a58"},
    )

    assert result2["type"] is FlowResultType.FORM
    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "get_encryption_key_4_5"
    assert result2["errors"]["bindkey"] == "expected_32_characters"

    # Check can still finish flow
    with patch(
        "homeassistant.components.xiaomi_ble.async_setup_entry", return_value=True
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"bindkey": "5b51a7c91cde6707c9ef18dfda143a58"},
        )

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Smoke Detector 9CBC (JTYJGD03MI)"
    assert result2["data"] == {"bindkey": "5b51a7c91cde6707c9ef18dfda143a58"}
    assert result2["result"].unique_id == "54:EF:44:E3:9C:BC"


async def test_async_step_user_with_found_devices_legacy_encryption(
    hass: HomeAssistant,
) -> None:
    """Test setup from service info cache with devices found, with legacy encryption."""
    with patch(
        "homeassistant.components.xiaomi_ble.config_flow.async_discovered_service_info",
        return_value=[YLKG07YL_SERVICE_INFO],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result1 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"address": "F8:24:41:C5:98:8B"},
    )
    assert result1["type"] is FlowResultType.FORM
    assert result1["step_id"] == "get_encryption_key_legacy"

    with patch(
        "homeassistant.components.xiaomi_ble.async_setup_entry", return_value=True
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"bindkey": "b853075158487ca39a5b5ea9"},
        )
    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Dimmer Switch 988B (YLKG07YL/YLKG08YL)"
    assert result2["data"] == {"bindkey": "b853075158487ca39a5b5ea9"}
    assert result2["result"].unique_id == "F8:24:41:C5:98:8B"


async def test_async_step_user_with_found_devices_legacy_encryption_wrong_key(
    hass: HomeAssistant,
) -> None:
    """Test setup from service info cache with devices found, with legacy encryption and wrong key."""
    with patch(
        "homeassistant.components.xiaomi_ble.config_flow.async_discovered_service_info",
        return_value=[YLKG07YL_SERVICE_INFO],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result1 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"address": "F8:24:41:C5:98:8B"},
    )
    assert result1["type"] is FlowResultType.FORM
    assert result1["step_id"] == "get_encryption_key_legacy"

    # Enter an incorrect code
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"bindkey": "aaaaaaaaaaaaaaaaaaaaaaaa"},
    )
    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "get_encryption_key_legacy"
    assert result2["errors"]["bindkey"] == "decryption_failed"

    # Check you can finish the flow
    with patch(
        "homeassistant.components.xiaomi_ble.async_setup_entry", return_value=True
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"bindkey": "b853075158487ca39a5b5ea9"},
        )
    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Dimmer Switch 988B (YLKG07YL/YLKG08YL)"
    assert result2["data"] == {"bindkey": "b853075158487ca39a5b5ea9"}
    assert result2["result"].unique_id == "F8:24:41:C5:98:8B"


async def test_async_step_user_with_found_devices_legacy_encryption_wrong_key_length(
    hass: HomeAssistant,
) -> None:
    """Test setup from service info cache with devices found, with legacy encryption and wrong key length."""
    with patch(
        "homeassistant.components.xiaomi_ble.config_flow.async_discovered_service_info",
        return_value=[YLKG07YL_SERVICE_INFO],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result1 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"address": "F8:24:41:C5:98:8B"},
    )
    assert result1["type"] is FlowResultType.FORM
    assert result1["step_id"] == "get_encryption_key_legacy"

    # Enter an incorrect code
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"bindkey": "b85307518487ca39a5b5ea9"},
    )
    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "get_encryption_key_legacy"
    assert result2["errors"]["bindkey"] == "expected_24_characters"

    # Check you can finish the flow
    with patch(
        "homeassistant.components.xiaomi_ble.async_setup_entry", return_value=True
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"bindkey": "b853075158487ca39a5b5ea9"},
        )
    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Dimmer Switch 988B (YLKG07YL/YLKG08YL)"
    assert result2["data"] == {"bindkey": "b853075158487ca39a5b5ea9"}
    assert result2["result"].unique_id == "F8:24:41:C5:98:8B"


async def test_async_step_user_device_added_between_steps(hass: HomeAssistant) -> None:
    """Test the device gets added via another flow between steps."""
    with patch(
        "homeassistant.components.xiaomi_ble.config_flow.async_discovered_service_info",
        return_value=[LYWSDCGQ_SERVICE_INFO],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="58:2D:34:35:93:21",
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.xiaomi_ble.async_setup_entry", return_value=True
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"address": "58:2D:34:35:93:21"},
        )
    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "already_configured"


async def test_async_step_user_with_found_devices_already_setup(
    hass: HomeAssistant,
) -> None:
    """Test setup from service info cache with devices found."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="58:2D:34:35:93:21",
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.xiaomi_ble.config_flow.async_discovered_service_info",
        return_value=[LYWSDCGQ_SERVICE_INFO],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"


async def test_async_step_bluetooth_devices_already_setup(hass: HomeAssistant) -> None:
    """Test we can't start a flow if there is already a config entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="00:81:F9:DD:6F:C1",
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=MMC_T201_1_SERVICE_INFO,
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_async_step_bluetooth_already_in_progress(hass: HomeAssistant) -> None:
    """Test we can't start a flow for the same device twice."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=MMC_T201_1_SERVICE_INFO,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=MMC_T201_1_SERVICE_INFO,
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_in_progress"


async def test_async_step_user_takes_precedence_over_discovery(
    hass: HomeAssistant,
) -> None:
    """Test manual setup takes precedence over discovery."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=MMC_T201_1_SERVICE_INFO,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"

    with patch(
        "homeassistant.components.xiaomi_ble.config_flow.async_discovered_service_info",
        return_value=[MMC_T201_1_SERVICE_INFO],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )
        assert result["type"] is FlowResultType.FORM

    with patch(
        "homeassistant.components.xiaomi_ble.async_setup_entry", return_value=True
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"address": "00:81:F9:DD:6F:C1"},
        )
    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Baby Thermometer 6FC1 (MMC-T201-1)"
    assert result2["data"] == {}
    assert result2["result"].unique_id == "00:81:F9:DD:6F:C1"

    # Verify the original one was aborted
    assert not hass.config_entries.flow.async_progress(DOMAIN)


async def test_async_step_reauth_legacy(hass: HomeAssistant) -> None:
    """Test reauth with a legacy key."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="F8:24:41:C5:98:8B",
    )
    entry.add_to_hass(hass)
    saved_callback = None

    def _async_register_callback(_hass, _callback, _matcher, _mode):
        nonlocal saved_callback
        saved_callback = _callback
        return lambda: None

    with patch(
        "homeassistant.components.bluetooth.update_coordinator.async_register_callback",
        _async_register_callback,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 0

    # WARNING: This test data is synthetic, rather than captured from a real device
    # obj type is 0x1310, payload len is 0x2 and payload is 0x6000
    saved_callback(
        make_advertisement(
            "F8:24:41:C5:98:8B",
            b"X0\xb6\x03\xd2\x8b\x98\xc5A$\xf8\xc3I\x14vu~\x00\x00\x00\x99",
        ),
        BluetoothChange.ADVERTISEMENT,
    )

    await hass.async_block_till_done()

    results = hass.config_entries.flow.async_progress()
    assert len(results) == 1
    result = results[0]

    assert result["step_id"] == "get_encryption_key_legacy"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"bindkey": "b853075158487ca39a5b5ea9"},
    )
    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "reauth_successful"


async def test_async_step_reauth_legacy_wrong_key(hass: HomeAssistant) -> None:
    """Test reauth with a bad legacy key, and that we can recover."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="F8:24:41:C5:98:8B",
    )
    entry.add_to_hass(hass)
    saved_callback = None

    def _async_register_callback(_hass, _callback, _matcher, _mode):
        nonlocal saved_callback
        saved_callback = _callback
        return lambda: None

    with patch(
        "homeassistant.components.bluetooth.update_coordinator.async_register_callback",
        _async_register_callback,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 0

    # WARNING: This test data is synthetic, rather than captured from a real device
    # obj type is 0x1310, payload len is 0x2 and payload is 0x6000
    saved_callback(
        make_advertisement(
            "F8:24:41:C5:98:8B",
            b"X0\xb6\x03\xd2\x8b\x98\xc5A$\xf8\xc3I\x14vu~\x00\x00\x00\x99",
        ),
        BluetoothChange.ADVERTISEMENT,
    )

    await hass.async_block_till_done()

    results = hass.config_entries.flow.async_progress()
    assert len(results) == 1
    result = results[0]

    assert result["step_id"] == "get_encryption_key_legacy"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"bindkey": "b85307515a487ca39a5b5ea9"},
    )
    assert result2["type"] is FlowResultType.FORM
    assert result["step_id"] == "get_encryption_key_legacy"
    assert result2["errors"]["bindkey"] == "decryption_failed"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"bindkey": "b853075158487ca39a5b5ea9"},
    )
    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "reauth_successful"


async def test_async_step_reauth_v4(hass: HomeAssistant) -> None:
    """Test reauth with a v4 key."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="54:EF:44:E3:9C:BC",
    )
    entry.add_to_hass(hass)
    saved_callback = None

    def _async_register_callback(_hass, _callback, _matcher, _mode):
        nonlocal saved_callback
        saved_callback = _callback
        return lambda: None

    with patch(
        "homeassistant.components.bluetooth.update_coordinator.async_register_callback",
        _async_register_callback,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 0

    # WARNING: This test data is synthetic, rather than captured from a real device
    # obj type is 0x1310, payload len is 0x2 and payload is 0x6000
    saved_callback(
        make_advertisement(
            "54:EF:44:E3:9C:BC",
            b"XY\x97\tf\xbc\x9c\xe3D\xefT\x01\x08\x12\x05\x00\x00\x00q^\xbe\x90",
        ),
        BluetoothChange.ADVERTISEMENT,
    )

    await hass.async_block_till_done()

    results = hass.config_entries.flow.async_progress()
    assert len(results) == 1
    result = results[0]

    assert result["step_id"] == "get_encryption_key_4_5"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"bindkey": "5b51a7c91cde6707c9ef18dfda143a58"},
    )
    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "reauth_successful"


async def test_async_step_reauth_v4_wrong_key(hass: HomeAssistant) -> None:
    """Test reauth for v4 with a bad key, and that we can recover."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="54:EF:44:E3:9C:BC",
    )
    entry.add_to_hass(hass)
    saved_callback = None

    def _async_register_callback(_hass, _callback, _matcher, _mode):
        nonlocal saved_callback
        saved_callback = _callback
        return lambda: None

    with patch(
        "homeassistant.components.bluetooth.update_coordinator.async_register_callback",
        _async_register_callback,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 0

    # WARNING: This test data is synthetic, rather than captured from a real device
    # obj type is 0x1310, payload len is 0x2 and payload is 0x6000
    saved_callback(
        make_advertisement(
            "54:EF:44:E3:9C:BC",
            b"XY\x97\tf\xbc\x9c\xe3D\xefT\x01\x08\x12\x05\x00\x00\x00q^\xbe\x90",
        ),
        BluetoothChange.ADVERTISEMENT,
    )

    await hass.async_block_till_done()

    results = hass.config_entries.flow.async_progress()
    assert len(results) == 1
    result = results[0]

    assert result["step_id"] == "get_encryption_key_4_5"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"bindkey": "5b51a7c91cde6707c9ef18dada143a58"},
    )
    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "get_encryption_key_4_5"
    assert result2["errors"]["bindkey"] == "decryption_failed"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"bindkey": "5b51a7c91cde6707c9ef18dfda143a58"},
    )
    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "reauth_successful"


async def test_async_step_reauth_abort_early(hass: HomeAssistant) -> None:
    """Test we can abort the reauth if there is no encryption.

    (This can't currently happen in practice).
    """
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="54:EF:44:E3:9C:BC",
    )
    entry.add_to_hass(hass)

    device = DeviceData()

    result = await entry.start_reauth_flow(hass, data={"device": device})

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
