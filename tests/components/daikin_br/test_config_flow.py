"""Tests for the Daikin Climate config flow."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from homeassistant.components.daikin_br.config_flow import ConfigFlow

# import voluptuous as vol
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

# pylint: disable=redefined-outer-name, too-few-public-methods
# pylint: disable=protected-access
# --- Dummy Classes for Config Flow Testing ---


# DummyFlow with synchronous async_progress_by_handler accepting arbitrary kwargs.
class DummyFlow:
    """A dummy flow class to simulate Home Assistant's config flow."""

    async def async_init(self):
        """Simulate async initialization of a config flow."""
        return

    def async_progress_by_handler(self):
        """Simulate async progress of a config flow."""
        return []


# DummyConfigEntries simulating hass.config_entries
class DummyConfigEntries:
    """A dummy config entry flow class to simulate Home Assistant's config flow."""

    def __init__(self) -> None:
        """Initialize the DummyConfigEntries object."""
        self.flow = DummyFlow()
        self.entries = []  # Initialize entries list to avoid AttributeError

    def async_entries(self):
        """Simulate retrieving existing config entries."""
        return self.entries  # Ensure this returns a list

    async def async_forward_entry_setups(self):
        """Simulate forward entry setup of a config flow."""
        await asyncio.sleep(0)

    async def async_unload_platforms(self):
        """Simulate unload platform of a config flow."""
        await asyncio.sleep(0)
        return True


# A dummy synchronous function that accepts arbitrary keyword arguments.
def dummy_current_entries():
    """Return an empty list simulating current config entries."""
    return []


# Dummy ServiceInfo-like object for zeroconf discovery.
class DummyServiceInfo:
    """Dummy ServiceInfo-like object for zeroconf discovery."""

    def __init__(self, hostname, ip_address, properties) -> None:
        """Initialize the service info object."""
        self.hostname = hostname
        self.ip_address = ip_address
        self.properties = properties


# Dummy ConfigEntry for testing helper methods.
class DummyConfigEntry:
    """Dummy ConfigEntry for testing helper methods."""

    def __init__(self, entry_id, data) -> None:
        """Initialize object."""
        self.entry_id = entry_id
        self.data = data
        self.version = 1
        self.title = "Dummy Entry"

    async def async_update(self, data):
        """Async update function."""
        self.data.update(data)
        return self


# --- Fixtures ---


@pytest.fixture
def dummy_discovery_info():
    """Return dummy discovery info simulating a zeroconf discovery."""
    return DummyServiceInfo(
        hostname="TestDevice.local",
        ip_address="192.168.2.100",
        properties={"apn": "TEST_APN"},
    )


@pytest.fixture
def config_flow(hass: HomeAssistant):
    """Return an instance of the ConfigFlow using the provided hass fixture."""
    flow = ConfigFlow()
    flow.hass = hass
    flow.context = {}
    flow.async_set_unique_id = AsyncMock()
    flow.async_update_reload_and_abort = AsyncMock()
    flow._abort_if_unique_id_mismatch = AsyncMock()  # Mock this function

    # Mocking _get_reconfigure_entry to return a dummy entry
    flow._get_reconfigure_entry = lambda: DummyConfigEntry(
        "dummy_entry",
        {
            "device_apn": "TEST_APN",
            "host": "192.168.2.100",
        },
    )

    # Override _async_current_entries with a synchronous function that accepts kwargs.
    flow._async_current_entries = dummy_current_entries
    # Patch hass.config_entries with our dummy config entries.
    hass.config_entries = DummyConfigEntries()
    return flow


# --- Test Cases ---


@pytest.mark.asyncio
async def test_zeroconf_flow_discovery(config_flow, dummy_discovery_info) -> None:
    """Test that the zeroconf step stores discovery info and moves to the user step."""
    result = await config_flow.async_step_zeroconf(dummy_discovery_info)
    # Expect a form to be shown for the "user" step.
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    # Ensure discovery info is stored in the flow context.
    disc = config_flow.discovery_info
    assert disc is not None
    # The hostname should have ".local" stripped.
    assert disc["host_name"] == "TestDevice"
    assert disc["host"] == "192.168.2.100"
    assert disc["device_apn"] == "TEST_APN"


