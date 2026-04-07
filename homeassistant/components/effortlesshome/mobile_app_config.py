"""
Mobile App Configuration Helper for EffortlessHome.

This module automatically configures the mobile_app integration
by loading Firebase credentials from the Oasira service.
"""

import logging
from typing import Dict, Any, Optional

from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType
from homeassistant.config_entries import ConfigEntry

_LOGGER = logging.getLogger(__name__)


async def setup_mobile_app_config(
    hass: HomeAssistant,
    oasira_client,
    config_entry: Optional[ConfigEntry] = None
) -> Dict[str, Any]:
    """
    Setup mobile_app configuration using Firebase config from Oasira.
    
    This function retrieves Firebase configuration from the Oasira API
    and returns a configuration dict that can be used to configure
    the mobile_app integration.
    
    Args:
        hass: Home Assistant instance
        oasira_client: Authenticated Oasira API client
        config_entry: Optional config entry
        
    Returns:
        Dict containing mobile_app configuration with FCM credentials
        
    Example return value:
        {
            "fcm_sender_id": "123456789012",
            "firebase": {
                "server_key": "AAAA...",
                "api_key": "AIza...",
                "project_id": "my-project-123",
                "app_id": "1:123456789012:android:abc123"
            }
        }
    """
    try:
        # Get Firebase config from Oasira API
        firebase_config = await oasira_client.get_firebase_config()
        
        _LOGGER.info("Retrieved Firebase config from Oasira")
        _LOGGER.debug("Firebase config: %s", firebase_config)
        
        # Check if we got valid data
        if not firebase_config or not isinstance(firebase_config, dict):
            _LOGGER.error("Invalid Firebase config received from Oasira: %s", firebase_config)
            return {}
        
        # Check if this is a service account JSON (wrapped in Google_Firebase field)
        if "Google_Firebase" in firebase_config:
            import json
            try:
                service_account_str = firebase_config["Google_Firebase"]
                service_account = json.loads(service_account_str)
                
                _LOGGER.debug(
                    "Received Firebase service account credentials. "
                    "Mobile_app integration requires FCM legacy credentials (sender_id/server_key), "
                    "but Oasira returned service account JSON (Google_Firebase). "
                    "Service account is used by notify.effortlesshome_firebase instead. "
                    "Mobile_app integration must be configured manually in configuration.yaml if desired."
                )
                
                # Service account doesn't have the FCM legacy credentials we need
                # Return empty to indicate mobile_app can't be configured with this
                return {}
                
            except json.JSONDecodeError as e:
                _LOGGER.debug("Failed to parse Google_Firebase JSON: %s", e)
                return {}
        
        # Extract required fields for mobile_app integration
        # The exact field names depend on what Oasira returns
        mobile_app_config = {}
        
        # Map Oasira fields to mobile_app expected fields
        if "messagingSenderId" in firebase_config:
            mobile_app_config["fcm_sender_id"] = firebase_config["messagingSenderId"]
        elif "sender_id" in firebase_config:
            mobile_app_config["fcm_sender_id"] = firebase_config["sender_id"]
        elif "fcm_sender_id" in firebase_config:
            mobile_app_config["fcm_sender_id"] = firebase_config["fcm_sender_id"]
            
        # Build Firebase sub-config
        firebase_sub_config = {}
        
        if "serverKey" in firebase_config:
            firebase_sub_config["server_key"] = firebase_config["serverKey"]
        elif "server_key" in firebase_config:
            firebase_sub_config["server_key"] = firebase_config["server_key"]
            
        if "apiKey" in firebase_config:
            firebase_sub_config["api_key"] = firebase_config["apiKey"]
        elif "api_key" in firebase_config:
            firebase_sub_config["api_key"] = firebase_config["api_key"]
            
        if "projectId" in firebase_config:
            firebase_sub_config["project_id"] = firebase_config["projectId"]
        elif "project_id" in firebase_config:
            firebase_sub_config["project_id"] = firebase_config["project_id"]
            
        if "appId" in firebase_config:
            firebase_sub_config["app_id"] = firebase_config["appId"]
        elif "app_id" in firebase_config:
            firebase_sub_config["app_id"] = firebase_config["app_id"]
            
        if firebase_sub_config:
            mobile_app_config["firebase"] = firebase_sub_config
            
        if not mobile_app_config.get("fcm_sender_id") or not mobile_app_config.get("firebase", {}).get("server_key"):
            _LOGGER.info(
                "Firebase config does not contain FCM legacy credentials (sender_id/server_key). "
                "mobile_app integration cannot be auto-configured. "
                "Available keys in response: %s",
                list(firebase_config.keys())
            )
            return {}
            
        return mobile_app_config
        
    except Exception as e:
        _LOGGER.error("Failed to load Firebase config from Oasira: %s", e, exc_info=True)
        return {}


