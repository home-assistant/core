"""Heiman Storage System.

Provides persistent storage for:
- OAuth tokens
- User configurations
- Device lists
- Language data
- Device specifications
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

_LOGGER = logging.getLogger(__name__)


class HeimanStorage:
    """Base class for Heiman storage system."""

    def __init__(
        self,
        root_path: str,
        loop: asyncio.AbstractEventLoop | None = None,
    ) -> None:
        """Initialize storage.

        Args:
            root_path: Root path for storage files
            loop: Event loop
        """
        self._root_path = root_path
        self._loop = loop or asyncio.get_running_loop()
        self._data: dict[str, Any] = {}
        self._initialized = False

    async def init_async(self) -> bool:
        """Initialize storage asynchronously.

        Returns:
            True if successful
        """
        if self._initialized:
            return True

        try:
            # Load existing data
            await self.load_async()
            self._initialized = True
            _LOGGER.debug("Storage initialized at %s", self._root_path)
        except Exception as err:  # noqa: BLE001
            _LOGGER.error("Failed to initialize storage: %s", err)
            return False
        else:
            return True

    async def load_async(self) -> None:
        """Load data from disk."""
        # To be implemented by subclasses

    async def save_async(self, domain: str, name: str, data: Any) -> None:
        """Save data to disk.

        Args:
            domain: Data domain (e.g., 'auth_tokens', 'user_configs')
            name: Data name within domain
            data: Data to save
        """
        # To be implemented by subclasses

    def get(self, key: str, default: Any = None) -> Any:
        """Get value from cache.

        Args:
            key: Key to look up
            default: Default value if not found

        Returns:
            Cached value or default
        """
        return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Set value in cache.

        Args:
            key: Key to set
            value: Value to store
        """
        self._data[key] = value

    def remove(self, key: str) -> None:
        """Remove value from cache.

        Args:
            key: Key to remove
        """
        if key in self._data:
            del self._data[key]

    def clear(self) -> None:
        """Clear all cached data."""
        self._data.clear()


class TokenStorage(HeimanStorage):
    """Storage for OAuth tokens."""

    def set_access_token(self, token: str, expires_in: int) -> None:
        """Store access token with expiry."""
        self.set("access_token", token)
        self.set("token_expires_at", time.time() + expires_in)
        self.set("token_type", "bearer")

    def get_access_token(self) -> str | None:
        """Get access token if not expired."""
        token = self.get("access_token")
        expires_at = self.get("token_expires_at")

        if token and expires_at and time.time() < expires_at:
            return token
        return None

    def is_token_valid(self) -> bool:
        """Check if stored token is still valid."""
        return self.get_access_token() is not None

    def clear_token(self) -> None:
        """Clear stored token."""
        self.remove("access_token")
        self.remove("token_expires_at")
        self.remove("token_type")


class AuthTokenStorage(HeimanStorage):
    """Enhanced OAuth token storage with refresh token support."""

    async def save_auth_tokens(
        self,
        user_id: str,
        access_token: str,
        refresh_token: str,
        expires_in: int,
        token_type: str = "bearer",
    ) -> None:
        """Save OAuth tokens.

        Args:
            user_id: User identifier
            access_token: Access token
            refresh_token: Refresh token
            expires_in: Token expiration time in seconds
            token_type: Token type (default: bearer)
        """
        auth_data = {
            "user_id": user_id,
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": token_type,
            "expires_at": time.time() + expires_in,
            "created_at": time.time(),
        }

        await self.save_async(domain="auth_tokens", name=user_id, data=auth_data)
        _LOGGER.info("Saved auth tokens for user: %s", user_id)

    async def load_auth_tokens(self, user_id: str) -> dict[str, Any] | None:
        """Load OAuth tokens.

        Args:
            user_id: User identifier

        Returns:
            Auth tokens dict or None if not found/expired
        """
        await self.load_async()
        auth_data = self.get(user_id)

        if not auth_data:
            return None

        # Check if token is expired
        expires_at = auth_data.get("expires_at", 0)
        if time.time() >= expires_at:
            _LOGGER.warning("Auth token expired for user: %s", user_id)
            return None

        return auth_data

    async def update_access_token(
        self,
        user_id: str,
        access_token: str,
        expires_in: int,
    ) -> None:
        """Update access token only.

        Args:
            user_id: User identifier
            access_token: New access token
            expires_in: New expiration time in seconds
        """
        await self.load_async()
        auth_data = self.get(user_id)

        if auth_data:
            auth_data["access_token"] = access_token
            auth_data["expires_at"] = time.time() + expires_in
            auth_data["updated_at"] = time.time()

            await self.save_async(
                domain="auth_tokens",
                name=user_id,
                data={user_id: auth_data},
            )
            _LOGGER.debug("Updated access token for user: %s", user_id)

    async def remove_auth_tokens(self, user_id: str) -> None:
        """Remove auth tokens.

        Args:
            user_id: User identifier
        """
        await self.load_async()
        self.remove(user_id)
        await self.save_async(domain="auth_tokens", name=user_id, data=None)
        _LOGGER.debug("Removed auth tokens for user: %s", user_id)


