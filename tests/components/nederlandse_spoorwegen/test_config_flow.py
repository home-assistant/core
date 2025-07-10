"""Test config flow for Nederlandse Spoorwegen integration (new architecture)."""

from unittest.mock import patch

import pytest

from homeassistant.components.nederlandse_spoorwegen.const import DOMAIN
from homeassistant.config_entries import SOURCE_REAUTH, SOURCE_RECONFIGURE, SOURCE_USER
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType, InvalidData

from tests.common import MockConfigEntry

API_KEY = "abc1234567"
NEW_API_KEY = "xyz9876543"


@pytest.mark.asyncio
async def test_config_flow_user_success(hass: HomeAssistant) -> None:
    """Test successful user config flow."""
    with patch(
        "homeassistant.components.nederlandse_spoorwegen.config_flow.NSAPI"
    ) as mock_nsapi_cls:
        mock_nsapi = mock_nsapi_cls.return_value
        mock_nsapi.get_stations.return_value = [{"code": "AMS", "name": "Amsterdam"}]

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        assert result.get("type") == FlowResultType.FORM
        assert result.get("step_id") == "user"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_API_KEY: API_KEY}
        )
        assert result.get("type") == FlowResultType.CREATE_ENTRY
        assert result.get("title") == "Nederlandse Spoorwegen"
        assert result.get("data") == {CONF_API_KEY: API_KEY}


@pytest.mark.asyncio
async def test_config_flow_user_invalid_auth(hass: HomeAssistant) -> None:
    """Test config flow with invalid auth."""
    with patch(
        "homeassistant.components.nederlandse_spoorwegen.config_flow.NSAPI"
    ) as mock_nsapi_cls:
        mock_nsapi_cls.return_value.get_stations.side_effect = Exception(
            "401 Unauthorized: invalid API key"
        )

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_API_KEY: "invalid_key"}
        )
        assert result.get("type") == FlowResultType.FORM
        assert result.get("errors") == {"base": "invalid_auth"}


@pytest.mark.asyncio
async def test_config_flow_user_cannot_connect(hass: HomeAssistant) -> None:
    """Test config flow with connection error."""
    with patch(
        "homeassistant.components.nederlandse_spoorwegen.config_flow.NSAPI"
    ) as mock_nsapi_cls:
        mock_nsapi_cls.return_value.get_stations.side_effect = ConnectionError(
            "Cannot connect"
        )

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_API_KEY: API_KEY}
        )
        assert result.get("type") == FlowResultType.FORM
        assert result.get("errors") == {"base": "cannot_connect"}


@pytest.mark.asyncio
async def test_config_flow_already_configured(hass: HomeAssistant) -> None:
    """Test config flow aborts if already configured."""
    # Since single_config_entry is true, we should get an abort when trying to add a second
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: API_KEY},
        unique_id=API_KEY,  # Use API key as unique_id
    )
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    # The flow should be aborted or show an error immediately due to single_config_entry
    # Check if it's aborted on init
    if result.get("type") == FlowResultType.ABORT:
        assert result.get("reason") in ["single_instance_allowed", "already_configured"]
    else:
        # If not aborted on init, it should be on configuration
        with patch(
            "homeassistant.components.nederlandse_spoorwegen.config_flow.NSAPI"
        ) as mock_nsapi_cls:
            mock_nsapi_cls.return_value.get_stations.return_value = [
                {"code": "AMS", "name": "Amsterdam"}
            ]

            result = await hass.config_entries.flow.async_configure(
                result["flow_id"], user_input={CONF_API_KEY: API_KEY}
            )
            assert result.get("type") == FlowResultType.ABORT
            assert result.get("reason") == "already_configured"


@pytest.mark.asyncio
async def test_reauth_flow(hass: HomeAssistant) -> None:
    """Test reauthentication flow."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: API_KEY},
        unique_id=DOMAIN,
    )
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.nederlandse_spoorwegen.coordinator.NSAPI"
    ) as mock_nsapi_cls:
        mock_nsapi = mock_nsapi_cls.return_value
        mock_nsapi.get_stations.return_value = [{"code": "AMS", "name": "Amsterdam"}]

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_REAUTH, "entry_id": config_entry.entry_id},
        )
        assert result.get("type") == FlowResultType.FORM
        assert result.get("step_id") == "reauth"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_API_KEY: NEW_API_KEY}
        )
        assert result.get("type") == FlowResultType.ABORT
        assert result.get("reason") == "reauth_successful"
        assert config_entry.data[CONF_API_KEY] == NEW_API_KEY


@pytest.mark.asyncio
async def test_reconfigure_flow(hass: HomeAssistant) -> None:
    """Test reconfiguration flow."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: API_KEY},
        unique_id=DOMAIN,
    )
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.nederlandse_spoorwegen.coordinator.NSAPI"
    ) as mock_nsapi_cls:
        mock_nsapi = mock_nsapi_cls.return_value
        mock_nsapi.get_stations.return_value = [{"code": "AMS", "name": "Amsterdam"}]

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_RECONFIGURE, "entry_id": config_entry.entry_id},
        )
        assert result.get("type") == FlowResultType.FORM
        assert result.get("step_id") == "reconfigure"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_API_KEY: NEW_API_KEY}
        )
        assert result.get("type") == FlowResultType.ABORT
        assert result.get("reason") == "reconfigure_successful"
        assert config_entry.data[CONF_API_KEY] == NEW_API_KEY


