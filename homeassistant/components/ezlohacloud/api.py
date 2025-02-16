import logging
import time

_LOGGER = logging.getLogger(__name__)


def authenticate(username, password):
    # """Simulated authentication for testing with a 1-minute expiration."""

    _LOGGER.info("🚀 Ezlo HA Cloud: Simulated authentication request")
    # _LOGGER.debug(f"🔑 Attempting login for username: {username}")

    # Simulated network delay
    time.sleep(1)

    # Mocked authentication logic (Replace with real API later)
    if username == "admin" and password == "password123":
        _LOGGER.info("✅ Ezlo HA Cloud: Authentication successful")

        expiry_time = time.time() + 60  # ✅ Token expires in 1 minute
        return {
            "success": True,
            "token": "dummy_token_abc123",
            "user": {"name": "Fahad Khan", "email": "fahad@example.com"},
            "expires_in": 60,  # ✅ Explicit expiry time
            "expires_at": expiry_time,
        }

    _LOGGER.warning("⚠️ Ezlo HA Cloud: Authentication failed (Invalid credentials)")
    return {"success": False, "error": "Invalid username or password"}