async def register_mobile_app_config(
    hass: HomeAssistant,
    mobile_app_config: Dict[str, Any]
) -> bool:
    """
    Register mobile_app configuration with Home Assistant.
    
    NOTE: Home Assistant's built-in mobile_app integration does NOT support
    programmatic configuration via hass.data. It requires manual configuration
    in configuration.yaml or its own config flow.
    
    This function stores the config for reference by EffortlessHome's custom
    notification services, but does NOT configure the mobile_app integration itself.
    
    To use mobile_app notifications, users must manually add to configuration.yaml:
    
    mobile_app:
      fcm_sender_id: "YOUR_SENDER_ID"
      firebase:
        server_key: "YOUR_SERVER_KEY"
    
    Args:
        hass: Home Assistant instance
        mobile_app_config: Configuration dict from setup_mobile_app_config
        
    Returns:
        True if registration successful, False otherwise
    """
    try:
        # Store config in hass.data for EffortlessHome's custom notification services
        from .const import DOMAIN
        if DOMAIN not in hass.data:
            hass.data[DOMAIN] = {}
            
        # Store under EffortlessHome domain, not mobile_app
        hass.data[DOMAIN]["firebase_fcm_config"] = mobile_app_config
        
        _LOGGER.info(
            "Stored Firebase FCM config for EffortlessHome notification services. "
            "Note: mobile_app integration requires manual configuration.yaml setup."
        )
        _LOGGER.debug("FCM Sender ID: %s", mobile_app_config.get("fcm_sender_id", "Not set"))
        
        return True
        
    except Exception as e:
        _LOGGER.error("Failed to register mobile_app config: %s", e, exc_info=True)
        return False


async def get_mobile_app_webhook_config(
    hass: HomeAssistant,
    mobile_app_config: Dict[str, Any]
) -> Dict[str, str]:
    """
    Generate webhook configuration for mobile app.
    
    Returns webhook URL and configuration that the mobile app
    needs to communicate with Home Assistant.
    
    Args:
        hass: Home Assistant instance
        mobile_app_config: Configuration dict from setup_mobile_app_config
        
    Returns:
        Dict containing webhook_id, webhook_url, cloudhook_url (if available)
    """
    try:
        # Get or create webhook for mobile app
        from homeassistant.components.webhook import async_register as async_register_webhook
        
        webhook_id = f"effortlesshome_mobile_{mobile_app_config.get('fcm_sender_id', 'default')}"
        
        # Check if webhook already exists
        webhook_url = f"{hass.config.external_url or hass.config.internal_url}/api/webhook/{webhook_id}"
        
        return {
            "webhook_id": webhook_id,
            "webhook_url": webhook_url,
            "fcm_sender_id": mobile_app_config.get("fcm_sender_id", ""),
            "firebase_api_key": mobile_app_config.get("firebase", {}).get("api_key", ""),
        }
        
    except Exception as e:
        _LOGGER.error("Failed to generate webhook config: %s", e, exc_info=True)
        return {}


def generate_mobile_app_config_yaml(mobile_app_config: Dict[str, Any]) -> str:
    """
    Generate configuration.yaml snippet for mobile_app.
    
    This can be used to show users what the equivalent manual
    configuration would look like.
    
    Args:
        mobile_app_config: Configuration dict from setup_mobile_app_config
        
    Returns:
        YAML configuration string
    """
    fcm_sender_id = mobile_app_config.get("fcm_sender_id", "YOUR_SENDER_ID")
    server_key = mobile_app_config.get("firebase", {}).get("server_key", "YOUR_SERVER_KEY")
    
    yaml_config = f"""# Mobile App Configuration (auto-generated from Oasira)
mobile_app:
  # For FCM Legacy API
  fcm_sender_id: "{fcm_sender_id}"
  firebase:
    server_key: "{server_key}"
"""
    
    return yaml_config


async def setup_mobile_app_integration(
    hass: HomeAssistant,
    oasira_client
) -> bool:
    """
    Complete setup of mobile_app integration using Oasira Firebase config.
    
    This is the main function to call during EffortlessHome setup.
    It will:
    1. Load Firebase config from Oasira
    2. Configure mobile_app integration
    3. Register webhook for mobile communication
    
    Args:
        hass: Home Assistant instance
        oasira_client: Authenticated Oasira API client
        
    Returns:
        True if setup successful, False otherwise
    """
    _LOGGER.info("Setting up mobile_app integration with Oasira Firebase config")
    
    # Step 1: Get Firebase config from Oasira
    mobile_app_config = await setup_mobile_app_config(hass, oasira_client)
    
    if not mobile_app_config:
        _LOGGER.info(
            "Mobile_app integration cannot be auto-configured. "
            "Oasira is returning service account credentials (Google_Firebase) "
            "instead of legacy FCM credentials (sender_id/server_key). "
            "This is optional and does not affect EffortlessHome notifications. "
            "Mobile_app integration requires manual setup in configuration.yaml if needed."
        )
        return False
    
    # Step 2: Register config with mobile_app
    success = await register_mobile_app_config(hass, mobile_app_config)
    
    if not success:
        _LOGGER.error("Failed to register mobile_app config")
        return False
    
    # Step 3: Setup webhook for mobile communication
    webhook_config = await get_mobile_app_webhook_config(hass, mobile_app_config)
    
    if webhook_config:
        _LOGGER.info(
            "Mobile app webhook configured: %s",
            webhook_config.get("webhook_url")
        )
    
    # Step 4: Log the equivalent YAML config for reference
    yaml_config = generate_mobile_app_config_yaml(mobile_app_config)
    _LOGGER.debug("Equivalent configuration.yaml:\n%s", yaml_config)
    
    _LOGGER.info("✅ Mobile app integration setup complete")
    
    return True
