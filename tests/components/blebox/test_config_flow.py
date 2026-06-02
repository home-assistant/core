"""Test Home Assistant config flow for BleBox devices."""

from ipaddress import ip_address
from unittest.mock import DEFAULT, AsyncMock, PropertyMock, create_autospec, patch

import blebox_uniapi
import blebox_uniapi.box
import pytest

from homeassistant import config_entries
from homeassistant.components.blebox import config_flow
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_IP_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo
from homeassistant.setup import async_setup_component

from .conftest import (
    async_setup_config_entry,
    mock_config,
    mock_feature,
    mock_only_feature,
    setup_product_mock,
)

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

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data={config_flow.CONF_HOST: "172.2.3.4", config_flow.CONF_PORT: 80},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "My gate controller"
    assert result["data"] == {
        config_flow.CONF_HOST: "172.2.3.4",
        config_flow.CONF_PORT: 80,
    }


@pytest.fixture(name="product_class_mock")
def product_class_mock_fixture():
    """Return a mocked feature."""
    path = "homeassistant.components.blebox.config_flow.Box"
    return patch(path, DEFAULT, blebox_uniapi.box.Box, True, True)


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


async def test_flow_with_auth_failure(hass: HomeAssistant, product_class_mock) -> None:
    """Test that config flow works."""
    with product_class_mock as products_class:
        products_class.async_from_host = AsyncMock(
            side_effect=blebox_uniapi.error.UnauthorizedRequest
        )

        result = await hass.config_entries.flow.async_init(
            config_flow.DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={config_flow.CONF_HOST: "172.2.3.4", config_flow.CONF_PORT: 80},
        )
        assert result["errors"] == {"base": "cannot_connect"}


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
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "address_already_configured"


async def test_async_setup_entry(
    hass: HomeAssistant, valid_feature_mock, config_entry: MockConfigEntry
) -> None:
    """Test async_setup_entry (for coverage)."""

    await async_setup_config_entry(hass, config_entry, assert_success=True)

    assert hass.config_entries.async_entries() == [config_entry]
    assert config_entry.state is ConfigEntryState.LOADED


async def test_async_remove_entry(
    hass: HomeAssistant, valid_feature_mock, config_entry: MockConfigEntry
) -> None:
    """Test async_setup_entry (for coverage)."""

    await async_setup_config_entry(hass, config_entry, assert_success=True)

    assert await hass.config_entries.async_remove(config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.config_entries.async_entries() == []
    assert config_entry.state is ConfigEntryState.NOT_LOADED


async def test_flow_with_zeroconf(hass: HomeAssistant) -> None:
    """Test setup from zeroconf discovery."""
    result = await hass.config_entries.flow.async_init(
        config_flow.DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=ZeroconfServiceInfo(
            ip_address=ip_address("172.100.123.4"),
            ip_addresses=[ip_address("172.100.123.4")],
            port=80,
            hostname="bbx-bbtest123456.local.",
            type="_bbxsrv._tcp.local.",
            name="bbx-bbtest123456._bbxsrv._tcp.local.",
            properties={"_raw": {}},
        ),
    )

    assert result["type"] is FlowResultType.FORM

    with patch("homeassistant.components.blebox.async_setup_entry", return_value=True):
        result2 = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
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
            data=ZeroconfServiceInfo(
                ip_address=ip_address("172.100.123.4"),
                ip_addresses=[ip_address("172.100.123.4")],
                port=80,
                hostname="bbx-bbtest123456.local.",
                type="_bbxsrv._tcp.local.",
                name="bbx-bbtest123456._bbxsrv._tcp.local.",
                properties={"_raw": {}},
            ),
        )

        assert result2["type"] is FlowResultType.ABORT
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
            data=ZeroconfServiceInfo(
                ip_address=ip_address("172.100.123.4"),
                ip_addresses=[ip_address("172.100.123.4")],
                port=80,
                hostname="bbx-bbtest123456.local.",
                type="_bbxsrv._tcp.local.",
                name="bbx-bbtest123456._bbxsrv._tcp.local.",
                properties={"_raw": {}},
            ),
        )
        assert result["type"] is FlowResultType.ABORT
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
            data=ZeroconfServiceInfo(
                ip_address=ip_address("172.100.123.4"),
                ip_addresses=[ip_address("172.100.123.4")],
                port=80,
                hostname="bbx-bbtest123456.local.",
                type="_bbxsrv._tcp.local.",
                name="bbx-bbtest123456._bbxsrv._tcp.local.",
                properties={"_raw": {}},
            ),
        )
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "unsupported_device_response"


