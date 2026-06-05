"""Utility functions for the MQTT integration."""

import asyncio
from collections.abc import Callable, Coroutine
from functools import lru_cache
import logging
from pathlib import Path
import tempfile
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import MAX_LENGTH_STATE_STATE, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    entity_registry as er,
    template,
)
from homeassistant.helpers.typing import ConfigType
from homeassistant.util.async_ import create_eager_task

from .const import (
    ATTR_PAYLOAD,
    ATTR_QOS,
    ATTR_RETAIN,
    ATTR_TOPIC,
    CONF_CERTIFICATE,
    CONF_CLIENT_CERT,
    CONF_CLIENT_KEY,
    DEFAULT_ENCODING,
    DEFAULT_QOS,
    DEFAULT_RETAIN,
    DOMAIN,
)
from .models import DATA_MQTT, DATA_MQTT_AVAILABLE, ReceiveMessage

AVAILABILITY_TIMEOUT = 50.0

TEMP_DIR_NAME = f"home-assistant-{DOMAIN}"

_VALID_QOS_SCHEMA = vol.All(vol.Coerce(int), vol.In([0, 1, 2]))

_LOGGER = logging.getLogger(__name__)


class EnsureJobAfterCooldown:
    """Ensure at least one complete execution runs after all requests settle.

    If a task is already running when a new execute request arrives, a
    follow-up run is scheduled via the cooldown timer rather than cancelling
    the in-flight task. If no task is running, any pending cooldown timer is
    cancelled and execution starts immediately.

    We allow patching this util, as we generally have exceptions
    for sleeps/waits/debouncers/timers causing long run times in tests.

    Args:
        timeout (float): Cooldown period in seconds between the last
            schedule request and the next execution.
        callback_job (Callable[[], Coroutine[Any, None, None]]): Async
            callable invoked after each cooldown period elapses.
    """

    def __init__(
        self, timeout: float, callback_job: Callable[[], Coroutine[Any, None, None]]
    ) -> None:
        """Initialize the timer."""
        self._loop = asyncio.get_running_loop()
        self._timeout = timeout
        self._callback = callback_job
        self._task: asyncio.Task | None = None
        self._timer: asyncio.TimerHandle | None = None
        self._next_execute_time = 0.0

    def set_timeout(self, timeout: float) -> None:
        """Set a new timeout period.

        Args:
            timeout (float): New cooldown duration in seconds.
        """
        self._timeout = timeout

    async def _async_job(self) -> None:
        """Execute after a cooldown period."""
        try:
            await self._callback()
        except HomeAssistantError as ha_error:
            _LOGGER.error("%s", ha_error)

    @callback
    def _async_task_done(self, task: asyncio.Task) -> None:
        """Clear the internal task reference when the task completes.

        Args:
            task (asyncio.Task): The completed task (unused).
        """
        self._task = None

    @callback
    def async_execute(self) -> asyncio.Task:
        """Execute the callback job immediately, or reschedule if already running.

        If a task is already in progress, schedules a follow-up cooldown via
        :meth:`async_schedule` and returns the existing task.  Otherwise,
        cancels any pending timer and starts the job immediately.

        Returns:
            asyncio.Task: The running (or newly created) task for the callback.
        """
        if self._task:
            self.async_schedule()
            return self._task

        self._async_cancel_timer()
        self._task = create_eager_task(self._async_job())
        self._task.add_done_callback(self._async_task_done)
        return self._task

    @callback
    def _async_cancel_timer(self) -> None:
        """Cancel any pending cooldown timer."""
        if self._timer:
            self._timer.cancel()
            self._timer = None
            self._next_execute_time = 0.0

    @callback
    def async_schedule(self) -> None:
        """Request execution after the cooldown period.

        If no timer is pending, sets one for ``now + timeout``.  If a timer is
        already pending but the new requested time is later, pushes
        ``_next_execute_time`` forward so the timer callback will reschedule
        itself rather than firing early.
        """
        next_when = self._loop.time() + self._timeout
        if not self._timer:
            self._next_execute_time = next_when
            self._timer = self._loop.call_at(next_when, self._async_timer_reached)
            return

        if self._timer.when() < next_when:
            self._next_execute_time = next_when

    @callback
    def _async_timer_reached(self) -> None:
        """Fire the cooldown timer and either execute or reschedule.

        Called by the event loop when the timer handle elapses.  Executes the
        job immediately if the current time has reached ``_next_execute_time``;
        otherwise reschedules the timer for the updated target time.
        """
        self._timer = None
        if self._loop.time() >= self._next_execute_time:
            self.async_execute()
            return
        self._timer = self._loop.call_at(
            self._next_execute_time, self._async_timer_reached
        )

    async def async_cleanup(self) -> None:
        """Cancel any pending timer and wait for an in-progress task to finish.

        Safe to call even when no timer or task is active.  Cancels the task
        and swallows the resulting :class:`asyncio.CancelledError`; any other
        exception from the task is logged.
        """
        self._async_cancel_timer()
        if not self._task:
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        except Exception:
            _LOGGER.exception("Error cleaning up task")


