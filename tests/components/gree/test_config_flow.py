"""Tests for the Gree config flow."""

import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant import config_entries
from homeassistant.components.gree.const import CONF_KNOWN_HOSTS, DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


@pytest.mark.parametrize(
    ("user_input", "expected_hosts"),
    [
        pytest.param({}, [], id="broadcast-only"),
        pytest.param(
            {CONF_KNOWN_HOSTS: [" 192.168.0.10 ", "", " ", "192.168.0.11"]},
            ["192.168.0.10", "192.168.0.11"],
            id="manual-targets",
        ),
    ],
)
async def test_offline_setup(
    hass: HomeAssistant,
    user_input: dict[str, list[str]],
    expected_hosts: list[str],
) -> None:
    """Test setup succeeds without devices, with or without IPv4 hints."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "config"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Gree Climate"
    assert result["data"] == {CONF_KNOWN_HOSTS: expected_hosts}
    assert result["result"].unique_id == DOMAIN


@pytest.mark.parametrize(
    "invalid_host",
    [
        pytest.param("not-an-ip", id="hostname"),
        pytest.param("2001:db8::1", id="ipv6"),
        pytest.param("256.0.0.1", id="invalid-ipv4"),
    ],
)
async def test_setup_invalid_host_recovery(
    hass: HomeAssistant, invalid_host: str
) -> None:
    """Test invalid IPv4 hints can be corrected without restarting setup."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_KNOWN_HOSTS: [invalid_host]}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_KNOWN_HOSTS: "invalid_host"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_KNOWN_HOSTS: [" 192.168.0.20 "]}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_KNOWN_HOSTS: ["192.168.0.20"]}
    assert result["result"].unique_id == DOMAIN


@pytest.mark.parametrize(
    ("initial_data", "user_input", "expected_data"),
    [
        pytest.param(
            {CONF_KNOWN_HOSTS: ["192.168.0.10"], "unrelated": "preserved"},
            {CONF_KNOWN_HOSTS: [" 192.168.0.20 "]},
            {CONF_KNOWN_HOSTS: ["192.168.0.20"], "unrelated": "preserved"},
            id="update-targets",
        ),
        pytest.param({}, {}, {CONF_KNOWN_HOSTS: []}, id="legacy-entry"),
        pytest.param(
            {CONF_KNOWN_HOSTS: ["192.168.0.10"], "unrelated": "preserved"},
            {CONF_KNOWN_HOSTS: []},
            {CONF_KNOWN_HOSTS: [], "unrelated": "preserved"},
            id="clear-targets",
        ),
    ],
)
async def test_configure_known_hosts(
    hass: HomeAssistant,
    initial_data: dict[str, list[str] | str],
    user_input: dict[str, list[str]],
    expected_data: dict[str, list[str] | str],
) -> None:
    """Test Configure updates targets without replacing entry data or identity."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id=DOMAIN, data=initial_data)
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {}
    assert entry.data == expected_data
    assert hass.config_entries.async_entries(DOMAIN) == [entry]


@pytest.mark.parametrize(
    "invalid_host",
    [
        pytest.param("not-an-ip", id="hostname"),
        pytest.param("2001:db8::1", id="ipv6"),
        pytest.param("256.0.0.1", id="invalid-ipv4"),
    ],
)
async def test_configure_invalid_host_recovery(
    hass: HomeAssistant, invalid_host: str
) -> None:
    """Test invalid Configure input can be corrected without losing entry data."""
    initial_data = {CONF_KNOWN_HOSTS: ["192.168.0.10"], "unrelated": "preserved"}
    entry = MockConfigEntry(domain=DOMAIN, unique_id=DOMAIN, data=initial_data)
    entry.add_to_hass(hass)
    entry_id = entry.entry_id

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_KNOWN_HOSTS: [invalid_host]}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_KNOWN_HOSTS: "invalid_host"}
    assert entry.data == initial_data

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_KNOWN_HOSTS: [" 192.168.0.20 ", "", " "]}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.data == {
        CONF_KNOWN_HOSTS: ["192.168.0.20"],
        "unrelated": "preserved",
    }
    assert entry.entry_id == entry_id
    assert hass.config_entries.async_get_entry(entry_id) is entry


async def test_already_configured(hass: HomeAssistant) -> None:
    """Test the shared discovery entry cannot be configured twice."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id=DOMAIN, data={})
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"
