"""Test ONVIF config flow."""

import logging
from unittest.mock import MagicMock, patch

import pytest

from homeassistant import config_entries
from homeassistant.components import dhcp
from homeassistant.components.onvif import DOMAIN, config_flow
from homeassistant.config_entries import SOURCE_DHCP
from homeassistant.const import CONF_HOST, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import device_registry as dr

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
        "HARDWARE": "IPC model",
    },
    {
        "EPR": "urn:uuid:987654321",
        config_flow.CONF_NAME: "TestCamera2",
        config_flow.CONF_HOST: "5.6.7.8",
        config_flow.CONF_PORT: PORT,
        "MAC": "ff:ee:dd:cc:bb:aa",
    },
]
DHCP_DISCOVERY = dhcp.DhcpServiceInfo(
    hostname="any", ip="5.6.7.8", macaddress=MAC.lower().replace(":", "")
)
DHCP_DISCOVERY_SAME_IP = dhcp.DhcpServiceInfo(
    hostname="any", ip="1.2.3.4", macaddress=MAC.lower().replace(":", "")
)


def setup_mock_discovery(
    mock_discovery,
    with_name=False,
    with_mac=False,
    two_devices=False,
    with_hardware=True,
    no_devices=False,
):
    """Prepare mock discovery result."""
    services = []
    for item in DISCOVERY:
        if no_devices:
            continue
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
        if with_hardware and "HARDWARE" in item:
            scope = MagicMock()
            scope.getValue = MagicMock(
                return_value=f"onvif://www.onvif.org/hardware/{item['HARDWARE']}"
            )
            scopes.append(scope)
        service.getScopes = MagicMock(return_value=scopes)
        services.append(service)

    mock_ws_discovery = MagicMock()
    mock_ws_discovery.searchServices = MagicMock(return_value=services)
    mock_discovery.return_value = mock_ws_discovery


async def test_flow_discovered_devices(hass: HomeAssistant) -> None:
    """Test that config flow works for discovered devices."""
    logging.getLogger("homeassistant.components.onvif").setLevel(logging.DEBUG)

    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    with (
        patch(
            "homeassistant.components.onvif.config_flow.get_device"
        ) as mock_onvif_camera,
        patch(
            "homeassistant.components.onvif.config_flow.WSDiscovery"
        ) as mock_discovery,
        patch("homeassistant.components.onvif.ONVIFDevice") as mock_device,
    ):
        setup_mock_onvif_camera(mock_onvif_camera)
        setup_mock_discovery(mock_discovery)
        setup_mock_device(mock_device)

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={"auto": True}
        )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "device"
        container = result["data_schema"].schema[config_flow.CONF_HOST].container
        assert len(container) == 3
        assert container == {
            "Manually configure ONVIF device": "Manually configure ONVIF device",
            "1.2.3.4": "urn:uuid:123456789 (1.2.3.4) [IPC model]",
            "5.6.7.8": "urn:uuid:987654321 (5.6.7.8)",
        }

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={config_flow.CONF_HOST: HOST}
        )

        assert result["type"] is FlowResultType.FORM
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

        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["title"] == f"{URN} - {MAC}"
        assert result["data"] == {
            config_flow.CONF_NAME: URN,
            config_flow.CONF_HOST: HOST,
            config_flow.CONF_PORT: PORT,
            config_flow.CONF_USERNAME: USERNAME,
            config_flow.CONF_PASSWORD: PASSWORD,
        }


async def test_flow_discovered_devices_ignore_configured_manual_input(
    hass: HomeAssistant,
) -> None:
    """Test that config flow discovery ignores configured devices."""
    logging.getLogger("homeassistant.components.onvif").setLevel(logging.DEBUG)
    await setup_onvif_integration(hass)

    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    with (
        patch(
            "homeassistant.components.onvif.config_flow.get_device"
        ) as mock_onvif_camera,
        patch(
            "homeassistant.components.onvif.config_flow.WSDiscovery"
        ) as mock_discovery,
        patch("homeassistant.components.onvif.ONVIFDevice") as mock_device,
    ):
        setup_mock_onvif_camera(mock_onvif_camera)
        setup_mock_discovery(mock_discovery, with_mac=True)
        setup_mock_device(mock_device)

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={"auto": True}
        )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "device"
        assert len(result["data_schema"].schema[config_flow.CONF_HOST].container) == 2

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={config_flow.CONF_HOST: config_flow.CONF_MANUAL_INPUT},
        )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "configure"


