"""Tests configuration for Govee Local API."""

from asyncio import Event
from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

from govee_local_api import GoveeDevice, GoveeLightCapabilities, GoveeLightFeatures
from govee_local_api.light_capabilities import COMMON_FEATURES, SCENE_CODES
import pytest

from homeassistant.components.govee_light_local.const import DOMAIN
from homeassistant.components.govee_light_local.coordinator import GoveeController
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture(name="mock_govee_api")
def fixture_mock_govee_api() -> Generator[AsyncMock]:
    """Set up Govee Local API fixture."""
    mock_api = AsyncMock(spec=GoveeController)
    mock_api.start = AsyncMock()
    mock_api.cleanup = MagicMock(return_value=Event())
    mock_api.cleanup.return_value.set()
    mock_api.turn_on_off = AsyncMock()
    mock_api.set_brightness = AsyncMock()
    mock_api.set_color = AsyncMock()
    mock_api.set_scene = AsyncMock()
    mock_api._async_update_data = AsyncMock()

    with (
        patch(
            "homeassistant.components.govee_light_local.coordinator.GoveeController",
            return_value=mock_api,
        ) as mock_controller,
        patch(
            "homeassistant.components.govee_light_local.config_flow.GoveeController",
            return_value=mock_api,
        ),
    ):
        yield mock_controller.return_value


@pytest.fixture(name="mock_setup_entry")
def fixture_mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.govee_light_local.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry


DEFAULT_CAPABILITIES: GoveeLightCapabilities = GoveeLightCapabilities(
    features=COMMON_FEATURES, segments=[], scenes={}
)

SCENE_CAPABILITIES: GoveeLightCapabilities = GoveeLightCapabilities(
    features=COMMON_FEATURES | GoveeLightFeatures.SCENES,
    segments=[],
    scenes=SCENE_CODES,
)


async def setup_light(
    hass: HomeAssistant,
    mock_govee_api: AsyncMock,
    capabilities: GoveeLightCapabilities = DEFAULT_CAPABILITIES,
    *,
    ip: str = "192.168.1.100",
    fingerprint: str = "asdawdqwdqwd",
    sku: str = "H615A",
) -> tuple[MockConfigEntry, GoveeDevice]:
    """Set up a single mocked Govee light device and return its entry and device.

    The returned tuple lets tests that need to mutate the device after setup
    (e.g. ``device.update(...)`` in availability tests) access the underlying
    ``GoveeDevice`` directly. Tests that only need the entry or neither can
    discard the unused half with ``_``.
    """
    device = GoveeDevice(
        controller=mock_govee_api,
        ip=ip,
        fingerprint=fingerprint,
        sku=sku,
        capabilities=capabilities,
    )
    mock_govee_api.devices = [device]

    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    return entry, device
