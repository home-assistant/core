"""The tests for the Binary sensor component."""

from collections.abc import Generator
from unittest import mock

import pytest

from homeassistant.components import binary_sensor
from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.binary_sensor.device_condition import ENTITY_CONDITIONS
from homeassistant.components.binary_sensor.device_trigger import ENTITY_TRIGGERS
from homeassistant.config_entries import ConfigEntry, ConfigFlow
from homeassistant.const import STATE_OFF, STATE_ON, EntityCategory, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .common import MockBinarySensor

from tests.common import (
    MockConfigEntry,
    MockModule,
    MockPlatform,
    mock_config_flow,
    mock_integration,
    mock_platform,
)

TEST_DOMAIN = "test"


def test_state() -> None:
    """Test binary sensor state."""
    sensor = binary_sensor.BinarySensorEntity()
    assert sensor.state is None
    with mock.patch(
        "homeassistant.components.binary_sensor.BinarySensorEntity.is_on",
        new=False,
    ):
        assert binary_sensor.BinarySensorEntity().state == STATE_OFF
    with mock.patch(
        "homeassistant.components.binary_sensor.BinarySensorEntity.is_on",
        new=True,
    ):
        assert binary_sensor.BinarySensorEntity().state == STATE_ON


class MockFlow(ConfigFlow):
    """Test flow."""


@pytest.fixture(autouse=True)
def config_flow_fixture(hass: HomeAssistant) -> Generator[None]:
    """Mock config flow."""
    mock_platform(hass, f"{TEST_DOMAIN}.config_flow")

    with mock_config_flow(TEST_DOMAIN, MockFlow):
        yield


async def test_name(hass: HomeAssistant) -> None:
    """Test binary sensor name."""

    async def async_setup_entry_init(
        hass: HomeAssistant, config_entry: ConfigEntry
    ) -> bool:
        """Set up test config entry."""
        await hass.config_entries.async_forward_entry_setups(
            config_entry, [Platform.BINARY_SENSOR]
        )
        return True

    mock_platform(hass, f"{TEST_DOMAIN}.config_flow")
    mock_integration(
        hass,
        MockModule(
            TEST_DOMAIN,
            async_setup_entry=async_setup_entry_init,
        ),
    )

    # Unnamed binary sensor without device class -> no name
    entity1 = binary_sensor.BinarySensorEntity()
    entity1.entity_id = "binary_sensor.test1"

    # Unnamed binary sensor with device class but has_entity_name False -> no name
    entity2 = binary_sensor.BinarySensorEntity()
    entity2.entity_id = "binary_sensor.test2"
    entity2._attr_device_class = binary_sensor.BinarySensorDeviceClass.BATTERY

    # Unnamed binary sensor with device class and has_entity_name True -> named
    entity3 = binary_sensor.BinarySensorEntity()
    entity3.entity_id = "binary_sensor.test3"
    entity3._attr_device_class = binary_sensor.BinarySensorDeviceClass.BATTERY
    entity3._attr_has_entity_name = True

    # Unnamed binary sensor with device class and has_entity_name True -> named
    entity4 = binary_sensor.BinarySensorEntity()
    entity4.entity_id = "binary_sensor.test4"
    entity4.entity_description = binary_sensor.BinarySensorEntityDescription(
        "test",
        binary_sensor.BinarySensorDeviceClass.BATTERY,
        has_entity_name=True,
    )

    async def async_setup_entry_platform(
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        async_add_entities: AddConfigEntryEntitiesCallback,
    ) -> None:
        """Set up test binary_sensor platform via config entry."""
        async_add_entities([entity1, entity2, entity3, entity4])

    mock_platform(
        hass,
        f"{TEST_DOMAIN}.{binary_sensor.DOMAIN}",
        MockPlatform(async_setup_entry=async_setup_entry_platform),
    )

    config_entry = MockConfigEntry(domain=TEST_DOMAIN)
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(entity1.entity_id)
    assert state.attributes == {}

    state = hass.states.get(entity2.entity_id)
    assert state.attributes == {"device_class": "battery"}

    state = hass.states.get(entity3.entity_id)
    assert state.attributes == {"device_class": "battery", "friendly_name": "Battery"}

    state = hass.states.get(entity4.entity_id)
    assert state.attributes == {"device_class": "battery", "friendly_name": "Battery"}


