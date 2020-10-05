"""Test ONVIF config flow."""
from onvif.exceptions import ONVIFError
from zeep.exceptions import Fault

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.onvif import config_flow

from tests.async_mock import AsyncMock, MagicMock, patch
from tests.common import MockConfigEntry

URN = "urn:uuid:123456789"
NAME = "TestCamera"
HOST = "1.2.3.4"
PORT = 80
USERNAME = "admin"
PASSWORD = "12345"
MAC = "aa:bb:cc:dd:ee"
SERIAL_NUMBER = "ABCDEFGHIJK"

DISCOVERY = [
    {
        "EPR": URN,
        config_flow.CONF_NAME: NAME,
        config_flow.CONF_HOST: HOST,
        config_flow.CONF_PORT: PORT,
        "MAC": MAC,
    },
    {
        "EPR": "urn:uuid:987654321",
        config_flow.CONF_NAME: "TestCamera2",
        config_flow.CONF_HOST: "5.6.7.8",
        config_flow.CONF_PORT: PORT,
        "MAC": "ee:dd:cc:bb:aa",
    },
]


def setup_mock_onvif_camera(
    mock_onvif_camera,
    with_h264=True,
    two_profiles=False,
    with_interfaces=True,
    with_serial=True,
):
    """Prepare mock onvif.ONVIFCamera."""
    devicemgmt = MagicMock()

    device_info = MagicMock()
    device_info.SerialNumber = SERIAL_NUMBER if with_serial else None
    devicemgmt.GetDeviceInformation = AsyncMock(return_value=device_info)

    interface = MagicMock()
    interface.Enabled = True
    interface.Info.HwAddress = MAC

    devicemgmt.GetNetworkInterfaces = AsyncMock(
        return_value=[interface] if with_interfaces else []
    )

    media_service = MagicMock()

    profile1 = MagicMock()
    profile1.VideoEncoderConfiguration.Encoding = "H264" if with_h264 else "MJPEG"
    profile2 = MagicMock()
    profile2.VideoEncoderConfiguration.Encoding = "H264" if two_profiles else "MJPEG"

    media_service.GetProfiles = AsyncMock(return_value=[profile1, profile2])

    mock_onvif_camera.update_xaddrs = AsyncMock(return_value=True)
    mock_onvif_camera.create_devicemgmt_service = MagicMock(return_value=devicemgmt)
    mock_onvif_camera.create_media_service = MagicMock(return_value=media_service)

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


def setup_mock_discovery(
    mock_discovery, with_name=False, with_mac=False, two_devices=False
):
    """Prepare mock discovery result."""
    services = []
    for item in DISCOVERY:
        service = MagicMock()
        service.getXAddrs = MagicMock(
            return_value=[
                f"http://{item[config_flow.CONF_HOST]}:{item[config_flow.CONF_PORT]}/onvif/device_service"
            ]
        )
        service.getEPR = MagicMock(return_value=item["EPR"])
        scopes = []
        if with_name:
            scope = MagicMock()
            scope.getValue = MagicMock(
                return_value=f"onvif://www.onvif.org/name/{item[config_flow.CONF_NAME]}"
            )
            scopes.append(scope)
        if with_mac:
            scope = MagicMock()
            scope.getValue = MagicMock(
                return_value=f"onvif://www.onvif.org/mac/{item['MAC']}"
            )
            scopes.append(scope)
        service.getScopes = MagicMock(return_value=scopes)
        services.append(service)
    mock_discovery.return_value = services


def setup_mock_device(mock_device):
    """Prepare mock ONVIFDevice."""
    mock_device.async_setup = AsyncMock(return_value=True)

    def mock_constructor(hass, config):
        """Fake the controller constructor."""
        return mock_device

    mock_device.side_effect = mock_constructor


async def setup_onvif_integration(
    hass,
    config=None,
    options=None,
    unique_id=MAC,
    entry_id="1",
    source="user",
):
    """Create an ONVIF config entry."""
    if not config:
        config = {
            config_flow.CONF_NAME: NAME,
            config_flow.CONF_HOST: HOST,
            config_flow.CONF_PORT: PORT,
            config_flow.CONF_USERNAME: USERNAME,
            config_flow.CONF_PASSWORD: PASSWORD,
        }

    config_entry = MockConfigEntry(
        domain=config_flow.DOMAIN,
        source=source,
        data={**config},
        connection_class=config_entries.CONN_CLASS_LOCAL_PUSH,
        options=options or {},
        entry_id=entry_id,
        unique_id=unique_id,
    )
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.onvif.config_flow.get_device"
    ) as mock_onvif_camera, patch(
        "homeassistant.components.onvif.config_flow.wsdiscovery"
    ) as mock_discovery, patch(
        "homeassistant.components.onvif.ONVIFDevice"
    ) as mock_device:
        setup_mock_onvif_camera(mock_onvif_camera, two_profiles=True)
        # no discovery
        mock_discovery.return_value = []
        setup_mock_device(mock_device)
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
    return config_entry


