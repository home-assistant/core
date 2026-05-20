"""Tests for the Overkiz switch platform."""

from collections.abc import Generator
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
from pyoverkiz.enums import EventName
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_UNAVAILABLE,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import FixtureDevice, MockOverkizClient, SetupOverkizIntegration
from .helpers import assert_command_call, async_deliver_events, build_event

from tests.common import snapshot_platform

ON_OFF = FixtureDevice(
    "setup/cloud_somfy_tahoma_v2_europe.json",
    "io://1234-1234-6233/16168460",
    "switch.music_room_pool_pump_on_off",
)
SWIMMING_POOL = FixtureDevice(
    "setup/cloud_somfy_tahoma_v2_europe.json",
    "io://1234-1234-6233/16580352",
    "switch.pool_house",
)
RTD_OUTDOOR_SIREN = FixtureDevice(
    "setup/cloud_somfy_tahoma_v2_europe.json",
    "rtds://1234-1234-6233/4065441",
    "switch.willow_house_external_siren",
)
MYFOX_CAMERA = FixtureDevice(
    "setup/cloud_somfy_myfox_europe.json",
    "myfox://SOMFY_PROTECT-1234567890ABCDEF/jQ5ul40RVLnipT6JB8b3JK96tUsf14mR",
    "switch.outdoor_camera_camera_shutter",
)
DOMESTIC_HOT_WATER_TANK = FixtureDevice(
    "setup/cloud_somfy_myfox_europe.json",
    "io://1234-5678-1202/6019143#7",
    "switch.hot_water_tank_undefinedtype_singleton",
)


@pytest.fixture(autouse=True)
def fixture_platforms() -> Generator[None]:
    """Limit platforms to switch only."""
    with patch("homeassistant.components.overkiz.PLATFORMS", [Platform.SWITCH]):
        yield


SNAPSHOT_FIXTURES = [
    ON_OFF,
    MYFOX_CAMERA,
]


@pytest.mark.parametrize(
    "device",
    SNAPSHOT_FIXTURES,
    ids=[device.fixture.split("/")[-1] for device in SNAPSHOT_FIXTURES],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_switch_entities_snapshot(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    device: FixtureDevice,
) -> None:
    """Test representative real setups via snapshot."""
    config_entry = await setup_overkiz_integration(fixture=device.fixture)

    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


async def test_switch_on_off_turn_on(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
    mock_client: MockOverkizClient,
) -> None:
    """Test turning on an OnOff switch sends the correct command."""
    await setup_overkiz_integration(fixture=ON_OFF.fixture)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: ON_OFF.entity_id},
        blocking=True,
    )

    assert_command_call(
        mock_client,
        device_url=ON_OFF.device_url,
        command_name="on",
    )


async def test_switch_on_off_turn_off(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
    mock_client: MockOverkizClient,
) -> None:
    """Test turning off an OnOff switch sends the correct command."""
    await setup_overkiz_integration(fixture=ON_OFF.fixture)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: ON_OFF.entity_id},
        blocking=True,
    )

    assert_command_call(
        mock_client,
        device_url=ON_OFF.device_url,
        command_name="off",
    )


async def test_switch_swimming_pool_turn_on(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
    mock_client: MockOverkizClient,
) -> None:
    """Test turning on a SwimmingPool switch sends the correct command."""
    await setup_overkiz_integration(fixture=SWIMMING_POOL.fixture)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: SWIMMING_POOL.entity_id},
        blocking=True,
    )

    assert_command_call(
        mock_client,
        device_url=SWIMMING_POOL.device_url,
        command_name="on",
    )


async def test_switch_swimming_pool_turn_off(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
    mock_client: MockOverkizClient,
) -> None:
    """Test turning off a SwimmingPool switch sends the correct command."""
    await setup_overkiz_integration(fixture=SWIMMING_POOL.fixture)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: SWIMMING_POOL.entity_id},
        blocking=True,
    )

    assert_command_call(
        mock_client,
        device_url=SWIMMING_POOL.device_url,
        command_name="off",
    )


