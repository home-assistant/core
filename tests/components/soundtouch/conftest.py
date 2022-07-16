"""Fixtures for Bose SoundTouch integration tests."""
import pytest
from requests_mock import Mocker

from homeassistant.components.media_player.const import DOMAIN as MEDIA_PLAYER_DOMAIN
from homeassistant.components.soundtouch.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_NAME

from tests.common import MockConfigEntry, load_fixture

DEVICE_1_ID = "020000000001"
DEVICE_2_ID = "020000000002"
DEVICE_1_IP = "192.168.42.1"
DEVICE_2_IP = "192.168.42.2"
DEVICE_1_URL = f"http://{DEVICE_1_IP}:8090"
DEVICE_2_URL = f"http://{DEVICE_2_IP}:8090"
DEVICE_1_NAME = "My SoundTouch 1"
DEVICE_2_NAME = "My SoundTouch 2"
DEVICE_1_ENTITY_ID = f"{MEDIA_PLAYER_DOMAIN}.my_soundtouch_1"
DEVICE_2_ENTITY_ID = f"{MEDIA_PLAYER_DOMAIN}.my_soundtouch_2"


# pylint: disable=redefined-outer-name


@pytest.fixture
def device1_config() -> MockConfigEntry:
    """Mock SoundTouch device 1 config entry."""
    yield MockConfigEntry(
        domain=DOMAIN,
        unique_id=DEVICE_1_ID,
        data={
            CONF_HOST: DEVICE_1_IP,
            CONF_NAME: "",
        },
    )


@pytest.fixture
def device2_config() -> MockConfigEntry:
    """Mock SoundTouch device 2 config entry."""
    yield MockConfigEntry(
        domain=DOMAIN,
        unique_id=DEVICE_2_ID,
        data={
            CONF_HOST: DEVICE_2_IP,
            CONF_NAME: "",
        },
    )


@pytest.fixture(scope="session")
def device1_info() -> str:
    """Load SoundTouch device 1 info response and return it."""
    return load_fixture("soundtouch/device1_info.xml")


@pytest.fixture(scope="session")
def device1_now_playing_aux() -> str:
    """Load SoundTouch device 1 now_playing response and return it."""
    return load_fixture("soundtouch/device1_now_playing_aux.xml")


@pytest.fixture(scope="session")
def device1_now_playing_bluetooth() -> str:
    """Load SoundTouch device 1 now_playing response and return it."""
    return load_fixture("soundtouch/device1_now_playing_bluetooth.xml")


@pytest.fixture(scope="session")
def device1_now_playing_radio() -> str:
    """Load SoundTouch device 1 now_playing response and return it."""
    return load_fixture("soundtouch/device1_now_playing_radio.xml")


@pytest.fixture(scope="session")
def device1_now_playing_standby() -> str:
    """Load SoundTouch device 1 now_playing response and return it."""
    return load_fixture("soundtouch/device1_now_playing_standby.xml")


@pytest.fixture(scope="session")
def device1_now_playing_upnp() -> str:
    """Load SoundTouch device 1 now_playing response and return it."""
    return load_fixture("soundtouch/device1_now_playing_upnp.xml")


@pytest.fixture(scope="session")
def device1_now_playing_upnp_paused() -> str:
    """Load SoundTouch device 1 now_playing response and return it."""
    return load_fixture("soundtouch/device1_now_playing_upnp_paused.xml")


@pytest.fixture(scope="session")
def device1_presets() -> str:
    """Load SoundTouch device 1 presets response and return it."""
    return load_fixture("soundtouch/device1_presets.xml")


@pytest.fixture(scope="session")
def device1_volume() -> str:
    """Load SoundTouch device 1 volume response and return it."""
    return load_fixture("soundtouch/device1_volume.xml")


@pytest.fixture(scope="session")
def device1_volume_muted() -> str:
    """Load SoundTouch device 1 volume response and return it."""
    return load_fixture("soundtouch/device1_volume_muted.xml")


@pytest.fixture(scope="session")
def device1_zone_master() -> str:
    """Load SoundTouch device 1 getZone response and return it."""
    return load_fixture("soundtouch/device1_getZone_master.xml")


@pytest.fixture(scope="session")
def device2_info() -> str:
    """Load SoundTouch device 2 info response and return it."""
    return load_fixture("soundtouch/device2_info.xml")


@pytest.fixture(scope="session")
def device2_volume() -> str:
    """Load SoundTouch device 2 volume response and return it."""
    return load_fixture("soundtouch/device2_volume.xml")


@pytest.fixture(scope="session")
def device2_now_playing_standby() -> str:
    """Load SoundTouch device 2 now_playing response and return it."""
    return load_fixture("soundtouch/device2_now_playing_standby.xml")


@pytest.fixture(scope="session")
def device2_zone_slave() -> str:
    """Load SoundTouch device 2 getZone response and return it."""
    return load_fixture("soundtouch/device2_getZone_slave.xml")


@pytest.fixture(scope="session")
def zone_empty() -> str:
    """Load empty SoundTouch getZone response and return it."""
    return load_fixture("soundtouch/getZone_empty.xml")