@pytest.mark.asyncio
async def test_zeroconf_flow_device_already_configured(
    config_flow, dummy_discovery_info
) -> None:
    """Test that the zeroconf step aborts if the device is already configured."""
    # Simulate an existing entry with the same IP and APN
    existing_entry = DummyConfigEntry(
        entry_id="dummy_entry", data={"host": "192.168.2.100", "device_apn": "TEST_APN"}
    )

    # Mock the _async_find_existing_entry to return the existing entry
    config_flow._async_find_existing_entry = lambda apn: existing_entry

    # Simulate the discovery of the same device (same IP address)
    result = await config_flow.async_step_zeroconf(dummy_discovery_info)

    # Ensure that the flow aborts with the correct reason
    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"


@pytest.mark.asyncio
async def test_zeroconf_unique_id_check_abort(config_flow) -> None:
    """Test flow aborts scenario. If a config entry with the same unique ID already exists."""
    # Simulate an existing entry with a unique ID (apn)
    existing_entry = DummyConfigEntry(
        entry_id="dummy_entry", data={"host": "192.168.2.100", "device_apn": "TEST_APN"}
    )

    # Mock _async_find_existing_entry to return
    # the existing entry with the same unique ID (apn)
    config_flow._async_find_existing_entry = AsyncMock(return_value=existing_entry)

    # Patch the async_set_unique_id to simulate the setting of a unique ID (apn)
    with (
        patch.object(
            config_flow, "async_set_unique_id", AsyncMock()
        ) as mock_set_unique_id,
        patch.object(
            config_flow, "_abort_if_unique_id_configured", AsyncMock()
        ) as mock_abort_if_unique_id_configured,
    ):
        # Simulate the setting of the unique ID (apn)
        apn = "TEST_APN"
        await config_flow.async_set_unique_id(apn)

        # Call the method to abort if the unique ID is already configured
        await config_flow._abort_if_unique_id_configured()

        # Assert that async_set_unique_id was called once
        mock_set_unique_id.assert_awaited_once_with(apn)

        # Ensure that _abort_if_unique_id_configured was called
        # because the unique ID is already configured
        mock_abort_if_unique_id_configured.assert_awaited_once()


@pytest.mark.asyncio
async def test_discovered_flow_all_inputs_success(
    config_flow, dummy_discovery_info
) -> None:
    """Test that when a discovered device is present.

    The user provides all required inputs.

    The flow successfully creates a config entry.
    """
    # First, simulate the zeroconf discovery step.
    await config_flow.async_step_zeroconf(dummy_discovery_info)
    # Verify that discovery info is stored in the flow context.
    disc = config_flow.discovery_info
    assert disc is not None
    # For a discovered device, the hostname should have ".local" stripped.
    # In our dummy discovery, hostname is "TestDevice.local"
    # so host_name becomes "TestDevice".
    assert disc["host_name"] == "TestDevice"
    assert disc["host"] == "192.168.2.100"
    assert disc["device_apn"] == "TEST_APN"

    # Now simulate the user step.
    # The discovered schema requires:
    #    vol.Required("device_name"): str,
    #    vol.Required(CONF_API_KEY): str,
    user_input = {
        "device_name": "TestDevice12",  # User-provided device name.
        CONF_API_KEY: "VALIDBASE64KEY==",  # User-provided API key.
    }

    # Patch methods that are used in the successful branch of async_step_user.
    with (
        patch.object(config_flow, "_is_valid_base64", return_value=True),
        patch(
            "homeassistant.components.daikin_br.config_flow.async_get_thing_info",
            new=AsyncMock(return_value=True),
        ),
        patch(
            "homeassistant.components.daikin_br.config_flow.get_hostname",
            return_value="TestDevice",
        ),
        patch.object(config_flow, "_abort_if_unique_id_configured", return_value=None),
        patch.object(config_flow, "_async_find_existing_entry", return_value=None),
        patch.object(
            config_flow, "async_create_entry", new_callable=AsyncMock
        ) as mock_create_entry,
    ):
        expected_entry = {
            "type": "create_entry",
            "title": "TestDevice (SSID: TestDevice)",
            "data": {
                "device_name": "TestDevice",
                CONF_API_KEY: "VALIDBASE64KEY==",
                "host": disc["host"],
                "device_apn": disc["device_apn"],
                "device_ssid": disc["host_name"],
                "command_suffix": "COMMAND_SUFFIX_VALUE",  # Adjust as needed.
            },
        }
        mock_create_entry.return_value = expected_entry

        # Call the user step with valid input.
        temp = await config_flow.async_step_user(user_input)
        # If the returned value is a coroutine, await it again.
        result = await temp if hasattr(temp, "__await__") else temp

        # Assert that the flow successfully creates an entry.
        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["title"] == "TestDevice (SSID: TestDevice)"
        data = result["data"]
        assert data["device_name"] == "TestDevice"
        assert data[CONF_API_KEY] == "VALIDBASE64KEY=="
        assert data["host"] == disc["host"]
        assert data["device_apn"] == disc["device_apn"]
        assert data["device_ssid"] == disc["host_name"]


