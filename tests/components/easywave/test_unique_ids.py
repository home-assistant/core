"""Tests to ensure all Easywave entities have valid unique IDs."""

from unittest.mock import MagicMock

from homeassistant.components.easywave.const import (
    CONF_BUTTON_COUNT,
    CONF_ENTRY_TYPE,
    CONF_GROUPING_MODE,
    CONF_OPERATING_TYPE,
    CONF_SWITCH_MODE,
    CONF_TRANSMITTER_SERIAL,
    ENTRY_TYPE_TRANSMITTER,
    TRANSMITTER_GROUPING_GROUP,
    TRANSMITTER_SWITCH_IMPULSE,
)
from homeassistant.components.easywave.entity import (
    EasywaveDeviceEntry,
    EasywaveTransmitterEntity,
)


def test_transmitter_entity_unique_id_with_subentry_id() -> None:
    """Ensure transmitter entity generates unique_id from subentry_id."""
    entry_mock = MagicMock()
    entry_mock.entry_id = "test_entry_123"

    subentry = EasywaveDeviceEntry(
        subentry_id="my_transmitter_id",
        title="Test Transmitter",
        data={
            CONF_ENTRY_TYPE: ENTRY_TYPE_TRANSMITTER,
            CONF_TRANSMITTER_SERIAL: "ABC123",
            CONF_OPERATING_TYPE: "1",
            CONF_BUTTON_COUNT: 4,
            CONF_GROUPING_MODE: TRANSMITTER_GROUPING_GROUP,
            CONF_SWITCH_MODE: TRANSMITTER_SWITCH_IMPULSE,
        },
    )

    entity = EasywaveTransmitterEntity(entry_mock, subentry, "test_suffix")
    assert entity._attr_unique_id == "my_transmitter_id_test_suffix"
