"""Test the switchbot services."""

from collections.abc import Callable
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.components.switchbot.const import (
    CONF_ENCRYPTION_KEY,
    CONF_KEY_ID,
    DOMAIN,
)
from homeassistant.components.switchbot.services import (
    SERVICE_ADD_PASSWORD,
    SERVICE_GET_PASSWORD_COUNT,
    async_setup_services,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_ADDRESS,
    CONF_NAME,
    CONF_SENSOR_TYPE,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er

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

        await hass.services.async_call(
            DOMAIN,
            SERVICE_ADD_PASSWORD,
            {
                ATTR_ENTITY_ID: "sensor.test_name_battery",
                "password": "123456",
            },
            blocking=True,
        )

        mocked_instance.assert_called_once_with("123456")


@pytest.mark.parametrize(
    ("ble_service_info", "sensor_type", "result"),
    [
        (KEYPAD_VISION_INFO, "keypad_vision", {"pin": 2}),
        (KEYPAD_VISION_PRO_INFO, "keypad_vision_pro", {"pin": 3, "fingerprint": 5}),
    ],
)
async def test_get_password_count_service(
    hass: HomeAssistant,
    mock_entry_encrypted_factory: Callable[[str], MockConfigEntry],
    ble_service_info: BluetoothServiceInfoBleak,
    sensor_type: str,
    result: dict[str, int],
) -> None:
    """Test the get_password_count service."""
    inject_bluetooth_service_info(hass, ble_service_info)

    entry = mock_entry_encrypted_factory(sensor_type=sensor_type)
    entry.add_to_hass(hass)

    mocked_instance = AsyncMock(return_value=result)
    with patch.multiple(
        "homeassistant.components.switchbot.switchbot.SwitchbotKeypadVision",
        update=AsyncMock(return_value=None),
        get_password_count=mocked_instance,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        response = await hass.services.async_call(
            DOMAIN,
            SERVICE_GET_PASSWORD_COUNT,
            {
                ATTR_ENTITY_ID: "sensor.test_name_battery",
            },
            blocking=True,
            return_response=True,
        )

        assert response == result
        mocked_instance.assert_called_once()


async def test_entity_not_found(
    hass: HomeAssistant,
    mock_entry_encrypted_factory: Callable[[str], MockConfigEntry],
) -> None:
    """Test the add_password service with non-existent entity."""
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
                    ATTR_ENTITY_ID: "sensor.nonexistent_entity",
                    "password": "123456",
                },
                blocking=True,
            )

        assert err.value.translation_domain == DOMAIN
        assert err.value.translation_key == "invalid_entity_id"
        assert err.value.translation_placeholders == {
            "entity_id": "sensor.nonexistent_entity"
        }


async def test_entity_not_belonging(hass: HomeAssistant) -> None:
    """Test service errors when entity belongs to a different integration."""
    async_setup_services(hass)

    other_entry = MockConfigEntry(domain="not_switchbot", data={}, title="Other")
    other_entry.add_to_hass(hass)

    entity_registry = er.async_get(hass)
    entity_entry = entity_registry.async_get_or_create(
        "sensor",
        "not_switchbot",
        "other_unique_id",
        suggested_object_id="other_entity",
        config_entry=other_entry,
    )

    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_ADD_PASSWORD,
            {
                ATTR_ENTITY_ID: entity_entry.entity_id,
                "password": "123456",
            },
            blocking=True,
        )

    assert err.value.translation_domain == DOMAIN
    assert err.value.translation_key == "entity_not_belonging"
    assert err.value.translation_placeholders == {"entity_id": entity_entry.entity_id}


async def test_entry_not_loaded(
    hass: HomeAssistant,
    mock_entry_encrypted_factory: Callable[[str], MockConfigEntry],
) -> None:
    """Test service errors when the config entry is not loaded."""
    async_setup_services(hass)

    entry = mock_entry_encrypted_factory(sensor_type="keypad_vision")
    entry.add_to_hass(hass)

    entity_registry = er.async_get(hass)
    entity_entry = entity_registry.async_get_or_create(
        "sensor",
        DOMAIN,
        "not_loaded_unique_id",
        suggested_object_id="not_loaded_entity",
        config_entry=entry,
    )

    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_ADD_PASSWORD,
            {
                ATTR_ENTITY_ID: entity_entry.entity_id,
                "password": "123456",
            },
            blocking=True,
        )

    assert err.value.translation_domain == DOMAIN
    assert err.value.translation_key == "entry_not_loaded"
    assert err.value.translation_placeholders == {"entity_id": entity_entry.entity_id}


