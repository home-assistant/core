"""Tests for the Bosch SHC logbook describer."""

from unittest.mock import MagicMock

from homeassistant.components import logbook
from homeassistant.components.bosch_shc.const import (
    ATTR_EVENT_SUBTYPE,
    ATTR_EVENT_TYPE,
    DOMAIN,
    EVENT_BOSCH_SHC,
)
from homeassistant.components.bosch_shc.logbook import async_describe_events
from homeassistant.components.logbook.models import LogbookConfig
from homeassistant.const import ATTR_NAME
from homeassistant.core import Event, HomeAssistant

from .conftest import setup_integration

from tests.common import MockConfigEntry
from tests.components.logbook.common import MockRow, mock_humanify

# ---------------------------------------------------------------------------
# Helper — wire the describer into a fake LogbookConfig on hass.data
# ---------------------------------------------------------------------------


def _setup_logbook_external_events(hass: HomeAssistant) -> None:
    """Register bosch_shc logbook describer without loading the logbook component.

    async_setup_component(hass, "logbook", {}) fails in this test environment
    because the ``frontend`` dependency is not installed.  Instead, we
    manually create a LogbookConfig and call async_describe_events directly so
    that mock_humanify can find the describer in external_events.
    """
    external_events: dict = {}
    hass.data[logbook.DOMAIN] = LogbookConfig(external_events, None, None)

    def _async_describe_event(domain, event_name, describe_callback):
        external_events[event_name] = (domain, describe_callback)

    async_describe_events(hass, _async_describe_event)


# ---------------------------------------------------------------------------
# Direct-callback tests — no recorder / logbook component needed
# ---------------------------------------------------------------------------


async def test_async_describe_events_motion(hass: HomeAssistant) -> None:
    """async_describe_bosch_shc_event returns correct dict for MOTION events."""
    captured_describer = None

    def _capture(domain, event_type, describer_fn):
        nonlocal captured_describer
        assert domain == DOMAIN
        assert event_type == EVENT_BOSCH_SHC
        captured_describer = describer_fn

    async_describe_events(hass, _capture)
    assert captured_describer is not None

    event = Event(
        EVENT_BOSCH_SHC,
        data={
            ATTR_NAME: "Front Door Sensor",
            ATTR_EVENT_TYPE: "MOTION",
            ATTR_EVENT_SUBTYPE: "",
        },
    )
    result = captured_describer(event)
    assert result["name"] == "Bosch SHC"
    assert result["message"] == "'Front Door Sensor' motion event was fired."


async def test_async_describe_events_alarm(hass: HomeAssistant) -> None:
    """async_describe_bosch_shc_event returns correct dict for ALARM events."""
    captured_describer = None

    def _capture(domain, event_type, describer_fn):
        nonlocal captured_describer
        captured_describer = describer_fn

    async_describe_events(hass, _capture)
    assert captured_describer is not None

    event = Event(
        EVENT_BOSCH_SHC,
        data={
            ATTR_NAME: "Smoke Detector",
            ATTR_EVENT_TYPE: "ALARM",
            ATTR_EVENT_SUBTYPE: "INTRUSION_ALARM",
        },
    )
    result = captured_describer(event)
    assert result["name"] == "Bosch SHC"
    assert result["message"] == (
        "'Smoke Detector' alarm event 'INTRUSION_ALARM' was fired."
    )


async def test_async_describe_events_scenario(hass: HomeAssistant) -> None:
    """async_describe_bosch_shc_event returns correct dict for SCENARIO events."""
    captured_describer = None

    def _capture(domain, event_type, describer_fn):
        nonlocal captured_describer
        captured_describer = describer_fn

    async_describe_events(hass, _capture)
    assert captured_describer is not None

    event = Event(
        EVENT_BOSCH_SHC,
        data={
            ATTR_NAME: "Scenario Controller",
            ATTR_EVENT_TYPE: "SCENARIO",
            ATTR_EVENT_SUBTYPE: "good_night",
        },
    )
    result = captured_describer(event)
    assert result["name"] == "Bosch SHC"
    assert result["message"] == "'Scenario Controller' scenario trigger event was fired."


