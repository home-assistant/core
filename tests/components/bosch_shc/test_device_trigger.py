"""Tests for Bosch SHC device triggers."""

from unittest.mock import MagicMock

from pytest_unordered import unordered

from homeassistant.components import automation
from homeassistant.components.bosch_shc.const import (
    ALARM_EVENTS_SUBTYPES_SD,
    ALARM_EVENTS_SUBTYPES_SDS,
    ATTR_EVENT_SUBTYPE,
    ATTR_EVENT_TYPE,
    CONF_SUBTYPE,
    DOMAIN,
    EVENT_BOSCH_SHC,
    INPUTS_EVENTS_SUBTYPES_SWITCH2,
    INPUTS_EVENTS_SUBTYPES_WRC2,
)
from homeassistant.components.device_automation import DeviceAutomationType
from homeassistant.const import (
    ATTR_DEVICE_ID,
    CONF_DEVICE_ID,
    CONF_DOMAIN,
    CONF_PLATFORM,
    CONF_TYPE,
)
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import device_registry as dr
from homeassistant.setup import async_setup_component

from .conftest import make_device, setup_integration

from tests.common import MockConfigEntry, async_get_device_automations

# ---------------------------------------------------------------------------
# Module-level fixture: suppress missing automation translation key that arises
# when async_setup_component(hass, automation.DOMAIN, …) is called in tests.
# ---------------------------------------------------------------------------




# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _register_device(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    shc_device: MagicMock,
) -> dr.DeviceEntry:
    """Register a fake SHC device in the HA device registry."""
    device_registry = dr.async_get(hass)
    return device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, shc_device.id)},
        name=shc_device.name,
        manufacturer=shc_device.manufacturer,
        model=shc_device.device_model,
    )


# ---------------------------------------------------------------------------
# async_get_triggers — per device model
# ---------------------------------------------------------------------------