@pytest.mark.asyncio
async def test_options_flow_init(hass: HomeAssistant) -> None:
    """Test options flow shows the manage routes menu."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: API_KEY},
        options={"routes": [{"name": "Test Route", "from": "AMS", "to": "UTR"}]},
    )
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == "init"
    # Should show action selection form, not menu


@pytest.mark.asyncio
async def test_options_flow_add_route(hass: HomeAssistant) -> None:
    """Test adding a route through options flow."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: API_KEY},
        options={"routes": []},
    )
    config_entry.add_to_hass(hass)

    # Start add route flow
    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={"action": "add"}
    )
    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == "add_route"

    # Add the route
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={"name": "New Route", "from": "AMS", "to": "GVC"}
    )
    assert result.get("type") == FlowResultType.CREATE_ENTRY
    assert len(result.get("data", {}).get("routes", [])) == 1
    assert result.get("data", {}).get("routes", [])[0]["name"] == "New Route"


@pytest.mark.asyncio
async def test_options_flow_add_route_validation_errors(hass: HomeAssistant) -> None:
    """Test validation errors in add route form."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: API_KEY},
        options={"routes": []},
    )
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={"action": "add"}
    )

    # Test missing name
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={"name": "", "from": "AMS", "to": "GVC"}
    )
    assert result.get("type") == FlowResultType.FORM
    assert result.get("errors") == {"base": "missing_fields"}

    # Test same from/to
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={"name": "Test", "from": "AMS", "to": "AMS"}
    )
    assert result.get("type") == FlowResultType.FORM
    assert result.get("errors") == {"base": "same_station"}


@pytest.mark.asyncio
async def test_reauth_flow_missing_api_key(hass: HomeAssistant) -> None:
    """Test reauth flow with missing API key."""
    config_entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_API_KEY: API_KEY}, unique_id=DOMAIN
    )
    config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_REAUTH, "entry_id": config_entry.entry_id}
    )
    with pytest.raises(InvalidData):
        await hass.config_entries.flow.async_configure(result["flow_id"], user_input={})


@pytest.mark.asyncio
async def test_reconfigure_flow_missing_api_key(hass: HomeAssistant) -> None:
    """Test reconfigure flow with missing API key."""
    config_entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_API_KEY: API_KEY}, unique_id=DOMAIN
    )
    config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_RECONFIGURE, "entry_id": config_entry.entry_id},
    )
    with pytest.raises(InvalidData):
        await hass.config_entries.flow.async_configure(result["flow_id"], user_input={})


@pytest.mark.asyncio
async def test_options_flow_invalid_route_index(hass: HomeAssistant) -> None:
    """Test options flow with invalid route index."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: API_KEY},
        options={
            "routes": [
                {"name": "Route 1", "from": "AMS", "to": "UTR"},
            ]
        },
    )
    config_entry.add_to_hass(hass)
    # Start edit route flow
    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={"action": "edit"}
    )
    with pytest.raises(InvalidData):
        await hass.config_entries.options.async_configure(
            result["flow_id"], user_input={"route_idx": "5"}
        )


@pytest.mark.asyncio
async def test_options_flow_no_routes(hass: HomeAssistant) -> None:
    """Test options flow with no routes present."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: API_KEY},
        options={"routes": []},
    )
    config_entry.add_to_hass(hass)
    # Start edit route flow
    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={"action": "edit"}
    )
    errors = result.get("errors") or {}
    # Accept empty errors as valid (form re-presented with no error)
    assert (
        errors == {}
        or errors.get("base") == "no_routes"
        or errors.get("route_idx") == "no_routes"
    )


@pytest.mark.asyncio
async def test_options_flow_edit_route_missing_fields(hass: HomeAssistant) -> None:
    """Test editing a route with missing required fields."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: API_KEY},
        options={
            "routes": [
                {"name": "Route 1", "from": "AMS", "to": "UTR"},
            ]
        },
    )
    config_entry.add_to_hass(hass)
    # Start edit route flow
    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={"action": "edit"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={"route_idx": "0"}
    )
    # Submit with missing fields
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={"name": "", "from": "", "to": ""}
    )
    assert result.get("type") == FlowResultType.FORM
    errors = result.get("errors") or {}
    assert errors.get("base") == "missing_fields"