async def test_switch_rtd_outdoor_siren_turn_on(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
    mock_client: MockOverkizClient,
) -> None:
    """Test turning on an RTDOutdoorSiren switch sends the correct command."""
    await setup_overkiz_integration(fixture=RTD_OUTDOOR_SIREN.fixture)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: RTD_OUTDOOR_SIREN.entity_id},
        blocking=True,
    )

    assert_command_call(
        mock_client,
        device_url=RTD_OUTDOOR_SIREN.device_url,
        command_name="on",
    )


async def test_switch_rtd_outdoor_siren_turn_off(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
    mock_client: MockOverkizClient,
) -> None:
    """Test turning off an RTDOutdoorSiren switch sends the correct command."""
    await setup_overkiz_integration(fixture=RTD_OUTDOOR_SIREN.fixture)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: RTD_OUTDOOR_SIREN.entity_id},
        blocking=True,
    )

    assert_command_call(
        mock_client,
        device_url=RTD_OUTDOOR_SIREN.device_url,
        command_name="off",
    )


async def test_switch_myfox_camera_turn_on(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
    mock_client: MockOverkizClient,
) -> None:
    """Test opening the MyFox camera shutter sends the open command."""
    await setup_overkiz_integration(fixture=MYFOX_CAMERA.fixture)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: MYFOX_CAMERA.entity_id},
        blocking=True,
    )

    assert_command_call(
        mock_client,
        device_url=MYFOX_CAMERA.device_url,
        command_name="open",
    )


async def test_switch_myfox_camera_turn_off(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
    mock_client: MockOverkizClient,
) -> None:
    """Test closing the MyFox camera shutter sends the close command."""
    await setup_overkiz_integration(fixture=MYFOX_CAMERA.fixture)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: MYFOX_CAMERA.entity_id},
        blocking=True,
    )

    assert_command_call(
        mock_client,
        device_url=MYFOX_CAMERA.device_url,
        command_name="close",
    )


async def test_switch_domestic_hot_water_tank_turn_on(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
    mock_client: MockOverkizClient,
) -> None:
    """Test turning on a DomesticHotWaterTank sends setForceHeating on."""
    await setup_overkiz_integration(fixture=DOMESTIC_HOT_WATER_TANK.fixture)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: DOMESTIC_HOT_WATER_TANK.entity_id},
        blocking=True,
    )

    assert_command_call(
        mock_client,
        device_url=DOMESTIC_HOT_WATER_TANK.device_url,
        command_name="setForceHeating",
        parameters=["on"],
    )


async def test_switch_domestic_hot_water_tank_turn_off(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
    mock_client: MockOverkizClient,
) -> None:
    """Test turning off a DomesticHotWaterTank sends setForceHeating off."""
    await setup_overkiz_integration(fixture=DOMESTIC_HOT_WATER_TANK.fixture)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: DOMESTIC_HOT_WATER_TANK.entity_id},
        blocking=True,
    )

    assert_command_call(
        mock_client,
        device_url=DOMESTIC_HOT_WATER_TANK.device_url,
        command_name="setForceHeating",
        parameters=["off"],
    )


async def test_switch_unavailability(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
    mock_client: MockOverkizClient,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test switch becomes unavailable when device goes offline."""
    await setup_overkiz_integration(fixture=ON_OFF.fixture)

    state = hass.states.get(ON_OFF.entity_id)
    assert state
    assert state.state != STATE_UNAVAILABLE

    await async_deliver_events(
        hass,
        freezer,
        mock_client,
        [
            build_event(
                EventName.DEVICE_UNAVAILABLE.value,
                device_url=ON_OFF.device_url,
            )
        ],
    )

    assert hass.states.get(ON_OFF.entity_id).state == STATE_UNAVAILABLE