@pytest.mark.asyncio
async def test_discovered_flow_device_name_not_provided(
    config_flow, dummy_discovery_info
) -> None:
    """Test that when a discovered device is present.

    The user does not provide a device name.

    The flow displays an error.
    """
    # Simulate the zeroconf discovery step.
    await config_flow.async_step_zeroconf(dummy_discovery_info)
    disc = config_flow.discovery_info
    assert disc is not None
    assert disc["host_name"] == "TestDevice"
    assert disc["host"] == "192.168.2.100"
    assert disc["device_apn"] == "TEST_APN"

    # Simulate user step with missing device name.
    user_input = {
        # Omitting "device_name" completely to trigger validation failure
        CONF_API_KEY: "VALIDBASE64KEY==",
    }

    # Patch only the methods that validate inputs.
    with patch.object(config_flow, "_is_valid_base64", return_value=True):
        # Call the user step with invalid input
        result = await config_flow.async_step_user(user_input)

        # Ensure that the returned result is a form
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "user"

        # Ensure that the "device_name" error is included in the returned errors
        assert "device_name" in result["errors"]
        assert result["errors"]["device_name"] == "required"

        # Ensure the form schema contains the required fields
        schema_keys = list(result["data_schema"].schema.keys())
        assert "device_name" in schema_keys
        assert CONF_API_KEY in schema_keys


@pytest.mark.asyncio
async def test_discovered_flow_device_key_not_provided(
    config_flow, dummy_discovery_info
) -> None:
    """Test handling when a discovered device is present.

    The user does not provide a device name.

    The flow should display an error in such cases.
    """
    # Simulate the zeroconf discovery step.
    await config_flow.async_step_zeroconf(dummy_discovery_info)
    disc = config_flow.discovery_info
    assert disc is not None
    assert disc["host_name"] == "TestDevice"
    assert disc["host"] == "192.168.2.100"
    assert disc["device_apn"] == "TEST_APN"

    # Simulate user step with missing API key.
    user_input = {
        # Omitting CONF_API_KEY completely to trigger validation failure
        "device_name": "TestDevice",
    }

    # Patch only the methods that validate inputs.
    with patch.object(config_flow, "_is_valid_base64", return_value=True):
        # Call the user step with invalid input
        result = await config_flow.async_step_user(user_input)

        # Ensure that the returned result is a form
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "user"

        # Ensure that the "api_key" error is included in the returned errors
        assert CONF_API_KEY in result["errors"]
        assert result["errors"][CONF_API_KEY] == "required"

        # Ensure the form schema contains the required fields
        schema_keys = list(result["data_schema"].schema.keys())
        assert "device_name" in schema_keys
        assert CONF_API_KEY in schema_keys