@pytest.fixture
def device1_requests_mock(
    requests_mock: Mocker,
    device1_info: str,
    device1_volume: str,
    device1_presets: str,
    device1_zone_master: str,
) -> Mocker:
    """Mock SoundTouch device 1 API - base URLs."""
    requests_mock.get(f"{DEVICE_1_URL}/info", text=device1_info)
    requests_mock.get(f"{DEVICE_1_URL}/volume", text=device1_volume)
    requests_mock.get(f"{DEVICE_1_URL}/presets", text=device1_presets)
    requests_mock.get(f"{DEVICE_1_URL}/getZone", text=device1_zone_master)
    yield requests_mock


@pytest.fixture
def device1_requests_mock_standby(
    device1_requests_mock: Mocker,
    device1_now_playing_standby: str,
):
    """Mock SoundTouch device 1 API - standby."""
    device1_requests_mock.get(
        f"{DEVICE_1_URL}/now_playing", text=device1_now_playing_standby
    )


@pytest.fixture
def device1_requests_mock_aux(
    device1_requests_mock: Mocker,
    device1_now_playing_aux: str,
):
    """Mock SoundTouch device 1 API - playing AUX."""
    device1_requests_mock.get(
        f"{DEVICE_1_URL}/now_playing", text=device1_now_playing_aux
    )


@pytest.fixture
def device1_requests_mock_bluetooth(
    device1_requests_mock: Mocker,
    device1_now_playing_bluetooth: str,
):
    """Mock SoundTouch device 1 API - playing bluetooth."""
    device1_requests_mock.get(
        f"{DEVICE_1_URL}/now_playing", text=device1_now_playing_bluetooth
    )


@pytest.fixture
def device1_requests_mock_radio(
    device1_requests_mock: Mocker,
    device1_now_playing_radio: str,
):
    """Mock SoundTouch device 1 API - playing radio."""
    device1_requests_mock.get(
        f"{DEVICE_1_URL}/now_playing", text=device1_now_playing_radio
    )


@pytest.fixture
def device1_requests_mock_upnp(
    device1_requests_mock: Mocker,
    device1_now_playing_upnp: str,
):
    """Mock SoundTouch device 1 API - playing UPNP."""
    device1_requests_mock.get(
        f"{DEVICE_1_URL}/now_playing", text=device1_now_playing_upnp
    )


@pytest.fixture
def device1_requests_mock_upnp_paused(
    device1_requests_mock: Mocker,
    device1_now_playing_upnp_paused: str,
):
    """Mock SoundTouch device 1 API - playing UPNP (paused)."""
    device1_requests_mock.get(
        f"{DEVICE_1_URL}/now_playing", text=device1_now_playing_upnp_paused
    )


@pytest.fixture
def device1_requests_mock_key(
    device1_requests_mock: Mocker,
):
    """Mock SoundTouch device 1 API - key endpoint."""
    yield device1_requests_mock.post(f"{DEVICE_1_URL}/key")


@pytest.fixture
def device1_requests_mock_volume(
    device1_requests_mock: Mocker,
):
    """Mock SoundTouch device 1 API - volume endpoint."""
    yield device1_requests_mock.post(f"{DEVICE_1_URL}/volume")


@pytest.fixture
def device1_requests_mock_select(
    device1_requests_mock: Mocker,
):
    """Mock SoundTouch device 1 API - select endpoint."""
    yield device1_requests_mock.post(f"{DEVICE_1_URL}/select")


@pytest.fixture
def device1_requests_mock_set_zone(
    device1_requests_mock: Mocker,
):
    """Mock SoundTouch device 1 API - setZone endpoint."""
    yield device1_requests_mock.post(f"{DEVICE_1_URL}/setZone")


@pytest.fixture
def device1_requests_mock_add_zone_slave(
    device1_requests_mock: Mocker,
):
    """Mock SoundTouch device 1 API - addZoneSlave endpoint."""
    yield device1_requests_mock.post(f"{DEVICE_1_URL}/addZoneSlave")


@pytest.fixture
def device1_requests_mock_remove_zone_slave(
    device1_requests_mock: Mocker,
):
    """Mock SoundTouch device 1 API - removeZoneSlave endpoint."""
    yield device1_requests_mock.post(f"{DEVICE_1_URL}/removeZoneSlave")


@pytest.fixture
def device1_requests_mock_dlna(
    device1_requests_mock: Mocker,
):
    """Mock SoundTouch device 1 API - DLNA endpoint."""
    yield device1_requests_mock.post(f"http://{DEVICE_1_IP}:8091/AVTransport/Control")


@pytest.fixture
def device2_requests_mock_standby(
    requests_mock: Mocker,
    device2_info: str,
    device2_volume: str,
    device2_now_playing_standby: str,
    device2_zone_slave: str,
) -> Mocker:
    """Mock SoundTouch device 2 API."""
    requests_mock.get(f"{DEVICE_2_URL}/info", text=device2_info)
    requests_mock.get(f"{DEVICE_2_URL}/volume", text=device2_volume)
    requests_mock.get(f"{DEVICE_2_URL}/now_playing", text=device2_now_playing_standby)
    requests_mock.get(f"{DEVICE_2_URL}/getZone", text=device2_zone_slave)

    yield requests_mock