async def test_get_triggers_wrc2(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """async_get_triggers returns press triggers for each WRC2 button."""
    session = mock_setup_dependencies
    shc_device = make_device("wrc2-1", "Wall Remote", device_model="WRC2")
    session.devices = [shc_device]

    await setup_integration(hass, mock_config_entry)

    dr_entry = _register_device(hass, mock_config_entry, shc_device)
    device_id = dr_entry.id

    triggers = await async_get_device_automations(
        hass, DeviceAutomationType.TRIGGER, device_id
    )

    expected_types = {"PRESS_SHORT", "PRESS_LONG", "PRESS_LONG_RELEASED"}
    expected_subtypes = set(INPUTS_EVENTS_SUBTYPES_WRC2)

    assert triggers is not None
    assert len(triggers) == len(expected_types) * len(expected_subtypes)

    for trigger in triggers:
        assert trigger[CONF_PLATFORM] == "device"
        assert trigger[CONF_DEVICE_ID] == device_id
        assert trigger[CONF_DOMAIN] == DOMAIN
        assert trigger[CONF_TYPE] in expected_types
        assert trigger[CONF_SUBTYPE] in expected_subtypes


async def test_get_triggers_switch2(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """async_get_triggers returns press triggers for each SWITCH2 button."""
    session = mock_setup_dependencies
    shc_device = make_device("switch2-1", "Wall Switch", device_model="SWITCH2")
    session.devices = [shc_device]

    await setup_integration(hass, mock_config_entry)

    dr_entry = _register_device(hass, mock_config_entry, shc_device)
    device_id = dr_entry.id

    triggers = await async_get_device_automations(
        hass, DeviceAutomationType.TRIGGER, device_id
    )

    expected_types = {"PRESS_SHORT", "PRESS_LONG", "PRESS_LONG_RELEASED"}
    expected_subtypes = set(INPUTS_EVENTS_SUBTYPES_SWITCH2)

    assert triggers is not None
    assert len(triggers) == len(expected_types) * len(expected_subtypes)

    for trigger in triggers:
        assert trigger[CONF_PLATFORM] == "device"
        assert trigger[CONF_DEVICE_ID] == device_id
        assert trigger[CONF_DOMAIN] == DOMAIN
        assert trigger[CONF_TYPE] in expected_types
        assert trigger[CONF_SUBTYPE] in expected_subtypes


async def test_get_triggers_motion_detector(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """async_get_triggers returns a MOTION trigger for an MD device."""
    session = mock_setup_dependencies
    shc_device = make_device("md-1", "Motion Detector", device_model="MD")
    session.devices = [shc_device]

    await setup_integration(hass, mock_config_entry)

    dr_entry = _register_device(hass, mock_config_entry, shc_device)
    device_id = dr_entry.id

    triggers = await async_get_device_automations(
        hass, DeviceAutomationType.TRIGGER, device_id
    )

    assert triggers == [
        {
            CONF_PLATFORM: "device",
            CONF_DEVICE_ID: device_id,
            CONF_DOMAIN: DOMAIN,
            CONF_TYPE: "MOTION",
            CONF_SUBTYPE: "",
            "metadata": {},
        }
    ]


async def test_get_triggers_smoke_detector(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """async_get_triggers returns ALARM triggers for an SD device."""
    session = mock_setup_dependencies
    shc_device = make_device("sd-1", "Smoke Detector", device_model="SD")
    session.devices = [shc_device]

    await setup_integration(hass, mock_config_entry)

    dr_entry = _register_device(hass, mock_config_entry, shc_device)
    device_id = dr_entry.id

    triggers = await async_get_device_automations(
        hass, DeviceAutomationType.TRIGGER, device_id
    )

    expected = unordered(
        [
            {
                CONF_PLATFORM: "device",
                CONF_DEVICE_ID: device_id,
                CONF_DOMAIN: DOMAIN,
                CONF_TYPE: "ALARM",
                CONF_SUBTYPE: subtype,
                "metadata": {},
            }
            for subtype in ALARM_EVENTS_SUBTYPES_SD
        ]
    )
    assert triggers == expected


async def test_get_triggers_smoke_detection_system(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """async_get_triggers returns ALARM triggers for a SMOKE_DETECTION_SYSTEM device."""
    session = mock_setup_dependencies
    shc_device = make_device(
        "sds-1", "Smoke Detection System", device_model="SMOKE_DETECTION_SYSTEM"
    )
    session.devices = [shc_device]

    await setup_integration(hass, mock_config_entry)

    dr_entry = _register_device(hass, mock_config_entry, shc_device)
    device_id = dr_entry.id

    triggers = await async_get_device_automations(
        hass, DeviceAutomationType.TRIGGER, device_id
    )

    expected = unordered(
        [
            {
                CONF_PLATFORM: "device",
                CONF_DEVICE_ID: device_id,
                CONF_DOMAIN: DOMAIN,
                CONF_TYPE: "ALARM",
                CONF_SUBTYPE: subtype,
                "metadata": {},
            }
            for subtype in ALARM_EVENTS_SUBTYPES_SDS
        ]
    )
    assert triggers == expected


async def test_get_triggers_shc_scenario(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """async_get_triggers returns SCENARIO triggers from session.scenario_names for SHC."""
    session = mock_setup_dependencies
    # The SHC controller device uses identifiers=(DOMAIN, session.information.unique_id)
    # and device_model "SHC" is returned by get_device_from_id for the controller.
    # Populate scenario_names on the session mock so the trigger loop has items.
    session.scenario_names = ["Good Night", "Wake Up"]

    await setup_integration(hass, mock_config_entry)

    # The SHC controller device is registered during integration setup.
    device_registry = dr.async_get(hass)
    shc_device_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, "test-mac")}
    )
    assert shc_device_entry is not None
    device_id = shc_device_entry.id

    triggers = await async_get_device_automations(
        hass, DeviceAutomationType.TRIGGER, device_id
    )

    assert triggers == unordered(
        [
            {
                CONF_PLATFORM: "device",
                CONF_DEVICE_ID: device_id,
                CONF_DOMAIN: DOMAIN,
                CONF_TYPE: "SCENARIO",
                CONF_SUBTYPE: "Good Night",
                "metadata": {},
            },
            {
                CONF_PLATFORM: "device",
                CONF_DEVICE_ID: device_id,
                CONF_DOMAIN: DOMAIN,
                CONF_TYPE: "SCENARIO",
                CONF_SUBTYPE: "Wake Up",
                "metadata": {},
            },
        ]
    )


async def test_get_triggers_unknown_model_returns_empty(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """async_get_triggers returns empty list for unrecognised device model."""
    session = mock_setup_dependencies
    shc_device = make_device("unknown-1", "Unknown Device", device_model="UNKNOWN_MODEL")
    session.devices = [shc_device]

    await setup_integration(hass, mock_config_entry)

    dr_entry = _register_device(hass, mock_config_entry, shc_device)
    device_id = dr_entry.id

    triggers = await async_get_device_automations(
        hass, DeviceAutomationType.TRIGGER, device_id
    )

    assert triggers == []


# ---------------------------------------------------------------------------
# async_attach_trigger — event firing
# ---------------------------------------------------------------------------


async def test_attach_trigger_wrc2_fires_on_matching_event(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
    service_calls: list[ServiceCall],
) -> None:
    """Automation fires when a matching EVENT_BOSCH_SHC bus event is published."""
    session = mock_setup_dependencies
    shc_device = make_device("wrc2-fire", "Fire Switch", device_model="WRC2")
    session.devices = [shc_device]

    await setup_integration(hass, mock_config_entry)

    dr_entry = _register_device(hass, mock_config_entry, shc_device)
    device_id = dr_entry.id

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        CONF_PLATFORM: "device",
                        CONF_DOMAIN: DOMAIN,
                        CONF_DEVICE_ID: device_id,
                        CONF_TYPE: "PRESS_SHORT",
                        CONF_SUBTYPE: "UPPER_BUTTON",
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {"some": "wrc2_press_short"},
                    },
                }
            ]
        },
    )

    # Fire a matching event.
    hass.bus.async_fire(
        EVENT_BOSCH_SHC,
        {
            ATTR_DEVICE_ID: device_id,
            ATTR_EVENT_TYPE: "PRESS_SHORT",
            ATTR_EVENT_SUBTYPE: "UPPER_BUTTON",
        },
    )
    await hass.async_block_till_done()

    assert len(service_calls) == 1
    assert service_calls[0].data["some"] == "wrc2_press_short"