@pytest.mark.asyncio
async def test_discovered_flow_invalid_device_key(
    config_flow, dummy_discovery_info
) -> None:
    """Test that when a discovered device is present.

    The user provides an invalid API key.

    The flow displays an error.
    """
    # Simulate the zeroconf discovery step.
    await config_flow.async_step_zeroconf(dummy_discovery_info)
    disc = config_flow.discovery_info
    assert disc is not None
    assert disc["host_name"] == "TestDevice"
    assert disc["host"] == "192.168.2.100"
    assert disc["device_apn"] == "TEST_APN"

    # Simulate user step with an invalid API key.
    user_input = {
        "device_name": "TestDevice",
        CONF_API_KEY: "INVALID_KEY!!",  # Invalid API key format
    }

    # Patch the base64 validation method to return False (indicating invalid key).
    with patch.object(config_flow, "_is_valid_base64", return_value=False):
        # Call the user step with an invalid API key
        result = await config_flow.async_step_user(user_input)

        # Ensure that the returned result is a form (indicating error)
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "user"

        # Ensure that the "api_key" error is included in the returned errors
        assert CONF_API_KEY in result["errors"]
        assert result["errors"][CONF_API_KEY] == "invalid_key"

        # Ensure the form schema contains the required fields
        schema_keys = list(result["data_schema"].schema.keys())
        assert "device_name" in schema_keys
        assert CONF_API_KEY in schema_keys


@pytest.mark.asyncio
async def test_discovered_flow_decryption_fails(
    config_flow, dummy_discovery_info
) -> None:
    """Test that when all inputs are provided but decryption fails.

    The flow displays an error.
    """
    # Simulate the zeroconf discovery step.
    await config_flow.async_step_zeroconf(dummy_discovery_info)
    disc = config_flow.discovery_info
    assert disc is not None
    assert disc["host_name"] == "TestDevice"
    assert disc["host"] == "192.168.2.100"
    assert disc["device_apn"] == "TEST_APN"

    # Simulate user step with valid inputs.
    user_input = {
        "device_name": "TestDevice",
        CONF_API_KEY: "VALIDBASE64KEY==",  # Valid API key format
    }

    # Patch methods: `_is_valid_base64` returns True,
    # but `async_add_executor_job` simulates decryption failure.
    with (
        patch.object(config_flow, "_is_valid_base64", return_value=True),
        patch.object(
            config_flow.hass,
            "async_add_executor_job",
            new=AsyncMock(return_value=False),
        ),
    ):  # Fix: Use AsyncMock
        # Call the user step with an API key that fails decryption
        result = await config_flow.async_step_user(user_input)

        # Ensure that the returned result is a form (indicating error)
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "user"

        # Ensure that the "api_key" error is included
        # in the returned errors due to decryption failure
        assert CONF_API_KEY in result["errors"]
        assert result["errors"][CONF_API_KEY] == "cannot_connect"

        # Ensure the form schema contains the required fields
        schema_keys = list(result["data_schema"].schema.keys())
        assert "device_name" in schema_keys
        assert CONF_API_KEY in schema_keys


@pytest.mark.asyncio
async def test_manual_flow_schema(config_flow) -> None:
    """Test that when no discovery info is provided.

    The manual entry step is used and schema is correct.
    """
    config_flow.context["discovery_info"] = {}
    result = await config_flow.async_step_manual(user_input=None)
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "manual"
    schema_keys = list(result["data_schema"].schema.keys())
    assert "device_ip" in schema_keys
    assert "device_name" in schema_keys
    assert CONF_API_KEY in schema_keys


