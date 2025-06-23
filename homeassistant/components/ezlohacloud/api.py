"""Ezlo HA Cloud integration API for Home Assistant."""

import logging

import httpx

from .const import EZLO_API_URI, SIGNUP_UUID

_LOGGER = logging.getLogger(__name__)

AUTH_API_URL = f"{EZLO_API_URI}/api/auth"
STRIPE_API_URL = f"{EZLO_API_URI}/api/stripe"
API_URL = f"{EZLO_API_URI}/api"


async def authenticate(username, password, uuid):
    """Authenticate against Ezlo API (async)."""
    payload = {
        "username": username,
        "password": password,
        "oem_id": "1",
        "ha_instance_id": uuid,
    }
    # TODO: Move httpx.AsyncClient creation off event loop to avoid blocking warning
    client = httpx.AsyncClient(timeout=10)
    try:
        response = await client.post(f"{AUTH_API_URL}/login", json=payload)
        response.raise_for_status()
        data = response.json()
        _LOGGER.info("login response: {data}")

        token = data.get("token")
        if token and "uuid" in data:
            return {
                "success": True,
                "data": {
                    "token": token,
                    "user": {
                        "username": username,
                        "uuid": data["uuid"],
                        "oem_id": 1,
                    },
                },
                "error": None,
            }
        _LOGGER.warning("Login failed: {data}")
        return {"success": False, "data": None, "error": "Invalid credentials"}

    except httpx.RequestError as e:
        _LOGGER.error("Auth request failed: %s", e)
        return {"success": False, "data": None, "error": "API connection failed"}
    finally:
        await client.aclose()


async def signup(username, email, password, ha_instance_id):
    """Sends signup request to Go Auth API and returns the response."""
    _LOGGER.info("Sending signup request to Auth API...")
    payload = {
        "username": username,
        "password": password,
        "email": email,
        "uuid": SIGNUP_UUID,
        "ha_instance_id": ha_instance_id,
    }

    client = httpx.AsyncClient(timeout=5)
    try:
        response = await client.post(f"{AUTH_API_URL}/signup", json=payload)
        response.raise_for_status()
        data = response.json()

        token = data.get("token")
        if token:
            _LOGGER.info("Signup successful")
            return {"success": True, "data": {"token": token}, "error": None}
        _LOGGER.warning("Signup failed. Response: %s", data)
        return {
            "success": False,
            "data": None,
            "error": data.get("message", "Signup failed"),
        }

    except httpx.RequestError as e:
        _LOGGER.error("Signup failed: %s", e)
        return {"success": False, "data": None, "error": "Network error"}
    finally:
        await client.aclose()


async def create_stripe_session(user_id, price_id, back_ref_url):
    """Create a Stripe Checkout session."""
    _LOGGER.info(f"Creating Stripe checkout session for user: {user_id}")
    payload = {
        "user_id": user_id,
        "plan_price_id": price_id,
        "back_ref_url": back_ref_url,
    }

    client = httpx.AsyncClient(timeout=10)
    try:
        response = await client.post(f"{STRIPE_API_URL}/create-session", json=payload)
        response.raise_for_status()
        data = response.json()

        checkout_url = data.get("checkout_url")
        if checkout_url:
            _LOGGER.info("Stripe checkout session created.")
            return {
                "success": True,
                "data": {"checkout_url": checkout_url},
                "error": None,
            }
        _LOGGER.error("Stripe response missing checkout_url: %s", data)
        return {"success": False, "data": None, "error": "Missing checkout URL"}

    except httpx.RequestError as e:
        _LOGGER.error("Stripe checkout api error: %s", e)
        return {"success": False, "data": None, "error": "Stripe checkout api error"}
    finally:
        await client.aclose()


async def get_subscription_status(user_uuid):
    """Fetch subscription status from Ezlo backend."""
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.get(
                f"{API_URL}/subscription/status?user_uuid={user_uuid}",
                params={"user_uuid": user_uuid},
            )
            response.raise_for_status()
            data = response.json().get("data")

            if data:
                return {
                    "success": True,
                    "status": data.get("status", "unknown"),
                    "is_active": data.get("is_active", False),
                    "start_timestamp": data.get("start_timestamp", ""),
                    "end_timestamp": data.get("end_timestamp", ""),
                }

            return {"success": False, "error": "No data returned"}

    except httpx.RequestError as e:
        _LOGGER.error("Failed to fetch subscription status: %s", e)
        return {"success": False, "error": "Network error"}
