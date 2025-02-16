import requests
import logging, time

_LOGGER = logging.getLogger(__name__)

API_URL = "http://host.docker.internal:8080/api/auth/login"


def authenticate(username, password):
    """Calls the actual Ezlo API for authentication."""
    _LOGGER.info("🚀 Sending login request to Ezlo API...")

    payload = {
        "username": username,
        "password": password,
        "oem_id": "1",  # Required as per cURL request
    }

    try:
        response = requests.post(API_URL, json=payload, timeout=10)
        response_data = response.json()

        if response.status_code == 200 and response_data.get("status") == 1:
            _LOGGER.info("✅ Authentication successful!")

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

        _LOGGER.warning(f"⚠️ Login failed: {response_data}")
        return {"success": False, "error": "Invalid credentials or API error"}

    except requests.exceptions.RequestException as e:
        _LOGGER.error(f"❌ API request failed: {e}")
        return {"success": False, "error": "API connection failed"}


def signup(username, email, password):
    """Simulated sign-up API."""
    _LOGGER.info("🚀 Ezlo HA Cloud: Simulated signup request")

    # Simulated delay
    time.sleep(1)

    # ✅ Mocking success response (replace this with real API later)
    if username and email and password:
        _LOGGER.info("✅ Ezlo HA Cloud: Signup successful")
        return {
            "success": True,
            "message": "Account created successfully!",
            "user": {"name": username, "email": email},
        }

    _LOGGER.warning("⚠️ Ezlo HA Cloud: Signup failed (Invalid data)")
    return {"success": False, "error": "Invalid signup details"}