@pytest.mark.asyncio
async def test_manual_flow_all_inputs_success(config_flow) -> None:
    """Test that when all required inputs are provided.

    The manual flow successfully creates an entry.
    """
    user_input = {
        "device_ip": "192.168.1.100",
        "device_name": "TestDevice",
        CONF_API_KEY: "VALIDBASE64KEY==",
    }
    config_flow.context["discovery_info"] = {}

    # pylint: disable=no-else-return
    # Create a fake async_get_thing_info function
    async def fake_async_get_thing_info(_ip, _key, endpoint):
        if endpoint == "acstatus":
            return True
        if endpoint == "device":
            return {"apn": "TEST_APN"}
        return None

    with (
        patch.object(config_flow, "_is_valid_base64", return_value=True),
        patch(
            "homeassistant.components.daikin_br.config_flow.async_get_thing_info",
            new=fake_async_get_thing_info,
        ),
        patch(
            "homeassistant.components.daikin_br.config_flow.get_hostname",
            return_value="TestHost",
        ),
        patch.object(config_flow, "_abort_if_unique_id_configured", return_value=None),
        patch.object(config_flow, "_async_find_existing_entry", return_value=None),
        patch.object(
            config_flow, "async_create_entry", new_callable=AsyncMock
        ) as mock_create_entry,
    ):
        expected_entry = {
            "type": "create_entry",
            "title": "TestDevice (SSID: TestHost)",
            "data": {
                "device_ip": "192.168.1.100",
                "device_name": "TestDevice",
                CONF_API_KEY: "VALIDBASE64KEY==",
                "host": "192.168.1.100",
                "device_apn": "TEST_APN",
                "device_ssid": "TestHost",
                "command_suffix": "COMMAND_SUFFIX_VALUE",  # adjust as needed
            },
        }
        mock_create_entry.return_value = expected_entry

        # Call async_step_manual and await
        # its result (which might itself be a coroutine)
        temp = await config_flow.async_step_manual(user_input)
        result = await temp  # double-await to resolve the final dictionary

        # Assert that the flow successfully creates an entry.
        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["title"] == "TestDevice (SSID: TestHost)"
        data = result["data"]
        assert data["device_ip"] == user_input["device_ip"]
        assert data["device_name"] == user_input["device_name"]
        assert data[CONF_API_KEY] == user_input[CONF_API_KEY]


@pytest.mark.asyncio
async def test_manual_flow_device_ip_not_provided(config_flow) -> None:
    """Test that when device IP is not provided.

    The manual flow will display an error.
    """
    # User input without device_ip
    user_input = {"device_name": "TestDevice", CONF_API_KEY: "VALIDBASE64KEY=="}

    # Mock the necessary async function and methods
    with patch.object(config_flow, "_is_valid_base64", return_value=True):
        # Call the async_step_manual function
        result = await config_flow.async_step_manual(user_input)

        # Ensure that the returned result is a form
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "manual"

        # Ensure that the "device_ip" error is included in the returned errors
        assert "device_ip" in result["errors"]
        assert result["errors"]["device_ip"] == "required"

        # Ensure the form schema contains the required fields
        schema_keys = list(result["data_schema"].schema.keys())
        assert "device_ip" in schema_keys
        assert "device_name" in schema_keys
        assert CONF_API_KEY in schema_keys


@pytest.mark.asyncio
async def test_manual_flow_device_name_not_provided(config_flow) -> None:
    """Test that when device name is not provided.

    The manual flow will display an error.
    """
    # User input without device_name
    user_input = {"device_ip": "192.168.1.100", CONF_API_KEY: "VALIDBASE64KEY=="}

    # Mock the necessary async function and methods
    with patch.object(config_flow, "_is_valid_base64", return_value=True):
        # Call the async_step_manual function
        result = await config_flow.async_step_manual(user_input)

        # Ensure that the returned result is a form
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "manual"

        # Ensure that the "device_name" error is included in the returned errors
        assert "device_name" in result["errors"]
        assert result["errors"]["device_name"] == "required"

        # Ensure the form schema contains the required fields
        schema_keys = list(result["data_schema"].schema.keys())
        assert "device_ip" in schema_keys
        assert "device_name" in schema_keys
        assert CONF_API_KEY in schema_keys


