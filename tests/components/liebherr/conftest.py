"""Common fixtures for the liebherr tests."""

import asyncio
from collections.abc import AsyncIterator, Callable, Generator
import copy
from unittest.mock import AsyncMock, MagicMock, patch

from pyliebherrhomeapi import (
    AutoDoorControl,
    BioFreshPlusControl,
    BioFreshPlusMode,
    Device,
    DeviceControl,
    DeviceState,
    DeviceType,
    DoorState,
    HydroBreezeControl,
    HydroBreezeMode,
    IceMakerControl,
    IceMakerMode,
    PresentationLightControl,
    TemperatureControl,
    TemperatureUnit,
    ToggleControl,
    ZonePosition,
)
from pyliebherrhomeapi.exceptions import (
    LiebherrAuthenticationError,
    LiebherrConnectionError,
    LiebherrTimeoutError,
)
import pytest

from homeassistant.components.liebherr.const import DOMAIN
from homeassistant.const import CONF_API_KEY, Platform
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

# Complete multi-zone device for comprehensive testing
MOCK_DEVICE = Device(
    device_id="test_device_id",
    nickname="Test Fridge",
    device_type=DeviceType.COMBI,
    device_name="CBNes1234",
)

MOCK_DEVICE_STATE = DeviceState(
    device=MOCK_DEVICE,
    controls=[
        TemperatureControl(
            zone_id=1,
            zone_position=ZonePosition.TOP,
            name="Fridge",
            type="fridge",
            value=5,
            target=4,
            min=2,
            max=8,
            unit=TemperatureUnit.CELSIUS,
            set_temperature_steps=[2, 4, 6, 8],
            set_temperature_steps_enabled=True,
        ),
        TemperatureControl(
            zone_id=2,
            zone_position=ZonePosition.BOTTOM,
            name="Freezer",
            type="freezer",
            value=-18,
            target=-18,
            min=-24,
            max=-16,
            unit=TemperatureUnit.CELSIUS,
        ),
        ToggleControl(
            name="supercool",
            type="ToggleControl",
            zone_id=1,
            zone_position=ZonePosition.TOP,
            value=False,
        ),
        ToggleControl(
            name="superfrost",
            type="ToggleControl",
            zone_id=2,
            zone_position=ZonePosition.BOTTOM,
            value=True,
        ),
        ToggleControl(
            name="partymode",
            type="ToggleControl",
            zone_id=None,
            zone_position=None,
            value=False,
        ),
        ToggleControl(
            name="nightmode",
            type="ToggleControl",
            zone_id=None,
            zone_position=None,
            value=True,
        ),
        IceMakerControl(
            name="icemaker",
            type="IceMakerControl",
            zone_id=2,
            zone_position=ZonePosition.BOTTOM,
            ice_maker_mode=IceMakerMode.OFF,
            has_max_ice=True,
        ),
        HydroBreezeControl(
            name="hydrobreeze",
            type="HydroBreezeControl",
            zone_id=1,
            zone_position=ZonePosition.TOP,
            current_mode=HydroBreezeMode.LOW,
        ),
        BioFreshPlusControl(
            name="biofreshplus",
            type="BioFreshPlusControl",
            zone_id=1,
            zone_position=ZonePosition.TOP,
            current_mode=BioFreshPlusMode.ZERO_ZERO,
            supported_modes=[
                BioFreshPlusMode.ZERO_ZERO,
                BioFreshPlusMode.ZERO_MINUS_TWO,
                BioFreshPlusMode.MINUS_TWO_MINUS_TWO,
                BioFreshPlusMode.MINUS_TWO_ZERO,
            ],
        ),
        PresentationLightControl(
            name="presentationlight",
            type="PresentationLightControl",
            value=3,
            max=5,
        ),
        AutoDoorControl(
            name="autodoor",
            type="AutoDoorControl",
            zone_id=1,
            zone_position=ZonePosition.TOP,
            value=DoorState.CLOSED,
        ),
    ],
)


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.liebherr.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


