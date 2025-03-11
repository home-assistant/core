"""Tests for the ONVIF integration."""

from unittest.mock import AsyncMock, MagicMock, patch

from onvif.exceptions import ONVIFError
from zeep.exceptions import Fault

from homeassistant import config_entries
from homeassistant.components.onvif import config_flow
from homeassistant.components.onvif.const import CONF_SNAPSHOT_AUTH
from homeassistant.components.onvif.models import (
    Capabilities,
    DeviceInfo,
    Profile,
    PullPointManagerState,
    Resolution,
    Video,
    WebHookManagerState,
)
from homeassistant.const import HTTP_DIGEST_AUTHENTICATION
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

URN = "urn:uuid:123456789"
NAME = "TestCamera"
HOST = "1.2.3.4"
PORT = 80
USERNAME = "admin"
PASSWORD = "12345"
MAC = "aa:bb:cc:dd:ee:ff"
SERIAL_NUMBER = "ABCDEFGHIJK"
MANUFACTURER = "TestManufacturer"
MODEL = "TestModel"
FIRMWARE_VERSION = "TestFirmwareVersion"


def setup_mock_onvif_camera(
    mock_onvif_camera,
    with_h264=True,
    two_profiles=False,
    with_interfaces=True,
    with_interfaces_not_implemented=False,
    with_serial=True,
    profiles_transient_failure=False,
    auth_fail=False,
    update_xaddrs_fail=False,
    no_profiles=False,
    auth_failure=False,
    wrong_port=False,
):
    """Prepare mock onvif.ONVIFCamera."""
    devicemgmt = MagicMock()

    device_info = MagicMock()
    device_info.SerialNumber = SERIAL_NUMBER if with_serial else None

    devicemgmt.GetDeviceInformation = AsyncMock(return_value=device_info)

    interface = MagicMock()
    interface.Enabled = True
    interface.Info.HwAddress = MAC

    if with_interfaces_not_implemented:
        devicemgmt.GetNetworkInterfaces = AsyncMock(
            side_effect=Fault("not implemented")
        )
    else:
        devicemgmt.GetNetworkInterfaces = AsyncMock(
            return_value=[interface] if with_interfaces else []
        )

    media_service = MagicMock()

    profile1 = MagicMock()
    profile1.VideoEncoderConfiguration.Encoding = "H264" if with_h264 else "MJPEG"
    profile2 = MagicMock()
    profile2.VideoEncoderConfiguration.Encoding = "H264" if two_profiles else "MJPEG"

    if auth_fail:
        media_service.GetProfiles = AsyncMock(side_effect=Fault("Authority failure"))
    elif profiles_transient_failure:
        media_service.GetProfiles = AsyncMock(side_effect=Fault("camera not ready"))
    elif no_profiles:
        media_service.GetProfiles = AsyncMock(return_value=[])
    else:
        media_service.GetProfiles = AsyncMock(return_value=[profile1, profile2])

    if wrong_port:
        mock_onvif_camera.update_xaddrs = AsyncMock(side_effect=AttributeError)
    elif auth_failure:
        mock_onvif_camera.update_xaddrs = AsyncMock(
            side_effect=Fault(
                "not authorized", subcodes=[MagicMock(text="NotAuthorized")]
            )
        )
    elif update_xaddrs_fail:
        mock_onvif_camera.update_xaddrs = AsyncMock(
            side_effect=ONVIFError("camera not ready")
        )
    else:
        mock_onvif_camera.update_xaddrs = AsyncMock(return_value=True)
    mock_onvif_camera.create_devicemgmt_service = AsyncMock(return_value=devicemgmt)
    mock_onvif_camera.create_media_service = AsyncMock(return_value=media_service)
    mock_onvif_camera.close = AsyncMock(return_value=None)
    mock_onvif_camera.xaddrs = {}
    mock_onvif_camera.services = {}

    def mock_constructor(
        host,
        port,
        user,
        passwd,
        wsdl_dir,
        encrypt=True,
        no_cache=False,
        adjust_time=False,
        transport=None,
    ):
        """Fake the controller constructor."""
        return mock_onvif_camera

    mock_onvif_camera.side_effect = mock_constructor


def setup_mock_device(mock_device, capabilities=None, profiles=None):
    """Prepare mock ONVIFDevice."""
    mock_device.async_setup = AsyncMock(return_value=True)
    mock_device.port = 80
    mock_device.available = True
    mock_device.name = NAME
    mock_device.info = DeviceInfo(
        MANUFACTURER,
        MODEL,
        FIRMWARE_VERSION,
        SERIAL_NUMBER,
        MAC,
    )
    mock_device.capabilities = capabilities or Capabilities(imaging=True, ptz=True)
    profile1 = Profile(
        index=0,
        token="dummy",
        name="profile1",
        video=Video("any", Resolution(640, 480)),
        ptz=None,
        video_source_token=None,
    )
    mock_device.profiles = profiles or [profile1]
    mock_device.events = MagicMock(
        webhook_manager=MagicMock(state=WebHookManagerState.STARTED),
        pullpoint_manager=MagicMock(state=PullPointManagerState.PAUSED),
    )

    def mock_constructor(
        hass: HomeAssistant, config: config_entries.ConfigEntry
    ) -> MagicMock:
        """Fake the controller constructor."""
        return mock_device

    mock_device.side_effect = mock_constructor


async def setup_onvif_integration(
    hass: HomeAssistant,
    config=None,
    options=None,
    unique_id=MAC,
    entry_id="1",
    source=config_entries.SOURCE_USER,
    capabilities=None,
) -> tuple[MockConfigEntry, MagicMock, MagicMock]:
    """Create an ONVIF config entry."""
    if not config:
        config = {
            config_flow.CONF_NAME: NAME,
            config_flow.CONF_HOST: HOST,
            config_flow.CONF_PORT: PORT,
            config_flow.CONF_USERNAME: USERNAME,
            config_flow.CONF_PASSWORD: PASSWORD,
            CONF_SNAPSHOT_AUTH: HTTP_DIGEST_AUTHENTICATION,
        }

    config_entry = MockConfigEntry(
        domain=config_flow.DOMAIN,
        source=source,
        data={**config},
        options=options or {},
        entry_id=entry_id,
        unique_id=unique_id,
    )
    config_entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.onvif.config_flow.get_device"
        ) as mock_onvif_camera,
        patch(
            "homeassistant.components.onvif.config_flow.wsdiscovery"
        ) as mock_discovery,
        patch("homeassistant.components.onvif.ONVIFDevice") as mock_device,
    ):
        setup_mock_onvif_camera(mock_onvif_camera, two_profiles=True)
        # no discovery
        mock_discovery.return_value = []
        setup_mock_device(mock_device, capabilities=capabilities)
        mock_device.device = mock_onvif_camera
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
    return config_entry, mock_onvif_camera, mock_device
