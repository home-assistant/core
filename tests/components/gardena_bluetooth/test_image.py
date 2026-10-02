"""Test Gardena Bluetooth image entities."""

from collections.abc import Awaitable, Callable, Generator, Iterable
from http import HTTPStatus
from unittest.mock import Mock, patch

from aiohttp.test_utils import TestClient
from gardena_bluetooth.const import (
    AquaContour,
    AquaContourContours,
    AquaContourPosition,
    Spray,
)
from gardena_bluetooth.exceptions import CharacteristicNoAccess
from gardena_bluetooth.parse import CharacteristicContourPoints
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.gardena_bluetooth.coordinator import SEGMENTED_SCAN_COUNT
from homeassistant.components.gardena_bluetooth.image import CONTOURS
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import AQUA_CONTOUR_SERVICE_INFO, setup_entry

from tests.common import snapshot_platform
from tests.typing import ClientSessionGenerator

pytestmark = pytest.mark.usefixtures("constant_advertisements")

ENTITY_ID = "image.mock_title_contour_1"


def _contour_reads(client: Mock) -> int:
    """Count how many segmented contour reads the client was asked for."""
    return sum(
        isinstance(args[0], CharacteristicContourPoints)
        for args, _ in client.read_char.call_args_list
    )


async def _contour(client: TestClient, entity_id: str) -> str:
    """Fetch the svg an image entity currently serves."""
    resp = await client.get(f"/api/image_proxy/{entity_id}")
    assert resp.status == HTTPStatus.OK
    return (await resp.read()).decode()


