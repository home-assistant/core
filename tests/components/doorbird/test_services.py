"""Test DoorBird services."""

from typing import Any

import aiohttp
import pytest
from pytest_homeassistant.common import MockConfigEntry, MockUser

from homeassistant.components.doorbird.const import (
    CONF_EVENTS,
    DEFAULT_DOORBELL_EVENT,
    DEFAULT_MOTION_EVENT,
    DOMAIN,
)
from homeassistant.components.doorbird.services import SERVICE_RESTART
from homeassistant.const import ATTR_DEVICE_ID, CONF_HOST, CONF_NAME
from homeassistant.core import Context, HomeAssistant
from homeassistant.exceptions import (
    HomeAssistantError,
    ServiceValidationError,
    Unauthorized,
)
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import VALID_CONFIG
from .conftest import DoorbirdMockerType


def _get_device_id(hass: HomeAssistant, entity_id: str = "button.mydoorbird_ir") -> str:
    """Return the ID of the device that owns an entity."""
    entity_entry = er.async_get(hass).async_get(entity_id)
    assert entity_entry is not None
    assert entity_entry.device_id is not None
    return entity_entry.device_id


@pytest.mark.parametrize("as_list", [True, False], ids=["list", "single_id"])
async def test_restart(
    hass: HomeAssistant,
    doorbird_mocker: DoorbirdMockerType,
    as_list: bool,
) -> None:
    """Test restarting a DoorBird."""
    doorbird_entry = await doorbird_mocker()
    device_id = _get_device_id(hass)

    await hass.services.async_call(
        DOMAIN,
        SERVICE_RESTART,
        {ATTR_DEVICE_ID: [device_id] if as_list else device_id},
        blocking=True,
    )

    assert doorbird_entry.api.restart.call_count == 1


async def test_restart_multiple_devices(
    hass: HomeAssistant,
    doorbird_mocker: DoorbirdMockerType,
    doorbird_info: dict[str, Any],
) -> None:
    """Test restarting more than one DoorBird in a single call."""
    first = await doorbird_mocker()
    second = await doorbird_mocker(
        entry=MockConfigEntry(
            domain=DOMAIN,
            unique_id="1CCAE3BBBBBB",
            data={**VALID_CONFIG, CONF_HOST: "1.2.3.5", CONF_NAME: "seconddoorbird"},
            options={CONF_EVENTS: [DEFAULT_DOORBELL_EVENT, DEFAULT_MOTION_EVENT]},
        ),
        info={**doorbird_info, "PRIMARY_MAC_ADDR": "1CCAE3BBBBBB"},
    )

    await hass.services.async_call(
        DOMAIN,
        SERVICE_RESTART,
        {
            ATTR_DEVICE_ID: [
                _get_device_id(hass),
                _get_device_id(hass, "button.seconddoorbird_ir"),
            ]
        },
        blocking=True,
    )

    assert first.api.restart.call_count == 1
    assert second.api.restart.call_count == 1


async def test_restart_requires_admin(
    hass: HomeAssistant,
    doorbird_mocker: DoorbirdMockerType,
    hass_read_only_user: MockUser,
) -> None:
    """Test that a non-admin user cannot restart a DoorBird."""
    doorbird_entry = await doorbird_mocker()
    device_id = _get_device_id(hass)

    with pytest.raises(Unauthorized):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_RESTART,
            {ATTR_DEVICE_ID: [device_id]},
            blocking=True,
            context=Context(user_id=hass_read_only_user.id),
        )

    assert doorbird_entry.api.restart.call_count == 0


async def test_restart_unknown_device(
    hass: HomeAssistant,
    doorbird_mocker: DoorbirdMockerType,
) -> None:
    """Test that a device ID that does not exist is rejected."""
    doorbird_entry = await doorbird_mocker()

    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_RESTART,
            {ATTR_DEVICE_ID: ["not_a_real_device_id"]},
            blocking=True,
        )

    assert exc_info.value.translation_key == "device_not_found"
    assert doorbird_entry.api.restart.call_count == 0


async def test_restart_device_from_other_integration(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    doorbird_mocker: DoorbirdMockerType,
) -> None:
    """Test that a device that is not a DoorBird is rejected."""
    doorbird_entry = await doorbird_mocker()
    other_entry = MockConfigEntry(domain="other", data={})
    other_entry.add_to_hass(hass)
    other_device = device_registry.async_get_or_create(
        config_entry_id=other_entry.entry_id,
        identifiers={("other", "device_1")},
    )

    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_RESTART,
            {ATTR_DEVICE_ID: [other_device.id]},
            blocking=True,
        )

    assert exc_info.value.translation_key == "device_not_found"
    assert doorbird_entry.api.restart.call_count == 0


async def test_restart_unloaded_entry(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    doorbird_mocker: DoorbirdMockerType,
) -> None:
    """Test that a DoorBird whose config entry is not loaded is rejected."""
    doorbird_entry = await doorbird_mocker()
    # A DoorBird config entry that was never set up has no runtime data
    unloaded_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="1CCAE3CCCCCC",
        data={**VALID_CONFIG, CONF_HOST: "1.2.3.6", CONF_NAME: "unloadeddoorbird"},
    )
    unloaded_entry.add_to_hass(hass)
    unloaded_device = device_registry.async_get_or_create(
        config_entry_id=unloaded_entry.entry_id,
        identifiers={(DOMAIN, "1CCAE3CCCCCC")},
    )

    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_RESTART,
            {ATTR_DEVICE_ID: [unloaded_device.id]},
            blocking=True,
        )

    assert exc_info.value.translation_key == "device_not_found"
    assert doorbird_entry.api.restart.call_count == 0


async def test_restart_validates_all_targets_first(
    hass: HomeAssistant,
    doorbird_mocker: DoorbirdMockerType,
) -> None:
    """Test that no device is restarted when any target is invalid."""
    doorbird_entry = await doorbird_mocker()
    device_id = _get_device_id(hass)

    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_RESTART,
            {ATTR_DEVICE_ID: [device_id, "not_a_real_device_id"]},
            blocking=True,
        )

    assert exc_info.value.translation_key == "device_not_found"
    assert doorbird_entry.api.restart.call_count == 0


@pytest.mark.parametrize(
    ("return_value", "side_effect"),
    [
        (False, None),
        (True, aiohttp.ClientError("connection failed")),
        (True, TimeoutError),
    ],
    ids=["api_returns_false", "client_error", "timeout"],
)
async def test_restart_failure(
    hass: HomeAssistant,
    doorbird_mocker: DoorbirdMockerType,
    return_value: bool,
    side_effect: Exception | type[Exception] | None,
) -> None:
    """Test that a failed restart is reported to the caller."""
    doorbird_entry = await doorbird_mocker()
    device_id = _get_device_id(hass)
    doorbird_entry.api.restart.return_value = return_value
    doorbird_entry.api.restart.side_effect = side_effect

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_RESTART,
            {ATTR_DEVICE_ID: [device_id]},
            blocking=True,
        )

    assert exc_info.value.translation_key == "restart_failed"
    assert exc_info.value.translation_placeholders == {"name": "mydoorbird"}
    assert doorbird_entry.api.restart.call_count == 1
