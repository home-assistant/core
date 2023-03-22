"""Test Home Assistant config flow for BleBox devices."""
from unittest.mock import DEFAULT, AsyncMock, PropertyMock, patch

import blebox_uniapi
import pytest

from homeassistant import config_entries, data_entry_flow
from homeassistant.components import zeroconf
from homeassistant.components.blebox import config_flow
from homeassistant.const import CONF_IP_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.setup import async_setup_component

from .conftest import mock_config, mock_feature, mock_only_feature, setup_product_mock

from tests.common import MockConfigEntry


def create_valid_feature_mock(path="homeassistant.components.blebox.Products"):
    """Return a valid, complete BleBox feature mock."""
    feature = mock_only_feature(
        blebox_uniapi.cover.Cover,
        unique_id="BleBox-gateBox-1afe34db9437-0.position",
        full_name="gateBox-0.position",
        device_class="gate",
        state=0,
        async_update=AsyncMock(),
        current=None,
    )

    product = setup_product_mock("covers", [feature], path)

    type(product).name = PropertyMock(return_value="My gate controller")
    type(product).model = PropertyMock(return_value="gateController")
    type(product).type = PropertyMock(return_value="gateBox")
    type(product).brand = PropertyMock(return_value="BleBox")
    type(product).firmware_version = PropertyMock(return_value="1.23")
    type(product).unique_id = PropertyMock(return_value="abcd0123ef5678")

    return feature


@pytest.fixture(name="valid_feature_mock")
def valid_feature_mock_fixture():
    """Return a valid, complete BleBox feature mock."""
    return create_valid_feature_mock()


@pytest.fixture(name="flow_feature_mock")
def flow_feature_mock_fixture():
    """Return a mocked user flow feature."""
    return create_valid_feature_mock(
        "homeassistant.components.blebox.config_flow.Products"
    )


async def test_flow_works(
    hass: HomeAssistant, valid_feature_mock, flow_feature_mock
) -> None:
    """Test that config flow works."""

    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data={config_flow.CONF_HOST: "172.2.3.4", config_flow.CONF_PORT: 80},
    )

    assert result["type"] == "create_entry"
    assert result["title"] == "My gate controller"
    assert result["data"] == {
        config_flow.CONF_HOST: "172.2.3.4",
        config_flow.CONF_PORT: 80,
    }


@pytest.fixture(name="product_class_mock")
def product_class_mock_fixture():
    """Return a mocked feature."""
    path = "homeassistant.components.blebox.config_flow.Box"
    patcher = patch(path, DEFAULT, blebox_uniapi.box.Box, True, True)
    return patcher


async def test_flow_with_connection_failure(
    hass: HomeAssistant, product_class_mock
) -> None:
    """Test that config flow works."""
    with product_class_mock as products_class:
        products_class.async_from_host = AsyncMock(
            side_effect=blebox_uniapi.error.ConnectionError
        )

        result = await hass.config_entries.flow.async_init(
            config_flow.DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={config_flow.CONF_HOST: "172.2.3.4", config_flow.CONF_PORT: 80},
        )
        assert result["errors"] == {"base": "cannot_connect"}


async def test_flow_with_api_failure(hass: HomeAssistant, product_class_mock) -> None:
    """Test that config flow works."""
    with product_class_mock as products_class:
        products_class.async_from_host = AsyncMock(
            side_effect=blebox_uniapi.error.Error
        )

        result = await hass.config_entries.flow.async_init(
            config_flow.DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={config_flow.CONF_HOST: "172.2.3.4", config_flow.CONF_PORT: 80},
        )
        assert result["errors"] == {"base": "cannot_connect"}


async def test_flow_with_unknown_failure(
    hass: HomeAssistant, product_class_mock
) -> None:
    """Test that config flow works."""
    with product_class_mock as products_class:
        products_class.async_from_host = AsyncMock(side_effect=RuntimeError)
        result = await hass.config_entries.flow.async_init(
            config_flow.DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={config_flow.CONF_HOST: "172.2.3.4", config_flow.CONF_PORT: 80},
        )
        assert result["errors"] == {"base": "unknown"}


async def test_flow_with_unsupported_version(
    hass: HomeAssistant, product_class_mock
) -> None:
    """Test that config flow works."""
    with product_class_mock as products_class:
        products_class.async_from_host = AsyncMock(
            side_effect=blebox_uniapi.error.UnsupportedBoxVersion
        )

        result = await hass.config_entries.flow.async_init(
            config_flow.DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={config_flow.CONF_HOST: "172.2.3.4", config_flow.CONF_PORT: 80},
        )
        assert result["errors"] == {"base": "unsupported_version"}


async def test_async_setup(hass: HomeAssistant) -> None:
    """Test async_setup (for coverage)."""
    assert await async_setup_component(hass, "blebox", {"host": "172.2.3.4"})
    await hass.async_block_till_done()


