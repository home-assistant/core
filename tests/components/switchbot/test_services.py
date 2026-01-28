"""Test the switchbot services."""

from collections.abc import Callable
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.components.switchbot.const import DOMAIN
from homeassistant.components.switchbot.services import (
    SERVICE_ADD_PASSWORD,
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

        device_registry = dr.async_get(hass)
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


async def test_device_not_belonging(hass: HomeAssistant) -> None:
    """Test service errors when device belongs to a different integration."""
    async_setup_services(hass)

    other_entry = MockConfigEntry(domain="not_switchbot", data={}, title="Other")
    other_entry.add_to_hass(hass)

    device_registry = dr.async_get(hass)
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
) -> None:
    """Test service errors when the config entry is not loaded."""
    async_setup_services(hass)

    entry = mock_entry_encrypted_factory(sensor_type="keypad_vision")
    entry.add_to_hass(hass)

    device_registry = dr.async_get(hass)
    device_entry = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
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


async def test_missing_device_id(hass: HomeAssistant) -> None:
    """Test service errors when device_id is missing."""
    async_setup_services(hass)

    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_ADD_PASSWORD,
            {"password": "123456", "device_id": []},
            blocking=True,
        )

    assert err.value.translation_domain == DOMAIN
    assert err.value.translation_key == "missing_device_id"


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

    device_registry = dr.async_get(hass)
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


async def test_device_without_config_entry_id(hass: HomeAssistant) -> None:
    """Test service errors when device has no config entry id."""
    async_setup_services(hass)

    device_registry = dr.async_get(hass)
    entry = MockConfigEntry(domain=DOMAIN, data={}, title="No entry device")
    entry.add_to_hass(hass)
    device_entry = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, "no_config_entry_unique_id")},
        name="No config entry device",
    )
    device_registry.async_update_device(
        device_entry.id, remove_config_entry_id=entry.entry_id
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
    assert err.value.translation_key == "invalid_device_id"
    assert err.value.translation_placeholders == {"device_id": device_entry.id}


async def test_device_without_config_entry(
    hass: HomeAssistant,
    mock_entry_encrypted_factory: Callable[[str], MockConfigEntry],
) -> None:
    """Test service errors when device has no config entries."""
    async_setup_services(hass)
    inject_bluetooth_service_info(hass, KEYPAD_VISION_INFO)

    entry = mock_entry_encrypted_factory(sensor_type="keypad_vision")
    entry.add_to_hass(hass)

    with patch.multiple(
        "homeassistant.components.switchbot.switchbot.SwitchbotKeypadVision",
        update=AsyncMock(return_value=None),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    device_registry = dr.async_get(hass)
    device_entry = dr.async_entries_for_config_entry(device_registry, entry.entry_id)[0]

    device_registry.devices[device_entry.id].config_entries.clear()

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
    assert err.value.translation_key == "device_without_config_entry"
    assert err.value.translation_placeholders == {"device_id": device_entry.id}
