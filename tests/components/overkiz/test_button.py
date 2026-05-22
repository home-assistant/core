"""Tests for the Overkiz button platform."""

from collections.abc import Generator
from pathlib import Path
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
from pyoverkiz.enums import EventName
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import FixtureDevice, MockOverkizClient, SetupOverkizIntegration
from .helpers import assert_command_call, async_deliver_events, build_event

from tests.common import snapshot_platform

MY_POSITION = FixtureDevice(
    "setup/cloud_somfy_tahoma_v2_europe.json",
    "io://1234-1234-6233/12184029",
    "button.office_garden_house_shutter_my_position",
)
IDENTIFY = FixtureDevice(
    "setup/cloud_somfy_tahoma_v2_europe.json",
    "io://1234-1234-6233/12184029",
    "button.office_garden_house_shutter_identify",
)
GO_TO_ALIAS = FixtureDevice(
    "setup/local_somfy_tahoma_switch_europe_2.json",
    "io://1234-5678-1516/77700",
    "button.roof_window_my_position",
)
CHECK_EVENT_TRIGGER = FixtureDevice(
    "setup/cloud_nexity_rail_din_europe.json",
    "io://1234-5678-1698/8907539",
    "button.maple_residence_living_room_smoke_detector_test",
)

SNAPSHOT_FIXTURES = [
    MY_POSITION,
    GO_TO_ALIAS,
    CHECK_EVENT_TRIGGER,
]


@pytest.fixture(autouse=True)
def fixture_platforms() -> Generator[None]:
    """Limit platforms to button only."""
    with patch("homeassistant.components.overkiz.PLATFORMS", [Platform.BUTTON]):
        yield


@pytest.mark.parametrize(
    "device",
    SNAPSHOT_FIXTURES,
    ids=[Path(device.fixture).name for device in SNAPSHOT_FIXTURES],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_button_entities_snapshot(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    device: FixtureDevice,
) -> None:
    """Test representative real setups via snapshot."""
    config_entry = await setup_overkiz_integration(fixture=device.fixture)

    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


async def test_button_press(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
    mock_client: MockOverkizClient,
) -> None:
    """Test pressing a button without arguments sends the correct command."""
    await setup_overkiz_integration(fixture=MY_POSITION.fixture)

    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: MY_POSITION.entity_id},
        blocking=True,
    )

    assert_command_call(
        mock_client,
        device_url=MY_POSITION.device_url,
        command_name="my",
    )


async def test_button_press_with_args(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
    mock_client: MockOverkizClient,
) -> None:
    """Test pressing a button with arguments sends the correct command."""
    await setup_overkiz_integration(fixture=GO_TO_ALIAS.fixture)

    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: GO_TO_ALIAS.entity_id},
        blocking=True,
    )

    assert_command_call(
        mock_client,
        device_url=GO_TO_ALIAS.device_url,
        command_name="goToAlias",
        parameters=["1"],
    )


async def test_button_unavailability(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
    mock_client: MockOverkizClient,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test button becomes unavailable when device goes offline."""
    await setup_overkiz_integration(fixture=MY_POSITION.fixture)

    state = hass.states.get(MY_POSITION.entity_id)
    assert state
    assert state.state != STATE_UNAVAILABLE

    await async_deliver_events(
        hass,
        freezer,
        mock_client,
        [
            build_event(
                EventName.DEVICE_UNAVAILABLE.value,
                device_url=MY_POSITION.device_url,
            )
        ],
    )

    assert hass.states.get(MY_POSITION.entity_id).state == STATE_UNAVAILABLE
