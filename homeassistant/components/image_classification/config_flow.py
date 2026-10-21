"""Config flow for Image classification."""

from typing import Any, override

import probatio

from homeassistant.components import ai_task
from homeassistant.components.ai_task import DOMAIN as AI_TASK_DOMAIN
from homeassistant.components.camera import DOMAIN as CAMERA_DOMAIN
from homeassistant.config_entries import (
    ConfigEntryState,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.const import (
    CONF_DEVICE_CLASS,
    CONF_ENTITY_ID,
    CONF_NAME,
    CONF_REGION,
    CONF_STATE,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import selector, translation
from homeassistant.util import dt as dt_util

from .const import (
    CONF_AI_TASK_ENTITY_ID,
    CONF_BOTTOM,
    CONF_FRAMES,
    CONF_LEFT,
    CONF_RIGHT,
    CONF_TOP,
    DEFAULT_DEVICE_CLASS,
    DEFAULT_REGION,
    DEVICE_CLASSES,
    DOMAIN,
    STATES,
)
from .coordinator import ImageClassificationConfigEntry, ImageClassificationCoordinator
from .frame_source import (
    FrameUnavailable,
    InvalidFrame,
    async_fetch_frame,
    prepare_frame,
    region_error,
)
from .preview import async_preview_url
from .taught_frames import EntryClosed

PERCENT = selector.NumberSelector(
    selector.NumberSelectorConfig(
        min=0,
        max=100,
        step=0.1,
        mode=selector.NumberSelectorMode.BOX,
        unit_of_measurement="%",
    )
)

AI_TASK_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_AI_TASK_ENTITY_ID): selector.EntitySelector(
            selector.EntitySelectorConfig(
                filter=selector.EntityWithDeviceFilterSelectorConfig(
                    domain=AI_TASK_DOMAIN,
                    supported_features=["ai_task.AITaskEntityFeature.CLASSIFY_IMAGE"],
                )
            )
        ),
    }
)

USER_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_ENTITY_ID): selector.EntitySelector(
            selector.EntitySelectorConfig(domain=CAMERA_DOMAIN)
        ),
        probatio.Required(
            CONF_DEVICE_CLASS, default=DEFAULT_DEVICE_CLASS
        ): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=list(DEVICE_CLASSES),
                mode=selector.SelectSelectorMode.DROPDOWN,
                translation_key="device_class",
            )
        ),
        probatio.Required(CONF_NAME): selector.TextSelector(),
    }
).extend(AI_TASK_SCHEMA.schema)

REGION_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_LEFT): PERCENT,
        probatio.Required(CONF_TOP): PERCENT,
        probatio.Required(CONF_RIGHT): PERCENT,
        probatio.Required(CONF_BOTTOM): PERCENT,
    }
)


def _teach_schema(device_class: str) -> probatio.Schema:
    return probatio.Schema(
        {
            probatio.Required(CONF_STATE): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=list(STATES),
                    mode=selector.SelectSelectorMode.LIST,
                    # Labels follow the kind, e.g. open / closed for a door.
                    translation_key=f"state_{device_class}",
                )
            )
        }
    )


@callback
def _default_ai_task_entity_id(hass: HomeAssistant) -> str | None:
    """Return the preferred image classification entity, if one is set."""
    return ai_task.async_get_classify_image_entity_id(hass)


