"""Test ONVIF config flow."""
from unittest.mock import MagicMock, patch

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.onvif import config_flow

from . import (
    HOST,
    MAC,
    NAME,
    PASSWORD,
    PORT,
    URN,
    USERNAME,
    setup_mock_device,
    setup_mock_onvif_camera,
    setup_onvif_integration,
)

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


async def test_flow_discovered_devices(hass):
    """Test that config flow works for discovered devices."""

    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
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
            result["flow_id"], user_input={"auto": True}
        )

        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "device"
        assert len(result["data_schema"].schema[config_flow.CONF_HOST].container) == 3

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={config_flow.CONF_HOST: f"{URN} ({HOST})"}
        )

        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "configure"

        with patch(
            "homeassistant.components.onvif.async_setup_entry", return_value=True
        ) as mock_setup_entry:
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                user_input={
                    config_flow.CONF_USERNAME: USERNAME,
                    config_flow.CONF_PASSWORD: PASSWORD,
                },
            )

            await hass.async_block_till_done()
            assert len(mock_setup_entry.mock_calls) == 1

        assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
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
        config_flow.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
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
            result["flow_id"], user_input={"auto": True}
        )

        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "device"
        assert len(result["data_schema"].schema[config_flow.CONF_HOST].container) == 2

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={config_flow.CONF_HOST: config_flow.CONF_MANUAL_INPUT},
        )

        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "configure"


async def test_flow_discovered_no_device(hass):
    """Test that config flow discovery no device."""
    await setup_onvif_integration(hass)

    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"

    with patch(
        "homeassistant.components.onvif.config_flow.get_device"
    ) as mock_onvif_camera, patch(
        "homeassistant.components.onvif.config_flow.wsdiscovery"
    ) as mock_discovery, patch(
        "homeassistant.components.onvif.ONVIFDevice"
    ) as mock_device:
        setup_mock_onvif_camera(mock_onvif_camera)
        mock_discovery.return_value = []
        setup_mock_device(mock_device)

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={"auto": True}
        )

        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "configure"


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
        config_flow.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
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
            result["flow_id"], user_input={"auto": True}
        )

        # It should skip to manual entry if the only devices are already configured
        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "configure"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                config_flow.CONF_NAME: NAME,
                config_flow.CONF_HOST: HOST,
                config_flow.CONF_PORT: PORT,
                config_flow.CONF_USERNAME: USERNAME,
                config_flow.CONF_PASSWORD: PASSWORD,
            },
        )

        # It should abort if already configured and entered manually
        assert result["type"] == data_entry_flow.FlowResultType.ABORT


async def test_flow_manual_entry(hass):
    """Test that config flow works for discovered devices."""
    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
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
            user_input={"auto": False},
        )

        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "configure"

        with patch(
            "homeassistant.components.onvif.async_setup_entry", return_value=True
        ) as mock_setup_entry:
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                user_input={
                    config_flow.CONF_NAME: NAME,
                    config_flow.CONF_HOST: HOST,
                    config_flow.CONF_PORT: PORT,
                    config_flow.CONF_USERNAME: USERNAME,
                    config_flow.CONF_PASSWORD: PASSWORD,
                },
            )

            await hass.async_block_till_done()
            assert len(mock_setup_entry.mock_calls) == 1

        assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
        assert result["title"] == f"{NAME} - {MAC}"
        assert result["data"] == {
            config_flow.CONF_NAME: NAME,
            config_flow.CONF_HOST: HOST,
            config_flow.CONF_PORT: PORT,
            config_flow.CONF_USERNAME: USERNAME,
            config_flow.CONF_PASSWORD: PASSWORD,
        }


async def test_option_flow(hass):
    """Test config flow options."""
    entry, _, _ = await setup_onvif_integration(hass)

    result = await hass.config_entries.options.async_init(
        entry.entry_id, context={"show_advanced_options": True}
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "onvif_devices"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            config_flow.CONF_EXTRA_ARGUMENTS: "",
            config_flow.CONF_RTSP_TRANSPORT: list(config_flow.RTSP_TRANSPORTS)[1],
            config_flow.CONF_USE_WALLCLOCK_AS_TIMESTAMPS: True,
        },
    )

    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        config_flow.CONF_EXTRA_ARGUMENTS: "",
        config_flow.CONF_RTSP_TRANSPORT: list(config_flow.RTSP_TRANSPORTS)[1],
        config_flow.CONF_USE_WALLCLOCK_AS_TIMESTAMPS: True,
    }
