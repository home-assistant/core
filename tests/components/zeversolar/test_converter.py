"""Test the ZeversolarCoordinator class."""

from homeassistant.components.zeversolar.const import DOMAIN
from homeassistant.components.zeversolar.coordinator import ZeversolarCoordinator
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from tests.common import MockConfigEntry


async def test_ZeversolarCoordinator_constructor(hass: HomeAssistant) -> None:
    """Simple test for construction and initialization."""

    config = MockConfigEntry(
        data={
            "host": "my host",
            "port": 10200,
        },
        domain=DOMAIN,
        options={},
        title="My NEW_DOMAIN",
    )

    zeversolarCoordinator = ZeversolarCoordinator(hass=hass, entry=config)

    assert type(zeversolarCoordinator) is ZeversolarCoordinator
    assert issubclass(type(zeversolarCoordinator), DataUpdateCoordinator)
