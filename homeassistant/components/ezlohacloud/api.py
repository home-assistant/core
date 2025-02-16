import logging
import requests

_LOGGER = logging.getLogger(__name__)

API_BASE_URL = "http://host.docker.internal:8080/api/auth"


def authenticate(username, password):
    """Calls the actual Ezlo API for authentication."""
    _LOGGER.info("Sending login request to Ezlo API...")

    payload = {
        "username": username,
        "password": password,
        "oem_id": "1",  # Required as per cURL request
    }

    try:
        response = requests.post(f"{API_BASE_URL}/login", json=payload, timeout=10)
        response_data = response.json()

        if response.status_code == 200 and response_data.get("status") == 1:
            _LOGGER.info("Authentication successful!")

            token = response_data["data"]["token"]
            expiry_time = response_data["data"]["expires"]

            return {
                "success": True,
                "token": token,
                "expires_at": expiry_time,
                "user": {
                    "username": username,
                    "oem_id": 1,
                },
            }

        _LOGGER.warning(f"Login failed: {response_data}")
        return {"success": False, "error": "Invalid credentials or API error"}

    except requests.exceptions.RequestException as e:
        _LOGGER.error(f"API request failed: {e}")
        return {"success": False, "error": "API connection failed"}


def signup(username, email, password):
    """Sends signup request to Ezlo API and returns the response."""
    _LOGGER.info("Sending signup request to Ezlo API...")

    payload = {
        "username": username,
        "password": password,
        "email": email,
        "uuid": "ad58a0a0-3517-11ed-890c-31443f0b6e4c",
    }

    try:
        response = requests.post(f"{API_BASE_URL}/signup", json=payload, timeout=5)
        response.raise_for_status()

        data = response.json()
        if data.get("status") == 1 and "data" in data:
            _LOGGER.info("Signup successful.")
            return {"success": True, "message": "Signup successful!"}
        else:
            _LOGGER.warning("Signup failed. Response: %s", data)
            return {"success": False, "error": "Signup failed"}

    except requests.RequestException as err:
        _LOGGER.error("Signup API request failed: %s", err)
        return {"success": False, "error": "API request failed"}