async def test_service_unsupported_device(
    hass: HomeAssistant,
    mock_entry_encrypted_factory: Callable[[str], MockConfigEntry],
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

    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_ADD_PASSWORD,
            {
                ATTR_ENTITY_ID: "sensor.test_name_battery",
                "password": "123456",
            },
            blocking=True,
        )

    assert err.value.translation_domain == DOMAIN
    assert err.value.translation_key == "not_keypad_vision_device"
    assert err.value.translation_placeholders == {
        "entity_id": "sensor.test_name_battery"
    }


async def test_get_password_count_multiple_entries(
    hass: HomeAssistant,
) -> None:
    """Test get_password_count returns per-entity results for multiple devices."""
    inject_bluetooth_service_info(hass, KEYPAD_VISION_INFO)
    inject_bluetooth_service_info(hass, KEYPAD_VISION_PRO_INFO)

    entry_1 = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_ADDRESS: "AA:BB:CC:DD:EE:FF",
            CONF_NAME: "test-name1",
            CONF_SENSOR_TYPE: "keypad_vision",
            CONF_KEY_ID: "ff",
            CONF_ENCRYPTION_KEY: "ffffffffffffffffffffffffffffffff",
        },
        unique_id="aabbccddeeff",
    )
    entry_1.add_to_hass(hass)

    entry_2 = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_ADDRESS: "AA:BB:CC:DD:EE:FF",
            CONF_NAME: "test-name2",
            CONF_SENSOR_TYPE: "keypad_vision_pro",
            CONF_KEY_ID: "ff",
            CONF_ENCRYPTION_KEY: "ffffffffffffffffffffffffffffffff",
        },
        unique_id="aabbccddeegg",
    )
    entry_2.add_to_hass(hass)

    result_1 = {"pin": 2}
    result_2 = {"pin": 3, "fingerprint": 5}

    with patch.multiple(
        "homeassistant.components.switchbot.switchbot.SwitchbotKeypadVision",
        update=AsyncMock(return_value=None),
    ):
        await hass.config_entries.async_setup(entry_1.entry_id)
        await hass.async_block_till_done()

        with (
            patch.object(
                entry_1.runtime_data.device,
                "get_password_count",
                AsyncMock(return_value=result_1),
            ),
            patch.object(
                entry_2.runtime_data.device,
                "get_password_count",
                AsyncMock(return_value=result_2),
            ),
        ):
            response = await hass.services.async_call(
                DOMAIN,
                SERVICE_GET_PASSWORD_COUNT,
                {
                    ATTR_ENTITY_ID: [
                        "sensor.test_name1_battery",
                        "sensor.test_name2_battery",
                    ],
                },
                blocking=True,
                return_response=True,
            )

            assert response == {
                "entities": {
                    "sensor.test_name1_battery": result_1,
                    "sensor.test_name2_battery": result_2,
                }
            }


async def test_entity_without_config_entry_id(hass: HomeAssistant) -> None:
    """Test service errors when entity has no config entry id."""
    async_setup_services(hass)

    entity_registry = er.async_get(hass)
    entity_entry = entity_registry.async_get_or_create(
        "sensor",
        DOMAIN,
        "no_config_entry_unique_id",
        suggested_object_id="no_config_entry_entity",
    )

    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_ADD_PASSWORD,
            {
                ATTR_ENTITY_ID: entity_entry.entity_id,
                "password": "123456",
            },
            blocking=True,
        )

    assert err.value.translation_domain == DOMAIN
    assert err.value.translation_key == "entity_without_config_entry"
    assert err.value.translation_placeholders == {"entity_id": entity_entry.entity_id}
