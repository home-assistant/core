"""Test the baf config flow."""

from ipaddress import ip_address
from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.components import zeroconf
from homeassistant.components.baf.const import DOMAIN
from homeassistant.const import CONF_IP_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import MOCK_NAME, MOCK_UUID, MockBAFDevice

from tests.common import MockConfigEntry


def _patch_device_config_flow(side_effect=None):
    """Mock out the BAF Device object."""

    def _create_mock_baf(*args, **kwargs):
        return MockBAFDevice(side_effect)

    return patch("homeassistant.components.baf.config_flow.Device", _create_mock_baf)


async def test_form_user(hass: HomeAssistant) -> None:
    """Test we get the user form."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with (
        _patch_device_config_flow(),
        patch(
            "homeassistant.components.baf.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_IP_ADDRESS: "127.0.0.1"},
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == MOCK_NAME
    assert result2["data"] == {CONF_IP_ADDRESS: "127.0.0.1"}
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with _patch_device_config_flow(TimeoutError):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_IP_ADDRESS: "127.0.0.1"},
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {CONF_IP_ADDRESS: "cannot_connect"}


async def test_form_unknown_exception(hass: HomeAssistant) -> None:
    """Test we handle unknown exceptions."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with _patch_device_config_flow(Exception):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_IP_ADDRESS: "127.0.0.1"},
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "unknown"}


async def test_zeroconf_discovery(hass: HomeAssistant) -> None:
    """Test we can setup from zeroconf discovery."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=zeroconf.ZeroconfServiceInfo(
            ip_address=ip_address("127.0.0.1"),
            ip_addresses=[ip_address("127.0.0.1")],
            hostname="mock_hostname",
            name="testfan",
            port=None,
            properties={"name": "My Fan", "model": "Haiku", "uuid": MOCK_UUID},
            type="mock_type",
        ),
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None

    with patch(
        "homeassistant.components.baf.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "My Fan"
    assert result2["data"] == {CONF_IP_ADDRESS: "127.0.0.1"}
    assert len(mock_setup_entry.mock_calls) == 1


async def test_zeroconf_updates_existing_ip(hass: HomeAssistant) -> None:
    """Test we can setup from zeroconf discovery."""
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_IP_ADDRESS: "127.0.0.2"}, unique_id=MOCK_UUID
    )
    entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=zeroconf.ZeroconfServiceInfo(
            ip_address=ip_address("127.0.0.1"),
            ip_addresses=[ip_address("127.0.0.1")],
            hostname="mock_hostname",
            name="testfan",
            port=None,
            properties={"name": "My Fan", "model": "Haiku", "uuid": MOCK_UUID},
            type="mock_type",
        ),
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.data[CONF_IP_ADDRESS] == "127.0.0.1"


async def test_zeroconf_rejects_ipv6(hass: HomeAssistant) -> None:
    """Test zeroconf discovery rejects ipv6."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=zeroconf.ZeroconfServiceInfo(
            ip_address=ip_address("fd00::b27c:63bb:cc85:4ea0"),
            ip_addresses=[ip_address("fd00::b27c:63bb:cc85:4ea0")],
            hostname="mock_hostname",
            name="testfan",
            port=None,
            properties={"name": "My Fan", "model": "Haiku", "uuid": MOCK_UUID},
            type="mock_type",
        ),
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "ipv6_not_supported"


async def test_user_flow_is_not_blocked_by_discovery(hass: HomeAssistant) -> None:
    """Test we can setup from the user flow when there is also a discovery."""
    discovery_result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=zeroconf.ZeroconfServiceInfo(
            ip_address=ip_address("127.0.0.1"),
            ip_addresses=[ip_address("127.0.0.1")],
            hostname="mock_hostname",
            name="testfan",
            port=None,
            properties={"name": "My Fan", "model": "Haiku", "uuid": MOCK_UUID},
            type="mock_type",
        ),
    )
    assert discovery_result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with (
        _patch_device_config_flow(),
        patch(
            "homeassistant.components.baf.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_IP_ADDRESS: "127.0.0.1"},
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == MOCK_NAME
    assert result2["data"] == {CONF_IP_ADDRESS: "127.0.0.1"}
    assert len(mock_setup_entry.mock_calls) == 1