async def test_flow_discovered_no_device(hass: HomeAssistant) -> None:
    """Test that config flow discovery no device."""
    await setup_onvif_integration(hass)

    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    with (
        patch(
            "homeassistant.components.onvif.config_flow.get_device"
        ) as mock_onvif_camera,
        patch(
            "homeassistant.components.onvif.config_flow.WSDiscovery"
        ) as mock_discovery,
        patch("homeassistant.components.onvif.ONVIFDevice") as mock_device,
    ):
        setup_mock_onvif_camera(mock_onvif_camera)
        setup_mock_discovery(mock_discovery, no_devices=True)
        setup_mock_device(mock_device)

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={"auto": True}
        )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "configure"


async def test_flow_discovery_ignore_existing_and_abort(hass: HomeAssistant) -> None:
    """Test that config flow discovery ignores setup devices."""
    logging.getLogger("homeassistant.components.onvif").setLevel(logging.DEBUG)
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

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    with (
        patch(
            "homeassistant.components.onvif.config_flow.get_device"
        ) as mock_onvif_camera,
        patch(
            "homeassistant.components.onvif.config_flow.WSDiscovery"
        ) as mock_discovery,
        patch("homeassistant.components.onvif.ONVIFDevice") as mock_device,
    ):
        setup_mock_onvif_camera(mock_onvif_camera)
        setup_mock_discovery(mock_discovery, with_name=True, with_mac=True)
        setup_mock_device(mock_device)

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={"auto": True}
        )

        # It should skip to manual entry if the only devices are already configured
        assert result["type"] is FlowResultType.FORM
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
        assert result["type"] is FlowResultType.ABORT


async def test_flow_manual_entry(hass: HomeAssistant) -> None:
    """Test that config flow works for discovered devices."""
    logging.getLogger("homeassistant.components.onvif").setLevel(logging.DEBUG)
    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    with (
        patch(
            "homeassistant.components.onvif.config_flow.get_device"
        ) as mock_onvif_camera,
        patch(
            "homeassistant.components.onvif.config_flow.WSDiscovery"
        ) as mock_discovery,
        patch("homeassistant.components.onvif.ONVIFDevice") as mock_device,
    ):
        setup_mock_onvif_camera(mock_onvif_camera, two_profiles=True)
        # no discovery
        mock_discovery.return_value = []
        setup_mock_device(mock_device)

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"auto": False},
        )

        assert result["type"] is FlowResultType.FORM
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

        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["title"] == f"{NAME} - {MAC}"
        assert result["data"] == {
            config_flow.CONF_NAME: NAME,
            config_flow.CONF_HOST: HOST,
            config_flow.CONF_PORT: PORT,
            config_flow.CONF_USERNAME: USERNAME,
            config_flow.CONF_PASSWORD: PASSWORD,
        }


async def test_flow_manual_entry_no_profiles(hass: HomeAssistant) -> None:
    """Test that config flow when no profiles are returned."""
    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    with (
        patch(
            "homeassistant.components.onvif.config_flow.get_device"
        ) as mock_onvif_camera,
        patch(
            "homeassistant.components.onvif.config_flow.WSDiscovery"
        ) as mock_discovery,
        patch("homeassistant.components.onvif.ONVIFDevice") as mock_device,
    ):
        setup_mock_onvif_camera(mock_onvif_camera, no_profiles=True)
        # no discovery
        mock_discovery.return_value = []
        setup_mock_device(mock_device)

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"auto": False},
        )
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

        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "no_h264"


