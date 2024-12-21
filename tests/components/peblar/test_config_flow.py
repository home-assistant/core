"""Configuration flow tests for the Peblar integration."""

from ipaddress import ip_address
from unittest.mock import MagicMock

from peblar import PeblarAuthenticationError, PeblarConnectionError
import pytest

from homeassistant.components import zeroconf
from homeassistant.components.peblar.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER, SOURCE_ZEROCONF
from homeassistant.const import CONF_HOST, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


@pytest.mark.usefixtures("mock_peblar")
async def test_user_flow(hass: HomeAssistant) -> None:
    """Test the full happy path user flow from start to finish."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_HOST: "127.0.0.1",
            CONF_PASSWORD: "OMGPUPPIES",
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY

    config_entry = result["result"]
    assert config_entry.unique_id == "23-45-A4O-MOF"
    assert config_entry.data == {
        CONF_HOST: "127.0.0.1",
        CONF_PASSWORD: "OMGPUPPIES",
    }
    assert not config_entry.options


@pytest.mark.parametrize(
    ("side_effect", "expected_error"),
    [
        (PeblarConnectionError, {CONF_HOST: "cannot_connect"}),
        (PeblarAuthenticationError, {CONF_PASSWORD: "invalid_auth"}),
        (Exception, {"base": "unknown"}),
    ],
)
async def test_user_flow_errors(
    hass: HomeAssistant,
    mock_peblar: MagicMock,
    side_effect: Exception,
    expected_error: dict[str, str],
) -> None:
    """Test we show user form on a connection error."""
    mock_peblar.login.side_effect = side_effect

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={
            CONF_HOST: "127.0.0.1",
            CONF_PASSWORD: "OMGCATS!",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == expected_error

    mock_peblar.login.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_HOST: "127.0.0.2",
            CONF_PASSWORD: "OMGPUPPIES!",
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY

    config_entry = result["result"]
    assert config_entry.unique_id == "23-45-A4O-MOF"
    assert config_entry.data == {
        CONF_HOST: "127.0.0.2",
        CONF_PASSWORD: "OMGPUPPIES!",
    }
    assert not config_entry.options


@pytest.mark.usefixtures("mock_peblar")
async def test_user_flow_already_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test configuration flow aborts when the device is already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={
            CONF_HOST: "127.0.0.1",
            CONF_PASSWORD: "OMGSPIDERS",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("mock_peblar")
async def test_zeroconf_flow(hass: HomeAssistant) -> None:
    """Test the zeroconf happy flow from start to finish."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=zeroconf.ZeroconfServiceInfo(
            ip_address=ip_address("127.0.0.1"),
            ip_addresses=[ip_address("127.0.0.1")],
            port=80,
            hostname="pblr-0000645.local.",
            name="mock_name",
            properties={
                "sn": "23-45-A4O-MOF",
                "version": "1.6.1+1+WL-1",
            },
            type="mock_type",
        ),
    )

    assert result["step_id"] == "zeroconf_confirm"
    assert result["type"] is FlowResultType.FORM

    progress = hass.config_entries.flow.async_progress()
    assert len(progress) == 1
    assert progress[0].get("flow_id") == result["flow_id"]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_PASSWORD: "OMGPINEAPPLES"}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY

    config_entry = result["result"]
    assert config_entry.unique_id == "23-45-A4O-MOF"
    assert config_entry.data == {
        CONF_HOST: "127.0.0.1",
        CONF_PASSWORD: "OMGPINEAPPLES",
    }
    assert not config_entry.options


async def test_zeroconf_flow_abort_no_serial(hass: HomeAssistant) -> None:
    """Test the zeroconf aborts when it advertises incompatible data."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=zeroconf.ZeroconfServiceInfo(
            ip_address=ip_address("127.0.0.1"),
            ip_addresses=[ip_address("127.0.0.1")],
            port=80,
            hostname="pblr-0000645.local.",
            name="mock_name",
            properties={},
            type="mock_type",
        ),
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_serial_number"


@pytest.mark.parametrize(
    ("side_effect", "expected_error"),
    [
        (PeblarConnectionError, {"base": "unknown"}),
        (PeblarAuthenticationError, {CONF_PASSWORD: "invalid_auth"}),
        (Exception, {"base": "unknown"}),
    ],
)
async def test_zeroconf_flow_errors(
    hass: HomeAssistant,
    mock_peblar: MagicMock,
    side_effect: Exception,
    expected_error: dict[str, str],
) -> None:
    """Test we show form on a error."""
    mock_peblar.login.side_effect = side_effect

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=zeroconf.ZeroconfServiceInfo(
            ip_address=ip_address("127.0.0.1"),
            ip_addresses=[ip_address("127.0.0.1")],
            port=80,
            hostname="pblr-0000645.local.",
            name="mock_name",
            properties={
                "sn": "23-45-A4O-MOF",
                "version": "1.6.1+1+WL-1",
            },
            type="mock_type",
        ),
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_PASSWORD: "OMGPUPPIES",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "zeroconf_confirm"
    assert result["errors"] == expected_error

    mock_peblar.login.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_PASSWORD: "OMGPUPPIES",
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY

    config_entry = result["result"]
    assert config_entry.unique_id == "23-45-A4O-MOF"
    assert config_entry.data == {
        CONF_HOST: "127.0.0.1",
        CONF_PASSWORD: "OMGPUPPIES",
    }
    assert not config_entry.options


@pytest.mark.usefixtures("mock_peblar")
async def test_zeroconf_flow_not_discovered_again(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the zeroconf doesn't re-discover an existing device."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=zeroconf.ZeroconfServiceInfo(
            ip_address=ip_address("127.0.0.1"),
            ip_addresses=[ip_address("127.0.0.1")],
            port=80,
            hostname="pblr-0000645.local.",
            name="mock_name",
            properties={
                "sn": "23-45-A4O-MOF",
                "version": "1.6.1+1+WL-1",
            },
            type="mock_type",
        ),
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("mock_peblar")
async def test_user_flow_with_zeroconf_in_progress(hass: HomeAssistant) -> None:
    """Test the full happy path user flow from start to finish.

    While zeroconf discovery is already in progress.
    """
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=zeroconf.ZeroconfServiceInfo(
            ip_address=ip_address("127.0.0.1"),
            ip_addresses=[ip_address("127.0.0.1")],
            port=80,
            hostname="pblr-0000645.local.",
            name="mock_name",
            properties={
                "sn": "23-45-A4O-MOF",
                "version": "1.6.1+1+WL-1",
            },
            type="mock_type",
        ),
    )

    progress = hass.config_entries.flow.async_progress()
    assert len(progress) == 1

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    progress = hass.config_entries.flow.async_progress()
    assert len(progress) == 2

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_HOST: "127.0.0.1",
            CONF_PASSWORD: "OMGPUPPIES",
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY

    assert not hass.config_entries.flow.async_progress()
