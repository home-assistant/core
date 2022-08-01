"""The tests for the xiaomi_miio select component."""

import enum
import logging

from arrow import utcnow
import pytest

from homeassistant.components.asuswrt.router import KEY_COORDINATOR
from homeassistant.components.select.const import (
    ATTR_OPTION,
    ATTR_OPTIONS,
    SERVICE_SELECT_OPTION,
)
from homeassistant.components.xiaomi_miio import (
    UPDATE_INTERVAL,
    _async_update_data_default,
)
from homeassistant.components.xiaomi_miio.const import (
    CONF_DEVICE,
    CONF_FLOW_TYPE,
    CONF_MAC,
    DOMAIN,
    KEY_DEVICE,
)
from homeassistant.components.xiaomi_miio.select import (
    MODEL_TO_ATTR_MAP,
    SELECTOR_TYPES,
    AttributeEnumMapping,
    XiaomiMiioSelectDescription,
)
from homeassistant.const import ATTR_ENTITY_ID, CONF_MODEL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from tests.common import MockConfigEntry, async_fire_time_changed
from tests.components.xiaomi_miio import TEST_MAC

_LOGGER = logging.getLogger(__name__)


class DummyEnum_0(enum.Enum):
    """Enum to test auto naming."""

    Option_0 = 0
    Option_1 = 1


class DummyEnum_1(enum.Enum):
    """Enum to test predefined naming."""

    BadName_0 = 0
    BadName_1 = 1


class DummySelectStatus:
    """Dummy device status."""

    def __init__(self):
        """Initialize the dummy device status."""
        self.dummy = DummyEnum_0.Option_1
        self.bad_name = DummyEnum_1.BadName_1


class DummySelectDevice:
    """Dummy device."""

    def __init__(self, model, *args, **kwargs):
        """Initialize the dummy device."""
        self.data = DummySelectStatus()

    def status(self):
        """Retrieve properties."""
        return self.data

    def set_dummy_value(self, value: DummyEnum_0):
        """Set dummy enum value."""
        self.data.dummy = value
        return True

    def set_bad_name_value(self, value: DummyEnum_1):
        """Set bad name enum value."""
        self.data.bad_name = value
        return True


@pytest.fixture(autouse=True)
async def setup_select(hass: HomeAssistant):
    """Initialize setup xiaomi_miio airhumidifier select entity."""

    dummy_device = DummySelectDevice("Dummy")

    MODEL_TO_ATTR_MAP["Dummy"] = [
        AttributeEnumMapping("dummy", DummyEnum_0),
        AttributeEnumMapping("bad_name", DummyEnum_1),
    ]
    SELECTOR_TYPES.append(
        XiaomiMiioSelectDescription(
            key="dummy",
            attr_name="dummy",
            name="Dummy",
            set_method="set_dummy_value",
            set_method_error_message="Set dummy value failed.",
            options=("option_0", "option_1"),
        )
    )
    SELECTOR_TYPES.append(
        XiaomiMiioSelectDescription(
            key="bad_name",
            attr_name="bad_name",
            name="Bad Name",
            options_map={
                "BadName_0": "New_0",
                "BadName_1": "New_1",
            },
            set_method="set_bad_name_value",
            set_method_error_message="Set bad name value failed.",
            options=("new_0", "new_1"),
        )
    )

    hass.data.setdefault(DOMAIN, {})

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_FLOW_TYPE: CONF_DEVICE,
            CONF_MODEL: "Dummy",
            CONF_MAC: TEST_MAC,
        },
        title="dummy",
    )
    config_entry.add_to_hass(hass)

    # Create update miio device and coordinator
    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=config_entry.title,
        update_method=_async_update_data_default(hass, dummy_device),
        # Polling interval. Will only be polled if there are subscribers.
        update_interval=UPDATE_INTERVAL,
    )
    hass.data[DOMAIN][config_entry.entry_id] = {
        KEY_DEVICE: dummy_device,
        KEY_COORDINATOR: coordinator,
    }

    # Trigger first data fetch
    await coordinator.async_config_entry_first_refresh()

    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(config_entry, "select")
    )

    await hass.async_block_till_done()

    return dummy_device


def test_select_params(hass: HomeAssistant) -> None:
    """Test the initial parameters."""

    select_entity = hass.states.get("select.dummy_dummy")
    assert select_entity
    assert select_entity.state == "option_1"
    assert select_entity.attributes.get(ATTR_OPTIONS) == ["option_0", "option_1"]

    select_entity = hass.states.get("select.dummy_bad_name")
    assert select_entity
    assert select_entity.state == "new_1"
    assert select_entity.attributes.get(ATTR_OPTIONS) == ["new_0", "new_1"]


async def test_select_bad_attr(hass: HomeAssistant) -> None:
    """Test selecting a different option with invalid option value."""

    state = hass.states.get("select.dummy_dummy")
    assert state
    assert state.state == "option_1"

    with pytest.raises(ValueError):
        await hass.services.async_call(
            "select",
            SERVICE_SELECT_OPTION,
            {ATTR_OPTION: "option_4", ATTR_ENTITY_ID: "select.dummy_dummy"},
            blocking=True,
        )
    await hass.async_block_till_done()

    state = hass.states.get("select.dummy_dummy")
    assert state
    assert state.state == "option_1"


async def test_select_option(hass: HomeAssistant) -> None:
    """Test selecting of a option."""
    state = hass.states.get("select.dummy_dummy")
    assert state
    assert state.state == "option_1"

    await hass.services.async_call(
        "select",
        SERVICE_SELECT_OPTION,
        {ATTR_OPTION: "option_0", ATTR_ENTITY_ID: "select.dummy_dummy"},
        blocking=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get("select.dummy_dummy")
    assert state
    assert state.state == "option_0"


async def test_select_coordinator_update(hass: HomeAssistant, setup_select) -> None:
    """Test coordinator update of a option."""
    state = hass.states.get("select.dummy_dummy")
    assert state
    assert state.state == "option_1"

    # emulate someone change state from device maybe used app
    setup_select.set_dummy_value(DummyEnum_0.Option_0)

    async_fire_time_changed(hass, utcnow() + UPDATE_INTERVAL)
    await hass.async_block_till_done()

    state = hass.states.get("select.dummy_dummy")
    assert state
    assert state.state == "option_0"
