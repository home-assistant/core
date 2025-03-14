"""Define tests for the PurpleAir init flow."""

from homeassistant.components.purpleair import async_migrate_entry
from homeassistant.components.purpleair.const import (
    CONF_SENSOR_INDEX,
    CONF_SENSOR_LIST,
    CONF_SENSOR_READ_KEY,
    DOMAIN,
    SCHEMA_VERSION,
    TITLE,
)
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant

from .const import TEST_API_KEY, TEST_SENSOR_INDEX1

from tests.common import MockConfigEntry


async def test_migrate_entry(
    hass: HomeAssistant,
) -> None:
    """Test migrate entry to version 2."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_API_KEY,
        version=1,
        data={CONF_API_KEY: TEST_API_KEY},
        options={"sensor_indices": [TEST_SENSOR_INDEX1]},
        entry_id="1",
        title=TITLE,
    )
    entry.add_to_hass(hass)
    await hass.async_block_till_done()

    assert await async_migrate_entry(hass, entry) is True
    await hass.async_block_till_done()

    assert entry.version == SCHEMA_VERSION
    assert entry.data == {CONF_API_KEY: TEST_API_KEY}
    assert entry.options == {
        CONF_SENSOR_LIST: [
            {CONF_SENSOR_INDEX: TEST_SENSOR_INDEX1, CONF_SENSOR_READ_KEY: None}
        ]
    }