async def test_async_describe_events_button_default(hass: HomeAssistant) -> None:
    """async_describe_bosch_shc_event returns correct dict for button click events."""
    captured_describer = None

    def _capture(domain, event_type, describer_fn):
        nonlocal captured_describer
        captured_describer = describer_fn

    async_describe_events(hass, _capture)
    assert captured_describer is not None

    event = Event(
        EVENT_BOSCH_SHC,
        data={
            ATTR_NAME: "Wall Switch",
            ATTR_EVENT_TYPE: "PRESS_SHORT",
            ATTR_EVENT_SUBTYPE: "UPPER_BUTTON",
        },
    )
    result = captured_describer(event)
    assert result["name"] == "Bosch SHC"
    assert result["message"] == (
        "'PRESS_SHORT' click event for Wall Switch button 'UPPER_BUTTON' was fired."
    )


# ---------------------------------------------------------------------------
# mock_humanify tests — exercise the full logbook pipeline
# ---------------------------------------------------------------------------


async def test_humanify_bosch_shc_motion_event(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """Logbook pipeline humanifies a MOTION event correctly."""
    await setup_integration(hass, mock_config_entry)
    _setup_logbook_external_events(hass)

    (event,) = mock_humanify(
        hass,
        [
            MockRow(
                EVENT_BOSCH_SHC,
                {
                    ATTR_NAME: "Hall Sensor",
                    ATTR_EVENT_TYPE: "MOTION",
                    ATTR_EVENT_SUBTYPE: "",
                },
            )
        ],
    )

    assert event["name"] == "Bosch SHC"
    assert event["domain"] == DOMAIN
    assert event["message"] == "'Hall Sensor' motion event was fired."


async def test_humanify_bosch_shc_alarm_event(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """Logbook pipeline humanifies an ALARM event correctly."""
    await setup_integration(hass, mock_config_entry)
    _setup_logbook_external_events(hass)

    (event,) = mock_humanify(
        hass,
        [
            MockRow(
                EVENT_BOSCH_SHC,
                {
                    ATTR_NAME: "Smoke Detector",
                    ATTR_EVENT_TYPE: "ALARM",
                    ATTR_EVENT_SUBTYPE: "PRIMARY_ALARM",
                },
            )
        ],
    )

    assert event["name"] == "Bosch SHC"
    assert event["domain"] == DOMAIN
    assert event["message"] == (
        "'Smoke Detector' alarm event 'PRIMARY_ALARM' was fired."
    )


async def test_humanify_bosch_shc_scenario_event(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """Logbook pipeline humanifies a SCENARIO event correctly."""
    await setup_integration(hass, mock_config_entry)
    _setup_logbook_external_events(hass)

    (event,) = mock_humanify(
        hass,
        [
            MockRow(
                EVENT_BOSCH_SHC,
                {
                    ATTR_NAME: "SHC",
                    ATTR_EVENT_TYPE: "SCENARIO",
                    ATTR_EVENT_SUBTYPE: "good_night",
                },
            )
        ],
    )

    assert event["name"] == "Bosch SHC"
    assert event["domain"] == DOMAIN
    assert event["message"] == "'SHC' scenario trigger event was fired."


async def test_humanify_bosch_shc_button_event(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """Logbook pipeline humanifies a button click event correctly."""
    await setup_integration(hass, mock_config_entry)
    _setup_logbook_external_events(hass)

    (event,) = mock_humanify(
        hass,
        [
            MockRow(
                EVENT_BOSCH_SHC,
                {
                    ATTR_NAME: "Wall Switch",
                    ATTR_EVENT_TYPE: "PRESS_LONG",
                    ATTR_EVENT_SUBTYPE: "LOWER_BUTTON",
                },
            )
        ],
    )

    assert event["name"] == "Bosch SHC"
    assert event["domain"] == DOMAIN
    assert event["message"] == (
        "'PRESS_LONG' click event for Wall Switch button 'LOWER_BUTTON' was fired."
    )