def platforms_from_config(config: list[ConfigType]) -> set[Platform | str]:
    """Extract the set of platform names declared in the YAML config list.

    Each item in *config* is a dict whose keys are platform names (e.g.
    ``"alarm_control_panel"``).  Returns the union of all keys across all items.

    Args:
        config (list[ConfigType]): Parsed ``locknalert_mqtt:`` YAML section
            items, each a dict mapping platform name to a list of entity configs.

    Returns:
        set[Platform | str]: Platform names that need to be loaded.
    """
    return {key for platform in config for key in platform}


async def async_forward_entry_setup_and_setup_discovery(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    platforms: set[Platform | str],
    late: bool = False,
) -> None:
    """Forward config entry setup to any platforms not yet loaded.

    Filters *platforms* to those not already in ``mqtt_data.platforms_loaded``,
    then forwards the entry to each new platform concurrently.  After setup
    completes, marks those platforms as loaded so they are not re-initialised
    on future calls.

    Args:
        hass (HomeAssistant): The Home Assistant instance.
        config_entry (ConfigEntry): The locknalert_mqtt config entry to forward.
        platforms (set[Platform | str]): Candidate platforms to set up.
        late (bool): Reserved for future use; currently unused.
    """
    mqtt_data = hass.data[DATA_MQTT]
    platforms_loaded = mqtt_data.platforms_loaded
    new_platforms: set[Platform | str] = platforms - platforms_loaded
    tasks: list[asyncio.Task] = []
    if new_entity_platforms := new_platforms:
        tasks.append(
            create_eager_task(
                hass.config_entries.async_forward_entry_setups(
                    config_entry, new_entity_platforms
                )
            )
        )
    if not tasks:
        return
    await asyncio.gather(*tasks)
    platforms_loaded.update(new_platforms)


def mqtt_config_entry_enabled(hass: HomeAssistant) -> bool:
    """Return True when the locknalert_mqtt config entry is active and usable.

    Uses a fast path — checking whether the MQTT client is already connected
    via ``hass.data[DATA_MQTT]`` — before falling back to the more expensive
    config-entry registry lookup.

    Args:
        hass (HomeAssistant): The Home Assistant instance.

    Returns:
        bool: ``True`` if the integration is configured and enabled, ``False``
            if it is missing, disabled, or ignored.
    """
    # If the mqtt client is connected, skip the expensive config
    # entry check as its roughly two orders of magnitude faster.
    return (
        DATA_MQTT in hass.data and hass.data[DATA_MQTT].client.connected
    ) or hass.config_entries.async_has_entries(
        DOMAIN, include_disabled=False, include_ignore=False
    )


async def async_wait_for_mqtt_client(hass: HomeAssistant) -> bool:
    """Wait up to :data:`AVAILABILITY_TIMEOUT` seconds for the MQTT client to become available.

    Returns immediately if the integration is not configured or if the config
    entry is already fully loaded.  Otherwise suspends until the setup future
    (stored in ``hass.data[DATA_MQTT_AVAILABLE]``) resolves or the timeout
    elapses.  The client does not need to be connected — only setup must be
    complete.

    Args:
        hass (HomeAssistant): The Home Assistant instance.

    Returns:
        bool: ``True`` if the client is available, ``False`` if the
            integration is not configured or the wait timed out.
    """
    if not mqtt_config_entry_enabled(hass):
        return False

    entry = hass.config_entries.async_entries(DOMAIN)[0]
    if entry.state == ConfigEntryState.LOADED:
        return True

    state_reached_future: asyncio.Future[bool]
    if DATA_MQTT_AVAILABLE not in hass.data:
        state_reached_future = hass.loop.create_future()
        hass.data[DATA_MQTT_AVAILABLE] = state_reached_future
    else:
        state_reached_future = hass.data[DATA_MQTT_AVAILABLE]

    try:
        async with asyncio.timeout(AVAILABILITY_TIMEOUT):
            # Await the client setup or an error state was received
            return await state_reached_future
    except TimeoutError:
        return False


