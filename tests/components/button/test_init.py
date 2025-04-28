"""The tests for the Button component."""

from collections.abc import Generator
from datetime import timedelta
from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.button import (
    DOMAIN,
    SERVICE_PRESS,
    ButtonDeviceClass,
    ButtonEntity,
    ButtonEntityDescription,
)
from homeassistant.config_entries import ConfigEntry, ConfigFlow
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_PLATFORM,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from .const import TEST_DOMAIN

from tests.common import (
    MockConfigEntry,
    MockModule,
    MockPlatform,
    mock_config_flow,
    mock_integration,
    mock_platform,
    mock_restore_cache,
)


async def test_button(hass: HomeAssistant) -> None:
    """Test getting data from the mocked button entity."""
    button = ButtonEntity()
    assert button.state is None

    button.hass = hass

    with pytest.raises(NotImplementedError):
        await button.async_press()

    button.press = MagicMock()
    await button.async_press()

    assert button.press.called


@pytest.mark.usefixtures("enable_custom_integrations", "setup_platform")
async def test_custom_integration(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test we integration."""
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {CONF_PLATFORM: "test"}})
    await hass.async_block_till_done()

    assert hass.states.get("button.button_1").state == STATE_UNKNOWN

    now = dt_util.utcnow()
    await hass.services.async_call(
        DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: "button.button_1"},
        blocking=True,
    )

    assert hass.states.get("button.button_1").state == now.isoformat()
    assert "The button has been pressed" in caplog.text

    now_isoformat = dt_util.utcnow().isoformat()
    assert hass.states.get("button.button_1").state == now_isoformat

    new_time = dt_util.utcnow() + timedelta(weeks=1)
    freezer.move_to(new_time)
    await hass.services.async_call(
        DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: "button.button_1"},
        blocking=True,
    )

    new_time_isoformat = new_time.isoformat()
    assert hass.states.get("button.button_1").state == new_time_isoformat


@pytest.mark.usefixtures("enable_custom_integrations", "setup_platform")
async def test_restore_state(hass: HomeAssistant) -> None:
    """Test we restore state integration."""
    mock_restore_cache(hass, (State("button.button_1", "2021-01-01T23:59:59+00:00"),))

    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {CONF_PLATFORM: "test"}})
    await hass.async_block_till_done()

    assert hass.states.get("button.button_1").state == "2021-01-01T23:59:59+00:00"


@pytest.mark.usefixtures("enable_custom_integrations", "setup_platform")
async def test_restore_state_does_not_restore_unavailable(hass: HomeAssistant) -> None:
    """Test we restore state integration except for unavailable."""
    mock_restore_cache(hass, (State("button.button_1", STATE_UNAVAILABLE),))

    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {CONF_PLATFORM: "test"}})
    await hass.async_block_till_done()

    assert hass.states.get("button.button_1").state == STATE_UNKNOWN


class MockFlow(ConfigFlow):
    """Test flow."""


@pytest.fixture(autouse=True)
def config_flow_fixture(hass: HomeAssistant) -> Generator[None]:
    """Mock config flow."""
    mock_platform(hass, f"{TEST_DOMAIN}.config_flow")

    with mock_config_flow(TEST_DOMAIN, MockFlow):
        yield


async def test_name(hass: HomeAssistant) -> None:
    """Test button name."""

    async def async_setup_entry_init(
        hass: HomeAssistant, config_entry: ConfigEntry
    ) -> bool:
        """Set up test config entry."""
        await hass.config_entries.async_forward_entry_setups(config_entry, [DOMAIN])
        return True

    mock_platform(hass, f"{TEST_DOMAIN}.config_flow")
    mock_integration(
        hass,
        MockModule(
            TEST_DOMAIN,
            async_setup_entry=async_setup_entry_init,
        ),
    )

    # Unnamed button without device class -> no name
    entity1 = ButtonEntity()
    entity1.entity_id = "button.test1"

    # Unnamed button with device class but has_entity_name False -> no name
    entity2 = ButtonEntity()
    entity2.entity_id = "button.test2"
    entity2._attr_device_class = ButtonDeviceClass.RESTART

    # Unnamed button with device class and has_entity_name True -> named
    entity3 = ButtonEntity()
    entity3.entity_id = "button.test3"
    entity3._attr_device_class = ButtonDeviceClass.RESTART
    entity3._attr_has_entity_name = True

    # Unnamed button with device class and has_entity_name True -> named
    entity4 = ButtonEntity()
    entity4.entity_id = "sensor.test4"
    entity4.entity_description = ButtonEntityDescription(
        "test",
        ButtonDeviceClass.RESTART,
        has_entity_name=True,
    )

    async def async_setup_entry_platform(
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        async_add_entities: AddConfigEntryEntitiesCallback,
    ) -> None:
        """Set up test button platform via config entry."""
        async_add_entities([entity1, entity2, entity3, entity4])

    mock_platform(
        hass,
        f"{TEST_DOMAIN}.{DOMAIN}",
        MockPlatform(async_setup_entry=async_setup_entry_platform),
    )

    config_entry = MockConfigEntry(domain=TEST_DOMAIN)
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(entity1.entity_id)
    assert state
    assert state.attributes == {}

    state = hass.states.get(entity2.entity_id)
    assert state
    assert state.attributes == {"device_class": "restart"}

    state = hass.states.get(entity3.entity_id)
    assert state
    assert state.attributes == {"device_class": "restart", "friendly_name": "Restart"}

    state = hass.states.get(entity4.entity_id)
    assert state
    assert state.attributes == {"device_class": "restart", "friendly_name": "Restart"}