def _encode(points: Iterable[tuple[int, int]]) -> bytes:
    """Encode angle and distance pairs the way the device transmits them."""
    return b"".join(
        bytes([angle >> 1, ((angle & 1) << 7) | distance // 10])
        for angle, distance in points
    )


@pytest.fixture(autouse=True)
def mock_getrandbits() -> Generator[None]:
    """Mock image access token which normally is randomized."""
    with patch(
        "homeassistant.components.image.SystemRandom.getrandbits",
        return_value=1,
    ):
        yield


@pytest.fixture
def mock_contours(
    mock_read_char_raw: dict[str, bytes | Exception],
) -> dict[str, bytes | Exception]:
    """Mock contour data on the device."""
    mock_read_char_raw.update(
        {
            # The device exposes the pair the segmented read is written to and
            # received on; the five contours are virtual characteristics on it
            AquaContourContours.contour_receive.unique_id: b"",
            AquaContourContours.contour_transmit.unique_id: b"",
            AquaContourContours.contour_points_1.unique_id: _encode(
                [(0, 900), (90, 1200), (180, 900), (270, 600)]
            ),
            AquaContourContours.contour_points_2.unique_id: _encode(
                [(0, 500), (90, 800), (180, 500), (270, 800)]
            ),
            AquaContourContours.contour_points_3.unique_id: _encode(
                [(angle % 360, 900) for angle in range(300, 421, 10)]
            ),
            AquaContourContours.contour_points_4.unique_id: b"",
            AquaContourContours.contour_points_5.unique_id: b"",
            # Position 2 is assigned contour 1, with the sprinkler throwing
            # 700 out at 45 degrees.
            AquaContour.active_contour.unique_id: AquaContour.active_contour.encode(
                [3, 1, 2, 4, 5]
            ),
            AquaContourPosition.active_position.unique_id: (
                AquaContourPosition.active_position.encode(2)
            ),
            Spray.current_sector.unique_id: Spray.current_sector.encode(45),
            Spray.current_distance.unique_id: Spray.current_distance.encode(700),
        }
    )
    return mock_read_char_raw


@pytest.mark.usefixtures("mock_contours")
async def test_setup(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test setup creates expected entities."""
    entry = await setup_entry(
        hass, platforms=[Platform.IMAGE], service_info=AQUA_CONTOUR_SERVICE_INFO
    )
    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)


@pytest.mark.usefixtures("mock_contours")
@pytest.mark.parametrize(
    "entity_id",
    [
        "image.mock_title_contour_1",
        "image.mock_title_active_contour",
    ],
)
async def test_image_content(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    snapshot: SnapshotAssertion,
    entity_id: str,
) -> None:
    """Test the rendered contour is served as an svg."""
    await setup_entry(
        hass, platforms=[Platform.IMAGE], service_info=AQUA_CONTOUR_SERVICE_INFO
    )

    client = await hass_client()
    resp = await client.get(f"/api/image_proxy/{entity_id}")
    assert resp.status == HTTPStatus.OK
    assert resp.content_type == "image/svg+xml"
    assert (await resp.read()).decode() == snapshot


@pytest.mark.usefixtures("mock_contours")
async def test_image_without_contour(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test a contour slot that has no points has no image to serve."""
    await setup_entry(
        hass, platforms=[Platform.IMAGE], service_info=AQUA_CONTOUR_SERVICE_INFO
    )

    state = hass.states.get("image.mock_title_contour_4")
    assert state
    assert state.state == "unknown"
    assert "entity_picture" not in state.attributes

    client = await hass_client()
    resp = await client.get("/api/image_proxy/image.mock_title_contour_4")
    assert resp.status == HTTPStatus.INTERNAL_SERVER_ERROR


@pytest.mark.usefixtures("mock_contours")
async def test_contour_cleared_after_being_present(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_read_char_raw: dict[str, bytes | Exception],
    scan_step: Callable[[], Awaitable[None]],
) -> None:
    """Test a contour that is taught and then cleared goes back to unknown."""
    await setup_entry(
        hass, platforms=[Platform.IMAGE], service_info=AQUA_CONTOUR_SERVICE_INFO
    )

    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.state != "unknown"
    assert "entity_picture" in state.attributes

    client = await hass_client()
    resp = await client.get(f"/api/image_proxy/{ENTITY_ID}")
    assert resp.status == HTTPStatus.OK

    mock_read_char_raw[AquaContourContours.contour_points_1.unique_id] = b""
    for _ in range(SEGMENTED_SCAN_COUNT):
        await scan_step()

    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.state == "unknown"
    assert "entity_picture" not in state.attributes

    resp = await client.get(f"/api/image_proxy/{ENTITY_ID}")
    assert resp.status == HTTPStatus.INTERNAL_SERVER_ERROR


async def test_active_contour_follows_position(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_contours: dict[str, bytes | Exception],
    scan_step: Callable[[], Awaitable[None]],
) -> None:
    """Test the position selects which contour is drawn."""
    await setup_entry(
        hass, platforms=[Platform.IMAGE], service_info=AQUA_CONTOUR_SERVICE_INFO
    )
    client = await hass_client()
    active = "image.mock_title_active_contour"

    # Position 2 is assigned contour 1, position 3 is assigned contour 2. Stop
    # watering so the spray is not drawn over the contour being compared.
    mock_contours[Spray.current_distance.unique_id] = Spray.current_distance.encode(0)
    await scan_step()
    assert await _contour(client, active) == await _contour(
        client, "image.mock_title_contour_1"
    )

    mock_contours[AquaContourPosition.active_position.unique_id] = (
        AquaContourPosition.active_position.encode(3)
    )
    await scan_step()

    assert await _contour(client, active) == await _contour(
        client, "image.mock_title_contour_2"
    )


@pytest.mark.usefixtures("mock_contours")
async def test_active_contour_idle_drops_spray(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_read_char_raw: dict[str, bytes | Exception],
    scan_step: Callable[[], Awaitable[None]],
) -> None:
    """Test the spray is only drawn while a contour is being watered."""
    await setup_entry(
        hass, platforms=[Platform.IMAGE], service_info=AQUA_CONTOUR_SERVICE_INFO
    )
    client = await hass_client()

    watering = await _contour(client, "image.mock_title_active_contour")
    assert watering != await _contour(client, "image.mock_title_contour_1")

    mock_read_char_raw[Spray.current_distance.unique_id] = (
        Spray.current_distance.encode(0)
    )
    await scan_step()

    # Idle keeps the contour on screen, just without the jet drawn across it.
    idle = await _contour(client, "image.mock_title_active_contour")
    assert idle == await _contour(client, "image.mock_title_contour_1")


@pytest.mark.usefixtures("mock_contours")
async def test_contour_refresh(
    hass: HomeAssistant,
    mock_client: Mock,
    scan_step: Callable[[], Awaitable[None]],
) -> None:
    """Test the slow segmented reads run on their own slower cadence."""
    await setup_entry(
        hass, platforms=[Platform.IMAGE], service_info=AQUA_CONTOUR_SERVICE_INFO
    )
    assert _contour_reads(mock_client) == len(CONTOURS)

    # In between they are carried over from the previous poll.
    for _ in range(SEGMENTED_SCAN_COUNT - 1):
        await scan_step()
    assert _contour_reads(mock_client) == len(CONTOURS)

    await scan_step()

    assert _contour_reads(mock_client) == 2 * len(CONTOURS)


async def test_contour_read_failure(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_contours: dict[str, bytes | Exception],
) -> None:
    """Test an unreadable contour leaves the others rendered."""
    mock_contours[AquaContourContours.contour_points_1.unique_id] = (
        CharacteristicNoAccess("Mock failure")
    )

    await setup_entry(
        hass, platforms=[Platform.IMAGE], service_info=AQUA_CONTOUR_SERVICE_INFO
    )

    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.state == "unknown"

    client = await hass_client()
    assert await _contour(client, "image.mock_title_contour_2")