class SSEStreamHelper:
    """Test helper simulating ``LiebherrClient.stream_controls_forever``.

    Yields the current ``client.get_device_state`` result to the coordinator
    when :meth:`async_push` is called. Auth errors from the mocked
    ``get_device_state`` propagate to the coordinator; connection/timeout
    errors trigger the ``on_disconnect`` callback and drop the pending
    update without terminating the stream.
    """

    def __init__(self, hass: HomeAssistant, client: MagicMock) -> None:
        """Initialize the helper."""
        self._hass = hass
        self._client = client
        self._events: dict[str, asyncio.Event] = {}
        self._on_disconnect: dict[str, Callable[[], None] | None] = {}
        self._on_connect: dict[str, Callable[[], None] | None] = {}
        self._reconnect_next: dict[str, bool] = {}

    def _stream(
        self,
        device_id: str,
        *,
        on_connect: Callable[[], None] | None = None,
        on_disconnect: Callable[[], None] | None = None,
        **_: object,
    ) -> AsyncIterator[list[DeviceControl]]:
        self._on_connect[device_id] = on_connect
        self._on_disconnect[device_id] = on_disconnect
        return self._iter(device_id)

    async def _iter(self, device_id: str) -> AsyncIterator[list[DeviceControl]]:
        event = self._events.setdefault(device_id, asyncio.Event())
        state = await self._client.get_device_state(device_id)
        if (cb := self._on_connect.get(device_id)) is not None:
            cb()
        yield state.controls
        while True:
            await event.wait()
            event.clear()
            reconnect = self._reconnect_next.pop(device_id, False)
            try:
                state = await self._client.get_device_state(device_id)
            except LiebherrAuthenticationError:
                raise
            except LiebherrConnectionError, LiebherrTimeoutError:
                if (cb := self._on_disconnect.get(device_id)) is not None:
                    cb()
                continue
            if reconnect and (cb := self._on_connect.get(device_id)) is not None:
                cb()
            yield state.controls

    async def async_push(self, device_id: str = "test_device_id") -> None:
        """Trigger a stream event: coordinator re-reads ``get_device_state``."""
        event = self._events.setdefault(device_id, asyncio.Event())
        event.set()
        await self._hass.async_block_till_done()

    async def async_reconnect(self, device_id: str = "test_device_id") -> None:
        """Trigger a stream event that simulates a reconnect (full state replace)."""
        self._reconnect_next[device_id] = True
        await self.async_push(device_id)


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "test-api-key"},
        title="Liebherr",
    )


@pytest.fixture
def mock_liebherr_client(
    hass: HomeAssistant,
) -> Generator[MagicMock]:
    """Return a mocked Liebherr client."""
    with (
        patch(
            "homeassistant.components.liebherr.LiebherrClient",
            autospec=True,
        ) as mock_client,
        patch(
            "homeassistant.components.liebherr.config_flow.LiebherrClient",
            new=mock_client,
        ),
    ):
        client = mock_client.return_value
        client.get_devices.return_value = [MOCK_DEVICE]
        # Return a fresh copy each call so mutations don't leak between calls.
        client.get_device_state.side_effect = lambda *a, **kw: copy.deepcopy(
            MOCK_DEVICE_STATE
        )
        client.set_temperature = AsyncMock()
        client.set_super_cool = AsyncMock()
        client.set_super_frost = AsyncMock()
        client.set_party_mode = AsyncMock()
        client.set_night_mode = AsyncMock()
        client.set_ice_maker = AsyncMock()
        client.set_hydro_breeze = AsyncMock()
        client.set_bio_fresh_plus = AsyncMock()
        client.set_presentation_light = AsyncMock()
        client.trigger_auto_door = AsyncMock()
        helper = SSEStreamHelper(hass, client)
        client.stream_controls_forever.side_effect = helper._stream
        client._sse_helper = helper
        yield client


@pytest.fixture
def sse_helper(mock_liebherr_client: MagicMock) -> SSEStreamHelper:
    """Return the SSE stream helper for the mocked client."""
    return mock_liebherr_client._sse_helper


@pytest.fixture
def platforms() -> list[Platform]:
    """Fixture to specify platforms to test."""
    return [Platform.SENSOR]


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_liebherr_client: MagicMock,
    platforms: list[Platform],
) -> MockConfigEntry:
    """Set up the Liebherr integration for testing."""
    mock_config_entry.add_to_hass(hass)

    with patch("homeassistant.components.liebherr.PLATFORMS", platforms):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    return mock_config_entry
