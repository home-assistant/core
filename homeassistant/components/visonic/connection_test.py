"""Validate panel access using the direct and cloud libraries."""

import asyncio
from typing import TYPE_CHECKING, Any
import uuid

import aiohttp
from pyvisonic import VisonicClient, VisonicClientSettings
from pyvisonicalarm.alarm import AlarmSystem
from pyvisonicalarm.core import API
from pyvisonicalarm.exceptions import (
    ConnectionTimeoutError,
    Error,
    InvalidUserCodeError,
    UnauthorizedError,
    UserCodeIncorrectError,
    WrongPanelSerialOrMasterUserCodeError,
    WrongUsernameOrPasswordError,
)

from homeassistant.const import (
    CONF_CODE,
    CONF_DEVICE,
    CONF_EMAIL,
    CONF_EXTERNAL_URL,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
)

from .const import (
    CONF_CLOUD_APP_ID,
    CONF_DEVICE_BAUD,
    CONF_PANEL_SERIAL,
    CONFIG_CLOUD_ERROR,
    CONFIG_CONNECTION_REFUSED,
    CONFIG_CONNECTION_TIMEOUT,
    CONFIG_INVALID_AUTH_OR_PIN,
    CONFIG_NO_CLOUD_PANELS,
    CONFIG_SETTINGS_INVALID,
    LOGGER,
)
from .visonic_types import DeviceType

CLOUD_AUTH_ERRORS = (
    WrongUsernameOrPasswordError,
    WrongPanelSerialOrMasterUserCodeError,
    UserCodeIncorrectError,
    InvalidUserCodeError,
    UnauthorizedError,
)


class ConnectionTest:
    """Test protocol state or cloud credentials without retaining a connection."""

    def __init__(self, session: aiohttp.ClientSession | None = None) -> None:
        """Store the shared session and authenticated panel choices."""
        self.session = session
        self.panels: dict[str, str] = {}
        self._cloud_api: API | None = None

    async def _test_direct(self, device_type: DeviceType, data: dict[str, Any]) -> None:
        """Probe for a valid status reply and retain the working serial baud."""
        client = VisonicClient(
            VisonicClientSettings(
                connection_type=device_type.value,
                host=data.get(CONF_HOST, "127.0.0.1"),
                port=int(data.get(CONF_PORT, 30000)),
                path=data.get(CONF_DEVICE, "/dev/ttyUSB0"),
                baud=int(data.get(CONF_DEVICE_BAUD, 9600)),
                force_standard_mode=True,
                retry_count=0,
            )
        )
        if (baud := await client.async_test_connection()) is None:
            raise TimeoutError("No valid panel reply during connection test")
        if device_type == DeviceType.SERIAL:
            # For serial connections save the baud so it is used first for the next connection attempt
            data[CONF_DEVICE_BAUD] = baud

    async def _discover_cloud_panels(self, data: dict[str, Any]) -> str | None:
        """Authenticate the account without creating a panel session."""
        if TYPE_CHECKING:
            assert self.session is not None
        self._cloud_api = None
        self.panels = {}
        data.setdefault(CONF_CLOUD_APP_ID, str(uuid.uuid4()))
        api = API(self.session, data[CONF_EXTERNAL_URL], data[CONF_CLOUD_APP_ID])
        async with asyncio.timeout(30):
            await api.set_rest_version()
            if not await api.authenticate_user(data[CONF_EMAIL], data[CONF_PASSWORD]):
                raise WrongUsernameOrPasswordError
            for panel in await AlarmSystem(api).get_panels():
                if not panel.panel_serial:
                    raise ValueError("Cloud panel has no serial")
                serial = panel.panel_serial.strip().upper()
                self.panels[serial] = (
                    f"{panel.alias} ({serial})" if panel.alias else serial
                )
        if not self.panels:
            return CONFIG_NO_CLOUD_PANELS
        self._cloud_api = api
        return None

    async def _test_cloud(self, data: dict[str, Any]) -> str | None:
        """Discover panels first, then validate a choice using the same user token."""
        if CONF_CODE not in data:
            return await self._discover_cloud_panels(data)
        if self._cloud_api is None and (
            error := await self._discover_cloud_panels(data)
        ):
            return error
        api = self._cloud_api
        if TYPE_CHECKING:
            assert api is not None
        serial = data.get(CONF_PANEL_SERIAL, "").strip().upper()
        if not serial and len(self.panels) == 1:
            serial = next(iter(self.panels))
        if not serial and len(self.panels) > 1:
            return None
        if serial not in self.panels:
            raise ValueError("Panel serial is not registered to this account")
        data[CONF_PANEL_SERIAL] = serial
        logged_in = False
        try:
            async with asyncio.timeout(30):
                if not await api.panel_login(serial, data[CONF_CODE]):
                    raise InvalidUserCodeError
                logged_in = True
        finally:
            if logged_in:
                try:
                    async with asyncio.timeout(10):
                        await api.panel_logout()
                except (Error, OSError, TimeoutError, aiohttp.ClientError) as err:
                    # Cleanup failures must not invalidate successful authentication.
                    LOGGER.debug(
                        "Cloud panel logout failed after successful login (%s): %s",
                        type(err).__name__,
                        err,
                    )
        return None

    async def test_connection(
        self, device_type: DeviceType, data: dict[str, Any]
    ) -> str | None:
        """Map library validation failures to config-flow errors."""
        try:
            if device_type == DeviceType.CLOUD:
                return await self._test_cloud(data)
            await self._test_direct(device_type, data)
        except CLOUD_AUTH_ERRORS as err:
            LOGGER.debug("Cloud validation failed (%s)", type(err).__name__)
            if isinstance(err, UnauthorizedError):
                self._cloud_api = None
            return CONFIG_INVALID_AUTH_OR_PIN
        except TimeoutError, ConnectionTimeoutError:
            return CONFIG_CONNECTION_TIMEOUT
        except ValueError:
            return CONFIG_SETTINGS_INVALID
        except Error as err:
            LOGGER.warning("Cloud API rejected the request (%s)", type(err).__name__)
            return CONFIG_CLOUD_ERROR
        except OSError, aiohttp.ClientError:
            return CONFIG_CONNECTION_REFUSED
        return None