async def test_flow_manual_entry_no_mac(hass: HomeAssistant) -> None:
    """Test that config flow when no mac address is returned."""
    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    with (
        patch(
            "homeassistant.components.onvif.config_flow.get_device"
        ) as mock_onvif_camera,
        patch(
            "homeassistant.components.onvif.config_flow.WSDiscovery"
        ) as mock_discovery,
        patch("homeassistant.components.onvif.ONVIFDevice") as mock_device,
    ):
        setup_mock_onvif_camera(
            mock_onvif_camera, with_serial=False, with_interfaces=False
        )
        # no discovery
        mock_discovery.return_value = []
        setup_mock_device(mock_device)

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"auto": False},
        )
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

        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "no_mac"


async def test_flow_manual_entry_fails(hass: HomeAssistant) -> None:
    """Test that we get a good error when manual entry fails."""
    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    with (
        patch(
            "homeassistant.components.onvif.config_flow.get_device"
        ) as mock_onvif_camera,
        patch(
            "homeassistant.components.onvif.config_flow.WSDiscovery"
        ) as mock_discovery,
        patch("homeassistant.components.onvif.ONVIFDevice") as mock_device,
    ):
        setup_mock_onvif_camera(
            mock_onvif_camera, two_profiles=True, profiles_transient_failure=True
        )
        # no discovery
        mock_discovery.return_value = []
        setup_mock_device(mock_device)

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"auto": False},
        )

        assert result["type"] is FlowResultType.FORM
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
            assert len(mock_setup_entry.mock_calls) == 0

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "configure"
        assert result["errors"] == {"base": "onvif_error"}
        assert result["description_placeholders"] == {"error": "camera not ready"}
        setup_mock_onvif_camera(
            mock_onvif_camera, two_profiles=True, update_xaddrs_fail=True
        )

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
            assert len(mock_setup_entry.mock_calls) == 0

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "configure"
        assert result["errors"] == {"base": "onvif_error"}
        assert result["description_placeholders"] == {
            "error": "Unknown error: camera not ready"
        }
        setup_mock_onvif_camera(mock_onvif_camera, two_profiles=True)

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

        assert result["title"] == f"{NAME} - {MAC}"
        assert result["data"] == {
            config_flow.CONF_NAME: NAME,
            config_flow.CONF_HOST: HOST,
            config_flow.CONF_PORT: PORT,
            config_flow.CONF_USERNAME: USERNAME,
            config_flow.CONF_PASSWORD: PASSWORD,
        }


async def test_flow_manual_entry_wrong_password(hass: HomeAssistant) -> None:
    """Test that we get a an auth error with the wrong password."""
    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    with (
        patch(
            "homeassistant.components.onvif.config_flow.get_device"
        ) as mock_onvif_camera,
        patch(
            "homeassistant.components.onvif.config_flow.WSDiscovery"
        ) as mock_discovery,
        patch("homeassistant.components.onvif.ONVIFDevice") as mock_device,
    ):
        setup_mock_onvif_camera(mock_onvif_camera, two_profiles=True, auth_fail=True)
        # no discovery
        mock_discovery.return_value = []
        setup_mock_device(mock_device)

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"auto": False},
        )

        assert result["type"] is FlowResultType.FORM
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
            assert len(mock_setup_entry.mock_calls) == 0

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "configure"
        assert result["errors"] == {"password": "auth_failed"}
        assert result["description_placeholders"] == {"error": "Authority failure"}
        setup_mock_onvif_camera(mock_onvif_camera, two_profiles=True)

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

        assert result["title"] == f"{NAME} - {MAC}"
        assert result["data"] == {
            config_flow.CONF_NAME: NAME,
            config_flow.CONF_HOST: HOST,
            config_flow.CONF_PORT: PORT,
            config_flow.CONF_USERNAME: USERNAME,
            config_flow.CONF_PASSWORD: PASSWORD,
        }


