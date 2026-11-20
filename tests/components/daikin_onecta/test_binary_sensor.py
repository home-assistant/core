"""Tests for Daikin binary sensors."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from daikin_onecta.models import Characteristic
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.daikin_onecta.binary_sensor import (
    async_setup_entry as async_setup_binary_sensors,
)
from homeassistant.components.daikin_onecta.const import DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .platform_helpers import _async_setup_fixture, _load_gateway_devices


async def test_unknown_characteristic_is_skipped(hass: HomeAssistant) -> None:
    """Do not create untranslated binary sensors for unknown values."""
    management_point = SimpleNamespace(
        embedded_id="point",
        management_point_type="climateControl",
        air_purification=None,
        scalar_characteristics=lambda: {
            "futureCharacteristic": Characteristic(value=True)
        },
    )
    device = SimpleNamespace(
        device=SimpleNamespace(management_points=[management_point]),
        present_in_cloud=True,
    )
    coordinator = SimpleNamespace(
        data={"gateway": device},
        cloud_update_sequence=1,
        async_add_listener=MagicMock(return_value=MagicMock()),
    )
    config_entry = SimpleNamespace(
        runtime_data=coordinator, async_on_unload=MagicMock()
    )
    async_add_entities = MagicMock()

    await async_setup_binary_sensors(hass, config_entry, async_add_entities)

    async_add_entities.assert_not_called()


@pytest.mark.parametrize(
    ("fixture", "value", "initial_value", "updated_value"),
    [
        ("altherma", "dryKeepSetting", "on", "off"),
    ],
)
async def test_read_only_on_off_characteristics_are_binary_sensors(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    fixture: str,
    value: str,
    initial_value: str,
    updated_value: str,
) -> None:
    """Expose read-only string-valued binary characteristics as binary sensors."""
    await _async_setup_fixture(hass, config_entry, fixture)
    coordinator = config_entry.runtime_data
    device, point, characteristic = next(
        (device, point, characteristic)
        for device in coordinator.data.values()
        for point in device.device.management_points
        if (characteristic := point.scalar_characteristic(value)) is not None
        and not characteristic.settable
        and set(characteristic.values or []) == {"on", "off"}
    )
    unique_id = f"{device.id}_{point.embedded_id}_{value}"
    entity_id = entity_registry.async_get_entity_id(
        Platform.BINARY_SENSOR, DOMAIN, unique_id
    )

    assert entity_id is not None
    assert entity_registry.async_get_entity_id(SENSOR_DOMAIN, DOMAIN, unique_id) is None
    assert characteristic.value == initial_value
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == characteristic.value

    characteristic.value = updated_value
    coordinator.async_update_listeners()
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == updated_value


async def test_read_only_on_off_led_is_not_duplicated_as_sensor(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Expose read-only LED state only as a binary sensor."""
    devices = _load_gateway_devices("minimal_data")
    device = devices[0]
    point = device.management_points_by_type("climateControl")[0]
    point.characteristics["ledEnabled"] = Characteristic(
        value="off", settable=False, values=["on", "off"]
    )

    with patch(
        "tests.components.daikin_onecta.platform_helpers._load_gateway_devices",
        return_value=devices,
    ):
        await _async_setup_fixture(hass, config_entry, "minimal_data")

    unique_id = f"{device.id}_{point.embedded_id}_ledEnabled"
    binary_sensor_id = entity_registry.async_get_entity_id(
        Platform.BINARY_SENSOR, DOMAIN, unique_id
    )
    assert binary_sensor_id is not None
    assert entity_registry.async_get_entity_id(SENSOR_DOMAIN, DOMAIN, unique_id) is None
    state = hass.states.get(binary_sensor_id)
    assert state is not None
    assert state.state == "off"
