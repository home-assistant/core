"""Test the SteamVR Base Station selects."""

from unittest.mock import ANY, AsyncMock, PropertyMock, patch

from lighthouse_ble import BaseStationV2, PowerState, UnsupportedError
import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from pytest_homeassistant.components.bluetooth import (
    inject_bluetooth_service_info_bleak,
)
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.select import (
    ATTR_OPTION,
    ATTR_OPTIONS,
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import make_service_info, payload

POWER_MODE = "select.lhb_747a9bc5_power_mode"
CHANNEL = "select.lhb_747a9bc5_channel"


@pytest.fixture
def platforms() -> list[Platform]:
    """Only set up the select platform."""
    return [Platform.SELECT]


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_select_entities(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the select entities."""
    await snapshot_platform(hass, entity_registry, snapshot, init_integration.entry_id)


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        pytest.param(0x0B, "on", id="on"),
        pytest.param(0x08, "on", id="booting"),
        pytest.param(0x02, "standby", id="standby"),
        pytest.param(0x00, "sleep", id="sleep"),
        pytest.param(0x77, STATE_UNKNOWN, id="unknown_code"),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_power_mode_follows_advertisements(
    hass: HomeAssistant, code: int, expected: str
) -> None:
    """Test the power mode reflects the advertised power state."""
    inject_bluetooth_service_info_bleak(hass, make_service_info(payload(power=code)))
    await hass.async_block_till_done()
    assert hass.states.get(POWER_MODE).state == expected


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
async def test_channel_follows_advertisements(hass: HomeAssistant) -> None:
    """Test the channel reflects the advertised channel."""
    inject_bluetooth_service_info_bleak(hass, make_service_info(payload(channel=7)))
    await hass.async_block_till_done()
    assert hass.states.get(CHANNEL).state == "7"


@pytest.mark.parametrize(
    ("option", "target"),
    [
        pytest.param("on", PowerState.ON, id="on"),
        pytest.param("standby", PowerState.STANDBY, id="standby"),
        pytest.param("sleep", PowerState.SLEEP, id="sleep"),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_select_power_mode(
    hass: HomeAssistant, mock_set_power: AsyncMock, option: str, target: PowerState
) -> None:
    """Test choosing a power mode sends the matching power command."""
    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: POWER_MODE, ATTR_OPTION: option},
        blocking=True,
    )
    mock_set_power.assert_awaited_once_with(ANY, target)


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
async def test_select_channel(hass: HomeAssistant, mock_set_channel: AsyncMock) -> None:
    """Test choosing a channel moves the station to it."""
    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: CHANNEL, ATTR_OPTION: "5"},
        blocking=True,
    )
    mock_set_channel.assert_awaited_once_with(ANY, 5)


async def test_no_standby_on_legacy_firmware(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test standby is not offered once the firmware turns out not to support it."""
    with patch.object(
        BaseStationV2, "supports_standby", new_callable=PropertyMock, return_value=False
    ):
        init_integration.runtime_data.async_update_listeners()
        assert hass.states.get(POWER_MODE).attributes[ATTR_OPTIONS] == ["on", "sleep"]


@pytest.mark.usefixtures("init_integration")
async def test_standby_not_supported(
    hass: HomeAssistant, mock_set_power: AsyncMock
) -> None:
    """Test firmware rejecting standby raises a translated error."""
    mock_set_power.side_effect = UnsupportedError("no standby")
    with pytest.raises(HomeAssistantError) as raised:
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {ATTR_ENTITY_ID: POWER_MODE, ATTR_OPTION: "standby"},
            blocking=True,
        )
    assert raised.value.translation_key == "not_supported"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_unparsable_advertisement(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test the selects are unknown until the station advertises its state."""
    inject_bluetooth_service_info_bleak(hass, make_service_info(b"\x00"))
    mock_config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.steamvr_base_station.PLATFORMS", [Platform.SELECT]
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
    assert hass.states.get(POWER_MODE).state == STATE_UNKNOWN
    assert hass.states.get(CHANNEL).state == STATE_UNKNOWN