def valid_topic(topic: Any) -> str:
    """Validate and return a well-formed MQTT topic name or filter string.

    Enforces the MQTT 3.1.1 / 5.0 specification constraints: UTF-8 encoded,
    non-empty, maximum 65535 bytes, no null bytes, no control characters
    (U+0000-U+001F, U+007F-U+009F), and no Unicode non-characters.

    This function is intentionally uncached.  Callers that need caching
    (voluptuous validators) should use :func:`valid_subscribe_topic` or
    :func:`valid_publish_topic` which wrap it with ``@lru_cache``.

    Args:
        topic (Any): The candidate topic string to validate.  Non-string
            values are coerced to string by the underlying ``cv.string``
            validator.

    Returns:
        str: The validated topic string.

    Raises:
        vol.Invalid: If the topic violates any MQTT specification constraint.
    """
    validated_topic = cv.string(topic)
    try:
        raw_validated_topic = validated_topic.encode("utf-8")
    except UnicodeError as err:
        raise vol.Invalid("MQTT topic name/filter must be valid UTF-8 string.") from err
    if not raw_validated_topic:
        raise vol.Invalid("MQTT topic name/filter must not be empty.")
    if len(raw_validated_topic) > 65535:
        raise vol.Invalid(
            "MQTT topic name/filter must not be longer than 65535 encoded bytes."
        )

    for char in validated_topic:
        if char == "\0":
            raise vol.Invalid("MQTT topic name/filter must not contain null character.")
        if char <= "\u001f" or "\u007f" <= char <= "\u009f":
            raise vol.Invalid(
                "MQTT topic name/filter must not contain control characters."
            )
        if "\ufdd0" <= char <= "\ufdef" or (ord(char) & 0xFFFF) in (0xFFFE, 0xFFFF):
            raise vol.Invalid("MQTT topic name/filter must not contain non-characters.")

    return validated_topic


@lru_cache
def valid_subscribe_topic(topic: Any) -> str:
    """Validate and return a well-formed MQTT subscription topic filter.

    Extends :func:`valid_topic` by additionally enforcing wildcard placement
    rules: ``+`` must occupy a complete level, and ``#`` must be the last
    character and must follow a ``/`` separator (unless it is the whole filter).

    Results are cached with ``@lru_cache`` because this is called by voluptuous
    schemas on every config load.

    Args:
        topic (Any): The candidate topic filter string.

    Returns:
        str: The validated topic filter string.

    Raises:
        vol.Invalid: If the topic is invalid per :func:`valid_topic` or if
            the wildcard placement rules are violated.
    """
    validated_topic = valid_topic(topic)
    if "+" in validated_topic:
        for i in (i for i, c in enumerate(validated_topic) if c == "+"):
            if (i > 0 and validated_topic[i - 1] != "/") or (
                i < len(validated_topic) - 1 and validated_topic[i + 1] != "/"
            ):
                raise vol.Invalid(
                    "Single-level wildcard must occupy an entire level of the filter"
                )

    index = validated_topic.find("#")
    if index != -1:
        if index != len(validated_topic) - 1:
            # If there are multiple wildcards, this will also trigger
            raise vol.Invalid(
                "Multi-level wildcard must be the last character in the topic filter."
            )
        if len(validated_topic) > 1 and validated_topic[index - 1] != "/":
            raise vol.Invalid(
                "Multi-level wildcard must be after a topic level separator."
            )

    return validated_topic


def valid_subscribe_topic_template(value: Any) -> template.Template:
    """Validate a Jinja2 template that, when static, must also be a valid MQTT topic.

    For static (non-template) values the string is additionally validated as a
    subscription topic filter via :func:`valid_subscribe_topic`.

    Args:
        value (Any): A Jinja2 template string or a plain MQTT topic filter.

    Returns:
        template.Template: The compiled HA template object.

    Raises:
        vol.Invalid: If the value is not a valid template, or if static and not
            a valid MQTT subscription topic.
    """
    tpl = cv.template(value)

    if tpl.is_static:
        valid_subscribe_topic(value)

    return tpl


