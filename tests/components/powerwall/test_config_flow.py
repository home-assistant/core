"""Test the Powerwall config flow."""

from unittest.mock import patch

from tesla_powerwall import MissingAttributeError, PowerwallUnreachableError

from homeassistant import config_entries, setup
from homeassistant.components.dhcp import HOSTNAME, IP_ADDRESS, MAC_ADDRESS
from homeassistant.components.powerwall.const import DOMAIN
from homeassistant.const import CONF_IP_ADDRESS

from .mocks import _mock_powerwall_side_effect, _mock_powerwall_site_name

from tests.common import MockConfigEntry


async def test_form_source_user(hass):
    """Test we get config flow setup form as a user."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    mock_powerwall = await _mock_powerwall_site_name(hass, "My site")

    with patch(
        "homeassistant.components.powerwall.config_flow.Powerwall",
        return_value=mock_powerwall,
    ), patch(
        "homeassistant.components.powerwall.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.powerwall.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_IP_ADDRESS: "1.2.3.4"},
        )
        await hass.async_block_till_done()

    assert result2["type"] == "create_entry"
    assert result2["title"] == "My site"
    assert result2["data"] == {CONF_IP_ADDRESS: "1.2.3.4"}
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_source_import(hass):
    """Test we setup the config entry via import."""
    await setup.async_setup_component(hass, "persistent_notification", {})

    mock_powerwall = await _mock_powerwall_site_name(hass, "Imported site")
    with patch(
        "homeassistant.components.powerwall.config_flow.Powerwall",
        return_value=mock_powerwall,
    ), patch(
        "homeassistant.components.powerwall.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.powerwall.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={CONF_IP_ADDRESS: "1.2.3.4"},
        )
        await hass.async_block_till_done()

    assert result["type"] == "create_entry"
    assert result["title"] == "Imported site"
    assert result["data"] == {CONF_IP_ADDRESS: "1.2.3.4"}
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_cannot_connect(hass):
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_powerwall = _mock_powerwall_side_effect(site_info=PowerwallUnreachableError)

    with patch(
        "homeassistant.components.powerwall.config_flow.Powerwall",
        return_value=mock_powerwall,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_IP_ADDRESS: "1.2.3.4"},
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_unknown_exeption(hass):
    """Test we handle an unknown exception."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_powerwall = _mock_powerwall_side_effect(site_info=ValueError)

    with patch(
        "homeassistant.components.powerwall.config_flow.Powerwall",
        return_value=mock_powerwall,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_IP_ADDRESS: "1.2.3.4"},
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "unknown"}


async def test_form_wrong_version(hass):
    """Test we can handle wrong version error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_powerwall = _mock_powerwall_side_effect(
        site_info=MissingAttributeError({}, "")
    )

    with patch(
        "homeassistant.components.powerwall.config_flow.Powerwall",
        return_value=mock_powerwall,
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_IP_ADDRESS: "1.2.3.4"},
        )

    assert result3["type"] == "form"
    assert result3["errors"] == {"base": "wrong_version"}


async def test_already_configured(hass):
    """Test we abort when already configured."""
    await setup.async_setup_component(hass, "persistent_notification", {})

    config_entry = MockConfigEntry(domain=DOMAIN, data={CONF_IP_ADDRESS: "1.1.1.1"})
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_DHCP},
        data={
            IP_ADDRESS: "1.1.1.1",
            MAC_ADDRESS: "AA:BB:CC:DD:EE:FF",
            HOSTNAME: "any",
        },
    )
    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"


async def test_already_configured_with_ignored(hass):
    """Test ignored entries do not break checking for existing entries."""
    await setup.async_setup_component(hass, "persistent_notification", {})

    config_entry = MockConfigEntry(domain=DOMAIN, data={}, source="ignore")
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_DHCP},
        data={
            IP_ADDRESS: "1.1.1.1",
            MAC_ADDRESS: "AA:BB:CC:DD:EE:FF",
            HOSTNAME: "any",
        },
    )
    assert result["type"] == "form"


async def test_dhcp_discovery(hass):
    """Test we can process the discovery from dhcp."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_DHCP},
        data={
            IP_ADDRESS: "1.1.1.1",
            MAC_ADDRESS: "AA:BB:CC:DD:EE:FF",
            HOSTNAME: "any",
        },
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    mock_powerwall = await _mock_powerwall_site_name(hass, "Some site")
    with patch(
        "homeassistant.components.powerwall.config_flow.Powerwall",
        return_value=mock_powerwall,
    ), patch(
        "homeassistant.components.powerwall.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.powerwall.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_IP_ADDRESS: "1.1.1.1",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == "create_entry"
    assert result2["title"] == "Some site"
    assert result2["data"] == {
        CONF_IP_ADDRESS: "1.1.1.1",
    }
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1