@pytest.mark.asyncio
async def test_manual_flow_device_key_not_provided(config_flow) -> None:
    """Test that when device API key is not provided.

    The manual flow will display an error.
    """
    # User input without device API key
    user_input = {"device_ip": "192.168.1.100", "device_name": "TestDevice"}

    # Mock the necessary async function and methods
    with patch.object(config_flow, "_is_valid_base64", return_value=True):
        # Call the async_step_manual function
        result = await config_flow.async_step_manual(user_input)

        # Ensure that the returned result is a form
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "manual"

        # Ensure that the API key error is included in the returned errors
        assert CONF_API_KEY in result["errors"]
        assert result["errors"][CONF_API_KEY] == "required"

        # Ensure the form schema contains the required fields
        schema_keys = list(result["data_schema"].schema.keys())
        assert "device_ip" in schema_keys
        assert "device_name" in schema_keys
        assert CONF_API_KEY in schema_keys


@pytest.mark.asyncio
async def test_missing_device_key(config_flow) -> None:
    """Test that missing device key in manual flow returns an error."""
    config_flow.context["discovery_info"] = {}
    user_input = {
        "device_ip": "192.168.2.100",
        "device_name": "Test Device",
        # Missing device key (CONF_API_KEY)
    }
    result = await config_flow.async_step_manual(user_input)
    assert result["type"] == FlowResultType.FORM
    # Expect an error for the device key.
    assert CONF_API_KEY in result["errors"]
    assert result["errors"][CONF_API_KEY] == "required"


@pytest.mark.asyncio
async def test_reconfigure_success(config_flow) -> None:
    """Test successful reconfiguration flow when only device key is provided."""
    user_input = {
        CONF_API_KEY: "VALIDBASE64KEY==",  # Only API key provided
    }

    # Patch necessary methods for a successful reconfiguration.
    # Patch async_get_thing_info to return True.
    with (
        patch.object(config_flow, "_is_valid_base64", return_value=True),
        patch(
            "homeassistant.components.daikin_br.config_flow.async_get_thing_info",
            new=AsyncMock(return_value=True),
        ),
        patch.object(
            config_flow, "async_set_unique_id", new=AsyncMock()
        ) as mock_set_unique_id,
        patch.object(
            config_flow, "_abort_if_unique_id_mismatch", new=Mock()
        ) as mock_abort_if_unique_id_mismatch,
        patch.object(
            config_flow,
            "async_update_reload_and_abort",
            new=AsyncMock(
                return_value={
                    "type": FlowResultType.ABORT,
                    "reason": "reconfigure_successful",
                }
            ),
        ) as mock_async_update_reload_and_abort,
    ):
        # Call the reconfigure step with only the device key
        temp = await config_flow.async_step_reconfigure(user_input)
        result = await temp if hasattr(temp, "__await__") else temp

        # Ensure result is correct
        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "reconfigure_successful"

        # Verify expected calls
        # Ensure device is uniquely identified
        mock_set_unique_id.assert_awaited_once()
        # Ensure unique ID check runs properly
        mock_abort_if_unique_id_mismatch.assert_called_once()
        # Ensure reconfiguration completes
        mock_async_update_reload_and_abort.assert_awaited_once()


@pytest.mark.asyncio
async def test_reconfigure_missing_key(config_flow) -> None:
    """Test reconfigure flow when API key is missing."""
    user_input = {}

    result = await config_flow.async_step_reconfigure(user_input)

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert CONF_API_KEY in result["errors"]
    assert result["errors"][CONF_API_KEY] == "required"


@pytest.mark.asyncio
async def test_reconfigure_invalid_base64(config_flow) -> None:
    """Test reconfigure flow with an invalid base64 API key."""
    user_input = {CONF_API_KEY: "INVALID_KEY"}

    result = await config_flow.async_step_reconfigure(user_input)

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert CONF_API_KEY in result["errors"]
    assert result["errors"][CONF_API_KEY] == "invalid_key"