@lru_cache
def valid_publish_topic(topic: Any) -> str:
    """Validate and return a well-formed MQTT publish topic (no wildcards allowed).

    Extends :func:`valid_topic` by rejecting any topic containing ``+`` or
    ``#``, which are only permitted in subscription filters.

    Args:
        topic (Any): The candidate publish topic string.

    Returns:
        str: The validated publish topic string.

    Raises:
        vol.Invalid: If the topic is invalid per :func:`valid_topic` or if
            it contains wildcard characters.
    """
    validated_topic = valid_topic(topic)
    if "+" in validated_topic or "#" in validated_topic:
        raise vol.Invalid("Wildcards cannot be used in topic names")
    return validated_topic


def valid_qos_schema(qos: Any) -> int:
    """Validate and return an MQTT QoS value (0, 1, or 2).

    Args:
        qos (Any): The candidate QoS value.  Coerced to ``int`` before
            checking membership.

    Returns:
        int: The validated QoS level.

    Raises:
        vol.Invalid: If the value is not 0, 1, or 2.
    """
    validated_qos: int = _VALID_QOS_SCHEMA(qos)
    return validated_qos


_MQTT_WILL_BIRTH_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_TOPIC): valid_publish_topic,
        vol.Required(ATTR_PAYLOAD): cv.string,
        vol.Optional(ATTR_QOS, default=DEFAULT_QOS): valid_qos_schema,
        vol.Optional(ATTR_RETAIN, default=DEFAULT_RETAIN): cv.boolean,
    },
    required=True,
)


def valid_birth_will(config: ConfigType) -> ConfigType:
    """Validate an MQTT birth or will message configuration dict.

    Validates *config* against ``_MQTT_WILL_BIRTH_SCHEMA`` which requires a
    ``topic`` and ``payload`` and optionally accepts ``qos`` and ``retain``.
    An empty dict or falsy value is returned unchanged (no birth/will message
    configured).

    Args:
        config (ConfigType): Raw birth or will configuration dict from the
            config entry options.

    Returns:
        ConfigType: Validated and normalised configuration dict, or the
            original falsy value if empty.

    Raises:
        vol.Invalid: If the configuration is non-empty but fails schema
            validation.
    """
    if config:
        config = _MQTT_WILL_BIRTH_SCHEMA(config)
    return config


async def async_create_certificate_temp_files(
    hass: HomeAssistant, config: ConfigType
) -> None:
    """Write TLS certificate and key material to the integration temp directory.

    Each of the three certificate options (CA certificate, client certificate,
    client key) is written to a file under a temporary directory named
    ``home-assistant-locknalert_mqtt`` inside the system temp dir.  Files that
    are no longer needed (value is ``None``) are removed.  The directory is
    created with mode ``0o700`` on first use.

    All file I/O is executed in the default executor to avoid blocking the
    event loop.

    Args:
        hass (HomeAssistant): The Home Assistant instance, used to schedule
            the executor job.
        config (ConfigType): Config entry data containing
            :data:`~.const.CONF_CERTIFICATE`, :data:`~.const.CONF_CLIENT_CERT`,
            and :data:`~.const.CONF_CLIENT_KEY` values (PEM strings or ``None``).
    """

    def _create_temp_file(temp_file: Path, data: str | None) -> None:
        if data is None or data == "auto":
            temp_file.unlink(missing_ok=True)
            return
        temp_file.write_text(data)
        temp_file.chmod(0o600)

    def _create_temp_dir_and_files() -> None:
        """Create temporary directory."""
        temp_dir = Path(tempfile.gettempdir()) / TEMP_DIR_NAME

        if (
            config.get(CONF_CERTIFICATE)
            or config.get(CONF_CLIENT_CERT)
            or config.get(CONF_CLIENT_KEY)
        ) and not temp_dir.exists():
            temp_dir.mkdir(0o700)

        _create_temp_file(temp_dir / CONF_CERTIFICATE, config.get(CONF_CERTIFICATE))
        _create_temp_file(temp_dir / CONF_CLIENT_CERT, config.get(CONF_CLIENT_CERT))
        _create_temp_file(temp_dir / CONF_CLIENT_KEY, config.get(CONF_CLIENT_KEY))

    await hass.async_add_executor_job(_create_temp_dir_and_files)


