"""Test the switchbot services."""

from collections.abc import Callable
from unittest.mock import AsyncMock, patch

import pytest
from switchbot import SwitchbotOperationError

from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.components.switchbot.const import DOMAIN
from homeassistant.components.switchbot.services import (
    SERVICE_ADD_PASSWORD,
    SERVICE_GET_KEYPAD_INFO,
    async_setup_services,
)
from homeassistant.const import ATTR_DEVICE_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import device_registry as dr

from . import (
    KEYPAD_VISION_INFO,
    KEYPAD_VISION_PRO_INFO,
    SMART_THERMOSTAT_RADIATOR_SERVICE_INFO,
)

from tests.common import MockConfigEntry
from tests.components.bluetooth import inject_bluetooth_service_info


@pytest.mark.parametrize(
    ("ble_service_info", "sensor_type"),
    [
        (KEYPAD_VISION_INFO, "keypad_vision"),
        (KEYPAD_VISION_PRO_INFO, "keypad_vision_pro"),
    ],
)
async def test_add_password_service(
    hass: HomeAssistant,
    mock_entry_encrypted_factory: Callable[[str], MockConfigEntry],
    ble_service_info: BluetoothServiceInfoBleak,
    sensor_type: str,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test the add_password service."""
    inject_bluetooth_service_info(hass, ble_service_info)

    entry = mock_entry_encrypted_factory(sensor_type=sensor_type)
    entry.add_to_hass(hass)

    mocked_instance = AsyncMock(return_value=True)
    with patch.multiple(
        "homeassistant.components.switchbot.switchbot.SwitchbotKeypadVision",
        update=AsyncMock(return_value=None),
        add_password=mocked_instance,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        device_entry = dr.async_entries_for_config_entry(
            device_registry, entry.entry_id
        )[0]

        await hass.services.async_call(
            DOMAIN,
            SERVICE_ADD_PASSWORD,
            {
                ATTR_DEVICE_ID: device_entry.id,
                "password": "123456",
            },
            blocking=True,
        )

        mocked_instance.assert_called_once_with("123456")


@pytest.mark.parametrize(
    ("ble_service_info", "sensor_type", "credential_counts"),
    [
        (
            KEYPAD_VISION_INFO,
            "keypad_vision",
            {
                "pin": 3,
                "nfc": 2,
                "fingerprint": 1,
                "duress_pin": 1,
                "duress_fingerprint": 0,
            },
        ),
        (
            KEYPAD_VISION_PRO_INFO,
            "keypad_vision_pro",
            {
                "pin": 3,
                "nfc": 2,
                "fingerprint": 1,
                "duress_pin": 1,
                "duress_fingerprint": 0,
                "face": 2,
                "palm_vein": 1,
            },
        ),
    ],
)
async def test_get_keypad_info_service(
    hass: HomeAssistant,
    mock_entry_encrypted_factory: Callable[[str], MockConfigEntry],
    ble_service_info: BluetoothServiceInfoBleak,
    sensor_type: str,
    credential_counts: dict[str, int],
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test the get_keypad_info service."""
    inject_bluetooth_service_info(hass, ble_service_info)

    entry = mock_entry_encrypted_factory(sensor_type=sensor_type)
    entry.add_to_hass(hass)

    basic_info = {
        "battery": 95,
        "firmware": 2.4,
        "hardware": 22,
        "support_fingerprint": 1,
        "lock_button_enabled": True,
        "tamper_alarm_enabled": True,
        "backlight_enabled": True,
        "backlight_level": 5,
        "prompt_tone_enabled": True,
        "battery_charging": sensor_type == "keypad_vision",
    }
    get_basic_info = AsyncMock(return_value=basic_info)
    get_password_count = AsyncMock(return_value=credential_counts)
    with patch.multiple(
        "homeassistant.components.switchbot.switchbot.SwitchbotKeypadVision",
        update=AsyncMock(return_value=None),
        get_basic_info=get_basic_info,
        get_password_count=get_password_count,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        device_entry = dr.async_entries_for_config_entry(
            device_registry, entry.entry_id
        )[0]

        response = await hass.services.async_call(
            DOMAIN,
            SERVICE_GET_KEYPAD_INFO,
            {ATTR_DEVICE_ID: device_entry.id},
            blocking=True,
            return_response=True,
        )

    assert response == {
        "basic_info": basic_info,
        "credential_counts": credential_counts,
    }
    get_basic_info.assert_awaited_once_with()
    get_password_count.assert_awaited_once_with()


@pytest.mark.parametrize(
    ("basic_info", "credential_counts"),
    [
        (None, {"pin": 1}),
        ({"battery": 95}, None),
    ],
)
async def test_get_keypad_info_unavailable(
    hass: HomeAssistant,
    mock_entry_encrypted_factory: Callable[[str], MockConfigEntry],
    device_registry: dr.DeviceRegistry,
    basic_info: dict[str, int] | None,
    credential_counts: dict[str, int] | None,
) -> None:
    """Test the get_keypad_info service when keypad information is unavailable."""
    inject_bluetooth_service_info(hass, KEYPAD_VISION_INFO)

    entry = mock_entry_encrypted_factory(sensor_type="keypad_vision")
    entry.add_to_hass(hass)

    with patch.multiple(
        "homeassistant.components.switchbot.switchbot.SwitchbotKeypadVision",
        update=AsyncMock(return_value=None),
        get_basic_info=AsyncMock(return_value=basic_info),
        get_password_count=AsyncMock(return_value=credential_counts),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        device_entry = dr.async_entries_for_config_entry(
            device_registry, entry.entry_id
        )[0]

        with pytest.raises(ServiceValidationError) as err:
            await hass.services.async_call(
                DOMAIN,
                SERVICE_GET_KEYPAD_INFO,
                {ATTR_DEVICE_ID: device_entry.id},
                blocking=True,
                return_response=True,
            )

    assert err.value.translation_domain == DOMAIN
    assert err.value.translation_key == "keypad_info_unavailable"


@pytest.mark.parametrize("failing_method", ["get_basic_info", "get_password_count"])
async def test_get_keypad_info_operation_error(
    hass: HomeAssistant,
    mock_entry_encrypted_factory: Callable[[str], MockConfigEntry],
    device_registry: dr.DeviceRegistry,
    failing_method: str,
) -> None:
    """Test the get_keypad_info service translates SwitchBot operation errors."""
    inject_bluetooth_service_info(hass, KEYPAD_VISION_INFO)

    entry = mock_entry_encrypted_factory(sensor_type="keypad_vision")
    entry.add_to_hass(hass)

    get_basic_info = AsyncMock(return_value={"battery": 95})
    get_password_count = AsyncMock(return_value={"pin": 1})
    operation_error = SwitchbotOperationError("Bluetooth command failed")
    if failing_method == "get_basic_info":
        get_basic_info.side_effect = operation_error
    else:
        get_password_count.side_effect = operation_error

    with patch.multiple(
        "homeassistant.components.switchbot.switchbot.SwitchbotKeypadVision",
        update=AsyncMock(return_value=None),
        get_basic_info=get_basic_info,
        get_password_count=get_password_count,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        device_entry = dr.async_entries_for_config_entry(
            device_registry, entry.entry_id
        )[0]

        with pytest.raises(ServiceValidationError) as err:
            await hass.services.async_call(
                DOMAIN,
                SERVICE_GET_KEYPAD_INFO,
                {ATTR_DEVICE_ID: device_entry.id},
                blocking=True,
                return_response=True,
            )

    assert err.value.translation_domain == DOMAIN
    assert err.value.translation_key == "operation_error"
    assert err.value.translation_placeholders == {"error": "Bluetooth command failed"}


async def test_device_not_found(
    hass: HomeAssistant,
    mock_entry_encrypted_factory: Callable[[str], MockConfigEntry],
) -> None:
    """Test the add_password service with non-existent device."""
    inject_bluetooth_service_info(hass, KEYPAD_VISION_INFO)

    entry = mock_entry_encrypted_factory(sensor_type="keypad_vision")
    entry.add_to_hass(hass)

    with patch.multiple(
        "homeassistant.components.switchbot.switchbot.SwitchbotKeypadVision",
        update=AsyncMock(return_value=None),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        with pytest.raises(ServiceValidationError) as err:
            await hass.services.async_call(
                DOMAIN,
                SERVICE_ADD_PASSWORD,
                {
                    ATTR_DEVICE_ID: "nonexistent_device",
                    "password": "123456",
                },
                blocking=True,
            )

        assert err.value.translation_domain == DOMAIN
        assert err.value.translation_key == "invalid_device_id"
        assert err.value.translation_placeholders == {"device_id": "nonexistent_device"}


async def test_device_not_belonging(
    hass: HomeAssistant,
    mock_entry_encrypted_factory: Callable[[str], MockConfigEntry],
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test service errors when device belongs to a different integration."""
    inject_bluetooth_service_info(hass, KEYPAD_VISION_INFO)

    entry = mock_entry_encrypted_factory(sensor_type="keypad_vision")
    entry.add_to_hass(hass)

    with patch.multiple(
        "homeassistant.components.switchbot.switchbot.SwitchbotKeypadVision",
        update=AsyncMock(return_value=None),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    other_entry = MockConfigEntry(domain="not_switchbot", data={}, title="Other")
    other_entry.add_to_hass(hass)

    device_entry = device_registry.async_get_or_create(
        config_entry_id=other_entry.entry_id,
        identifiers={("not_switchbot", "other_unique_id")},
        name="Other device",
    )

    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_ADD_PASSWORD,
            {
                ATTR_DEVICE_ID: device_entry.id,
                "password": "123456",
            },
            blocking=True,
        )

    assert err.value.translation_domain == DOMAIN
    assert err.value.translation_key == "device_not_belonging"
    assert err.value.translation_placeholders == {"device_id": device_entry.id}


async def test_device_entry_not_loaded(
    hass: HomeAssistant,
    mock_entry_encrypted_factory: Callable[[str], MockConfigEntry],
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test service errors when the config entry is not loaded."""
    inject_bluetooth_service_info(hass, KEYPAD_VISION_INFO)

    entry = mock_entry_encrypted_factory(sensor_type="keypad_vision")
    entry.add_to_hass(hass)

    with patch.multiple(
        "homeassistant.components.switchbot.switchbot.SwitchbotKeypadVision",
        update=AsyncMock(return_value=None),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    second_entry = mock_entry_encrypted_factory(sensor_type="keypad_vision")
    second_entry.add_to_hass(hass)

    device_entry = device_registry.async_get_or_create(
        config_entry_id=second_entry.entry_id,
        identifiers={(DOMAIN, "not_loaded_unique_id")},
        name="Not loaded device",
    )

    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_ADD_PASSWORD,
            {
                ATTR_DEVICE_ID: device_entry.id,
                "password": "123456",
            },
            blocking=True,
        )

    assert err.value.translation_domain == DOMAIN
    assert err.value.translation_key == "device_entry_not_loaded"
    assert err.value.translation_placeholders == {"device_id": device_entry.id}


async def test_service_unsupported_device(
    hass: HomeAssistant,
    mock_entry_encrypted_factory: Callable[[str], MockConfigEntry],
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test service errors when the device does not support the service."""
    inject_bluetooth_service_info(hass, SMART_THERMOSTAT_RADIATOR_SERVICE_INFO)

    entry = mock_entry_encrypted_factory(sensor_type="smart_thermostat_radiator")
    entry.add_to_hass(hass)

    with patch.multiple(
        "homeassistant.components.switchbot.switchbot.SwitchbotSmartThermostatRadiator",
        update=AsyncMock(return_value=None),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    device_entry = dr.async_entries_for_config_entry(device_registry, entry.entry_id)[0]

    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_ADD_PASSWORD,
            {
                ATTR_DEVICE_ID: device_entry.id,
                "password": "123456",
            },
            blocking=True,
        )

    assert err.value.translation_domain == DOMAIN
    assert err.value.translation_key == "not_keypad_vision_device"


async def test_device_without_config_entry_id(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test service errors when device has no config entry id."""
    async_setup_services(hass)

    entry = MockConfigEntry(domain=DOMAIN, data={}, title="No entry device")
    entry.add_to_hass(hass)

    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_ADD_PASSWORD,
            {
                ATTR_DEVICE_ID: "abc",
                "password": "123456",
            },
            blocking=True,
        )

    assert err.value.translation_domain == DOMAIN
    assert err.value.translation_key == "invalid_device_id"
    assert err.value.translation_placeholders == {"device_id": "abc"}
