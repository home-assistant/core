"""Config and options flows for Immich Frames."""

from typing import Any, override
from uuid import uuid4

from aioimmich import Immich
from aioimmich.assets.models import AssetType
from aioimmich.const import CONNECT_ERRORS
from aioimmich.exceptions import ImmichError, ImmichUnauthorizedError
import probatio

from homeassistant import config_entries
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigEntryState,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import (
    CONF_ALBUM_IDS,
    CONF_FRAME_ID,
    CONF_FRAME_NAME,
    CONF_IMMICH_ENTRY_ID,
    CONF_MODE,
    CONF_ORIENTATION,
    CONF_PAIR_WINDOW,
    CONF_PHOTO_FIT,
    CONF_SCREEN_SHAPE,
    CONF_SMART_QUERY,
    CONF_SOURCE,
    CONF_TIME_RANGE,
    DEFAULT_MODE,
    DEFAULT_ORIENTATION,
    DEFAULT_PAIR_WINDOW,
    DEFAULT_PHOTO_FIT,
    DEFAULT_SCREEN_SHAPE,
    DEFAULT_SOURCE,
    DEFAULT_TIME_RANGE,
    DOMAIN,
    MODE_OPTIONS,
    MODE_PAIRS_ONLY,
    ORIENTATION_ANY,
    ORIENTATION_OPTIONS,
    ORIENTATION_PORTRAIT,
    PHOTO_FIT_CROP,
    PHOTO_FIT_FULL,
    SCREEN_SIZES,
    SOURCE_ALBUM,
    SOURCE_ALL,
    SOURCE_SMART,
    TIME_RANGE_MONTHS,
)
from .coordinator import ImmichFramesConfigEntry

FRAME_SOURCE_OPTIONS = (SOURCE_ALL, SOURCE_ALBUM, SOURCE_SMART)
PHOTO_FIT_OPTIONS = (PHOTO_FIT_CROP, PHOTO_FIT_FULL)
SCREEN_SHAPE_OPTIONS = tuple(SCREEN_SIZES)


async def _async_validate_source(
    api: Immich | None, data: dict[str, Any]
) -> str | None:
    """Validate access to the selected source before saving it."""
    if api is None:
        return "immich_not_ready"
    try:
        source = data[CONF_SOURCE]
        if source == SOURCE_SMART:
            await api.search.async_smart_search(
                str(data[CONF_SMART_QUERY]),
                page_size=1,
                max_pages=1,
                asset_type=AssetType.IMAGE,
            )
        elif source == SOURCE_ALBUM:
            await api.search.async_get_all_by_album_ids(
                data.get(CONF_ALBUM_IDS, []), page_size=1, max_pages=1
            )
        else:
            await api.search.async_get_all(page_size=1, max_pages=1)
    except ImmichUnauthorizedError:
        return "immich_auth"
    except CONNECT_ERRORS:
        return "assets_unavailable"
    except ImmichError:
        return "assets_unavailable"
    return None


class ImmichFramesConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle configuration of a frame linked to an Immich account."""

    VERSION = 3

    def __init__(self) -> None:
        """Initialize flow state."""
        self._data: dict[str, Any] = {}
        self._reconfigure_entry: ConfigEntry | None = None

    @staticmethod
    @override
    @callback
    def async_get_options_flow(
        config_entry: ImmichFramesConfigEntry,
    ) -> ImmichFramesOptionsFlow:
        """Return the frame options flow."""
        return ImmichFramesOptionsFlow(config_entry)

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Select an Immich account and source."""
        entries = self._loaded_immich_entries()
        if not entries:
            reason = (
                "immich_not_ready"
                if self.hass.config_entries.async_entries("immich")
                else "immich_required"
            )
            return self.async_abort(reason=reason)

        errors: dict[str, str] = {}
        if user_input is not None:
            parent_id = user_input[CONF_IMMICH_ENTRY_ID]
            if parent_id not in entries:
                errors["base"] = "immich_unavailable"
            else:
                self._data = {
                    CONF_IMMICH_ENTRY_ID: parent_id,
                    CONF_SOURCE: user_input[CONF_SOURCE],
                }
                if self._data[CONF_SOURCE] == SOURCE_ALL:
                    if error := await self._async_validate_source():
                        return self.async_show_form(
                            step_id="user",
                            data_schema=self._user_schema(entries),
                            errors={"base": error},
                        )
                return await self._async_continue_source()

        return self.async_show_form(
            step_id="user",
            data_schema=self._user_schema(entries),
            errors=errors,
        )

    @staticmethod
    def _user_schema(entries: dict[str, ConfigEntry]) -> probatio.Schema:
        """Return the initial account and source schema."""
        return probatio.Schema(
            {
                probatio.Required(CONF_IMMICH_ENTRY_ID): SelectSelector(
                    SelectSelectorConfig(
                        options=[
                            SelectOptionDict(value=entry.entry_id, label=entry.title)
                            for entry in entries.values()
                        ],
                        mode=SelectSelectorMode.DROPDOWN,
                    )
                ),
                probatio.Required(CONF_SOURCE, default=DEFAULT_SOURCE): SelectSelector(
                    SelectSelectorConfig(
                        options=list(FRAME_SOURCE_OPTIONS),
                        translation_key=CONF_SOURCE,
                        mode=SelectSelectorMode.DROPDOWN,
                    )
                ),
            }
        )

    async def _async_continue_source(self) -> ConfigFlowResult:
        """Continue to source-specific settings."""
        source = self._data[CONF_SOURCE]
        if source == SOURCE_ALBUM:
            return await self.async_step_album()
        if source == SOURCE_SMART:
            return await self.async_step_smart()
        return await self._async_finish_create()

    async def async_step_album(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Select one or more albums."""
        api = self._parent_api()
        if api is None:
            return self.async_abort(reason="immich_not_ready")
        errors: dict[str, str] = {}
        try:
            albums = await api.albums.async_get_all_albums()
        except ImmichUnauthorizedError:
            errors["base"] = "immich_auth"
            albums = []
        except ImmichError:
            errors["base"] = "albums_unavailable"
            albums = []
        except CONNECT_ERRORS:
            errors["base"] = "albums_unavailable"
            albums = []
        if not albums and not errors:
            return self.async_abort(reason="no_albums")
        album_options = [
            SelectOptionDict(
                value=album.album_id, label=album.album_name or album.album_id
            )
            for album in sorted(albums, key=lambda item: item.album_name.casefold())
        ]
        if user_input is not None and not errors:
            album_ids = user_input.get(CONF_ALBUM_IDS, [])
            if not album_ids:
                errors["base"] = "album_required"
            elif not {album.album_id for album in albums}.issuperset(album_ids):
                errors["base"] = "album_unavailable"
            else:
                self._data[CONF_ALBUM_IDS] = album_ids
                if error := await self._async_validate_source():
                    errors["base"] = error
                else:
                    return await self._async_finish_create()
        return self.async_show_form(
            step_id="album",
            data_schema=probatio.Schema(
                {
                    probatio.Required(
                        CONF_ALBUM_IDS, default=self._data.get(CONF_ALBUM_IDS, [])
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=album_options,
                            multiple=True,
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    )
                }
            ),
            errors=errors,
        )

    async def async_step_smart(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Collect a natural-language Immich search."""
        errors: dict[str, str] = {}
        if user_input is not None:
            query = user_input[CONF_SMART_QUERY].strip()
            if not query:
                errors[CONF_SMART_QUERY] = "smart_query_required"
            else:
                self._data[CONF_SMART_QUERY] = query
                if error := await self._async_validate_source():
                    errors["base"] = error
                else:
                    return await self._async_finish_create()
        return self.async_show_form(
            step_id="smart",
            data_schema=probatio.Schema({probatio.Required(CONF_SMART_QUERY): str}),
            errors=errors,
        )

    async def _async_finish_create(self) -> ConfigFlowResult:
        """Create or reconfigure a frame entry."""
        if self._reconfigure_entry is not None:
            settings = {
                **self._reconfigure_entry.data,
                **self._reconfigure_entry.options,
                **self._data,
            }
            frame_id = self._reconfigure_entry.data.get(CONF_FRAME_ID, uuid4().hex)
            options = {
                key: value
                for key, value in settings.items()
                if key not in (CONF_IMMICH_ENTRY_ID, CONF_FRAME_ID, CONF_FRAME_NAME)
            }
            return self.async_update_reload_and_abort(
                self._reconfigure_entry,
                data_updates={
                    CONF_IMMICH_ENTRY_ID: settings[CONF_IMMICH_ENTRY_ID],
                    CONF_FRAME_ID: frame_id,
                },
                options=options,
                title=self._reconfigure_entry.title,
            )
        settings = {
            **self._data,
            CONF_MODE: DEFAULT_MODE,
            CONF_ORIENTATION: DEFAULT_ORIENTATION,
            CONF_TIME_RANGE: DEFAULT_TIME_RANGE,
            CONF_PAIR_WINDOW: DEFAULT_PAIR_WINDOW,
            CONF_SCREEN_SHAPE: DEFAULT_SCREEN_SHAPE,
            CONF_PHOTO_FIT: DEFAULT_PHOTO_FIT,
        }
        frame_id = uuid4().hex
        data = {
            CONF_IMMICH_ENTRY_ID: settings[CONF_IMMICH_ENTRY_ID],
            CONF_FRAME_ID: frame_id,
        }
        options = {
            key: value
            for key, value in settings.items()
            if key not in (CONF_IMMICH_ENTRY_ID, CONF_FRAME_ID, CONF_FRAME_NAME)
        }
        unique_id = f"{data[CONF_IMMICH_ENTRY_ID]}|{frame_id}"
        return await self._async_create_unique_entry(unique_id, data, options)

    async def _async_create_unique_entry(
        self, unique_id: str, data: dict[str, Any], options: dict[str, Any]
    ) -> ConfigFlowResult:
        """Create the unique frame entry asynchronously."""
        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured()
        return self.async_create_entry(
            title="Immich Frames", data=data, options=options
        )

    def _loaded_immich_entries(self) -> dict[str, ConfigEntry]:
        """Return loaded parent Immich entries."""
        return {
            entry.entry_id: entry
            for entry in self.hass.config_entries.async_entries("immich")
            if entry.state is ConfigEntryState.LOADED
        }

    def _parent_api(self) -> Immich | None:
        """Return the selected parent client, if available."""
        entry = self.hass.config_entries.async_get_entry(
            self._data.get(CONF_IMMICH_ENTRY_ID, "")
        )
        return getattr(getattr(entry, "runtime_data", None), "api", None)

    async def _async_validate_source(self) -> str | None:
        """Validate access to the selected source before creating an entry."""
        return await _async_validate_source(self._parent_api(), self._data)

    @staticmethod
    def _reconfigure_schema(source: str) -> probatio.Schema:
        """Return the reconfiguration source schema."""
        return probatio.Schema(
            {
                probatio.Required(CONF_SOURCE, default=source): SelectSelector(
                    SelectSelectorConfig(
                        options=list(FRAME_SOURCE_OPTIONS),
                        translation_key=CONF_SOURCE,
                        mode=SelectSelectorMode.DROPDOWN,
                    )
                ),
            }
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Reconfigure frame-specific settings."""
        self._reconfigure_entry = self._get_reconfigure_entry()
        self._data = {**self._reconfigure_entry.data, **self._reconfigure_entry.options}
        if user_input is None:
            return self.async_show_form(
                step_id="reconfigure",
                data_schema=self._reconfigure_schema(
                    self._data.get(CONF_SOURCE, DEFAULT_SOURCE)
                ),
            )
        self._data.update(user_input)
        if self._data[CONF_SOURCE] == SOURCE_ALL:
            if error := await self._async_validate_source():
                return self.async_show_form(
                    step_id="reconfigure",
                    data_schema=self._reconfigure_schema(self._data[CONF_SOURCE]),
                    errors={"base": error},
                )
        return await self._async_continue_source()


class ImmichFramesOptionsFlow(OptionsFlowWithReload):
    """Configure frame-specific photo selection and display settings."""

    def __init__(self, config_entry: ImmichFramesConfigEntry) -> None:
        """Initialize the options flow."""
        self._entry = config_entry
        self._data: dict[str, Any] = {
            **config_entry.data,
            **config_entry.options,
        }

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Configure source and display settings."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._data.update(user_input)
            if self._data[CONF_MODE] == MODE_PAIRS_ONLY and self._data[
                CONF_ORIENTATION
            ] not in (ORIENTATION_ANY, ORIENTATION_PORTRAIT):
                errors[CONF_ORIENTATION] = "pairs_only_portrait_required"
            if errors:
                return self.async_show_form(
                    step_id="init",
                    data_schema=self._settings_schema(),
                    errors=errors,
                )
            source = user_input[CONF_SOURCE]
            if source == SOURCE_ALBUM:
                return await self.async_step_album()
            if source == SOURCE_SMART:
                return await self.async_step_smart()
            if error := await self._async_validate_source():
                return self.async_show_form(
                    step_id="init",
                    data_schema=self._settings_schema(),
                    errors={"base": error},
                )
            return self._finish()
        return self.async_show_form(
            step_id="init",
            data_schema=self._settings_schema(),
        )

    async def async_step_album(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Configure album source options."""
        parent = self.hass.config_entries.async_get_entry(
            self._entry.data[CONF_IMMICH_ENTRY_ID]
        )
        api = getattr(getattr(parent, "runtime_data", None), "api", None)
        if api is None:
            return self.async_abort(reason="immich_not_ready")
        errors: dict[str, str] = {}
        try:
            albums = await api.albums.async_get_all_albums()
        except ImmichUnauthorizedError:
            errors["base"] = "immich_auth"
            albums = []
        except ImmichError:
            errors["base"] = "albums_unavailable"
            albums = []
        except CONNECT_ERRORS:
            errors["base"] = "albums_unavailable"
            albums = []
        if not albums and not errors:
            return self.async_abort(reason="no_albums")
        if user_input is not None and not errors:
            album_ids = user_input.get(CONF_ALBUM_IDS, [])
            if not album_ids:
                errors["base"] = "album_required"
            elif not {album.album_id for album in albums}.issuperset(album_ids):
                errors["base"] = "album_unavailable"
            else:
                self._data.update(user_input)
                if error := await self._async_validate_source():
                    errors["base"] = error
                else:
                    return self._finish()
        return self.async_show_form(
            step_id="album",
            data_schema=probatio.Schema(
                {
                    probatio.Required(
                        CONF_ALBUM_IDS, default=self._data.get(CONF_ALBUM_IDS, [])
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                SelectOptionDict(value=a.album_id, label=a.album_name)
                                for a in albums
                            ],
                            multiple=True,
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    )
                }
            ),
            errors=errors,
        )

    async def async_step_smart(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Configure smart-search source options."""
        errors: dict[str, str] = {}
        if user_input is not None:
            query = user_input[CONF_SMART_QUERY].strip()
            if not query:
                errors[CONF_SMART_QUERY] = "smart_query_required"
            else:
                self._data[CONF_SMART_QUERY] = query
                if error := await self._async_validate_source():
                    errors["base"] = error
                else:
                    return self._finish()
        return self.async_show_form(
            step_id="smart",
            data_schema=probatio.Schema(
                {
                    probatio.Required(
                        CONF_SMART_QUERY, default=self._data.get(CONF_SMART_QUERY, "")
                    ): str
                }
            ),
            errors=errors,
        )

    def _settings_schema(self) -> probatio.Schema:
        """Return common display settings."""
        return probatio.Schema(
            {
                probatio.Required(
                    CONF_SOURCE, default=self._data.get(CONF_SOURCE, DEFAULT_SOURCE)
                ): SelectSelector(
                    SelectSelectorConfig(
                        options=list(FRAME_SOURCE_OPTIONS),
                        translation_key=CONF_SOURCE,
                        mode=SelectSelectorMode.DROPDOWN,
                    )
                ),
                probatio.Required(
                    CONF_MODE, default=self._data.get(CONF_MODE, DEFAULT_MODE)
                ): SelectSelector(
                    SelectSelectorConfig(
                        options=list(MODE_OPTIONS),
                        translation_key=CONF_MODE,
                        mode=SelectSelectorMode.DROPDOWN,
                    )
                ),
                probatio.Required(
                    CONF_ORIENTATION,
                    default=self._data.get(CONF_ORIENTATION, DEFAULT_ORIENTATION),
                ): SelectSelector(
                    SelectSelectorConfig(
                        options=list(ORIENTATION_OPTIONS),
                        translation_key=CONF_ORIENTATION,
                        mode=SelectSelectorMode.DROPDOWN,
                    )
                ),
                probatio.Required(
                    CONF_TIME_RANGE,
                    default=self._data.get(CONF_TIME_RANGE, DEFAULT_TIME_RANGE),
                ): SelectSelector(
                    SelectSelectorConfig(
                        options=list(TIME_RANGE_MONTHS),
                        translation_key=CONF_TIME_RANGE,
                        mode=SelectSelectorMode.DROPDOWN,
                    )
                ),
                probatio.Required(
                    CONF_PAIR_WINDOW,
                    default=self._data.get(CONF_PAIR_WINDOW, DEFAULT_PAIR_WINDOW),
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=0, max=7, step=1, mode=NumberSelectorMode.BOX
                    )
                ),
                probatio.Required(
                    CONF_SCREEN_SHAPE,
                    default=self._data.get(CONF_SCREEN_SHAPE, DEFAULT_SCREEN_SHAPE),
                ): SelectSelector(
                    SelectSelectorConfig(
                        options=list(SCREEN_SHAPE_OPTIONS),
                        translation_key=CONF_SCREEN_SHAPE,
                        mode=SelectSelectorMode.DROPDOWN,
                    )
                ),
                probatio.Required(
                    CONF_PHOTO_FIT,
                    default=self._data.get(CONF_PHOTO_FIT, DEFAULT_PHOTO_FIT),
                ): SelectSelector(
                    SelectSelectorConfig(
                        options=list(PHOTO_FIT_OPTIONS),
                        translation_key=CONF_PHOTO_FIT,
                        mode=SelectSelectorMode.DROPDOWN,
                    )
                ),
            }
        )

    def _parent_api(self) -> Immich | None:
        """Return the parent client, if it is loaded."""
        parent = self.hass.config_entries.async_get_entry(
            self._data.get(CONF_IMMICH_ENTRY_ID, "")
        )
        return getattr(getattr(parent, "runtime_data", None), "api", None)

    async def _async_validate_source(self) -> str | None:
        """Validate access to the selected source before saving options."""
        return await _async_validate_source(self._parent_api(), self._data)

    def _finish(self) -> ConfigFlowResult:
        """Save options and reload the frame."""
        return self.async_create_entry(
            title="",
            data={
                key: value
                for key, value in self._data.items()
                if key not in (CONF_IMMICH_ENTRY_ID, CONF_FRAME_ID, CONF_FRAME_NAME)
            },
        )
