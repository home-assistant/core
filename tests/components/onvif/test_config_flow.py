"""Test ONVIF config flow."""
from asyncio import Future

from asynctest import MagicMock, patch

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.onvif import config_flow

from tests.common import MockConfigEntry

URN = "urn:uuid:123456789"
NAME = "TestCamera"
HOST = "1.2.3.4"
PORT = 80
USERNAME = "admin"
PASSWORD = "12345"
MAC = "aa:bb:cc:dd:ee"


def setup_mock_onvif_device(mock_device, two_profiles=False):
    """Prepare mock ONVIF device."""
    devicemgmt = MagicMock()

    interface = MagicMock()
    interface.Enabled = True
    interface.Info.HwAddress = MAC

    devicemgmt.GetNetworkInterfaces.return_value = Future()
    devicemgmt.GetNetworkInterfaces.return_value.set_result([interface])

    media_service = MagicMock()

    profile1 = MagicMock()
    profile1.VideoEncoderConfiguration.Encoding = "H264"
    profile2 = MagicMock()
    profile2.VideoEncoderConfiguration.Encoding = "H264" if two_profiles else "MJPEG"

    media_service.GetProfiles.return_value = Future()
    media_service.GetProfiles.return_value.set_result([profile1, profile2])

    mock_device.update_xaddrs.return_value = Future()
    mock_device.update_xaddrs.return_value.set_result(True)
    mock_device.create_devicemgmt_service = MagicMock(return_value=devicemgmt)
    mock_device.create_media_service = MagicMock(return_value=media_service)

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
        return mock_device

    mock_device.side_effect = mock_constructor


def setup_mock_discovery(mock_discovery, with_name=False, with_mac=False):
    """Prepare mock discovery result."""
    service = MagicMock()
    service.getXAddrs = MagicMock(
        return_value=[f"http://{HOST}:{PORT}/onvif/device_service"]
    )
    service.getEPR = MagicMock(return_value=URN)
    scopes = []
    if with_name:
        scope = MagicMock()
        scope.getValue = MagicMock(return_value=f"onvif://www.onvif.org/name/{NAME}")
        scopes.append(scope)
    if with_mac:
        scope = MagicMock()
        scope.getValue = MagicMock(return_value=f"onvif://www.onvif.org/mac/{MAC}")
        scopes.append(scope)
    service.getScopes = MagicMock(return_value=scopes)
    mock_discovery.return_value = [service]


def setup_mock_camera(mock_camera):
    """Prepare mock HASS camera."""
    mock_camera.async_initialize.return_value = Future()
    mock_camera.async_initialize.return_value.set_result(True)

    def mock_constructor(hass, config):
        """Fake the controller constructor."""
        return mock_camera

    mock_camera.side_effect = mock_constructor


async def setup_onvif_integration(
    hass, config=None, options=None, entry_id="1", source="user",
):
    """Create an ONVIF config entry."""
    if not config:
        config = {
            config_flow.CONF_NAME: NAME,
            config_flow.CONF_HOST: HOST,
            config_flow.CONF_PORT: PORT,
            config_flow.CONF_USERNAME: USERNAME,
            config_flow.CONF_PASSWORD: PASSWORD,
            config_flow.CONF_PROFILE: [0],
        }

    config_entry = MockConfigEntry(
        domain=config_flow.DOMAIN,
        source=source,
        data={**config},
        connection_class=config_entries.CONN_CLASS_LOCAL_PUSH,
        options=options or {},
        entry_id=entry_id,
        unique_id=MAC,
    )
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.onvif.config_flow.get_device"
    ) as mock_device, patch(
        "homeassistant.components.onvif.config_flow.wsdiscovery"
    ) as mock_discovery, patch(
        "homeassistant.components.onvif.camera.ONVIFHassCamera"
    ) as mock_camera:
        setup_mock_onvif_device(mock_device, two_profiles=True)
        # no discovery
        mock_discovery.return_value = []
        setup_mock_camera(mock_camera)
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
    ) as mock_device, patch(
        "homeassistant.components.onvif.config_flow.wsdiscovery"
    ) as mock_discovery, patch(
        "homeassistant.components.onvif.camera.ONVIFHassCamera"
    ) as mock_camera:
        setup_mock_onvif_device(mock_device)
        setup_mock_discovery(mock_discovery)
        setup_mock_camera(mock_camera)

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "device"
        assert len(result["data_schema"].schema[config_flow.CONF_HOST].container) == 2

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
            config_flow.CONF_PROFILE: [0],
        }


async def test_flow_discovery_ignore_existing_and_abort(hass):
    """Test that config flow discovery ignores setup devices."""
    await setup_onvif_integration(hass)

    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN, context={"source": "user"}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"

    with patch(
        "homeassistant.components.onvif.config_flow.get_device"
    ) as mock_device, patch(
        "homeassistant.components.onvif.config_flow.wsdiscovery"
    ) as mock_discovery, patch(
        "homeassistant.components.onvif.camera.ONVIFHassCamera"
    ) as mock_camera:
        setup_mock_onvif_device(mock_device)
        setup_mock_discovery(mock_discovery, with_name=True, with_mac=True)
        setup_mock_camera(mock_camera)

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
    ) as mock_device, patch(
        "homeassistant.components.onvif.config_flow.wsdiscovery"
    ) as mock_discovery, patch(
        "homeassistant.components.onvif.camera.ONVIFHassCamera"
    ) as mock_camera:
        setup_mock_onvif_device(mock_device, two_profiles=True)
        # no discovery
        mock_discovery.return_value = []
        setup_mock_camera(mock_camera)

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={config_flow.CONF_HOST: config_flow.CONF_MANUAL_INPUT},
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
            config_flow.CONF_PROFILE: [0, 1],
        }


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