def check_state_too_long(
    logger: logging.Logger, proposed_state: str, entity_id: str, msg: ReceiveMessage
) -> bool:
    """Return True and log a warning if *proposed_state* exceeds the HA state length limit.

    Home Assistant silently truncates entity states that exceed
    :data:`~homeassistant.const.MAX_LENGTH_STATE_STATE` characters, which leads
    to incorrect or misleading state values.  Call this before writing state and
    fall back to :data:`~homeassistant.const.STATE_UNKNOWN` when it returns
    ``True``.

    Args:
        logger (logging.Logger): Logger to use for the warning message.
        proposed_state (str): The rendered state string to check.
        entity_id (str): Entity id included in the warning for diagnostics.
        msg (ReceiveMessage): The MQTT message that produced the state, used
            to include the source topic and payload in the warning.

    Returns:
        bool: ``True`` if *proposed_state* is too long and the caller should
            fall back to ``STATE_UNKNOWN``, ``False`` if the state is within
            the allowed limit.
    """
    if (state_length := len(proposed_state)) > MAX_LENGTH_STATE_STATE:
        logger.warning(
            "Cannot update state for entity %s after processing "
            "payload on topic %s. The requested state (%s) exceeds "
            "the maximum allowed length (%s). Fall back to "
            "%s, failed state: %s",
            entity_id,
            msg.topic,
            state_length,
            MAX_LENGTH_STATE_STATE,
            STATE_UNKNOWN,
            proposed_state[:8192],
        )
        return True

    return False


def get_file_path(option: str, default: str | None = None) -> str | None:
    """Return the path to a certificate temp file if it exists, otherwise *default*.

    Checks whether the integration's temp directory exists and, within it,
    whether a file named *option* exists.  Returns its path as a ``str`` if
    found, or *default* otherwise.

    Args:
        option (str): Certificate config key name used as the filename
            (e.g. ``"certificate"``, ``"client_cert"``, ``"client_key"``).
        default (str | None): Value to return when the temp file is absent.

    Returns:
        str | None: Absolute path to the temp file, or *default*.
    """
    temp_dir = Path(tempfile.gettempdir()) / TEMP_DIR_NAME
    if not temp_dir.exists():
        return default

    file_path: Path = temp_dir / option
    if not file_path.exists():
        return default

    return str(temp_dir / option)


def migrate_certificate_file_to_content(file_name_or_auto: str) -> str | None:
    """Read a certificate file and return its content, or preserve special values.

    Used during config entry migration to convert legacy file-path certificate
    settings (where the user supplied a filesystem path) into inline PEM
    content stored in the config entry.  The special value ``"auto"`` is
    preserved as-is to indicate that the system certificate bundle should be
    used.

    Args:
        file_name_or_auto (str): Either the string ``"auto"``, or the absolute
            path to a PEM-encoded certificate file.

    Returns:
        str | None: ``"auto"`` if the input is ``"auto"``; the file content
            as a string if the file could be read; ``None`` if the file does
            not exist or cannot be read.
    """
    if file_name_or_auto == "auto":
        return "auto"
    try:
        with open(file_name_or_auto, encoding=DEFAULT_ENCODING) as certificate_file:
            return certificate_file.read()
    except OSError:
        return None


@callback
def learn_more_url(platform: str) -> str:
    """Return the HA documentation URL for an MQTT platform integration.

    Args:
        platform (str): The platform name (e.g. ``"alarm_control_panel"``).

    Returns:
        str: The full documentation URL for that platform's MQTT page.
    """
    return f"https://www.home-assistant.io/integrations/{platform}.mqtt/"


async def async_cleanup_device_registry(
    hass: HomeAssistant, device_id: str | None, config_entry_id: str | None
) -> None:
    """Remove the locknalert_mqtt config entry link from a device if no entities remain.

    Called after MQTT discovery cleanup to detach the config entry from the
    device when all its MQTT entities have been removed.  Does nothing if
    *device_id* is ``None``, the device has already been deleted, or if any
    non-disabled entities from the config entry still exist for the device.

    Args:
        hass (HomeAssistant): The Home Assistant instance.
        device_id (str | None): The device registry id to clean up, or
            ``None`` to skip.
        config_entry_id (str | None): The config entry id to remove from the
            device, or ``None`` to skip.
    """
    device_registry = dr.async_get(hass)
    entity_registry = er.async_get(hass)
    if (
        device_id
        and device_id not in device_registry.deleted_devices
        and config_entry_id
        and not er.async_entries_for_device(
            entity_registry, device_id, include_disabled_entities=False
        )
    ):
        device_registry.async_update_device(
            device_id, remove_config_entry_id=config_entry_id
        )
