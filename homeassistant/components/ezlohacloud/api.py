"""Ezlo HA Cloud integration API for Home Assistant."""

import logging

import requests

from .const import EZLO_API_URI, SIGNUP_UUID

_LOGGER = logging.getLogger(__name__)

AUTH_API_URL = f"{EZLO_API_URI}/api/auth"
STRIPE_API_URL = f"{EZLO_API_URI}/api/stripe"


def authenticate(username, password, uuid):
    """Calls the actual Ezlo API for authentication."""
    _LOGGER.info("Sending login request to Ezlo API...")
    _LOGGER.info(f"Sending login request with UUID: {uuid}")

    payload = {
        "username": username,
        "password": password,
        "oem_id": "1",  # Required as per cURL request
        "ha_instance_id": uuid,  # UUID is always passed
    }

    try:
        response = requests.post(f"{AUTH_API_URL}/login", json=payload, timeout=10)
        response_data = response.json()

        _LOGGER.info(f"login response: {response_data}")

        if response.status_code == 200:
            _LOGGER.info("Authentication successful!")

            token = response_data["token"]
            uuid = response_data["uuid"]
            # expiry_time = response_data["expires"]

            return {
                "success": True,
                "token": token,
                # "expires_at": expiry_time,
                "user": {
                    "username": username,
                    "oem_id": 1,
                    "uuid": uuid,
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
        "uuid": SIGNUP_UUID,
    }

    try:
        response = requests.post(f"{AUTH_API_URL}/signup", json=payload, timeout=5)
        response.raise_for_status()

        data = response.json()
        identity = data.get("data", {}).get("legacy", {}).get("identity")
        if data.get("status") == 1 and identity:
            _LOGGER.info("Signup successful.")
            return {
                "success": True,
                "message": "Signup successful!",
                "identity": identity,
            }

        _LOGGER.warning("Signup failed. Response: %s", data)
        return {"success": False, "error": "Signup failed"}

    except requests.RequestException as err:
        _LOGGER.error("Signup API request failed: %s", err)
        return {"success": False, "error": "API request failed"}


def create_stripe_session(user_id, price_id):
    """Creates a Stripe Checkout session and returns the checkout URL."""
    _LOGGER.info(f"Creating Stripe checkout session for user: {user_id}")

    payload = {
        "user_id": user_id,
        "plan_price_id": price_id,
    }

    try:
        response = requests.post(
            f"{STRIPE_API_URL}/create-session", json=payload, timeout=10
        )
        response.raise_for_status()

        data = response.json()
        checkout_url = data.get("checkout_url")

        if not checkout_url:
            _LOGGER.error("Stripe response missing checkout_url: %s", data)
            return None

        _LOGGER.info("Stripe checkout session created.")
        return {"checkout_url": checkout_url}

    except requests.RequestException as err:
        _LOGGER.error("Stripe session creation failed: %s", err)
        return None