@pytest.mark.parametrize("option_value", [True, False])
async def test_option_flow(hass: HomeAssistant, option_value: bool) -> None:
    """Test config flow options."""
    entry, _, _ = await setup_onvif_integration(hass)

    result = await hass.config_entries.options.async_init(
        entry.entry_id, context={"show_advanced_options": True}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "onvif_devices"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            config_flow.CONF_EXTRA_ARGUMENTS: "",
            config_flow.CONF_RTSP_TRANSPORT: list(config_flow.RTSP_TRANSPORTS)[1],
            config_flow.CONF_USE_WALLCLOCK_AS_TIMESTAMPS: option_value,
            config_flow.CONF_ENABLE_WEBHOOKS: option_value,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        config_flow.CONF_EXTRA_ARGUMENTS: "",
        config_flow.CONF_RTSP_TRANSPORT: list(config_flow.RTSP_TRANSPORTS)[1],
        config_flow.CONF_USE_WALLCLOCK_AS_TIMESTAMPS: option_value,
        config_flow.CONF_ENABLE_WEBHOOKS: option_value,
    }


async def test_discovered_by_dhcp_updates_host(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Test dhcp updates existing host."""
    config_entry, _camera, device = await setup_onvif_integration(hass)
    device.profiles = device.async_get_profiles()
    devices = dr.async_entries_for_config_entry(device_registry, config_entry.entry_id)
    assert len(devices) == 1
    device = devices[0]
    assert device.model == "TestModel"
    assert device.connections == {(dr.CONNECTION_NETWORK_MAC, MAC)}
    assert config_entry.data[CONF_HOST] == "1.2.3.4"
    await hass.config_entries.async_unload(config_entry.entry_id)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_DHCP}, data=DHCP_DISCOVERY
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert config_entry.data[CONF_HOST] == DHCP_DISCOVERY.ip


async def test_discovered_by_dhcp_does_nothing_if_host_is_the_same(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Test dhcp update does nothing if host is the same."""
    config_entry, _camera, device = await setup_onvif_integration(hass)
    device.profiles = device.async_get_profiles()
    devices = dr.async_entries_for_config_entry(device_registry, config_entry.entry_id)
    assert len(devices) == 1
    device = devices[0]
    assert device.model == "TestModel"
    assert device.connections == {(dr.CONNECTION_NETWORK_MAC, MAC)}
    assert config_entry.data[CONF_HOST] == DHCP_DISCOVERY_SAME_IP.ip
    await hass.config_entries.async_unload(config_entry.entry_id)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_DHCP}, data=DHCP_DISCOVERY_SAME_IP
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert config_entry.data[CONF_HOST] == DHCP_DISCOVERY_SAME_IP.ip


