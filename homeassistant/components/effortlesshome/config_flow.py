"""Config flow for EffortlessHome integration."""
import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult

from oasira import OasiraAPIClient, OasiraAPIError
from .const import DOMAIN, NAME

_LOGGER = logging.getLogger(__name__)

CONF_EMAIL = "email"
CONF_PASSWORD = "password"
CONF_SYSTEM_ID = "system_id"
CONF_CUSTOMER_ID = "customer_id"
CONF_FIREBASE_UID = "firebase_uid"
CONF_ID_TOKEN = "id_token"
CONF_REFRESH_TOKEN = "refresh_token"


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the EffortlessHome integration setup with Firebase OAuth."""

    VERSION = 2

    def __init__(self):
        """Initialize the config flow."""
        self._firebase_uid = None
        self._id_token = None
        self._refresh_token = None
        self._email = None
        self._customer_id = None
        self._system_id = None
        self._available_systems = []

    async def async_step_user(self, user_input: dict | None = None) -> FlowResult:
        """Handle the initial step - collect email and password for Firebase auth."""
        errors = {}

        if user_input is not None:
            email = user_input.get(CONF_EMAIL)
            password = user_input.get(CONF_PASSWORD)

            if not email or not password:
                errors["base"] = "missing_fields"
            else:
                # Attempt Firebase authentication
                try:
                    auth_result = await self._authenticate_firebase(email, password)
                    
                    if auth_result:
                        self._firebase_uid = auth_result["firebase_uid"]
                        self._id_token = auth_result["id_token"]
                        self._refresh_token = auth_result["refresh_token"]
                        self._email = email
                        
                        # Fetch system list from API
                        try:
                            systems = await self._fetch_system_list(email)
                            
                            if not systems:
                                _LOGGER.warning("No systems found for user %s", email)
                                errors["base"] = "no_system_found"
                            elif len(systems) == 1:
                                # Single system - use it automatically
                                system = systems[0]
                                self._customer_id = str(system["customer_id"])
                                self._system_id = str(system["SystemID"])
                                
                                # Check if already configured
                                await self.async_set_unique_id(f"{self._customer_id}_{self._system_id}")
                                self._abort_if_unique_id_configured()
                                
                                return self.async_create_entry(
                                    title=f"{NAME} ({email})",
                                    data={
                                        CONF_EMAIL: email,
                                        CONF_FIREBASE_UID: self._firebase_uid,
                                        CONF_ID_TOKEN: self._id_token,
                                        CONF_REFRESH_TOKEN: self._refresh_token,
                                        CONF_CUSTOMER_ID: self._customer_id,
                                        CONF_SYSTEM_ID: self._system_id,
                                    },
                                )
                            else:
                                # Multiple systems - let user choose
                                self._available_systems = systems
                                return await self.async_step_select_system()
                                
                        except OasiraAPIError as err:
                            _LOGGER.error("Failed to fetch system list: %s", err)
                            errors["base"] = "cannot_connect"
                    else:
                        errors["base"] = "invalid_auth"
                        
                except Exception as err:
                    _LOGGER.exception("Unexpected error during authentication: %s", err)
                    errors["base"] = "unknown"

        data_schema = vol.Schema({
            vol.Required(CONF_EMAIL): str,
            vol.Required(CONF_PASSWORD): str,
        })

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
            description_placeholders={
                "info": "Enter your EffortlessHome account credentials to link your system."
            }
        )

    async def async_step_select_system(self, user_input: dict | None = None) -> FlowResult:
        """Handle system selection when user has multiple systems."""
        errors = {}

        if user_input is not None:
            selected_system_key = user_input.get(CONF_SYSTEM_ID)
            
            # Find the selected system
            selected_system = None
            for system in self._available_systems:
                system_key = f"{system['customer_id']}_{system['SystemID']}"
                if system_key == selected_system_key:
                    selected_system = system
                    break
            
            if selected_system:
                self._customer_id = str(selected_system["customer_id"])
                self._system_id = str(selected_system["SystemID"])
                
                # Check if already configured
                await self.async_set_unique_id(f"{self._customer_id}_{self._system_id}")
                self._abort_if_unique_id_configured()
                
                return self.async_create_entry(
                    title=f"{NAME} ({self._email})",
                    data={
                        CONF_EMAIL: self._email,
                        CONF_FIREBASE_UID: self._firebase_uid,
                        CONF_ID_TOKEN: self._id_token,
                        CONF_REFRESH_TOKEN: self._refresh_token,
                        CONF_CUSTOMER_ID: self._customer_id,
                        CONF_SYSTEM_ID: self._system_id,
                    },
                )
            else:
                errors["base"] = "invalid_system"

        # Build system selection options
        system_options = {}
        for system in self._available_systems:
            system_key = f"{system['customer_id']}_{system['SystemID']}"
            ha_url = system.get("ha_url", "Unknown")
            system_options[system_key] = f"System {system['SystemID']} - {ha_url}"

        data_schema = vol.Schema({
            vol.Required(CONF_SYSTEM_ID): vol.In(system_options),
        })

        return self.async_show_form(
            step_id="select_system",
            data_schema=data_schema,
            errors=errors,
            description_placeholders={
                "info": "Multiple systems found. Please select which system to configure."
            }
        )

    async def async_step_manual_entry(self, user_input: dict | None = None) -> FlowResult:
        """Handle manual entry of customer_id and system_id if API lookup fails."""
        errors = {}

        if user_input is not None:
            customer_id = user_input.get(CONF_CUSTOMER_ID)
            system_id = user_input.get(CONF_SYSTEM_ID)

            if not customer_id or not system_id:
                errors["base"] = "missing_fields"
            else:
                # Store the manually entered IDs
                self._customer_id = customer_id
                self._system_id = system_id
                
                # Check if already configured
                await self.async_set_unique_id(f"{self._customer_id}_{self._system_id}")
                self._abort_if_unique_id_configured()
                
                return self.async_create_entry(
                    title=f"{NAME} ({self._email})",
                    data={
                        CONF_EMAIL: self._email,
                        CONF_FIREBASE_UID: self._firebase_uid,
                        CONF_ID_TOKEN: self._id_token,
                        CONF_CUSTOMER_ID: self._customer_id,
                        CONF_SYSTEM_ID: self._system_id,
                    },
                )

        data_schema = vol.Schema({
            vol.Required(CONF_CUSTOMER_ID): str,
            vol.Required(CONF_SYSTEM_ID): str,
        })

        return self.async_show_form(
            step_id="manual_entry",
            data_schema=data_schema,
            errors=errors,
            description_placeholders={
                "info": "Enter your Customer ID and System ID to complete setup."
            }
        )

    async def _authenticate_firebase(self, email: str, password: str) -> dict[str, Any] | None:
        """Authenticate with Firebase and return user credentials.
        
        Args:
            email: User's email
            password: User's password
            
        Returns:
            Dictionary with firebase_uid and id_token, or None if authentication fails
        """
        try:
            async with OasiraAPIClient() as client:
                data = await client.firebase_sign_in(email, password)
                
                # Validate that we got the required tokens
                firebase_uid = data.get("localId")
                id_token = data.get("idToken")
                refresh_token = data.get("refreshToken")
                
                if not firebase_uid or not id_token:
                    _LOGGER.error("Firebase auth response missing required fields. Response: %s", data)
                    return None
                
                return {
                    "firebase_uid": firebase_uid,
                    "id_token": id_token,
                    "refresh_token": refresh_token,
                }
        except OasiraAPIError as err:
            _LOGGER.error("Firebase auth error: %s", err)
            return None
        except Exception as err:
            _LOGGER.exception("Error calling Firebase auth API: %s", err)
            return None

    async def _fetch_system_list(self, email: str) -> list[dict[str, Any]]:
        """Fetch list of systems for the user from EffortlessHome API.
        
        Args:
            email: User's email address
            
        Returns:
            List of system dictionaries, each containing SystemID, customer_id, ha_url, etc.
        """
        _LOGGER.debug("Fetching system list for email %s", email)
        
        if not self._id_token:
            _LOGGER.error("Cannot fetch system list: id_token is not set")
            raise OasiraAPIError("Authentication token is missing")
        
        try:
            async with OasiraAPIClient(id_token=self._id_token) as client:
                systems = await client.get_system_list_by_email(email)
                _LOGGER.info("Found %d system(s) for email %s", len(systems), email)
                return systems
        except OasiraAPIError as err:
            _LOGGER.exception("Failed to fetch system list: %s", err)
            raise
        except Exception as err:
            _LOGGER.exception("Unexpected error fetching system list: %s", err)
            raise OasiraAPIError(f"Unexpected error: {err}") from err

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow for EffortlessHome."""

    def __init__(self, config_entry):
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Optional(
                    "debug_mode",
                    default=self.config_entry.options.get("debug_mode", False),
                ): bool,
            })
        )
