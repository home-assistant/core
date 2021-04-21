"""Test the Enphase Envoy config flow."""
from unittest.mock import MagicMock, patch

import httpx

from homeassistant import config_entries, setup
from homeassistant.components.enphase_envoy.const import DOMAIN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.enphase_envoy.config_flow.EnvoyReader.getData",
        return_value=True,
    ), patch(
        "homeassistant.components.enphase_envoy.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.1.1.1",
                "username": "test-username",
                "password": "test-password",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == "create_entry"
    assert result2["title"] == "Envoy"
    assert result2["data"] == {
        "host": "1.1.1.1",
        "name": "Envoy",
        "username": "test-username",
        "password": "test-password",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_invalid_auth(hass: HomeAssistant) -> None:
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.enphase_envoy.config_flow.EnvoyReader.getData",
        side_effect=httpx.HTTPStatusError(
            "any", request=MagicMock(), response=MagicMock()
        ),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.1.1.1",
                "username": "test-username",
                "password": "test-password",
            },
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.enphase_envoy.config_flow.EnvoyReader.getData",
        side_effect=httpx.HTTPError("any", request=MagicMock()),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.1.1.1",
                "username": "test-username",
                "password": "test-password",
            },
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_unknown_error(hass: HomeAssistant) -> None:
    """Test we handle unknown error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.enphase_envoy.config_flow.EnvoyReader.getData",
        side_effect=ValueError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.1.1.1",
                "username": "test-username",
                "password": "test-password",
            },
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "unknown"}


async def test_import(hass: HomeAssistant) -> None:
    """Test we can import from yaml."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    with patch(
        "homeassistant.components.enphase_envoy.config_flow.EnvoyReader.getData",
        return_value=True,
    ), patch(
        "homeassistant.components.enphase_envoy.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "import"},
            data={
                "ip_address": "1.1.1.1",
                "name": "Pool Envoy",
                "username": "test-username",
                "password": "test-password",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == "create_entry"
    assert result2["title"] == "Pool Envoy"
    assert result2["data"] == {
        "host": "1.1.1.1",
        "name": "Pool Envoy",
        "username": "test-username",
        "password": "test-password",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_zeroconf(hass: HomeAssistant) -> None:
    """Test we can setup from zeroconf."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "zeroconf"},
        data={
            "properties": {"serialnum": "1234"},
            "host": "1.1.1.1",
        },
    )
    await hass.async_block_till_done()

    assert result["type"] == "form"
    assert result["step_id"] == "user"

    with patch(
        "homeassistant.components.enphase_envoy.config_flow.EnvoyReader.getData",
        return_value=True,
    ), patch(
        "homeassistant.components.enphase_envoy.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.1.1.1",
                "username": "test-username",
                "password": "test-password",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == "create_entry"
    assert result2["title"] == "Envoy 1234"
    assert result2["result"].unique_id == "1234"
    assert result2["data"] == {
        "host": "1.1.1.1",
        "name": "Envoy 1234",
        "username": "test-username",
        "password": "test-password",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_host_already_exists(hass: HomeAssistant) -> None:
    """Test host already exists."""
    await setup.async_setup_component(hass, "persistent_notification", {})

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "host": "1.1.1.1",
            "name": "Envoy",
            "username": "test-username",
            "password": "test-password",
        },
        title="Envoy",
    )
    config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.enphase_envoy.config_flow.EnvoyReader.getData",
        return_value=True,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.1.1.1",
                "username": "test-username",
                "password": "test-password",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == "abort"
    assert result2["reason"] == "already_configured"


async def test_zeroconf_serial_already_exists(hass: HomeAssistant) -> None:
    """Test serial number already exists from zeroconf."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "host": "1.1.1.1",
            "name": "Envoy",
            "username": "test-username",
            "password": "test-password",
        },
        unique_id="1234",
        title="Envoy",
    )
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "zeroconf"},
        data={
            "properties": {"serialnum": "1234"},
            "host": "1.1.1.1",
        },
    )

    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"


async def test_zeroconf_host_already_exists(hass: HomeAssistant) -> None:
    """Test hosts already exists from zeroconf."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "host": "1.1.1.1",
            "name": "Envoy",
            "username": "test-username",
            "password": "test-password",
        },
        title="Envoy",
    )
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.enphase_envoy.config_flow.EnvoyReader.getData",
        return_value=True,
    ), patch(
        "homeassistant.components.enphase_envoy.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "zeroconf"},
            data={
                "properties": {"serialnum": "1234"},
                "host": "1.1.1.1",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"

    assert config_entry.unique_id == "1234"
    assert config_entry.title == "Envoy 1234"
    assert len(mock_setup_entry.mock_calls) == 1


async def test_reauth(hass: HomeAssistant) -> None:
    """Test we reauth auth."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "host": "1.1.1.1",
            "name": "Envoy",
            "username": "test-username",
            "password": "test-password",
        },
        title="Envoy",
    )
    config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "unique_id": config_entry.unique_id,
            "entry_id": config_entry.entry_id,
        },
    )

    with patch(
        "homeassistant.components.enphase_envoy.config_flow.EnvoyReader.getData",
        return_value=True,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.1.1.1",
                "username": "test-username",
                "password": "test-password",
            },
        )

    assert result2["type"] == "abort"
    assert result2["reason"] == "reauth_successful"