async def test_entity_category_config_raises_error(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test error is raised when entity category is set to config."""

    async def async_setup_entry_init(
        hass: HomeAssistant, config_entry: ConfigEntry
    ) -> bool:
        """Set up test config entry."""
        await hass.config_entries.async_forward_entry_setups(
            config_entry, [Platform.BINARY_SENSOR]
        )
        return True

    mock_platform(hass, f"{TEST_DOMAIN}.config_flow")
    mock_integration(
        hass,
        MockModule(
            TEST_DOMAIN,
            async_setup_entry=async_setup_entry_init,
        ),
    )

    description1 = binary_sensor.BinarySensorEntityDescription(
        "diagnostic", entity_category=EntityCategory.DIAGNOSTIC
    )
    entity1 = MockBinarySensor()
    entity1.entity_description = description1
    entity1.entity_id = "binary_sensor.test1"

    description2 = binary_sensor.BinarySensorEntityDescription(
        "config", entity_category=EntityCategory.CONFIG
    )
    entity2 = MockBinarySensor()
    entity2.entity_description = description2
    entity2.entity_id = "binary_sensor.test2"

    async def async_setup_entry_platform(
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        async_add_entities: AddConfigEntryEntitiesCallback,
    ) -> None:
        """Set up test binary_sensor platform via config entry."""
        async_add_entities([entity1, entity2])

    mock_platform(
        hass,
        f"{TEST_DOMAIN}.{binary_sensor.DOMAIN}",
        MockPlatform(async_setup_entry=async_setup_entry_platform),
    )

    config_entry = MockConfigEntry(domain=TEST_DOMAIN)
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    state1 = hass.states.get("binary_sensor.test1")
    assert state1 is not None
    state2 = hass.states.get("binary_sensor.test2")
    assert state2 is None
    assert (
        "Entity binary_sensor.test2 cannot be added as the"
        " entity category is set to config" in caplog.text
    )


def test_glass_break_device_class() -> None:
    """Test glass break device class enum value and automation mappings."""
    assert BinarySensorDeviceClass.GLASS_BREAK == "glass_break"
    assert BinarySensorDeviceClass.GLASS_BREAK in ENTITY_CONDITIONS
    assert BinarySensorDeviceClass.GLASS_BREAK in ENTITY_TRIGGERS
    conditions = ENTITY_CONDITIONS[BinarySensorDeviceClass.GLASS_BREAK]
    assert len(conditions) == 2
    condition_types = {c["type"] for c in conditions}
    assert condition_types == {"is_glass_break", "is_no_glass_break"}
    triggers = ENTITY_TRIGGERS[BinarySensorDeviceClass.GLASS_BREAK]
    assert len(triggers) == 2
    trigger_types = {t["type"] for t in triggers}
    assert trigger_types == {"glass_break", "no_glass_break"}


async def test_glass_break_entity_state(hass: HomeAssistant) -> None:
    """Test a glass break binary sensor reports the correct state and attributes."""

    async def async_setup_entry_init(
        hass: HomeAssistant, config_entry: ConfigEntry
    ) -> bool:
        """Set up test config entry."""
        await hass.config_entries.async_forward_entry_setups(
            config_entry, [Platform.BINARY_SENSOR]
        )
        return True

    mock_platform(hass, f"{TEST_DOMAIN}.config_flow")
    mock_integration(
        hass,
        MockModule(
            TEST_DOMAIN,
            async_setup_entry=async_setup_entry_init,
        ),
    )

    entity = binary_sensor.BinarySensorEntity()
    entity.entity_id = "binary_sensor.glass_break_1"
    entity._attr_device_class = BinarySensorDeviceClass.GLASS_BREAK
    entity._attr_is_on = True

    async def async_setup_entry_platform(
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        async_add_entities: AddConfigEntryEntitiesCallback,
    ) -> None:
        """Set up test binary_sensor platform via config entry."""
        async_add_entities([entity])

    mock_platform(
        hass,
        f"{TEST_DOMAIN}.{binary_sensor.DOMAIN}",
        MockPlatform(async_setup_entry=async_setup_entry_platform),
    )

    config_entry = MockConfigEntry(domain=TEST_DOMAIN)
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.glass_break_1")
    assert state.state == STATE_ON
    assert state.attributes["device_class"] == "glass_break"
