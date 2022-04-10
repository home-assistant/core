"""Test the Nina binary sensor."""
from __future__ import annotations

from typing import Any
from unittest.mock import patch

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.nina.const import (
    ATTR_DESCRIPTION,
    ATTR_EXPIRES,
    ATTR_HEADLINE,
    ATTR_ID,
    ATTR_SENDER,
    ATTR_SENT,
    ATTR_SEVERITY,
    ATTR_START,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import mocked_request_function

from tests.common import MockConfigEntry

ENTRY_DATA: dict[str, Any] = {
    "slots": 5,
    "corona_filter": True,
    "regions": {"083350000000": "Aach, Stadt"},
}

ENTRY_DATA_NO_CORONA: dict[str, Any] = {
    "slots": 5,
    "corona_filter": False,
    "regions": {"083350000000": "Aach, Stadt"},
}


async def test_sensors(hass: HomeAssistant) -> None:
    """Test the creation and values of the NINA sensors."""

    with patch(
        "pynina.baseApi.BaseAPI._makeRequest",
        wraps=mocked_request_function,
    ):

        conf_entry: MockConfigEntry = MockConfigEntry(
            domain=DOMAIN, title="NINA", data=ENTRY_DATA
        )

        entity_registry: er = er.async_get(hass)
        conf_entry.add_to_hass(hass)

        await hass.config_entries.async_setup(conf_entry.entry_id)
        await hass.async_block_till_done()

        assert conf_entry.state == ConfigEntryState.LOADED

        state_w1 = hass.states.get("binary_sensor.warning_aach_stadt_1")
        entry_w1 = entity_registry.async_get("binary_sensor.warning_aach_stadt_1")

        assert state_w1.state == STATE_ON
        assert state_w1.attributes.get(ATTR_HEADLINE) == "Ausfall Notruf 112"
        assert (
            state_w1.attributes.get(ATTR_DESCRIPTION)
            == "Es treten Sturmböen mit Geschwindigkeiten zwischen 70 km/h (20m/s, 38kn, Bft 8) und 85 km/h (24m/s, 47kn, Bft 9) aus westlicher Richtung auf. In Schauernähe sowie in exponierten Lagen muss mit schweren Sturmböen bis 90 km/h (25m/s, 48kn, Bft 10) gerechnet werden."
        )
        assert state_w1.attributes.get(ATTR_SENDER) == "Deutscher Wetterdienst"
        assert state_w1.attributes.get(ATTR_SEVERITY) == "Minor"
        assert state_w1.attributes.get(ATTR_ID) == "mow.DE-NW-BN-SE030-20201014-30-000"
        assert state_w1.attributes.get(ATTR_SENT) == "2021-10-11T05:20:00+01:00"
        assert state_w1.attributes.get(ATTR_START) == "2021-11-01T05:20:00+01:00"
        assert state_w1.attributes.get(ATTR_EXPIRES) == "3021-11-22T05:19:00+01:00"

        assert entry_w1.unique_id == "083350000000-1"
        assert state_w1.attributes.get("device_class") == BinarySensorDeviceClass.SAFETY

        state_w2 = hass.states.get("binary_sensor.warning_aach_stadt_2")
        entry_w2 = entity_registry.async_get("binary_sensor.warning_aach_stadt_2")

        assert state_w2.state == STATE_OFF
        assert state_w2.attributes.get(ATTR_HEADLINE) is None
        assert state_w2.attributes.get(ATTR_DESCRIPTION) is None
        assert state_w2.attributes.get(ATTR_SENDER) is None
        assert state_w2.attributes.get(ATTR_SEVERITY) is None
        assert state_w2.attributes.get(ATTR_ID) is None
        assert state_w2.attributes.get(ATTR_SENT) is None
        assert state_w2.attributes.get(ATTR_START) is None
        assert state_w2.attributes.get(ATTR_EXPIRES) is None

        assert entry_w2.unique_id == "083350000000-2"
        assert state_w2.attributes.get("device_class") == BinarySensorDeviceClass.SAFETY

        state_w3 = hass.states.get("binary_sensor.warning_aach_stadt_3")
        entry_w3 = entity_registry.async_get("binary_sensor.warning_aach_stadt_3")

        assert state_w3.state == STATE_OFF
        assert state_w3.attributes.get(ATTR_HEADLINE) is None
        assert state_w3.attributes.get(ATTR_DESCRIPTION) is None
        assert state_w3.attributes.get(ATTR_SENDER) is None
        assert state_w3.attributes.get(ATTR_SEVERITY) is None
        assert state_w3.attributes.get(ATTR_ID) is None
        assert state_w3.attributes.get(ATTR_SENT) is None
        assert state_w3.attributes.get(ATTR_START) is None
        assert state_w3.attributes.get(ATTR_EXPIRES) is None

        assert entry_w3.unique_id == "083350000000-3"
        assert state_w3.attributes.get("device_class") == BinarySensorDeviceClass.SAFETY

        state_w4 = hass.states.get("binary_sensor.warning_aach_stadt_4")
        entry_w4 = entity_registry.async_get("binary_sensor.warning_aach_stadt_4")

        assert state_w4.state == STATE_OFF
        assert state_w4.attributes.get(ATTR_HEADLINE) is None
        assert state_w4.attributes.get(ATTR_DESCRIPTION) is None
        assert state_w4.attributes.get(ATTR_SENDER) is None
        assert state_w4.attributes.get(ATTR_SEVERITY) is None
        assert state_w4.attributes.get(ATTR_ID) is None
        assert state_w4.attributes.get(ATTR_SENT) is None
        assert state_w4.attributes.get(ATTR_START) is None
        assert state_w4.attributes.get(ATTR_EXPIRES) is None

        assert entry_w4.unique_id == "083350000000-4"
        assert state_w4.attributes.get("device_class") == BinarySensorDeviceClass.SAFETY

        state_w5 = hass.states.get("binary_sensor.warning_aach_stadt_5")
        entry_w5 = entity_registry.async_get("binary_sensor.warning_aach_stadt_5")

        assert state_w5.state == STATE_OFF
        assert state_w5.attributes.get(ATTR_HEADLINE) is None
        assert state_w5.attributes.get(ATTR_DESCRIPTION) is None
        assert state_w5.attributes.get(ATTR_SENDER) is None
        assert state_w5.attributes.get(ATTR_SEVERITY) is None
        assert state_w5.attributes.get(ATTR_ID) is None
        assert state_w5.attributes.get(ATTR_SENT) is None
        assert state_w5.attributes.get(ATTR_START) is None
        assert state_w5.attributes.get(ATTR_EXPIRES) is None

        assert entry_w5.unique_id == "083350000000-5"
        assert state_w5.attributes.get("device_class") == BinarySensorDeviceClass.SAFETY


async def test_sensors_without_corona_filter(hass: HomeAssistant) -> None:
    """Test the creation and values of the NINA sensors without the corona filter."""

    with patch(
        "pynina.baseApi.BaseAPI._makeRequest",
        wraps=mocked_request_function,
    ):

        conf_entry: MockConfigEntry = MockConfigEntry(
            domain=DOMAIN, title="NINA", data=ENTRY_DATA_NO_CORONA
        )

        entity_registry: er = er.async_get(hass)
        conf_entry.add_to_hass(hass)

        await hass.config_entries.async_setup(conf_entry.entry_id)
        await hass.async_block_till_done()

        assert conf_entry.state == ConfigEntryState.LOADED

        state_w1 = hass.states.get("binary_sensor.warning_aach_stadt_1")
        entry_w1 = entity_registry.async_get("binary_sensor.warning_aach_stadt_1")

        assert state_w1.state == STATE_ON
        assert (
            state_w1.attributes.get(ATTR_HEADLINE)
            == "Corona-Verordnung des Landes: Warnstufe durch Landesgesundheitsamt ausgerufen"
        )
        assert (
            state_w1.attributes.get(ATTR_DESCRIPTION)
            == "Die Zahl der mit dem Corona-Virus infizierten Menschen steigt gegenwärtig stark an. Es wächst daher die Gefahr einer weiteren Verbreitung der Infektion und - je nach Einzelfall - auch von schweren Erkrankungen."
        )
        assert state_w1.attributes.get(ATTR_SENDER) == ""
        assert state_w1.attributes.get(ATTR_SEVERITY) == "Minor"
        assert state_w1.attributes.get(ATTR_ID) == "mow.DE-BW-S-SE018-20211102-18-001"
        assert state_w1.attributes.get(ATTR_SENT) == "2021-11-02T20:07:16+01:00"
        assert state_w1.attributes.get(ATTR_START) == ""
        assert state_w1.attributes.get(ATTR_EXPIRES) == ""

        assert entry_w1.unique_id == "083350000000-1"
        assert state_w1.attributes.get("device_class") == BinarySensorDeviceClass.SAFETY

        state_w2 = hass.states.get("binary_sensor.warning_aach_stadt_2")
        entry_w2 = entity_registry.async_get("binary_sensor.warning_aach_stadt_2")

        assert state_w2.state == STATE_ON
        assert state_w2.attributes.get(ATTR_HEADLINE) == "Ausfall Notruf 112"
        assert (
            state_w2.attributes.get(ATTR_DESCRIPTION)
            == "Es treten Sturmböen mit Geschwindigkeiten zwischen 70 km/h (20m/s, 38kn, Bft 8) und 85 km/h (24m/s, 47kn, Bft 9) aus westlicher Richtung auf. In Schauernähe sowie in exponierten Lagen muss mit schweren Sturmböen bis 90 km/h (25m/s, 48kn, Bft 10) gerechnet werden."
        )
        assert state_w2.attributes.get(ATTR_SENDER) == "Deutscher Wetterdienst"
        assert state_w2.attributes.get(ATTR_SEVERITY) == "Minor"
        assert state_w2.attributes.get(ATTR_ID) == "mow.DE-NW-BN-SE030-20201014-30-000"
        assert state_w2.attributes.get(ATTR_SENT) == "2021-10-11T05:20:00+01:00"
        assert state_w2.attributes.get(ATTR_START) == "2021-11-01T05:20:00+01:00"
        assert state_w2.attributes.get(ATTR_EXPIRES) == "3021-11-22T05:19:00+01:00"

        assert entry_w2.unique_id == "083350000000-2"
        assert state_w2.attributes.get("device_class") == BinarySensorDeviceClass.SAFETY

        state_w3 = hass.states.get("binary_sensor.warning_aach_stadt_3")
        entry_w3 = entity_registry.async_get("binary_sensor.warning_aach_stadt_3")

        assert state_w3.state == STATE_OFF
        assert state_w3.attributes.get(ATTR_HEADLINE) is None
        assert state_w3.attributes.get(ATTR_DESCRIPTION) is None
        assert state_w3.attributes.get(ATTR_SENDER) is None
        assert state_w3.attributes.get(ATTR_SEVERITY) is None
        assert state_w3.attributes.get(ATTR_ID) is None
        assert state_w3.attributes.get(ATTR_SENT) is None
        assert state_w3.attributes.get(ATTR_START) is None
        assert state_w3.attributes.get(ATTR_EXPIRES) is None

        assert entry_w3.unique_id == "083350000000-3"
        assert state_w3.attributes.get("device_class") == BinarySensorDeviceClass.SAFETY

        state_w4 = hass.states.get("binary_sensor.warning_aach_stadt_4")
        entry_w4 = entity_registry.async_get("binary_sensor.warning_aach_stadt_4")

        assert state_w4.state == STATE_OFF
        assert state_w4.attributes.get(ATTR_HEADLINE) is None
        assert state_w4.attributes.get(ATTR_DESCRIPTION) is None
        assert state_w4.attributes.get(ATTR_SENDER) is None
        assert state_w4.attributes.get(ATTR_SEVERITY) is None
        assert state_w4.attributes.get(ATTR_ID) is None
        assert state_w4.attributes.get(ATTR_SENT) is None
        assert state_w4.attributes.get(ATTR_START) is None
        assert state_w4.attributes.get(ATTR_EXPIRES) is None

        assert entry_w4.unique_id == "083350000000-4"
        assert state_w4.attributes.get("device_class") == BinarySensorDeviceClass.SAFETY

        state_w5 = hass.states.get("binary_sensor.warning_aach_stadt_5")
        entry_w5 = entity_registry.async_get("binary_sensor.warning_aach_stadt_5")

        assert state_w5.state == STATE_OFF
        assert state_w5.attributes.get(ATTR_HEADLINE) is None
        assert state_w5.attributes.get(ATTR_DESCRIPTION) is None
        assert state_w5.attributes.get(ATTR_SENDER) is None
        assert state_w5.attributes.get(ATTR_SEVERITY) is None
        assert state_w5.attributes.get(ATTR_ID) is None
        assert state_w5.attributes.get(ATTR_SENT) is None
        assert state_w5.attributes.get(ATTR_START) is None
        assert state_w5.attributes.get(ATTR_EXPIRES) is None

        assert entry_w5.unique_id == "083350000000-5"
        assert state_w5.attributes.get("device_class") == BinarySensorDeviceClass.SAFETY