async def test_attach_trigger_does_not_fire_on_wrong_subtype(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
    service_calls: list[ServiceCall],
) -> None:
    """Automation does NOT fire when event subtype does not match."""
    session = mock_setup_dependencies
    shc_device = make_device("wrc2-mismatch", "Mismatch Switch", device_model="WRC2")
    session.devices = [shc_device]

    await setup_integration(hass, mock_config_entry)

    dr_entry = _register_device(hass, mock_config_entry, shc_device)
    device_id = dr_entry.id

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        CONF_PLATFORM: "device",
                        CONF_DOMAIN: DOMAIN,
                        CONF_DEVICE_ID: device_id,
                        CONF_TYPE: "PRESS_SHORT",
                        CONF_SUBTYPE: "UPPER_BUTTON",
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {"some": "should_not_fire"},
                    },
                }
            ]
        },
    )

    # Fire an event with the wrong subtype.
    hass.bus.async_fire(
        EVENT_BOSCH_SHC,
        {
            ATTR_DEVICE_ID: device_id,
            ATTR_EVENT_TYPE: "PRESS_SHORT",
            ATTR_EVENT_SUBTYPE: "LOWER_BUTTON",  # wrong subtype
        },
    )
    await hass.async_block_till_done()

    assert len(service_calls) == 0


async def test_attach_trigger_motion_fires_on_matching_event(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
    service_calls: list[ServiceCall],
) -> None:
    """Automation fires when a MOTION EVENT_BOSCH_SHC bus event is published."""
    session = mock_setup_dependencies
    shc_device = make_device("md-fire", "Motion Sensor", device_model="MD")
    session.devices = [shc_device]

    await setup_integration(hass, mock_config_entry)

    dr_entry = _register_device(hass, mock_config_entry, shc_device)
    device_id = dr_entry.id

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        CONF_PLATFORM: "device",
                        CONF_DOMAIN: DOMAIN,
                        CONF_DEVICE_ID: device_id,
                        CONF_TYPE: "MOTION",
                        CONF_SUBTYPE: "",
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {"some": "motion_triggered"},
                    },
                }
            ]
        },
    )

    hass.bus.async_fire(
        EVENT_BOSCH_SHC,
        {
            ATTR_DEVICE_ID: device_id,
            ATTR_EVENT_TYPE: "MOTION",
            ATTR_EVENT_SUBTYPE: "",
        },
    )
    await hass.async_block_till_done()

    assert len(service_calls) == 1
    assert service_calls[0].data["some"] == "motion_triggered"


async def test_attach_trigger_alarm_fires_on_matching_event(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
    service_calls: list[ServiceCall],
) -> None:
    """Automation fires when an ALARM EVENT_BOSCH_SHC bus event is published."""
    session = mock_setup_dependencies
    shc_device = make_device("sd-fire", "Smoke Detector", device_model="SD")
    session.devices = [shc_device]

    await setup_integration(hass, mock_config_entry)

    dr_entry = _register_device(hass, mock_config_entry, shc_device)
    device_id = dr_entry.id

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        CONF_PLATFORM: "device",
                        CONF_DOMAIN: DOMAIN,
                        CONF_DEVICE_ID: device_id,
                        CONF_TYPE: "ALARM",
                        CONF_SUBTYPE: "INTRUSION_ALARM",
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {"some": "alarm_triggered"},
                    },
                }
            ]
        },
    )

    hass.bus.async_fire(
        EVENT_BOSCH_SHC,
        {
            ATTR_DEVICE_ID: device_id,
            ATTR_EVENT_TYPE: "ALARM",
            ATTR_EVENT_SUBTYPE: "INTRUSION_ALARM",
        },
    )
    await hass.async_block_till_done()

    assert len(service_calls) == 1
    assert service_calls[0].data["some"] == "alarm_triggered"