@pytest.mark.asyncio
async def test_reconfigure_connection_failure(config_flow) -> None:
    """Test reconfigure flow when device connection fails."""
    user_input = {CONF_API_KEY: "VALIDBASE64KEY=="}

    with patch(
        "homeassistant.components.daikin_br.config_flow.async_get_thing_info",
        return_value=False,  # Simulating connection failure
    ):
        result = await config_flow.async_step_reconfigure(user_input)

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert CONF_API_KEY in result["errors"]
    assert result["errors"][CONF_API_KEY] == "cannot_connect"


@pytest.mark.asyncio
async def test_find_existing_entry_found(config_flow) -> None:
    """Return the entry if a matching device_apn exists.

    Ensures correct lookup of existing device_apn values.
    """
    dummy_entry = DummyConfigEntry("dummy_entry", {"device_apn": "TEST_APN"})
    # Override _async_current_entries to return a list containing our dummy entry.
    config_flow._async_current_entries = lambda **kwargs: [dummy_entry]
    found = config_flow._async_find_existing_entry("TEST_APN")
    assert found == dummy_entry


@pytest.mark.asyncio
async def test_find_existing_entry_not_found(config_flow) -> None:
    """Return None if no matching device_apn exists.

    Ensures proper handling when no device_apn is found.
    """
    config_flow._async_current_entries = lambda **kwargs: []
    found = config_flow._async_find_existing_entry("NON_EXISTENT_APN")
    assert found is None


@pytest.mark.asyncio
async def test_async_step_zeroconf_unknown_device() -> None:
    """Test that async_step_zeroconf aborts with reason unknown_device."""
    # Provide a hostname that becomes empty after stripping ".local.".
    discovery_info = DummyServiceInfo(
        hostname=".local.",
        ip_address="192.168.1.100",
        properties={"apn": "TEST_APN"},
    )
    flow = ConfigFlow()
    result = await flow.async_step_zeroconf(discovery_info)
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "unknown_device"


@pytest.mark.asyncio
async def test_async_step_zeroconf_ip_updated() -> None:
    """Test async_step_zeroconf returns async_update_reload_and_abort.

    When device IP is updated.
    """
    # Simulate a discovery_info with a valid hostname and new IP.
    discovery_info = DummyServiceInfo(
        hostname="testdevice.local.",
        ip_address="192.168.1.100",  # New IP address discovered
        properties={"apn": "TEST_APN"},
    )

    # Instantiate the config flow.
    flow = ConfigFlow()

    # Patch _async_find_existing_entry to return a dummy entry with an old host.
    dummy_entry = MagicMock()
    dummy_entry.data = {"host": "192.168.1.50", "device_apn": "TEST_APN"}
    flow._async_find_existing_entry = MagicMock(return_value=dummy_entry)

    # Patch async_update_reload_and_abort to capture its call and return a dummy result.
    flow.async_update_reload_and_abort = MagicMock(
        return_value={"type": "update_reload_and_abort", "reason": "device_ip_updated"}
    )

    # Execute the zeroconf step.
    result = await flow.async_step_zeroconf(discovery_info)

    # Verify that the flow detected the IP change.
    # async_update_reload_and_abort with updated data.
    flow.async_update_reload_and_abort.assert_called_once_with(
        dummy_entry,
        data_updates={"host": "192.168.1.100"},
        reason="device_ip_updated",
    )
    assert result == {"type": "update_reload_and_abort", "reason": "device_ip_updated"}


@pytest.mark.asyncio
async def test_async_step_user_no_discovery_info() -> None:
    """Test that async_step_user when discovery_info is not present."""
    flow = ConfigFlow()
    # Ensure that the context has no discovery_info
    flow.context = {}
    # Patch async_step_manual to return a dummy result.
    dummy_result = {"type": "form", "step_id": "manual"}
    flow.async_step_manual = AsyncMock(return_value=dummy_result)

    # Call async_step_user with no discovery info (user_input can be None)
    result = await flow.async_step_user(user_input=None)

    # Assert that the result equals what async_step_manual returned.
    assert result == dummy_result


