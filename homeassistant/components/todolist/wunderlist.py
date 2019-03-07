"""
Support for the Wunderlist todo lists.

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/todolist.wunderlist/
"""
import logging
import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.const import (
    CONF_ACCESS_TOKEN, ATTR_ID)

from homeassistant.components.todolist import (
    TodoListBase,
    PLATFORM_SCHEMA
)

REQUIREMENTS = ['wunderpy2==0.1.6']

_LOGGER = logging.getLogger(__name__)

CONF_CLIENT_ID = 'client_id'
CONF_LISTS = 'lists'

ATTR_STARRED = 'starred'
ATTR_COMPLETED = 'completed'
ATTR_TITLE = 'title'

WUNDERLIST_LISTS = "wunderlist_lists"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_CLIENT_ID): cv.string,
    vol.Required(CONF_ACCESS_TOKEN): cv.string,
    vol.Optional(CONF_LISTS, default=[]):
        vol.All(cv.ensure_list, [dict]),
}, extra=vol.ALLOW_EXTRA)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Wunderlist platform."""
    client_id = config.get(CONF_CLIENT_ID)
    access_token = config.get(CONF_ACCESS_TOKEN)
    lists = config.get(CONF_LISTS)

    _LOGGER.debug("Creating new Wunderlist client")
    client = create_client(access_token, client_id)
    if not check_credentials(client):
        _LOGGER.error("Invalid credentials")
        return False

    if WUNDERLIST_LISTS not in hass.data:
        hass.data[WUNDERLIST_LISTS] = []

    for list_info in lists:
        todolist = Wunderlist(client, list_info)
        hass.data[WUNDERLIST_LISTS].append(todolist)

    async_add_entities(hass.data[WUNDERLIST_LISTS])
    return True

def create_client(access_token, client_id):
    """Creates a wunderlist client instance."""
    import wunderpy2
    api = wunderpy2.WunderApi()
    client = api.get_client(access_token, client_id)
    return client

def check_credentials(client):
    """Check if the provided credentials are valid."""
    try:
        client.get_lists()
        return True
    except ValueError:
        return False

class Wunderlist(TodoListBase):
    """Representation of an interface to Wunderlist."""

    def __init__(self, client, list_info):
        """Create new instance of Wunderlist component."""
        self._client = client
        self._list_info = list_info

        _LOGGER.debug("Creating new Wunderlist list handler %s", self._list_id)

    @property
    def _list_id(self):
        return self._list_info["list_id"]

    @property
    def should_poll(self) -> bool:
        """Return True if entity has to be polled for state.

        False if entity pushes its state to HA.
        """
        return False

    @property
    def name(self):
        """Return the name of the device."""
        return self._list_info["name"]

    def map_from_todo_item(self, todo_item):
        """Converts todo item -> platform item."""
        platform_item = {
            'id': todo_item.get('id'),
            'title': todo_item.get('name'),
            'completed': todo_item.get('complete'),
        }
        return platform_item

    def map_to_todo_item(self, platform_item):
        """Converts platform item -> todo item."""
        todo_item = {
            'id': platform_item.get('id'),
            'name': platform_item.get('title'),
            'complete': platform_item.get('completed'),
        }
        return todo_item

    def _fetch_tasks(self, list_id, show_completed):
        """Return the tasks of a list, unordered."""
        incomplete_tasks = self._client.get_tasks(list_id, False)
        if show_completed is True:
            complete_tasks = self._client.get_tasks(list_id, True)
            return incomplete_tasks + complete_tasks
        return incomplete_tasks

    def _fetch_task_order(self, list_id):
        """Return the order object of tasks in a list."""
        order_obj = self._client.get_task_positions_objs(list_id)
        order = order_obj[0].get('values')
        return order

    def _order_tasks(self, tasks, order):
        """Order tasks"""
        # https://developer.wunderlist.com/documentation/endpoints/positions
        ordered_tasks = []

        # if task is found in the order list, append it to the result
        for task_id in order:
            found_task = [t for t in tasks if str(t["id"]) == str(task_id)]
            if found_task:
                ordered_tasks.append(found_task[0])
                tasks.remove(found_task[0])

        # append all the remaining unordered tasks to the end
        if len(tasks) > 0:
            tasks.sort(key=lambda x: x["id"])
            ordered_tasks = ordered_tasks + tasks

        return ordered_tasks

    def list_tasks(self, show_completed=True):
        """Return the tasks of a list, ordered."""
        tasks = self._fetch_tasks(self._list_id, show_completed)
        order = self._fetch_task_order(self._list_id)
        ordered_tasks = self._order_tasks(tasks, order)
        return ordered_tasks

    def _fetch_task(self, task_id):
        """Get a task by id."""
        task = self._client.get_task(
            task_id=task_id)
        return task

    def update_task(self, task):
        """Update a task."""
        task_id = task.get(ATTR_ID)
        existing_task = self._fetch_task(task_id)
        # define which revision of the object we would like to edit
        rev = existing_task.get("revision", 1)
        updated_task = self._client.update_task(
            task_id=task_id,
            revision=rev,
            title=task.get(ATTR_TITLE),
            completed=task.get(ATTR_COMPLETED))
        return updated_task

    def create_task(self, new_task):
        """Add a new task to a list."""
        added_task = self._client.create_task(
            list_id=self._list_id,
            title=new_task.get(ATTR_TITLE),
            completed=new_task.get(ATTR_COMPLETED))
        return added_task

    def _delete_task(self, task_id):
        """Delete a task by id."""
        existing_task = self._fetch_task(task_id)
        # define which revision of the object we would like to delete
        rev = existing_task.get("revision", 1)
        self._client.delete_task(
            task_id=task_id,
            revision=rev)
        return task_id

    def clear_completed(self):
        """Clear all the completed tasks from a list."""
        completed_tasks = self._client.get_tasks(self._list_id, True)
        for task in completed_tasks:
            task_id = task.get(ATTR_ID)
            self._delete_task(task_id)
        return True