async def test_flow_discovered_devices(hass):
    """Test that config flow works for discovered devices."""

    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN, context={"source": "user"}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"

    with patch(
        "homeassistant.components.onvif.config_flow.get_device"
    ) as mock_onvif_camera, patch(
        "homeassistant.components.onvif.config_flow.wsdiscovery"
    ) as mock_discovery, patch(
        "homeassistant.components.onvif.ONVIFDevice"
    ) as mock_device:
        setup_mock_onvif_camera(mock_onvif_camera)
        setup_mock_discovery(mock_discovery)
        setup_mock_device(mock_device)

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "device"
        assert len(result["data_schema"].schema[config_flow.CONF_HOST].container) == 3

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={config_flow.CONF_HOST: f"{URN} ({HOST})"}
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "auth"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                config_flow.CONF_USERNAME: USERNAME,
                config_flow.CONF_PASSWORD: PASSWORD,
            },
        )

        await hass.async_block_till_done()

        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert result["title"] == f"{URN} - {MAC}"
        assert result["data"] == {
            config_flow.CONF_NAME: URN,
            config_flow.CONF_HOST: HOST,
            config_flow.CONF_PORT: PORT,
            config_flow.CONF_USERNAME: USERNAME,
            config_flow.CONF_PASSWORD: PASSWORD,
        }


async def test_flow_discovered_devices_ignore_configured_manual_input(hass):
    """Test that config flow discovery ignores configured devices."""
    await setup_onvif_integration(hass)

    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN, context={"source": "user"}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"

    with patch(
        "homeassistant.components.onvif.config_flow.get_device"
    ) as mock_onvif_camera, patch(
        "homeassistant.components.onvif.config_flow.wsdiscovery"
    ) as mock_discovery, patch(
        "homeassistant.components.onvif.ONVIFDevice"
    ) as mock_device:
        setup_mock_onvif_camera(mock_onvif_camera)
        setup_mock_discovery(mock_discovery, with_mac=True)
        setup_mock_device(mock_device)

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "device"
        assert len(result["data_schema"].schema[config_flow.CONF_HOST].container) == 2

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={config_flow.CONF_HOST: config_flow.CONF_MANUAL_INPUT},
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "manual_input"


async def test_flow_discovery_ignore_existing_and_abort(hass):
    """Test that config flow discovery ignores setup devices."""
    await setup_onvif_integration(hass)
    await setup_onvif_integration(
        hass,
        config={
            config_flow.CONF_NAME: DISCOVERY[1]["EPR"],
            config_flow.CONF_HOST: DISCOVERY[1][config_flow.CONF_HOST],
            config_flow.CONF_PORT: DISCOVERY[1][config_flow.CONF_PORT],
            config_flow.CONF_USERNAME: "",
            config_flow.CONF_PASSWORD: "",
        },
        unique_id=DISCOVERY[1]["MAC"],
        entry_id="2",
    )

    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN, context={"source": "user"}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"

    with patch(
        "homeassistant.components.onvif.config_flow.get_device"
    ) as mock_onvif_camera, patch(
        "homeassistant.components.onvif.config_flow.wsdiscovery"
    ) as mock_discovery, patch(
        "homeassistant.components.onvif.ONVIFDevice"
    ) as mock_device:
        setup_mock_onvif_camera(mock_onvif_camera)
        setup_mock_discovery(mock_discovery, with_name=True, with_mac=True)
        setup_mock_device(mock_device)

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )

        # It should skip to manual entry if the only devices are already configured
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "manual_input"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                config_flow.CONF_NAME: NAME,
                config_flow.CONF_HOST: HOST,
                config_flow.CONF_PORT: PORT,
            },
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "auth"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                config_flow.CONF_USERNAME: USERNAME,
                config_flow.CONF_PASSWORD: PASSWORD,
            },
        )

        # It should abort if already configured and entered manually
        assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT


async def test_flow_manual_entry(hass):
    """Test that config flow works for discovered devices."""
    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN, context={"source": "user"}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"

    with patch(
        "homeassistant.components.onvif.config_flow.get_device"
    ) as mock_onvif_camera, patch(
        "homeassistant.components.onvif.config_flow.wsdiscovery"
    ) as mock_discovery, patch(
        "homeassistant.components.onvif.ONVIFDevice"
    ) as mock_device:
        setup_mock_onvif_camera(mock_onvif_camera, two_profiles=True)
        # no discovery
        mock_discovery.return_value = []
        setup_mock_device(mock_device)

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={},
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "manual_input"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                config_flow.CONF_NAME: NAME,
                config_flow.CONF_HOST: HOST,
                config_flow.CONF_PORT: PORT,
            },
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "auth"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                config_flow.CONF_USERNAME: USERNAME,
                config_flow.CONF_PASSWORD: PASSWORD,
            },
        )

        await hass.async_block_till_done()

        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert result["title"] == f"{NAME} - {MAC}"
        assert result["data"] == {
            config_flow.CONF_NAME: NAME,
            config_flow.CONF_HOST: HOST,
            config_flow.CONF_PORT: PORT,
            config_flow.CONF_USERNAME: USERNAME,
            config_flow.CONF_PASSWORD: PASSWORD,
        }