def create_product_mock(unique_id: str = "abcd0123ef5678"):
    """Return a product mock with a given unique_id."""
    product = create_autospec(blebox_uniapi.box.Box, True, True)
    type(product).unique_id = PropertyMock(return_value=unique_id)
    return product


async def test_reconfigure_flow_works(hass: HomeAssistant, product_class_mock) -> None:
    """Test that reconfigure flow updates host and port."""
    entry = MockConfigEntry(
        domain=config_flow.DOMAIN,
        data={config_flow.CONF_HOST: "172.2.3.4", config_flow.CONF_PORT: 80},
        unique_id="abcd0123ef5678",
    )
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    with product_class_mock as box_class:
        box_class.async_from_host = AsyncMock(
            return_value=create_product_mock("abcd0123ef5678")
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                config_flow.CONF_HOST: "172.2.3.5",
                config_flow.CONF_PORT: 80,
                config_flow.CONF_USERNAME: "admin",
                config_flow.CONF_PASSWORD: "secret",
            },
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data[config_flow.CONF_HOST] == "172.2.3.5"
    assert entry.data[config_flow.CONF_PORT] == 80
    assert entry.data[config_flow.CONF_USERNAME] == "admin"
    assert entry.data[config_flow.CONF_PASSWORD] == "secret"


async def test_reconfigure_flow_unique_id_mismatch(
    hass: HomeAssistant, product_class_mock
) -> None:
    """Test that reconfigure aborts when a different device is detected."""
    entry = MockConfigEntry(
        domain=config_flow.DOMAIN,
        data={config_flow.CONF_HOST: "172.2.3.4", config_flow.CONF_PORT: 80},
        unique_id="abcd0123ef5678",
    )
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)

    with product_class_mock as box_class:
        box_class.async_from_host = AsyncMock(
            return_value=create_product_mock("different_unique_id")
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {config_flow.CONF_HOST: "172.2.3.5", config_flow.CONF_PORT: 80},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unique_id_mismatch"


@pytest.mark.parametrize(
    ("exception", "expected_error"),
    [
        pytest.param(blebox_uniapi.error.Error, "cannot_connect", id="api_error"),
        pytest.param(
            blebox_uniapi.error.UnauthorizedRequest, "cannot_connect", id="auth_failure"
        ),
        pytest.param(
            blebox_uniapi.error.UnsupportedBoxVersion,
            "unsupported_version",
            id="unsupported_version",
        ),
        pytest.param(RuntimeError, "unknown", id="runtime_error"),
    ],
)
async def test_reconfigure_flow_errors(
    hass: HomeAssistant,
    product_class_mock,
    exception: type[Exception],
    expected_error: str,
) -> None:
    """Test that reconfigure shows the correct error for each exception type."""
    entry = MockConfigEntry(
        domain=config_flow.DOMAIN,
        data={config_flow.CONF_HOST: "172.2.3.4", config_flow.CONF_PORT: 80},
        unique_id="abcd0123ef5678",
    )
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)

    with product_class_mock as box_class:
        box_class.async_from_host = AsyncMock(side_effect=exception)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {config_flow.CONF_HOST: "172.2.3.5", config_flow.CONF_PORT: 80},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert result["errors"] == {"base": expected_error}
