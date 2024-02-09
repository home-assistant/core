"""Define test fixtures for myuplink."""
import pytest

from homeassistant.components.myuplink import DOMAIN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture(name="config_entry")
def config_entry_fixture(hass: HomeAssistant):
    """Define a config entry fixture."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={},
        options={},
        entry_id="2ab7896bda8c3875086f1fe6baad4948",
    )
    entry.add_to_hass(hass)
    return entry