class ImageClassificationConfigFlow(ConfigFlow, domain=DOMAIN):
    """Set up a camera region as a binary sensor."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the flow."""
        self._options: dict[str, Any] = {}
        self._frame = b""

    @staticmethod
    @callback
    @override
    def async_get_options_flow(
        config_entry: ImageClassificationConfigEntry,
    ) -> ImageClassificationOptionsFlow:
        """Get the options flow."""
        return ImageClassificationOptionsFlow()

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Pick the camera and the AI Task entity."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                frame = await async_fetch_frame(self.hass, user_input[CONF_ENTITY_ID])
                self._frame = await self.hass.async_add_executor_job(
                    prepare_frame, frame
                )
            except FrameUnavailable:
                errors["base"] = "cannot_connect"
            except InvalidFrame:
                errors["base"] = "invalid_frame"
            else:
                self._options = user_input
                return await self.async_step_region()
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                USER_SCHEMA,
                user_input
                or {CONF_AI_TASK_ENTITY_ID: _default_ai_task_entity_id(self.hass)},
            ),
            errors=errors,
        )

    async def async_step_region(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Set the region in percent of the frame."""
        errors: dict[str, str] = {}
        if user_input is not None:
            if error := region_error(user_input):
                errors["base"] = error
            else:
                self._options[CONF_REGION] = user_input
                return await self.async_step_region_confirm()
        region = user_input or self._options.get(CONF_REGION, DEFAULT_REGION)
        return self.async_show_form(
            step_id="region",
            data_schema=self.add_suggested_values_to_schema(REGION_SCHEMA, region),
            errors=errors,
            description_placeholders={
                "preview": await async_preview_url(
                    self.hass, self._frame, None if errors else region
                )
            },
        )

    async def async_step_region_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show the region on the current frame."""
        url = await async_preview_url(
            self.hass, self._frame, self._options[CONF_REGION]
        )
        return self.async_show_menu(
            step_id="region_confirm",
            menu_options=["finish", "region"],
            description_placeholders={"preview": url},
        )

    async def async_step_finish(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Create the entry."""
        name = self._options.pop(CONF_NAME)
        return self.async_create_entry(title=name, data={}, options=self._options)


class ImageClassificationOptionsFlow(OptionsFlowWithReload):
    """Teach and remove reference frames, change the AI Task entity."""

    config_entry: ImageClassificationConfigEntry

    def __init__(self) -> None:
        """Initialize the flow."""
        self._frame = b""

    def _coordinator(self) -> ImageClassificationCoordinator | None:
        """Return the coordinator, None while the entry is not loaded."""
        if self.config_entry.state is not ConfigEntryState.LOADED:
            return None
        return self.config_entry.runtime_data

    async def _state_labels(self) -> dict[str, str]:
        device_class = self.config_entry.options[CONF_DEVICE_CLASS]
        translations = await translation.async_get_translations(
            self.hass, self.hass.config.language, "selector", {DOMAIN}
        )
        prefix = f"component.{DOMAIN}.selector.state_{device_class}.options"
        return {state: translations.get(f"{prefix}.{state}", state) for state in STATES}

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Choose what to do."""
        if (coordinator := self._coordinator()) is None:
            return self.async_abort(reason="not_loaded")
        menu = ["teach"]
        if coordinator.taught_frames.frames:
            menu.append("remove")
        menu.append("ai_task")
        return self.async_show_menu(step_id="init", menu_options=menu)

    async def async_step_teach(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Store the shown frame as a reference."""
        # The entry may have reloaded while the dialog was open.
        if (coordinator := self._coordinator()) is None:
            return self.async_abort(reason="not_loaded")
        taught_frames = coordinator.taught_frames
        if user_input is not None:
            try:
                await taught_frames.async_teach(self._frame, user_input[CONF_STATE])
            except EntryClosed:
                return self.async_abort(reason="not_loaded")
            await coordinator.async_request_refresh()
            return self.async_abort(reason="teach_successful")
        options = self.config_entry.options
        try:
            frame = await async_fetch_frame(self.hass, options[CONF_ENTITY_ID])
            self._frame = await self.hass.async_add_executor_job(prepare_frame, frame)
        except FrameUnavailable:
            return self.async_abort(reason="cannot_connect")
        except InvalidFrame:
            return self.async_abort(reason="invalid_frame")
        url = await async_preview_url(self.hass, self._frame, options[CONF_REGION])
        labels = await self._state_labels()
        counts = taught_frames.counts()
        return self.async_show_form(
            step_id="teach",
            data_schema=_teach_schema(options[CONF_DEVICE_CLASS]),
            description_placeholders={
                "preview": url,
                "counts": ", ".join(
                    f"{labels[state]}: {counts[state]}" for state in STATES
                ),
            },
        )

    async def async_step_remove(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Delete taught frames."""
        if (coordinator := self._coordinator()) is None:
            return self.async_abort(reason="not_loaded")
        taught_frames = coordinator.taught_frames
        errors: dict[str, str] = {}
        if user_input is not None:
            if not user_input[CONF_FRAMES]:
                errors["base"] = "nothing_selected"
            else:
                try:
                    await taught_frames.async_remove(user_input[CONF_FRAMES])
                except EntryClosed:
                    return self.async_abort(reason="not_loaded")
                await coordinator.async_request_refresh()
                return self.async_abort(reason="remove_successful")
        labels = await self._state_labels()
        options = [
            selector.SelectOptionDict(
                value=frame.id,
                label=f"{labels[frame.label]}, {dt_util.as_local(frame.created):%Y-%m-%d %H:%M}",
            )
            for frame in taught_frames.frames
        ]
        return self.async_show_form(
            step_id="remove",
            data_schema=probatio.Schema(
                {
                    probatio.Required(CONF_FRAMES): selector.SelectSelector(
                        selector.SelectSelectorConfig(options=options, multiple=True)
                    )
                }
            ),
            errors=errors,
        )

    async def async_step_ai_task(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Change the AI Task entity that classifies the frames."""
        if user_input is not None:
            return self.async_create_entry(
                data={**self.config_entry.options, **user_input}
            )
        return self.async_show_form(
            step_id="ai_task",
            data_schema=self.add_suggested_values_to_schema(
                AI_TASK_SCHEMA, self.config_entry.options
            ),
        )