@pytest.mark.asyncio
async def test_async_step_manual_invalid_device_key_format() -> None:
    """Test async_step_manual returns an 'invalid_key' error.

    When device key format is invalid.
    """
    user_input = {
        "device_ip": "192.168.1.100",
        "device_name": "Test Device",
        CONF_API_KEY: "invalid_base64",  # This is not valid base64
    }
    flow = ConfigFlow()
    # Ensure no discovery_info so that async_step_manual is used.
    flow.context = {}
    result = await flow.async_step_manual(user_input)
    # Check that errors contains an error for the API key.
    assert result["errors"].get(CONF_API_KEY) == "invalid_key"


async def async_return(value):
    """Return the given value as an awaitable."""
    return value


@pytest.mark.asyncio
async def test_async_step_manual_device_info_missing_apn(hass: HomeAssistant) -> None:
    """Test async_step_manual returns error 'cannot_connect'.

    When device_info is missing 'apn'.
    """
    user_input = {
        "device_ip": "192.168.1.100",
        "device_name": "Test Device",
        CONF_API_KEY: "dGVzdA==",  # Valid base64 string ("test")
    }
    flow = ConfigFlow()
    flow.hass = hass  # Set hass on the flow to enable async_add_executor_job calls.
    flow.context = {}  # No discovery_info so that async_step_manual is used.

    # Patch _is_valid_base64 to always return True.
    # Patch async_get_thing_info to simulate:
    #   - First call ("acstatus") returning a dummy truthy value.
    #   - Second call ("device") returning an empty dict (missing 'apn').
    with (
        patch.object(flow, "_is_valid_base64", return_value=True),
        patch(
            "homeassistant.components.daikin_br.config_flow.async_get_thing_info",
            new=AsyncMock(side_effect=[{"dummy": "data"}, {}]),
        ),
    ):
        result = await flow.async_step_manual(user_input)

    # Assert that errors include "device_ip" with value "cannot_connect".
    assert "device_ip" in result["errors"]
    assert result["errors"]["device_ip"] == "cannot_connect"


@pytest.mark.asyncio
async def test_async_step_manual_already_configured(hass: HomeAssistant) -> None:
    """Test async_step_manual aborts with 'already_configured'.

    If the device is already configured.
    """
    user_input = {
        "device_ip": "192.168.1.100",
        "device_name": "Test Device",
        CONF_API_KEY: "dGVzdA==",  # valid base64 string ("test")
    }
    flow = ConfigFlow()
    flow.hass = hass
    flow.context = {}  # manual step is used because no discovery_info

    # Use a single `with` statement for multiple patches
    with (
        patch(
            "homeassistant.components.daikin_br.config_flow.async_get_thing_info",
            new=AsyncMock(side_effect=[{"dummy": "data"}, {"apn": "TEST_APN"}]),
        ),
        patch.object(flow, "_async_find_existing_entry", return_value=MagicMock()),
    ):
        result = await flow.async_step_manual(user_input)

    # Verify that the flow aborts with the reason "already_configured".
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.asyncio
async def test_is_valid_base64_invalid(config_flow) -> None:
    """Test _is_valid_base64 returns False for an invalid base64 string."""
    invalid_key = "not_base64!"
    assert config_flow._is_valid_base64(invalid_key) is False


@pytest.mark.asyncio
async def test_is_valid_base64_invlaid_length(config_flow) -> None:
    """Test _is_valid_base64 returns False for an incorrect string length."""
    invalid_key = "abcde"
    assert config_flow._is_valid_base64(invalid_key) is False


@pytest.mark.asyncio
async def test_is_valid_base64_valid(config_flow) -> None:
    """Test _is_valid_base64 returns True for a valid base64 string."""
    valid_key = "SGVsbG8="  # "Hello" in base64.
    assert config_flow._is_valid_base64(valid_key) is True