class UserConfigStorage(HeimanStorage):
    """Storage for user configurations."""

    async def save_user_config(
        self,
        uid: str,
        cloud_server: str,
        config: dict[str, Any],
    ) -> None:
        """Save user configuration.

        Args:
            uid: User ID
            cloud_server: Cloud server region
            config: Configuration dictionary
        """
        config_key = f"{uid}_{cloud_server}"
        await self.save_async(domain="user_configs", name=config_key, data=config)
        _LOGGER.info("Saved user config: %s", config_key)

    async def load_user_config(
        self,
        uid: str,
        cloud_server: str,
    ) -> dict[str, Any] | None:
        """Load user configuration.

        Args:
            uid: User ID
            cloud_server: Cloud server region

        Returns:
            Configuration dictionary or None
        """
        config_key = f"{uid}_{cloud_server}"
        await self.load_async()
        return self.get(config_key)

    async def update_user_config(
        self,
        uid: str,
        cloud_server: str,
        updates: dict[str, Any],
    ) -> None:
        """Update user configuration.

        Args:
            uid: User ID
            cloud_server: Cloud server region
            updates: Updates to apply
        """
        config_key = f"{uid}_{cloud_server}"
        await self.load_async()

        existing_config = self.get(config_key, {})
        existing_config.update(updates)

        await self.save_async(
            domain="user_configs",
            name=config_key,
            data=existing_config,
        )
        _LOGGER.debug("Updated user config: %s", config_key)

    async def remove_user_config(self, uid: str, cloud_server: str) -> None:
        """Remove user configuration.

        Args:
            uid: User ID
            cloud_server: Cloud server region
        """
        config_key = f"{uid}_{cloud_server}"
        await self.load_async()
        self.remove(config_key)
        await self.save_async(domain="user_configs", name=config_key, data=None)


class DeviceCacheStorage(HeimanStorage):
    """Storage for device list caching."""

    async def cache_devices(
        self,
        home_id: str,
        devices: dict[str, Any],
        ttl: int = 3600,
    ) -> None:
        """Cache device list.

        Args:
            home_id: Home identifier
            devices: Device dictionary
            ttl: Time to live in seconds (default: 1 hour)
        """
        cache_data = {"devices": devices, "cached_at": time.time(), "ttl": ttl}

        await self.save_async(domain="device_cache", name=home_id, data=cache_data)
        _LOGGER.debug("Cached %s devices for home %s", len(devices), home_id)

    async def get_cached_devices(self, home_id: str) -> dict[str, Any] | None:
        """Get cached devices.

        Args:
            home_id: Home identifier

        Returns:
            Device dictionary or None if not found/expired
        """
        await self.load_async()
        cache_data = self.get(home_id)

        if not cache_data:
            return None

        # Check if cache is expired
        cached_at = cache_data.get("cached_at", 0)
        ttl = cache_data.get("ttl", 3600)

        if time.time() - cached_at > ttl:
            _LOGGER.warning("Device cache expired for home %s", home_id)
            return None

        return cache_data.get("devices", {})

    async def clear_device_cache(self, home_id: str) -> None:
        """Clear device cache.

        Args:
            home_id: Home identifier
        """
        await self.load_async()
        self.remove(home_id)
        await self.save_async(domain="device_cache", name=home_id, data=None)
        _LOGGER.debug("Cleared device cache for home %s", home_id)


class LanguageDataStorage(HeimanStorage):
    """Storage for language/i18n data."""

    async def save_language_data(self, language: str, data: dict[str, Any]) -> None:
        """Save language translation data.

        Args:
            language: Language code (e.g., 'en', 'zh-Hans')
            data: Translation dictionary
        """
        await self.save_async(domain="language_data", name=language, data=data)
        _LOGGER.debug("Saved language data for: %s", language)

    async def load_language_data(self, language: str) -> dict[str, Any] | None:
        """Load language translation data.

        Args:
            language: Language code

        Returns:
            Translation dictionary or None
        """
        await self.load_async()
        return self.get(language)

    async def get_translation(
        self,
        language: str,
        key: str,
        default: str | None = None,
    ) -> str | None:
        """Get a translation.

        Args:
            language: Language code
            key: Translation key
            default: Default value if not found

        Returns:
            Translated string or default
        """
        lang_data = await self.load_language_data(language)
        if not lang_data:
            return default

        # Support nested keys (e.g., "device.type.sensor")
        keys = key.split(".")
        value = lang_data
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default

        return value if isinstance(value, str) else default


class SpecCacheStorage(HeimanStorage):
    """Storage for device specification caching."""

    async def cache_spec(
        self,
        product_id: str,
        spec_data: dict[str, Any],
        ttl: int = 86400,
    ) -> None:
        """Cache device specification.

        Args:
            product_id: Product identifier
            spec_data: Specification dictionary
            ttl: Time to live in seconds (default: 24 hours)
        """
        cache_data = {"spec": spec_data, "cached_at": time.time(), "ttl": ttl}

        await self.save_async(domain="spec_cache", name=product_id, data=cache_data)
        _LOGGER.debug("Cached spec for product %s", product_id)

    async def get_cached_spec(self, product_id: str) -> dict[str, Any] | None:
        """Get cached specification.

        Args:
            product_id: Product identifier

        Returns:
            Specification dictionary or None
        """
        await self.load_async()
        cache_data = self.get(product_id)

        if not cache_data:
            return None

        # Check if cache is expired
        cached_at = cache_data.get("cached_at", 0)
        ttl = cache_data.get("ttl", 86400)

        if time.time() - cached_at > ttl:
            _LOGGER.warning("Spec cache expired for product %s", product_id)
            return None

        return cache_data.get("spec", {})

    async def clear_spec_cache(self, product_id: str) -> None:
        """Clear spec cache.

        Args:
            product_id: Product identifier
        """
        await self.load_async()
        self.remove(product_id)
        await self.save_async(domain="spec_cache", name=product_id, data=None)
        _LOGGER.debug("Cleared spec cache for product %s", product_id)