async def test_discovered_by_dhcp_does_not_update_if_already_loaded(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Test dhcp does not update existing host if its already loaded."""
    config_entry, _camera, device = await setup_onvif_integration(hass)
    device.profiles = device.async_get_profiles()
    devices = dr.async_entries_for_config_entry(device_registry, config_entry.entry_id)
    assert len(devices) == 1
    device = devices[0]
    assert device.model == "TestModel"
    assert device.connections == {(dr.CONNECTION_NETWORK_MAC, MAC)}
    assert config_entry.data[CONF_HOST] == "1.2.3.4"

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_DHCP}, data=DHCP_DISCOVERY
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert config_entry.data[CONF_HOST] != DHCP_DISCOVERY.ip


async def test_discovered_by_dhcp_does_not_update_if_no_matching_entry(
    hass: HomeAssistant,
) -> None:
    """Test dhcp does not update existing host if there are no matching entries."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_DHCP}, data=DHCP_DISCOVERY
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"


def _get_schema_default(schema, key_name):
    """Iterate schema to find a key."""
    for schema_key in schema:
        if schema_key == key_name:
            return schema_key.default()
    raise KeyError(f"{key_name} not found in schema")


async def test_form_reauth(hass: HomeAssistant) -> None:
    """Test reauthenticate."""
    entry, _, _ = await setup_onvif_integration(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_REAUTH, "entry_id": entry.entry_id},
        data=entry.data,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert (
        _get_schema_default(result["data_schema"].schema, CONF_USERNAME)
        == entry.data[CONF_USERNAME]
    )

    with (
        patch(
            "homeassistant.components.onvif.config_flow.get_device"
        ) as mock_onvif_camera,
        patch("homeassistant.components.onvif.ONVIFDevice") as mock_device,
        patch(
            "homeassistant.components.onvif.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        setup_mock_onvif_camera(mock_onvif_camera, auth_failure=True)
        setup_mock_device(mock_device)

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                config_flow.CONF_USERNAME: "new-test-username",
                config_flow.CONF_PASSWORD: "new-test-password",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "reauth_confirm"
    assert result2["errors"] == {config_flow.CONF_PASSWORD: "auth_failed"}
    assert result2["description_placeholders"] == {
        "error": "not authorized (subcodes:NotAuthorized)"
    }

    with (
        patch(
            "homeassistant.components.onvif.config_flow.get_device"
        ) as mock_onvif_camera,
        patch("homeassistant.components.onvif.ONVIFDevice") as mock_device,
        patch(
            "homeassistant.components.onvif.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        setup_mock_onvif_camera(mock_onvif_camera)
        setup_mock_device(mock_device)

        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {
                config_flow.CONF_USERNAME: "new-test-username",
                config_flow.CONF_PASSWORD: "new-test-password",
            },
        )
        await hass.async_block_till_done()

    assert result3["type"] is FlowResultType.ABORT
    assert result3["reason"] == "reauth_successful"
    assert len(mock_setup_entry.mock_calls) == 1
    assert entry.data[config_flow.CONF_USERNAME] == "new-test-username"
    assert entry.data[config_flow.CONF_PASSWORD] == "new-test-password"


async def test_flow_manual_entry_updates_existing_user_password(
    hass: HomeAssistant,
) -> None:
    """Test that the existing username and password can be updated via manual entry."""
    entry, _, _ = await setup_onvif_integration(hass)

    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    with (
        patch(
            "homeassistant.components.onvif.config_flow.get_device"
        ) as mock_onvif_camera,
        patch(
            "homeassistant.components.onvif.config_flow.WSDiscovery"
        ) as mock_discovery,
        patch("homeassistant.components.onvif.ONVIFDevice") as mock_device,
    ):
        setup_mock_onvif_camera(mock_onvif_camera, two_profiles=True)
        # no discovery
        mock_discovery.return_value = []
        setup_mock_device(mock_device)

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"auto": False},
        )
        assert result["type"] is FlowResultType.FORM
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
                    config_flow.CONF_PASSWORD: "new_password",
                },
            )

            await hass.async_block_till_done()

        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "already_configured"
        assert entry.data[config_flow.CONF_USERNAME] == USERNAME
        assert entry.data[config_flow.CONF_PASSWORD] == "new_password"
        assert len(mock_setup_entry.mock_calls) == 1


async def test_flow_manual_entry_wrong_port(hass: HomeAssistant) -> None:
    """Test that we get a useful error with the wrong port."""
    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    with (
        patch(
            "homeassistant.components.onvif.config_flow.get_device"
        ) as mock_onvif_camera,
        patch(
            "homeassistant.components.onvif.config_flow.WSDiscovery"
        ) as mock_discovery,
        patch("homeassistant.components.onvif.ONVIFDevice") as mock_device,
    ):
        setup_mock_onvif_camera(mock_onvif_camera, wrong_port=True)
        # no discovery
        mock_discovery.return_value = []
        setup_mock_device(mock_device)

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"auto": False},
        )

        assert result["type"] is FlowResultType.FORM
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
            assert len(mock_setup_entry.mock_calls) == 0

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "configure"
        assert result["errors"] == {"port": "no_onvif_service"}
        assert result["description_placeholders"] == {}
        setup_mock_onvif_camera(mock_onvif_camera, two_profiles=True)

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

        assert result["title"] == f"{NAME} - {MAC}"
        assert result["data"] == {
            config_flow.CONF_NAME: NAME,
            config_flow.CONF_HOST: HOST,
            config_flow.CONF_PORT: PORT,
            config_flow.CONF_USERNAME: USERNAME,
            config_flow.CONF_PASSWORD: PASSWORD,
        }