async def test_already_configured(hass: HomeAssistant, valid_feature_mock) -> None:
    """Test that same device cannot be added twice."""

    config = mock_config("172.2.3.4")
    config.add_to_hass(hass)

    await hass.config_entries.async_setup(config.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data={config_flow.CONF_HOST: "172.2.3.4", config_flow.CONF_PORT: 80},
    )
    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "address_already_configured"


async def test_async_setup_entry(hass: HomeAssistant, valid_feature_mock) -> None:
    """Test async_setup_entry (for coverage)."""

    config = mock_config()
    config.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config.entry_id)
    await hass.async_block_till_done()

    assert hass.config_entries.async_entries() == [config]
    assert config.state is config_entries.ConfigEntryState.LOADED


async def test_async_remove_entry(hass: HomeAssistant, valid_feature_mock) -> None:
    """Test async_setup_entry (for coverage)."""

    config = mock_config()
    config.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config.entry_id)
    await hass.async_block_till_done()

    assert await hass.config_entries.async_remove(config.entry_id)
    await hass.async_block_till_done()

    assert hass.config_entries.async_entries() == []
    assert config.state is config_entries.ConfigEntryState.NOT_LOADED


async def test_flow_with_zeroconf(hass: HomeAssistant) -> None:
    """Test setup from zeroconf discovery."""
    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=zeroconf.ZeroconfServiceInfo(
            host="172.100.123.4",
            addresses=["172.100.123.4"],
            port=80,
            hostname="bbx-bbtest123456.local.",
            type="_bbxsrv._tcp.local.",
            name="bbx-bbtest123456._bbxsrv._tcp.local.",
            properties={"_raw": {}},
        ),
    )

    assert result["type"] == FlowResultType.FORM

    with patch("homeassistant.components.blebox.async_setup_entry", return_value=True):
        result2 = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["data"] == {"host": "172.100.123.4", "port": 80}


async def test_flow_with_zeroconf_when_already_configured(hass: HomeAssistant) -> None:
    """Test behaviour if device already configured."""
    entry = MockConfigEntry(
        domain=config_flow.DOMAIN,
        data={CONF_IP_ADDRESS: "172.100.123.4"},
        unique_id="abcd0123ef5678",
    )
    entry.add_to_hass(hass)
    feature: AsyncMock = mock_feature(
        "sensors",
        blebox_uniapi.sensor.Temperature,
    )
    with patch(
        "homeassistant.components.blebox.config_flow.Box.async_from_host",
        return_value=feature.product,
    ):
        result2 = await hass.config_entries.flow.async_init(
            config_flow.DOMAIN,
            context={"source": config_entries.SOURCE_ZEROCONF},
            data=zeroconf.ZeroconfServiceInfo(
                host="172.100.123.4",
                addresses=["172.100.123.4"],
                port=80,
                hostname="bbx-bbtest123456.local.",
                type="_bbxsrv._tcp.local.",
                name="bbx-bbtest123456._bbxsrv._tcp.local.",
                properties={"_raw": {}},
            ),
        )

        assert result2["type"] == FlowResultType.ABORT
        assert result2["reason"] == "already_configured"


async def test_flow_with_zeroconf_when_device_unsupported(hass: HomeAssistant) -> None:
    """Test behaviour when device is not supported."""
    with patch(
        "homeassistant.components.blebox.config_flow.Box.async_from_host",
        side_effect=blebox_uniapi.error.UnsupportedBoxVersion,
    ):
        result = await hass.config_entries.flow.async_init(
            config_flow.DOMAIN,
            context={"source": config_entries.SOURCE_ZEROCONF},
            data=zeroconf.ZeroconfServiceInfo(
                host="172.100.123.4",
                addresses=["172.100.123.4"],
                port=80,
                hostname="bbx-bbtest123456.local.",
                type="_bbxsrv._tcp.local.",
                name="bbx-bbtest123456._bbxsrv._tcp.local.",
                properties={"_raw": {}},
            ),
        )
        assert result["type"] == data_entry_flow.FlowResultType.ABORT
        assert result["reason"] == "unsupported_device_version"


async def test_flow_with_zeroconf_when_device_response_unsupported(
    hass: HomeAssistant,
) -> None:
    """Test behaviour when device returned unsupported response."""

    with patch(
        "homeassistant.components.blebox.config_flow.Box.async_from_host",
        side_effect=blebox_uniapi.error.UnsupportedBoxResponse,
    ):
        result = await hass.config_entries.flow.async_init(
            config_flow.DOMAIN,
            context={"source": config_entries.SOURCE_ZEROCONF},
            data=zeroconf.ZeroconfServiceInfo(
                host="172.100.123.4",
                addresses=["172.100.123.4"],
                port=80,
                hostname="bbx-bbtest123456.local.",
                type="_bbxsrv._tcp.local.",
                name="bbx-bbtest123456._bbxsrv._tcp.local.",
                properties={"_raw": {}},
            ),
        )
        assert result["type"] == data_entry_flow.FlowResultType.ABORT
        assert result["reason"] == "unsupported_device_response"