async def test_flow_import_no_mac(hass):
    """Test that config flow uses Serial Number when no MAC available."""
    with patch(
        "homeassistant.components.onvif.config_flow.get_device"
    ) as mock_onvif_camera, patch(
        "homeassistant.components.onvif.ONVIFDevice"
    ) as mock_device:
        setup_mock_onvif_camera(mock_onvif_camera, with_interfaces=False)
        setup_mock_device(mock_device)

        result = await hass.config_entries.flow.async_init(
            config_flow.DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={
                config_flow.CONF_NAME: NAME,
                config_flow.CONF_HOST: HOST,
                config_flow.CONF_PORT: PORT,
                config_flow.CONF_USERNAME: USERNAME,
                config_flow.CONF_PASSWORD: PASSWORD,
            },
        )

        await hass.async_block_till_done()

        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert result["title"] == f"{NAME} - {SERIAL_NUMBER}"
        assert result["data"] == {
            config_flow.CONF_NAME: NAME,
            config_flow.CONF_HOST: HOST,
            config_flow.CONF_PORT: PORT,
            config_flow.CONF_USERNAME: USERNAME,
            config_flow.CONF_PASSWORD: PASSWORD,
        }


async def test_flow_import_no_mac_or_serial(hass):
    """Test that config flow fails when no MAC or Serial Number available."""
    with patch(
        "homeassistant.components.onvif.config_flow.get_device"
    ) as mock_onvif_camera:
        setup_mock_onvif_camera(
            mock_onvif_camera, with_interfaces=False, with_serial=False
        )

        result = await hass.config_entries.flow.async_init(
            config_flow.DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={
                config_flow.CONF_NAME: NAME,
                config_flow.CONF_HOST: HOST,
                config_flow.CONF_PORT: PORT,
                config_flow.CONF_USERNAME: USERNAME,
                config_flow.CONF_PASSWORD: PASSWORD,
            },
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
        assert result["reason"] == "no_mac"


async def test_flow_import_no_h264(hass):
    """Test that config flow fails when no MAC available."""
    with patch(
        "homeassistant.components.onvif.config_flow.get_device"
    ) as mock_onvif_camera:
        setup_mock_onvif_camera(mock_onvif_camera, with_h264=False)

        result = await hass.config_entries.flow.async_init(
            config_flow.DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={
                config_flow.CONF_NAME: NAME,
                config_flow.CONF_HOST: HOST,
                config_flow.CONF_PORT: PORT,
                config_flow.CONF_USERNAME: USERNAME,
                config_flow.CONF_PASSWORD: PASSWORD,
            },
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
        assert result["reason"] == "no_h264"


async def test_flow_import_onvif_api_error(hass):
    """Test that config flow fails when ONVIF API fails."""
    with patch(
        "homeassistant.components.onvif.config_flow.get_device"
    ) as mock_onvif_camera:
        setup_mock_onvif_camera(mock_onvif_camera)
        mock_onvif_camera.create_devicemgmt_service = MagicMock(
            side_effect=ONVIFError("Could not get device mgmt service")
        )

        result = await hass.config_entries.flow.async_init(
            config_flow.DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={
                config_flow.CONF_NAME: NAME,
                config_flow.CONF_HOST: HOST,
                config_flow.CONF_PORT: PORT,
                config_flow.CONF_USERNAME: USERNAME,
                config_flow.CONF_PASSWORD: PASSWORD,
            },
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
        assert result["reason"] == "onvif_error"


async def test_flow_import_onvif_auth_error(hass):
    """Test that config flow fails when ONVIF API fails."""
    with patch(
        "homeassistant.components.onvif.config_flow.get_device"
    ) as mock_onvif_camera:
        setup_mock_onvif_camera(mock_onvif_camera)
        mock_onvif_camera.create_devicemgmt_service = MagicMock(
            side_effect=Fault("Auth Error")
        )

        result = await hass.config_entries.flow.async_init(
            config_flow.DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={
                config_flow.CONF_NAME: NAME,
                config_flow.CONF_HOST: HOST,
                config_flow.CONF_PORT: PORT,
                config_flow.CONF_USERNAME: USERNAME,
                config_flow.CONF_PASSWORD: PASSWORD,
            },
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "auth"
        assert result["errors"]["base"] == "connection_failed"


async def test_option_flow(hass):
    """Test config flow options."""
    entry = await setup_onvif_integration(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "onvif_devices"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            config_flow.CONF_EXTRA_ARGUMENTS: "",
            config_flow.CONF_RTSP_TRANSPORT: config_flow.RTSP_TRANS_PROTOCOLS[1],
        },
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["data"] == {
        config_flow.CONF_EXTRA_ARGUMENTS: "",
        config_flow.CONF_RTSP_TRANSPORT: config_flow.RTSP_TRANS_PROTOCOLS[1],
    }
