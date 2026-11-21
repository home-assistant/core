"""Web socket API for Insteon scenes."""

import probatio
from pyinsteon import devices
from pyinsteon.constants import ResponseStatus
from pyinsteon.managers.scene_controller_manager import (
    ControllerSchema,
    SceneControllerError,
)
from pyinsteon.managers.scene_manager import (
    DeviceLinkSchema,
    async_add_or_update_scene,
    async_delete_scene,
    async_find_device_scenes,
    async_get_scene,
    async_get_scenes,
    async_import_device_scene,
)

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant

from ..const import ID, TYPE


def _scene_to_dict(scene):
    """Return a dictionary mapping of a scene."""
    device_dict = {}
    for addr, links in scene["devices"].items():
        str_addr = str(addr)
        device_dict[str_addr] = []
        for data in links:
            device_dict[str_addr].append(
                {
                    "data1": data.data1,
                    "data2": data.data2,
                    "data3": data.data3,
                    "has_controller": data.has_controller,
                    "has_responder": data.has_responder,
                }
            )
    return {
        "name": scene["name"],
        "group": scene["group"],
        "devices": device_dict,
        "controllers": scene["controllers"],
        "pending": scene["pending"],
    }


@websocket_api.websocket_command({probatio.Required(TYPE): "insteon/scenes/get"})
@websocket_api.require_admin
@websocket_api.async_response
async def websocket_get_scenes(
    hass: HomeAssistant,
    connection: websocket_api.connection.ActiveConnection,
    msg: dict,
) -> None:
    """Get all Insteon scenes."""
    try:
        scenes = await async_get_scenes(work_dir=hass.config.config_dir)
    except SceneControllerError as err:
        connection.send_error(msg[ID], "scene_error", str(err))
        return
    scenes_dict = {
        scene_num: _scene_to_dict(scene) for scene_num, scene in scenes.items()
    }
    connection.send_result(msg[ID], scenes_dict)


@websocket_api.websocket_command(
    {probatio.Required(TYPE): "insteon/scene/get", probatio.Required("scene_id"): int}
)
@websocket_api.require_admin
@websocket_api.async_response
async def websocket_get_scene(
    hass: HomeAssistant,
    connection: websocket_api.connection.ActiveConnection,
    msg: dict,
) -> None:
    """Get an Insteon scene."""
    scene_id = msg["scene_id"]
    try:
        scene = await async_get_scene(
            scene_num=scene_id, work_dir=hass.config.config_dir
        )
    except SceneControllerError as err:
        connection.send_error(msg[ID], "scene_error", str(err))
        return
    connection.send_result(msg[ID], _scene_to_dict(scene))


@websocket_api.websocket_command(
    {
        probatio.Required(TYPE): "insteon/scene/save",
        probatio.Required("name"): str,
        probatio.Required("scene_id"): int,
        probatio.Required("links"): DeviceLinkSchema,
        probatio.Optional("controllers"): ControllerSchema,
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def websocket_save_scene(
    hass: HomeAssistant,
    connection: websocket_api.connection.ActiveConnection,
    msg: dict,
) -> None:
    """Save an Insteon scene."""
    scene_id = msg["scene_id"]
    name = msg["name"]
    links = msg["links"]

    try:
        scene_id, result = await async_add_or_update_scene(
            scene_num=scene_id,
            links=links,
            name=name,
            work_dir=hass.config.config_dir,
            controllers=msg.get("controllers"),
        )
    except ValueError as err:
        connection.send_error(msg[ID], "scene_error", str(err))
        return
    await devices.async_save(workdir=hass.config.config_dir)
    connection.send_result(
        msg[ID], {"scene_id": scene_id, "result": result == ResponseStatus.SUCCESS}
    )


@websocket_api.websocket_command(
    {
        probatio.Required(TYPE): "insteon/scene/delete",
        probatio.Required("scene_id"): int,
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def websocket_delete_scene(
    hass: HomeAssistant,
    connection: websocket_api.connection.ActiveConnection,
    msg: dict,
) -> None:
    """Delete an Insteon scene."""
    scene_id = msg["scene_id"]

    try:
        result = await async_delete_scene(
            scene_num=scene_id, work_dir=hass.config.config_dir
        )
    except SceneControllerError as err:
        connection.send_error(msg[ID], "scene_error", str(err))
        return
    await devices.async_save(workdir=hass.config.config_dir)
    connection.send_result(
        msg[ID], {"scene_id": scene_id, "result": result == ResponseStatus.SUCCESS}
    )


@websocket_api.websocket_command(
    {probatio.Required(TYPE): "insteon/scenes/device_scenes"}
)
@websocket_api.require_admin
@websocket_api.async_response
async def websocket_get_device_scenes(
    hass: HomeAssistant,
    connection: websocket_api.connection.ActiveConnection,
    msg: dict,
) -> None:
    """Get hand-made device scenes that can be imported."""
    try:
        device_scenes = await async_find_device_scenes(work_dir=hass.config.config_dir)
    except SceneControllerError as err:
        connection.send_error(msg[ID], "scene_error", str(err))
        return
    connection.send_result(msg[ID], device_scenes)


@websocket_api.websocket_command(
    {
        probatio.Required(TYPE): "insteon/scene/import",
        probatio.Required("name"): str,
        probatio.Required("controllers"): ControllerSchema,
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def websocket_import_scene(
    hass: HomeAssistant,
    connection: websocket_api.connection.ActiveConnection,
    msg: dict,
) -> None:
    """Import a hand-made device scene."""
    try:
        scene_id, result = await async_import_device_scene(
            controllers=msg["controllers"],
            name=msg["name"],
            work_dir=hass.config.config_dir,
        )
    except ValueError as err:
        connection.send_error(msg[ID], "scene_error", str(err))
        return
    await devices.async_save(workdir=hass.config.config_dir)
    connection.send_result(
        msg[ID], {"scene_id": scene_id, "result": result == ResponseStatus.SUCCESS}
    )
