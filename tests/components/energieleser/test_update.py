"""Tests for the energieleser update platform."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

from energieleser import DeviceType, EnergieleserConnectionError
from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.energieleser.const import CONF_SW_VERSION, DOMAIN
from homeassistant.components.energieleser.coordinator import FIRMWARE_SCAN_INTERVAL
from homeassistant.components.update import (
    ATTR_INSTALLED_VERSION,
    ATTR_LATEST_VERSION,
    ATTR_TITLE,
)
from homeassistant.const import (
    CONF_DEVICE_ID,
    CONF_HOST,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import (
    LATEST_FIRMWARE_VERSIONS,
    STROMLESER_DEVICE_ID,
    STROMLESER_SW_VERSION,
)

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


@pytest.fixture(autouse=True)
def only_update_platform() -> Generator[None]:
    """Only set up the update platform."""
    with patch("homeassistant.components.energieleser.PLATFORMS", [Platform.UPDATE]):
        yield


def _entry(extra_data: dict[str, str]) -> MockConfigEntry:
    return MockConfigEntry(
        title=STROMLESER_DEVICE_ID,
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.1.100",
            CONF_DEVICE_ID: STROMLESER_DEVICE_ID,
            **extra_data,
        },
        unique_id=STROMLESER_DEVICE_ID,
    )


async def _setup(hass: HomeAssistant, entry: MockConfigEntry) -> str:
    """Set up *entry* and return the update entity id."""
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    entity_id = er.async_get(hass).async_get_entity_id(
        Platform.UPDATE, DOMAIN, f"{STROMLESER_DEVICE_ID}_firmware"
    )
    assert entity_id is not None
    return entity_id


@pytest.mark.usefixtures("mock_energieleser_client")
async def test_update_entity_snapshot(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the update entity against a snapshot."""
    entry = _entry({CONF_SW_VERSION: STROMLESER_SW_VERSION})
    await _setup(hass, entry)
    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)


@pytest.mark.usefixtures("mock_energieleser_client")
async def test_update_available(hass: HomeAssistant) -> None:
    """Test a dev build older than the latest release reports an update."""
    entity_id = await _setup(hass, _entry({CONF_SW_VERSION: STROMLESER_SW_VERSION}))

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_ON
    assert state.attributes[ATTR_INSTALLED_VERSION] == STROMLESER_SW_VERSION
    assert state.attributes[ATTR_LATEST_VERSION] == "v1.4.30"
    assert state.attributes[ATTR_TITLE] == "stromleser.one"


@pytest.mark.parametrize(
    "sw_version",
    [
        pytest.param("v1.4.30", id="same"),
        pytest.param("1.4.30", id="same_without_v"),
        pytest.param("v1.4.30-2-gabcdef0", id="dev_build_on_latest"),
        pytest.param("v1.4.31", id="newer_than_server"),
    ],
)
@pytest.mark.usefixtures("mock_energieleser_client")
async def test_up_to_date(hass: HomeAssistant, sw_version: str) -> None:
    """Test equal or newer installed firmware is reported as up to date."""
    entity_id = await _setup(hass, _entry({CONF_SW_VERSION: sw_version}))

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_OFF


@pytest.mark.usefixtures("mock_energieleser_client")
async def test_installed_version_unknown(hass: HomeAssistant) -> None:
    """Test a manually added device without mDNS version shows unknown."""
    entity_id = await _setup(hass, _entry({}))

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_UNKNOWN


@pytest.mark.usefixtures("mock_energieleser_client")
async def test_device_type_missing_from_server(
    hass: HomeAssistant, mock_latest_firmware_versions: AsyncMock
) -> None:
    """Test the entity is unavailable when the server omits its device type."""
    mock_latest_firmware_versions.return_value = {DeviceType.GASLESER: "v1.5.35"}
    entity_id = await _setup(hass, _entry({CONF_SW_VERSION: STROMLESER_SW_VERSION}))

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


@pytest.mark.usefixtures("mock_energieleser_client")
async def test_api_failure_then_recovery(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_latest_firmware_versions: AsyncMock,
) -> None:
    """Test the entity is unavailable on API failure and recovers on next poll."""
    mock_latest_firmware_versions.side_effect = EnergieleserConnectionError("down")
    entity_id = await _setup(hass, _entry({CONF_SW_VERSION: STROMLESER_SW_VERSION}))

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE

    mock_latest_firmware_versions.side_effect = None
    mock_latest_firmware_versions.return_value = dict(LATEST_FIRMWARE_VERSIONS)
    freezer.tick(FIRMWARE_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_ON
    assert mock_latest_firmware_versions.call_count == 2
