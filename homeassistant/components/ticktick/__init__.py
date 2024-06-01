"""TickTick Mod Integration."""

from calendar import monthrange
import datetime
from functools import wraps
import json
import logging
import random
import re
import secrets

import pytz
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant

from .const import CONF_ACCESS_TOKEN, CONF_CLIENT_ID, CONF_CLIENT_SECRET, DOMAIN

PLATFORMS: list[Platform] = [Platform.TODO]

DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
VALID_HEX_VALUES = "^#([A-Fa-f0-9]{6}|[A-Fa-f0-9]{3})$"

_LOGGER = logging.getLogger(__name__)


def requests_retry_session(
    retries=3,
    backoff_factor=1,
    status_forcelist=(405, 500, 502, 504),
    session=None,
    allowed_methods=frozenset(["GET", "POST", "PUT", "DELETE"]),
):
    """Retry HTTP requests."""
    session = session or requests.session()
    retry = Retry(
        total=retries,
        read=retries,
        connect=retries,
        backoff_factor=backoff_factor,
        status_forcelist=status_forcelist,
        allowed_methods=allowed_methods,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


class OAuth2:
    """Implements the Authorization flow for TickTick's Open API."""

    OAUTH_AUTHORIZE_URL = "https://ticktick.com/oauth/authorize"
    OBTAIN_TOKEN_URL = "https://ticktick.com/oauth/token"

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
        access_token: str,
        scope: str = "tasks:write tasks:read",
        state: str | None = None,
        session=None,
    ) -> None:
        """Initialize the object.

        Arguments:
            client_id: Client ID string
            client_secret: Client secret string
            redirect_uri: Redirect uri
            access_token: Access token string in json format
            scope: Scope for the permissions. Current options are only the default.
            state (str): State parameter
            session (requests session): Requests session

        !!! examples

            === "Standard Method"

                This way would instantiate the steps to get a new access token, or just retrieve the cached one.

                ```python
                oauth = OAuth2(client_id=cliend_id,
                               client_secret=client_secret,
                               redirect_uri=redirect_uri)
                ```

            === "Check Environment Method"

                If you are in a situation where you don't want to keep the cached token file, you can save the
                access token dictionary as a string literal in your environment, and pass the name of the variable to
                prevent having to request a new access token.

                ``` python
                auth_client = OAuth2(client_id=client_id,
                                client_secret=client_secret,
                                redirect_uri=redirect_uri,
                                env_key='ACCESS_TOKEN_DICT')
                ```

                Where in the environment you have declared `ACCESS_TOKEN_DICT` to be
                the string literal of the token dictionary:

                ```
                '{'access_token': '628ff081-5331-4a37-8ddk-021974c9f43g',
                'token_type': 'bearer', 'expires_in': 14772375,
                'scope': 'tasks:read tasks:write',
                'expire_time': 1637192935,
                'readable_expire_time':
                'Wed Nov 17 15:48:55 2021'}'
                ```

        """
        self.session = (
            session or requests_retry_session()
        )  # If a proper session is passed then we will just use the existing session
        # Set the client_id
        self._client_id = client_id
        # Set the client_secret
        self._client_secret = client_secret
        # Set the redirect_uri
        self._redirect_uri = redirect_uri
        # Set the scope
        self._scope = scope
        # Set the state
        self._state = state
        # Initialize code parameter
        self._code = None
        # Set the access token
        self.access_token_info = json.loads(access_token)


def convert_local_time_to_utc(original_time, time_zone: str):
    """Convert a local time to UTC using the provided time zone.

    Arguments:
        original_time (datetime): Datetime object
        time_zone: Time zone of `original_time`

    Returns:
        datetime: Datetime object with the converted UTC time - with no timezone information attached.

    ??? info "Import Help"
        ```python
        from ticktick.helpers.time_methods import convert_local_time_to_utc
        ```

    ??? Example
        ```python
        pst = datetime(2020, 12, 11, 23, 59)
        converted = convert_local_time_to_utc(pst, 'US/Pacific')
        ```

        ??? success "Result"
            A datetime object that is the UTC equivalent of the original date.

            ```python
            datetime(2020, 12, 12, 7, 59)
            ```

    """
    utc = pytz.utc
    time_zone = pytz.timezone(time_zone)
    original_time = original_time.strftime(DATE_FORMAT)
    time_object = datetime.datetime.strptime(original_time, DATE_FORMAT)
    time_zone_dt = time_zone.localize(time_object)
    return time_zone_dt.astimezone(utc).replace(tzinfo=None)


def convert_date_to_tick_tick_format(datetime_obj, tz: str) -> str:
    """Convert a datetime object to TickTick date format.

    It first converts the datetime object to UTC time based off the passed time zone, and then
    returns a string with the TickTick required date format.

    !!! info Required Format
        ISO 8601 Format Example: 2020-12-23T01:56:07+00:00

        TickTick Required Format: 2020-12-23T01:56:07+0000 -> Where the last colon is removed for timezone

    Arguments:
        datetime_obj (datetime): Datetime object to be parsed.
        tz: Time zone string.

    Returns:
        str: The TickTick accepted date string.

    ??? info "Import Help"
        ```python
        from ticktick.helpers.time_methods import convert_iso_to_tick_tick_format
        ```

    ??? example
        ```python
        date = datetime(2022, 12, 31, 14, 30, 45)
        converted_date = convert_iso_to_tick_tick_format(date, 'US/Pacific')
        ```

        ??? success "Result"
            The proper format for a date string to be used with TickTick dates.

            ```python
            '2022-12-31T22:30:45+0000'
            ```

    """
    return (
        convert_local_time_to_utc(datetime_obj, tz)
        .replace(tzinfo=datetime.UTC)
        .isoformat()
        .replace(":", "", 1)[::-1]
    )


class TaskManager:
    """Handles all interactions for tasks."""

    TASK_CREATE_ENDPOINT = "/open/v1/task"

    def __init__(self, client_class) -> None:
        """Initialize the object."""
        self._client = client_class
        self.oauth_access_token = ""
        if self._client.oauth_manager.access_token_info is not None:
            self.oauth_access_token = self._client.oauth_manager.access_token_info[
                "access_token"
            ]
        self.oauth_headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.oauth_access_token}",
            "User-Agent": self._client.USER_AGENT,
        }
        self.headers = self._client.HEADERS

    def _generate_create_url(self):
        CREATE_ENDPOINT = "/open/v1/task"
        return self._client.OPEN_API_BASE_URL + CREATE_ENDPOINT

    def create(self, task):
        """Create a task.

        Use [`builder`][managers.tasks.TaskManager.builder] for easy task dictionary
        creation.

        !!! warning
            Creating tasks with tags is not functional but will be implemented in a future update.

        Arguments:
            task (dict): Task dictionary to be created.

        Returns:
            dict: Dictionary of created task object. Note that the task object is a "simplified" version of the full
            task object. Use [`get_by_id`][api.TickTickClient.get_by_id] for the full task object.

        !!! example "Creating Tasks"
            === "Just A Name"
                ```python
                title = "Molly's Birthday"
                task = client.task.builder(title)   # Local dictionary
                molly = client.task.create(task)    # Create task remotely
                ```

                ??? success "Result"

                    ```python
                    {'id': '60ca9dbc8f08516d9dd56324',
                     'projectId': 'inbox115781412',
                     'title': "Molly's Birthday",
                     'timeZone': '',
                     'reminders': [],
                     'priority': 0,
                     'status': 0,
                     'sortOrder': -1336456383561728,
                     'items': []}
                    ```
                    ![image](https://user-images.githubusercontent.com/56806733/122314079-5898ef00-cecc-11eb-8614-72b070b306c6.png)

            === "Dates and Descriptions"
                ```python
                title = "Molly's Birthday Party"

                start_time = datetime(2027, 7, 5, 14, 30)  # 7/5/2027 @ 2:30PM
                end_time = datetime(2027, 7, 5, 19, 30)    # 7/5/2027 @ 7:30PM

                content = "Bring Cake"

                task = client.task.builder(title,
                                           startDate=start_time,
                                           dueDate=end_time,
                                           content=content)

                mollys_party = client.task.create(task)
                ```

                ??? success "Result"
                    ```python
                    {'id': '60ca9fe58f08fe31011862f2',
                     'projectId': 'inbox115781412',
                     'title': "Molly's Birthday Party",
                     'content': 'Bring Cake',
                     'timeZone': '',
                     'startDate': '2027-07-05T21:30:00.000+0000',
                     'dueDate': '2027-07-06T02:30:00.000+0000',
                     'priority': 0,
                     'status': 0,
                     'sortOrder': -1337555895189504,
                     'items': [],
                     'allDay': False}
                    ```
                    ![image](https://user-images.githubusercontent.com/56806733/122314760-a4986380-cecd-11eb-88af-9562d352470f.png)

            === "Different Project"
                ```python
                # Get the project object
                events = client.get_by_fields(name="Events", search='projects')

                events_id = events['id']    # Need the project object id

                title = "Molly's Birthday"

                task = client.task.builder(title, projectId=events_id)

                mollys_birthday = client.task.create(task)
                ```

                ??? success "Result"
                    ```python
                    {'id': '60caa2278f08fe3101187002',
                     'projectId': '60caa20d8f08fe3101186f74',
                     'title': "Molly's Birthday",
                     'timeZone': '',
                     'reminders': [],
                     'priority': 0,
                     'status': 0,
                     'sortOrder': -1099511627776,
                     'items': []}
                    ```
                    ![image](https://user-images.githubusercontent.com/56806733/122315454-eece1480-cece-11eb-8394-94a2aec1ba70.png)

        """
        url = self._generate_create_url()
        response = self._client.http_post(
            url=url, json=task, headers=self.oauth_headers
        )
        self._client.sync()
        if response["projectId"] == "inbox":
            response["projectId"] = self._client.inbox_id
        return response

    def _generate_update_url(self, taskID: str):
        """Generate the url for updating a task based on the taskID."""
        UPDATE_ENDPOINT = f"/open/v1/task/{taskID}"
        return self._client.OPEN_API_BASE_URL + UPDATE_ENDPOINT

    def update(self, task):
        """Update a task.

        The task should already be created.

        To update a task, change any field in it's dictionary directly then pass to the method.

        !!! warning
            Creating tasks with tags is not functional but will be implemented in a future update.

        Arguments:
            task (dict): Task dictionary to be updated

        Returns:
            dict: The updated task dictionary object

        !!! tip "Formatting Dates Help"
            TickTick uses a certain syntax for their dates. To convert a datetime object to a compatible
            string to be used for updating dates, see [convert_date_to_tick_tick_format][helpers.time_methods.convert_date_to_tick_tick_format]

        !!! example "Changing The Date"

            ```python
            # Get the task
            mollys_birthday = client.get_by_fields(title="Molly's Birthday", search="tasks")

            # New Date
            new_date = datetime(2027, 5, 6)

            # Get the new date string
            new_date_string = convert_date_to_tick_tick_format(new_date, tz=client.time_zone)

            # Update the task dictionary
            mollys_birthday['startDate'] = new_date_string

            # Update the task
            molly_updated = client.task.update(mollys_birthday)
            ```

            **Original Task**
            ![image](https://user-images.githubusercontent.com/56806733/122316205-49b43b80-ced0-11eb-8d14-61fa5bb5b10a.png)

            ??? success "Result"
                ```python
                {'id': '60caa2278f08fe3101187002',
                'projectId': '60caa20d8f08fe3101186f74',
                'title': "Molly's Birthday",
                'content': '',
                'timeZone': '',
                'startDate': '2027-05-06T07:00:00.000+0000',
                'dueDate': '2027-05-05T07:00:00.000+0000',
                'reminders': [],
                'priority': 0,
                'status': 0,
                'sortOrder': -1099511627776,
                'items': [],
                'allDay': True}
                ```
                ![image](https://user-images.githubusercontent.com/56806733/122316408-ad3e6900-ced0-11eb-89f9-6d980b5cc954.png)

        """
        url = self._generate_update_url(task["id"])
        response = self._client.http_post(
            url=url, json=task, headers=self.oauth_headers
        )
        self._client.sync()
        return response

    def _generate_mark_complete_url(self, projectID, taskID):
        """Generate the url for marking a task as complete based off the projectID and taskID."""
        COMPLETE_ENDPOINT = f"/open/v1/project/{projectID}/task/{taskID}/complete"
        return self._client.OPEN_API_BASE_URL + COMPLETE_ENDPOINT

    def complete(self, task: dict):
        """Mark a task as complete.

        Pass in the task dictionary to be marked as completed.

        !!! note
            The task should already be created

        Arguments:
            task (dict): The task dictionary object.

        Returns:
            dict: The original passed in task.

        !!! example "Task Completing"
            ```python
            # Lets assume that we have a task named "Dentist" that we want to mark as complete.

            dentist_task = client.get_by_fields(title='Dentist', search='tasks')
            complete_task = client.task.complete(dentist_task)  # Pass the task dictionary
            ```

            ??? success "Result"
                The task is completed and the dictionary object returned.

                ```python
                {'id': '5fff5009b04b355792c79397', 'projectId': 'inbox115781412', 'sortOrder': -99230924406784,
                'title': 'Go To Dentist', 'content': '', 'startDate': '2021-01-13T08:00:00.000+0000',
                'dueDate': '2021-01-13T08:00:00.000+0000', 'timeZone': 'America/Los_Angeles', 'isFloating': False,
                'isAllDay': True, 'reminders': [], 'exDate': [], 'priority': 0, 'status': 2, 'items': [],
                'progress': 0, 'modifiedTime': '2021-01-13T19:56:11.000+0000', 'etag': 'djiiqso6', 'deleted': 0,
                'createdTime': '2021-01-13T19:54:49.000+0000', 'creator': 6147345572, 'kind': 'TEXT'}
                ```

                **Before**

                ![image](https://user-images.githubusercontent.com/56806733/104503673-39510b00-5596-11eb-88df-88eeee9ab4b0.png)

                **After**

                ![image](https://user-images.githubusercontent.com/56806733/104504069-c4ca9c00-5596-11eb-96c9-5698e19989ea.png)

        """
        url = self._generate_mark_complete_url(task["projectId"], task["id"])
        response = self._client.http_post(
            url=url, json=task, headers=self.oauth_headers
        )
        self._client.sync()
        if response == "":
            return task
        return response

    def _generate_delete_url(self):
        """Generate the url for deleting a task."""
        return self._client.BASE_URL + "batch/task"

    def delete(self, task):
        """Delete a task.

        Supports single task deletion, and batch task deletion.

        For a single task pass in the task dictionary. For multiple tasks pass in a list of task dictionaries.

        Arguments:
             task (str or list):
                 **Single Task (dict)**: Task dictionary to be deleted

                 **Multiple Tasks (list)**: List of task dictionaries to be deleted

        Returns:
             dict or list:
                **Single Task (dict)**: Task dictionary that was deleted

                **Multiple Tasks (list)**: List of task dictionaries that were deleted

        !!! example "Task Deletion"

            === "Single Task Deletion"

                ```python
                # Get the task
                task = client.get_by_fields(title="Molly's Birthday", search="tasks")

                # Delete the task
                deleted = client.task.delete(task)
                ```

                ??? success "Result"
                    ``` python
                    {'id': '60caa2278f08fe3101187002',
                    'projectId': '60caa20d8f08fe3101186f74',
                    'sortOrder': -1099511627776,
                    'title': "Molly's Birthday",
                    'content': '',
                    'startDate': '2027-05-06T07:00:00.000+0000',
                    'dueDate': '2027-05-06T07:00:00.000+0000',
                    'timeZone': '',
                    'isFloating': False,
                    'isAllDay': True,
                    'reminders': [],
                    'repeatFirstDate': '2027-05-05T07:00:00.000+0000',
                    'exDate': [],
                    'priority': 0,
                    'status': 0,
                    'items': [],
                    'progress': 0,
                    'modifiedTime': '2021-06-17T01:25:19.000+0000',
                    'etag': 'rrn4paqp',
                    'deleted': 0,
                    'createdTime': '2021-06-17T01:15:19.365+0000',
                    'creator': 119784412,
                    'kind': 'TEXT'}
                    ```

            === "Multiple Task Deletion"
                ``` python
                # Get the tasks
                wash_car = client.get_by_fields(title="Wash Car", search="tasks")
                do_dishes = client.get_by_fields(title="Do Dishes", search="tasks")

                # Make a list for the tasks
                to_delete = [wash_car, do_dishes]

                # Delete the tasks
                deleted = client.task.delete(to_delete)
                ```

                **Before**

                ![image](https://user-images.githubusercontent.com/56806733/122317746-e11a8e00-ced2-11eb-8449-519615de5935.png)


                ??? success "Result"
                    ```python
                    [{'id': '60caa8e714f7103cef35765a', 'projectId': '60caa20d8f08fe3101186f74',
                    'sortOrder': -1099511627776, 'title': 'Wash Car', 'content': '',
                    'timeZone': 'America/Los_Angeles', 'isFloating': False,
                    'reminder': '', 'reminders': [], 'exDate': [], 'priority': 0, 'status': 0,
                    'items': [], 'progress': 0, 'modifiedTime': '2021-06-17T01:44:07.000+0000', 'etag': '8372m61k',
                    'deleted': 0, 'createdTime': '2021-06-17T01:44:07.000+0000',
                    'creator': 115761422, 'tags': [], 'kind': 'TEXT'},

                    {'id': '60caa8ea14f7103cef35765f', 'projectId': '60caa20d8f08fe3101186f74',
                    'sortOrder': -2199023255552, 'title': 'Do Dishes', 'content': '',
                    'timeZone': 'America/Los_Angeles', 'isFloating': False, 'reminder': '',
                    'reminders': [], 'exDate': [], 'priority': 0, 'status': 0, 'items': [],
                    'progress': 0, 'modifiedTime': '2021-06-17T01:44:10.000+0000',
                    'etag': 'sfka0mvn', 'deleted': 0, 'createdTime': '2021-06-17T01:44:10.000+0000',
                    'creator': 1155481312, 'tags': [], 'kind': 'TEXT'}]
                    ```
                    ![image](https://user-images.githubusercontent.com/56806733/122317923-2212a280-ced3-11eb-8a6b-8a32fa8426ce.png)

        """
        url = self._generate_delete_url()
        to_delete = []
        if isinstance(task, dict):
            if task["projectId"] == "inbox":
                task["projectId"] = self._client.inbox_id
            delete_dict = {"projectId": task["projectId"], "taskId": task["id"]}
            to_delete.append(delete_dict)
        else:
            for item in task:
                if item["projectId"] == "inbox":
                    item["projectId"] = self._client.inbox_id
                delete_dict = {"projectId": item["projectId"], "taskId": item["id"]}
                to_delete.append(delete_dict)
        payload = {"delete": to_delete}
        self._client.http_post(
            url, json=payload, cookies=self._client.cookies, headers=self.headers
        )
        self._client.sync()
        return task

    def make_subtask(self, obj, parent: str):
        """Make the passed task(s) sub-tasks to the parent task.

        !!! note "Important"
            All of the tasks should already be created prior to using this method. Furthermore,
            the tasks should already be present in the same project as the parent task.

        Arguments:
            obj (dict):
                **Single Sub-Task (dict)**: The task object dictionary.

                **Multiple Sub-Tasks (list)**: A list of task object dictionaries.

            parent (str): The ID of the task that will be the parent task.

        Returns:
            dict:
             **Single Sub-Task (dict)**: Created sub-task dictionary.

             **Multiple Sub-Tasks (list)**: List of created sub-task dictionaries.

        Raises:
            TypeError: `obj` must be a dictionary or list of dictionaries. `parent` must be a string.
            ValueError: If `parent` task doesn't exist.
            ValueError: If `obj` does not share the same project as parent.
            RuntimeError: If the creation was unsuccessful.

        !!! example "Creating Sub-Tasks"
            === "Single Sub-Task Creation"
                Pass the task object that will be made a sub-task to the parent with the passed ID.

                ```python
                # Lets make a task in our inbox named "Read" with a sub-task "50 Pages"
                read_task = client.task.create('Read')
                pages_task = client.task.create('50 pages')
                now_subtask = client.task.make_subtask(pages_task, read_task['id'])
                ```

                ??? success "Result"
                    The dictionary of the sub-task is returned.

                    ```python
                    {'id': '5ffff4968f08af50b4654c6b', 'projectId': 'inbox115781412', 'sortOrder': -3298534883328,
                    'title': '50 pages', 'content': '', 'timeZone': 'America/Los_Angeles', 'isFloating': False,
                    'reminder': '', 'reminders': [], 'priority': 0, 'status': 0, 'items': [],
                    'modifiedTime': '2021-01-14T07:37:36.487+0000', 'etag': 'xv5cjzoz', 'deleted': 0,
                    'createdTime': '2021-01-14T07:36:54.751+0000', 'creator': 115781412,
                    'parentId': '5ffff4968f08af50b4654c62', 'kind': 'TEXT'}
                    ```

                    **Before**

                    ![image](https://user-images.githubusercontent.com/56806733/104558809-4272c400-55f8-11eb-8c55-e2f77c9d1ac8.png)

                    **After**

                    ![image](https://user-images.githubusercontent.com/56806733/104558849-55859400-55f8-11eb-9692-c3e01aa73233.png)

            === "Multiple Sub-Task Creation"
                Pass all the tasks you want to make sub-tasks in a list.

                ```python
                # Lets make a task in our inbox named "Read" with a sub-tasks "50 Pages", "100 Pages", and "200 Pages"
                read_task = client.task.create("Read")
                # Lets batch create our sub-tasks
                fifty_pages = client.task.builder('50 Pages')
                hundred_pages = client.task.builder('100 Pages')
                two_hundred_pages = client.task.builder('200 Pages')
                page_tasks = client.task.create([fifty_pages, hundred_pages, two_hundred_pages])
                # Make the page tasks sub-tasks to read_task
                subtasks = client.task.make_subtask(page_tasks, read_task['id'])
                ```

                ??? success "Result"
                    A list of the sub-tasks is returned.

                    ```python
                    [{'id': '5ffff6348f082c11cc0da84d', 'projectId': 'inbox115781412', 'sortOrder': -5497558138880,
                    'title': '50 Pages', 'content': '', 'timeZone': 'America/Los_Angeles',
                    'isFloating': False, 'reminder': '', 'reminders': [], 'priority': 0, 'status': 0,
                    'items': [], 'modifiedTime': '2021-01-14T07:45:04.032+0000', 'etag': 'avqm3u6o',
                    'deleted': 0, 'createdTime': '2021-01-14T07:43:48.858+0000', 'creator': 567893575,
                    'parentId': '5ffff6348f082c11cc0da84a', 'kind': 'TEXT'},

                    {'id': '5ffff6348f082c11cc0da84e', 'projectId': 'inbox115781412', 'sortOrder': -5497558138880,
                    'title': '100 Pages', 'content': '', 'timeZone': 'America/Los_Angeles',
                    'isFloating': False, 'reminder': '', 'reminders': [], 'priority': 0, 'status': 0,
                    'items': [], 'modifiedTime': '2021-01-14T07:45:04.035+0000', 'etag': '6295mmmu',
                    'deleted': 0, 'createdTime': '2021-01-14T07:43:49.286+0000', 'creator': 567893575,
                    'parentId': '5ffff6348f082c11cc0da84a', 'kind': 'TEXT'},

                    {'id': '5ffff6348f082c11cc0da84f', 'projectId': 'inbox115781412', 'sortOrder': -5497558138880,
                    'title': '200 Pages', 'content': '', 'timeZone': 'America/Los_Angeles',
                    'isFloating': False, 'reminder': '', 'reminders': [], 'priority': 0, 'status': 0,
                    'items': [], 'modifiedTime': '2021-01-14T07:45:04.038+0000', 'etag': 'du59zwck',
                    'deleted': 0, 'createdTime': '2021-01-14T07:43:49.315+0000', 'creator': 567893575,
                    'parentId': '5ffff6348f082c11cc0da84a', 'kind': 'TEXT'}]
                    ```

                    **Before**

                    ![image](https://user-images.githubusercontent.com/56806733/104559418-36d3cd00-55f9-11eb-9004-177671a92474.png)

                    **After**

                    ![image](https://user-images.githubusercontent.com/56806733/104559535-64207b00-55f9-11eb-84cf-ca4f989ea075.png)

        """
        if not isinstance(obj, dict) and not isinstance(obj, list):
            raise TypeError("obj must be a dictionary or list of dictionaries")
        if not isinstance(parent, str):
            raise TypeError("parent must be a string")
        if isinstance(obj, dict):
            obj = [obj]
        parent_obj = self._client.get_by_id(search="tasks", obj_id=parent)
        if not parent_obj:
            raise ValueError("Parent task must exist before creating sub-tasks")
        ids = []
        for o in obj:
            if o["projectId"] != parent_obj["projectId"]:
                raise ValueError("All tasks must be in the same project as the parent")
            ids.append(o["id"])
        subtasks = []
        for i in ids:  # Create the object dictionaries for setting the subtask
            temp = {
                "parentId": parent,
                "projectId": parent_obj["projectId"],
                "taskId": i,
            }
            subtasks.append(temp)
        url = self._client.BASE_URL + "batch/taskParent"
        self._client.http_post(
            url, json=subtasks, cookies=self._client.cookies, headers=self.headers
        )
        self._client.sync()
        subtasks = []
        for task_id in ids:
            subtasks.append(self._client.get_by_id(task_id, search="tasks"))
        if len(subtasks) == 1:
            return subtasks[0]  # Return just the dictionary object if its a single task
        return subtasks

    def move(self, obj, new: str):
        """Move task(s) from their current project to the new project.

        It will move the specified
        tasks with `obj` to the new project.

        !!! important
            If moving multiple tasks, they must all be from the same project.

        Arguments:
            obj (dict or list):
                **Single Task (dict)**: Pass the single task dictionary object to move.

                **Multiple Tasks (list)**: Pass a list of task dictionary objects to move.
            new: The ID string of the project that the task(s) should be moved to.

        Returns:
            dict or list:
            **Single Task (dict)**: Returns the dictionary of the moved task.

            **Multiple Tasks (list)**: Returns a list of dictionaries for the moved tasks.

        Raises:
            TypeError: If `obj` is not a dict or list or if `new` is not a str.
            ValueError: For multiple tasks, if the projects are not all the same.
            ValueError: If the new project does not exist.
            RuntimeError: If the task(s) could not be successfully moved.

        !!! example "Move Examples"
            === "Moving A Single Task"
                Pass in the task object, and the ID of the project the task should be moved to.

                ```python
                # Lets assume that we have a task 'Read' that exists in a project named "Work"
                # Lets move that task to the inbox
                read_task = client.get_by_fields(title='Read', search='tasks')
                move_read_task = client.task.move(read_task, client.inbox_id)
                ```

                ??? success "Result"
                    The dictionary object of the moved task is returned.

                    ```python
                    {'id': '5fffed61b04b355792c799a8', 'projectId': 'inbox115781412', 'sortOrder': 0,
                    'title': 'Read', 'content': '', 'startDate': '2021-01-13T08:00:00.000+0000',
                    'dueDate': '2021-01-13T08:00:00.000+0000', 'timeZone': 'America/Los_Angeles',
                    'isFloating': False, 'isAllDay': True, 'reminders': [], 'exDate': [], 'priority': 0,
                    'status': 0, 'items': [], 'progress': 0, 'modifiedTime': '2021-01-14T07:08:15.875+0000',
                    'etag': 'twrmcr55', 'deleted': 0, 'createdTime': '2021-01-14T07:06:09.000+0000',
                    'creator': 47593756, 'tags': [], 'kind': 'TEXT'}
                    ```

                    **Before**

                    ![image](https://user-images.githubusercontent.com/56806733/104556170-f1f96780-55f3-11eb-9a35-aecc3beea105.png)

                    **After**

                    ![image](https://user-images.githubusercontent.com/56806733/104556336-46044c00-55f4-11eb-98c1-4cffcf4bd006.png)

            === "Moving Multiple Tasks"
                Pass in the task objects in a list, and the ID of the project that tasks should be moved to.
                Again, the tasks in the list should all be from the same project.

                ```python
                # Lets move two tasks: 'Read' and 'Write' that exist in a project named "Work"
                # Lets move the tasks to another project named "Hobbies" that already exists.
                hobbies_project = client.get_by_fields(name='Hobbies', search='projects')
                hobbies_id = hobbies_project['id']  # Id of the hobbies project
                read_task = client.get_by_fields(title='Read', search='tasks')
                write_task = client.get_by_fields(title='Write', search='tasks')
                move_tasks = client.task.move([read_task, write_task], hobbies_id)  # Task objects in a list
                ```

                ??? success "Result"
                    The tasks that were moved are returned in a list.

                    ```python
                    [{'id': '5ffff003b04b355792c799d3', 'projectId': '5fffeff68f08654c982c141a', 'sortOrder': 0,
                    'title': 'Read', 'content': '', 'startDate': '2021-01-13T08:00:00.000+0000',
                    'dueDate': '2021-01-13T08:00:00.000+0000', 'timeZone': 'America/Los_Angeles',
                    'isFloating': False, 'isAllDay': True, 'reminders': [], 'exDate': [], 'priority': 0,
                    'status': 0, 'items': [], 'progress': 0, 'modifiedTime': '2021-01-14T07:19:28.595+0000',
                    'etag': 'co8jfqyn', 'deleted': 0, 'createdTime': '2021-01-14T07:17:23.000+0000',
                    'creator': 768495743, 'kind': 'TEXT'},

                    {'id': '5ffff004b04b355792c799d4', 'projectId': '5fffeff68f08654c982c141a', 'sortOrder': 0,
                    'title': 'Write', 'content': '', 'startDate': '2021-01-13T08:00:00.000+0000',
                    'dueDate': '2021-01-13T08:00:00.000+0000', 'timeZone': 'America/Los_Angeles',
                    'isFloating': False, 'isAllDay': True, 'reminders': [], 'exDate': [], 'priority': 0,
                    'status': 0, 'items': [], 'progress': 0, 'modifiedTime': '2021-01-14T07:19:28.596+0000',
                    'etag': '5unkf7xg', 'deleted': 0, 'createdTime': '2021-01-14T07:17:24.000+0000',
                    'creator': 768495743, 'tags': [], 'kind': 'TEXT'}]
                    ```

                    **Before**

                    ![image](https://user-images.githubusercontent.com/56806733/104557103-857f6800-55f5-11eb-8b92-cf51bc159745.png)

                    **After**

                    ![image](https://user-images.githubusercontent.com/56806733/104557388-063e6400-55f6-11eb-8ba4-aa64f3f739bd.png)

        """
        if not isinstance(obj, dict) and not isinstance(obj, list):
            raise TypeError("obj should be a dict or list of dicts")
        if not isinstance(new, str):
            raise TypeError("new should be a string")
        if new != self._client.inbox_id:
            project = self._client.get_by_id(new, search="projects")
            if not project:
                raise ValueError("The ID for the new project does not exist")
        if isinstance(obj, dict):
            obj = [obj]
        move_tasks = []
        project_id = obj[0]["projectId"]
        for task in obj:
            if task["projectId"] != project_id:
                raise ValueError("All the tasks must come from the same project")
            move_tasks.append(
                {
                    "fromProjectId": project_id,
                    "taskId": task["id"],
                    "toProjectId": new,
                }
            )
        url = self._client.BASE_URL + "batch/taskProject"
        self._client.http_post(
            url, json=move_tasks, cookies=self._client.cookies, headers=self.headers
        )
        self._client.sync()
        # Return the tasks in the new list
        ids = [x["id"] for x in obj]
        return_list = [self._client.get_by_id(i) for i in ids]
        if len(return_list) == 1:
            return return_list[0]
        return return_list

    def move_all(self, old: str, new: str) -> list:
        """Move all the tasks from the old project to the new project.

        Arguments:
            old: ID of the old project.
            new: ID of the new project.

        Returns:
            The tasks contained in the new project.

        Raises:
            ValueError: If either the old or new projects do not exist.
            RuntimeError: If the movement was unsuccessful.

        !!! example
            Lets assume that we have a project named "School", and another project named "Work". To move all the tasks from "School" to "Work":

            ```python
            # Get the projects
            school_project = client.get_by_fields(name='School', search='projects')
            work_project = client.get_by_fields(name='Work', search='projects')
            # Call the method
            moved_tasks = client.task.move_all(school_project['id'], work_project['id'])
            ```

            ??? success "Result"
                The tasks that were moved are returned.

                ```python
                [{'id': '5ffea9afe4b062d60dd62aef', 'projectId': '5ffea9afe4b062d60dd62aea', 'sortOrder': 0,
                'title': 'Finish documentation for project', 'content': '', 'timeZone': 'America/Los_Angeles',
                'isFloating': False, 'reminder': '', 'reminders': [], 'priority': 0, 'status': 0, 'items': [],
                'modifiedTime': '2021-01-13T08:06:31.407+0000', 'etag': 'ogclghmd', 'deleted': 0,
                'createdTime': '2021-01-13T08:05:03.901+0000', 'creator': 447666584, 'kind': 'TEXT'},

                {'id': '5ffea9b0e4b062d60dd62af4', 'projectId': '5ffea9afe4b062d60dd62aea', 'sortOrder': 0,
                'title': 'Call the boss man', 'content': '', 'timeZone': 'America/Los_Angeles',
                'isFloating': False, 'reminder': '', 'reminders': [], 'priority': 0, 'status': 0, 'items': [],
                'modifiedTime': '2021-01-13T08:06:31.409+0000', 'etag': '65c73q8i', 'deleted': 0,
                'createdTime': '2021-01-13T08:05:04.117+0000', 'creator': 447666584, 'kind': 'TEXT'}]
                ```

                **Before**: Two tasks are contained in the "School" project

                ![image](https://user-images.githubusercontent.com/56806733/104423574-1e997a80-5533-11eb-9417-34c31e603d21.png)

                **After**: The two tasks are moved to the 'Work' project

                ![image](https://user-images.githubusercontent.com/56806733/104423710-4a1c6500-5533-11eb-90f3-2c3d024280af.png)

        """
        if old != self._client.inbox_id:
            old_list = self._client.get_by_fields(id=old, search="projects")
            if not old_list:
                raise ValueError(f"Project Id '{old}' Does Not Exist")
        if new != self._client.inbox_id:
            new_list = self._client.get_by_fields(id=new, search="projects")
            if not new_list:
                raise ValueError(f"Project Id '{new}' Does Not Exist")
        tasks = self.get_from_project(old)
        if not tasks:
            return tasks  # No tasks to move so just return the empty list
        task_project = [
            {"fromProjectId": old, "taskId": task["id"], "toProjectId": new}
            for task in tasks
        ]
        url = self._client.BASE_URL + "batch/taskProject"
        self._client.http_post(
            url, json=task_project, cookies=self._client.cookies, headers=self.headers
        )
        self._client.sync()
        return self._client.task.get_from_project(new)

    def get_from_project(self, project: str):
        """Obtain the tasks that are contained in the project.

        Arguments:
            project: ID string of the project to get the tasks from.

        Returns:
            dict or list:
            **Single Task In Project (dict)**: The single task object dictionary.

            **Multiple Tasks In Project (list)**: A list of task object dictionaries.

            **No Tasks Found (list)**: Empty list.

        Raises:
            ValueError: If the project ID does not exist.

        !!! example "Getting Uncompleted Tasks From The Inbox"
            ```python
            tasks = client.task.get_from_project(client.inbox_id)
            ```

            ??? success "Result"
                See `Returns` for the different return values based on the amount of tasks present
                in the project.

                ```python
                [{'id': '5ffe93efb04b35082bbce7af', 'projectId': 'inbox115781412', 'sortOrder': 2199023255552, 'title': 'Go To Library',
                'content': '', 'startDate': '2021-01-12T08:00:00.000+0000', 'dueDate': '2021-01-12T08:00:00.000+0000',
                'timeZone': 'America/Los_Angeles', 'isFloating': False, 'isAllDay': True,
                'reminders': [], 'exDate': [], 'priority': 0, 'status': 0, 'items': [], 'progress': 0,
                'modifiedTime': '2021-01-13T06:32:15.000+0000', 'etag': 'kkh0w1jk', 'deleted': 0,
                'createdTime': '2021-01-13T06:32:15.000+0000', 'creator': 447666584, 'tags': [],
                'kind': 'TEXT'},

                {'id': '5ffe93f3b04b35082bbce7b0', 'projectId': 'inbox115781412', 'sortOrder': 1099511627776, 'title': 'Deposit Funds',
                'content': '', 'startDate': '2021-01-12T08:00:00.000+0000', 'dueDate': '2021-01-12T08:00:00.000+0000',
                'timeZone': 'America/Los_Angeles', 'isFloating': False, 'isAllDay': True,
                'reminders': [], 'exDate': [], 'priority': 0, 'status': 0, 'items': [], 'progress': 0, 'modifiedTime': '2021-01-13T06:32:19.000+0000',
                'etag': 'w4hj21wf', 'deleted': 0, 'createdTime': '2021-01-13T06:32:19.000+0000', 'creator': 447666584, 'tags': [],
                'kind': 'TEXT'}]
                ```

                ![image](https://user-images.githubusercontent.com/56806733/104415494-f86ddd80-5526-11eb-8b84-75bf3886ba46.png)

        """
        if project != self._client.inbox_id:
            obj = self._client.get_by_fields(id=project, search="projects")
            if not obj:
                raise ValueError(f"List Id '{project}' Does Not Exist")
        tasks = self._client.get_by_fields(projectId=project, search="tasks")
        if isinstance(tasks, dict):
            return [tasks]
        return tasks

    def get_completed(
        self, start, end=None, full: bool = True, tz: None | str = None
    ) -> list:
        """Obtain all completed tasks from the given start date and end date.

        !!! note
            There is a limit of 100 items for the request

        Arguments:
            start (datetime): Start time datetime object.
            end (datetime): End time datetime object.
            full: Boolean specifying whether hours, minutes, and seconds are to be taken into account for the query.
            tz: String specifying a specific time zone, however this will default to your accounts normal time zone.

        Returns:
            A list containing all the completed tasks based on the times.

        Raises:
            TypeError: If the proper types are not used.
            ValueError: If start occurs after end.
            KeyError: If the time zone string passed is not a valid time zone string.
            RuntimeError: If getting the tasks is unsuccessful.

        !!! example "Getting Completed Tasks"
            === "Completed Tasks In A Single Day"
                Getting the tasks for a full, complete day requires passing in
                the datetime object corresponding to the day that you want.

                ```python
                # Get the tasks for 1/11/2021
                tasks = client.task.get_completed(datetime(2021, 1, 11))
                ```

                ??? success "Result"
                    The list of completed tasks is returned.

                    ```python
                    [{'id': '5ffca35f4c201114702a0607', 'projectId': '004847faa60015487be444cb',
                    'sortOrder': -50027779063826, 'title': 'Shoulders and Arms', 'content': '', 'desc': '',
                    'startDate': '2021-01-11T08:00:00.000+0000', 'dueDate': '2021-01-11T08:00:00.000+0000',
                    'timeZone': 'America/Los_Angeles', 'isFloating': False, 'isAllDay': True, 'reminders': [],
                    'repeatFlag': '', 'exDate': [], 'completedTime': '2021-01-11T23:25:46.000+0000',
                    'completedUserId': 185769383, 'priority': 0, 'status': 2, 'items': [], 'progress': 0,
                    'modifiedTime': '2021-01-11T23:25:41.000+0000', 'etag': '6hlk4e8t', 'deleted': 0,
                    'createdTime': '2021-01-11T19:13:35.000+0000', 'creator': 185769383, 'tags': ['fitness'],
                    'commentCount': 0, 'pomodoroSummaries': [{'userId': 185769383, 'count': 0, 'estimatedPomo': 0,
                    'duration': 0}], 'focusSummaries': [{'userId': 185769383, 'pomoCount': 0, 'estimatedPomo': 0,
                    'estimatedDuration': 0, 'pomoDuration': 0, 'stopwatchDuration': 3720}], 'kind': 'TEXT'}]
                    ```

                    ![image](https://user-images.githubusercontent.com/56806733/104562952-e1e68580-55fd-11eb-9e09-f432caa8616b.png)

            === "Completed Tasks Over A Range Of Days"
                Getting the tasks for a range of days requires passing in datetime objects
                for the start day, and the end day that you want.

                ```python
                # Get the tasks between 8/7/18 and 8/10/18
                start = datetime(2018, 8, 7)
                end = datetime(2018, 8, 10)
                tasks = client.task.get_completed(start, end)
                ```

                ??? success "Result"
                    Completed tasks in a list are returned.

                    ```python
                    [{'id': '5ffffebab04b355792c79e38', 'projectId': 'inbox115781412', 'sortOrder': -7696581394432,
                    'title': 'Ride Bike', 'content': '', 'startDate': '2021-01-14T08:00:00.000+0000',
                    'dueDate': '2021-01-14T08:00:00.000+0000', 'timeZone': 'America/Los_Angeles',
                    'isFloating': False, 'isAllDay': True, 'reminders': [], 'exDate': [],
                    'completedTime': '2018-08-09T07:20:11.000+0000', 'completedUserId': 185769383,
                    'priority': 0, 'status': 2, 'items': [], 'progress': 0,
                    'modifiedTime': '2021-01-14T08:21:01.000+0000', 'etag': 'mhjyig4y',
                    'deleted': 0, 'createdTime': '2021-01-14T08:20:10.000+0000', 'creator': 185769383, 'kind': 'TEXT'},

                    {'id': '5ffffeaab04b355792c79d89', 'projectId': 'inbox115781412',
                    'sortOrder': -6597069766656, 'title': 'Read Book', 'content': '',
                    'startDate': '2021-01-14T08:00:00.000+0000', 'dueDate': '2021-01-14T08:00:00.000+0000',
                    'timeZone': 'America/Los_Angeles', 'isFloating': False, 'isAllDay': True, 'reminders': [],
                    'exDate': [], 'completedTime': '2018-08-08T07:20:12.000+0000', 'completedUserId': 185769383,
                    'priority': 0, 'status': 2, 'items': [], 'progress': 0,
                    'modifiedTime': '2021-01-14T08:20:46.000+0000', 'etag': 'tzd4coms', 'deleted': 0,
                    'createdTime': '2021-01-14T08:19:54.000+0000', 'creator': 185769383, 'kind': 'TEXT'}]
                    ```

                    ![image](https://user-images.githubusercontent.com/56806733/104563478-8c5ea880-55fe-11eb-9bcf-91bc44c02083.png)

            === "Completed Tasks Over A Specific Duration Of Time"
                You can also get completed tasks that were completed in a specific time duration.
                Include specific hours, minutes, and seconds for the datetime objects, and
                specify `full` to be false -> meaning that the specific times will be put into effect.

                ```python
                # Get the tasks completed between 12PM and 5PM on 12/15/2020
                start = datetime(2020, 12, 15, 12)  # 12PM 12/15/2020
                end = datetime(2020, 12, 15, 17)    # 5PM 12/15/2020
                tasks = client.task.get_completed(start, end, full=False)
                ```

        """
        url = self._client.BASE_URL + "project/all/completed"
        if tz is None:
            tz = self._client.time_zone
        if not isinstance(start, datetime.datetime):
            raise TypeError("Start Must Be A Datetime Object")
        if not isinstance(end, datetime.datetime) and end is not None:
            raise TypeError("End Must Be A Datetime Object")
        if end is not None and start > end:
            raise ValueError("Invalid Date Range: Start Date Occurs After End Date")
        if tz not in pytz.all_timezones_set:
            raise KeyError("Invalid Time Zone")
        if end is None:
            start = datetime.datetime(start.year, start.month, start.day, 0, 0, 0)
            end = datetime.datetime(start.year, start.month, start.day, 23, 59, 59)
        elif full is True and end is not None:
            start = datetime.datetime(start.year, start.month, start.day, 0, 0, 0)
            end = datetime.datetime(end.year, end.month, end.day, 23, 59, 59)
        start = convert_local_time_to_utc(start, tz)
        end = convert_local_time_to_utc(end, tz)
        parameters = {
            "from": start.strftime(DATE_FORMAT),
            "to": end.strftime(DATE_FORMAT),
            "limit": 100,
        }

        return self._client.http_get(
            url, params=parameters, cookies=self._client.cookies, headers=self.headers
        )

    def dates(self, start, due=None, tz=None):
        """Perform necessary date conversions from datetime objects to strings.

        This method allows for more natural input of data to the [`builder`][managers.tasks.TaskManager.builder]
        method.

        Arguments:
            start (datetime): Desired start time
            due (datetime): Desired end time
            tz (str): Time zone string if the desired time zone is not the account default.

        Returns:
            dict: Contains 'startDate', 'endDate', 'timeZone', and 'allDay' when applicable.


        1. All Day Start Time (single day task)
        2. All Day Start and End Time (multi-day range)
        3. Specific Start Time (specific time task)
        4. Specific Start and End Time (specific start and end task)

        !!! example "Last Day Of The Month"
            ```python
            start = datetime(2027, 3, 27)
            end = datetime(2027, 3, 31)

            dates = client.task.dates(start, end)
            ```

            ??? success "Result"
                ```
                {'startDate': '2027-03-27T07:00:00+0000',
                'dueDate': '2027-04-01T07:00:00+0000',
                'allDay': True}
                ```

        """
        dates = {}
        if tz is not None:
            dates["timeZone"] = tz
        else:
            tz = self._client.time_zone
        if due is None:
            if (
                start.hour != 0
                or start.minute != 0
                or start.second != 0
                or start.microsecond != 0
            ):
                dates["startDate"] = convert_date_to_tick_tick_format(start, tz)
                dates["allDay"] = False
            else:
                dates["startDate"] = convert_date_to_tick_tick_format(start, tz)
                dates["allDay"] = True
            return dates
        if (
            start.hour != 0
            or start.minute != 0
            or start.second != 0
            or start.microsecond != 0
            or due.hour != 0
            or due.minute != 0
            or due.second != 0
            or due.microsecond != 0
        ):
            dates["startDate"] = convert_date_to_tick_tick_format(start, tz)
            dates["dueDate"] = convert_date_to_tick_tick_format(due, tz)
            dates["allDay"] = False
            return dates
        days = monthrange(due.year, due.month)
        if due.day + 1 > days[1]:  # Last day of the month
            if due.month + 1 > 12:  # Last month of the year
                year = due.year + 1  # Both last day of month and last day of year
                day = 1
                month = 1
            else:  # Not last month of year, just reset the day and increment the month
                year = due.year
                month = due.month + 1
                day = 1
        else:  # Dont have to worry about incrementing year or month
            year = due.year
            day = due.day + 1
            month = due.month
        due = datetime.datetime(year, month, day)  # No hours, mins, or seconds needed
        dates["startDate"] = convert_date_to_tick_tick_format(start, tz)
        dates["dueDate"] = convert_date_to_tick_tick_format(due, tz)
        dates["allDay"] = True
        return dates

    def builder(
        self,
        title: str = "",
        projectId: str | None = None,
        content: str | None = None,
        desc: str | None = None,
        allDay: bool | None = None,
        startDate: datetime.datetime | None = None,
        dueDate: datetime.datetime | None = None,
        timeZone: str | None = None,
        reminders: list | None = None,
        repeat: str | None = None,
        priority: int | None = None,
        sortOrder: int | None = None,
        items: list | None = None,
    ):
        """Build a task dictionary with the passed fields.

        This is a helper
        method for task creation.

        Arguments:
            title (str): Desired name of the task
            projectId (str): ID string of the project
            content (str): Content body of the task
            desc (str): Description of the task checklist
            allDay (bool): Boolean for whether the task is all day or not
            startDate (datetime.datetime): Start time of the task
            dueDate (datetime.datetime): End time of the task
            timeZone (str): Time zone for the task
            reminders (list): List of reminder triggers
            repeat (str): Recurring rules for the task
            priority (int): None:0, Low:1, Medium:3, High5
            sortOrder (int): Task sort order
            items (list): Subtasks of task

        Returns:
            dict: A dictionary containing the fields necessary for task creation.

        !!! example
            Building a local task object with a title, start, and due time.

            ```python
            start = datetime(2027, 5, 2)
            end = datetime(2027, 5, 7)
            title = 'Festival'
            task_dict = client.task.builder(title, startDate=start, dueDate=end)
            ```

            ??? Result

                ```python
                {'startDate': '2027-05-02T07:00:00+0000',
                 'dueDate': '2027-05-08T07:00:00+0000',
                 'allDay': True,
                 'title': 'Festival'}```

        """

        task = {"title": title}
        if projectId is not None:
            task["projectId"] = projectId
        if content is not None:
            task["content"] = content
        if desc is not None:
            task["desc"] = desc
        if allDay is not None:
            task["allDay"] = allDay
        if reminders is not None:
            task["reminders"] = reminders
        if repeat is not None:
            task["repeat"] = repeat
        if priority is not None:
            task["priority"] = priority
        if sortOrder is not None:
            task["sortOrder"] = sortOrder
        if items is not None:
            task["items"] = items
        dates = {}
        # date conversions
        if startDate is not None:
            dates = self.dates(startDate, dueDate, timeZone)
        # merge dicts
        return {**dates, **task}


def _sort_string_value(sort_type: int) -> str:
    if sort_type not in {0, 1, 2, 3}:
        raise ValueError(
            f"Sort Number '{sort_type}' Is Invalid -> Must Be 0, 1, 2 or 3"
        )
    return {0: "project", 1: "dueDate", 2: "title", 3: "priority"}[sort_type]


class TagsManager:
    """Handle all interactions for tags."""

    SORT_DICTIONARY = {0: "project", 1: "dueDate", 2: "title", 3: "priority"}

    def __init__(self, client_class) -> None:
        """Initialize the TagsManager class."""
        self._client = client_class
        self.access_token = self._client.access_token
        self.headers = self._client.HEADERS

    def _sort_string_value(self, sort_type: int) -> str:
        """Return the string corresponding to the sort type integer.

        :param sort_type:

        :return str:

        """
        if sort_type not in {0, 1, 2, 3}:
            raise ValueError(
                f"Sort Number '{sort_type}' Is Invalid -> Must Be 0, 1, 2 or 3"
            )
        return self.SORT_DICTIONARY[sort_type]

    def _check_fields(
        self,
        label: str | None = None,
        color: str = "random",
        parent_label: str | None = None,
        sort: int | None = None,
    ) -> dict:
        if label is not None:
            if not isinstance(label, str):
                raise TypeError("Label Must Be A String")
            tag_list = self._client.get_by_fields(
                search="tags", name=label.lower()
            )  # Name is lowercase version of label
            if tag_list:
                raise ValueError(f"Invalid Tag Name '{label}' -> It Already Exists")
        if not isinstance(color, str):
            raise TypeError("Color Must Be A Hex Color String")
        if color.lower() == "random":
            color = generate_hex_color()  # Random color will be generated
        elif color is not None:
            if not check_hex_color(color):
                raise ValueError("Invalid Hex Color String")
        if parent_label is not None:
            if not isinstance(parent_label, str):
                raise TypeError("Parent Name Must Be A String")
            parent_label = parent_label.lower()
            parent = self._client.get_by_fields(search="tags", name=parent_label)
            if not parent:
                raise ValueError(
                    f"Invalid Parent Name '{parent_label}' -> Does Not Exist"
                )
        if sort is None:
            sort = "project"
        else:
            sort = _sort_string_value(sort)
        return {
            "label": label,
            "color": color,
            "parent": parent_label,
            "sortType": sort,
            "name": label.lower(),
        }

    def builder(
        self,
        label: str,
        color: str = "random",
        parent: str | None = None,
        sort: int | None = None,
    ) -> dict:
        """Create and returns a local tag object.

        Helper method for [create][managers.tags.TagsManager.create]
        to make batch creating projects easier.

        !!! note
            The parent tag must already exist prior to calling this method.

        Arguments:
            label: Desired label of the tag - tag labels cannot be repeated.
            color: Hex color string. A random color will be generated if no color is specified.
            parent: The label of the parent tag if desired (include capitals in the label if it exists).
            sort: The desired sort type of the tag. Valid integer values are present in the [sort dictionary](tags.md#sort-dictionary). The default
                sort value will be by 'project'

        Returns:
            A dictionary containing all the fields necessary to create a tag remotely.

        Raises:
            TypeError: If any of the types of the arguments are wrong.
            ValueError: Tag label already exists.
            ValueError: Parent tag does not exist.
            ValueError: The hex string color inputted is invalid.

        !!! example
            ```python
            tag_name = 'Books'  # The name for our tag
            parent_name = 'Productivity'  # The desired parent tag -> this should already exist.
            color_code = '#1387c4'
            sort_type = 1  # Sort by `dueDate`
            tag_object = client.tag.builder(tag_name, parent=parent_name, color=color_code, sort=sort_type)
            ```

            ??? success "Result"
                The required fields to create a tag object are created and returned in a dictionary.

                ```python
                {'label': 'Fiction', 'color': '#1387c4', 'parent': 'books', 'sortType': 'dueDate', 'name': 'fiction'}
                ```

        """
        return self._check_fields(label, color=color, parent_label=parent, sort=sort)

    def create(
        self,
        label,
        color: str = "random",
        parent: str | None = None,
        sort: int | None = None,
    ):
        r"""Create a tag remotely.

        Supports single tag creation or batch tag creation.

        !!! tip
            Allows creation with a label that may normally not be allowed by `TickTick` for tags.

            Normal `TickTick` excluded characters are: \\ / " # : * ? < > | Space

        Arguments:
            label (str or list):
                **Single Tag (str)**: The desired label of the tag. Tag labels cannot be repeated.

                **Multiple Tags (list)**: A list of tag objects created using the [builder][managers.tags.TagsManager.builder] method.
            color: Hex color string. A random color will be generated if no color is specified.
            parent: The label of the parent tag if desired (include capitals in if it exists).
            sort: The desired sort type of the tag. Valid integer values are present in the [sort dictionary](tags.md#sort-dictionary). The default
                sort value will be by 'project'

        Returns:
            dict or list:
            **Single Tag (dict)**: The created tag object dictionary.

            **Multiple Tags (list)**: A list of the created tag object dictionaries.

        Raises:
            TypeError: If any of the types of the arguments are wrong.
            ValueError: Tag label already exists.
            ValueError: Parent tag does not exist.
            ValueError: The hex string color inputted is invalid.
            RuntimeError: The tag(s) could not be created.

        !!! example "Single Tag"

            === "Just A Label"
                ```python
                tag = client.tag.create('Fun')
                ```

                ??? success "Result"
                    The tag object dictionary is returned.

                    ```python
                    {'name': 'fun', 'label': 'Fun', 'sortOrder': 0, 'sortType': 'project', 'color': '#9b69f3', 'etag': '7fc8zb58'}
                    ```
                    Our tag is created.

                    ![image](https://user-images.githubusercontent.com/56806733/104658773-5bbb5500-5678-11eb-9d44-27214203d70e.png)

            === "Specify a Color"
                A random color can be generated using [generate_hex_color][helpers.hex_color.generate_hex_color].
                However, just not specifying a color will automatically generate a random color (as seen in the previous tab)
                You can always specify the color that you want.

                ```python
                tag = client.tag.create('Fun', color='#86bb6d')
                ```

                ??? success "Result"
                    The tag object dictionary is returned and our project is created with the color specified.

                    ```python
                    {'name': 'fun', 'label': 'Fun', 'sortOrder': 0, 'sortType': 'project', 'color': '#86bb6d', 'etag': '8bzzdws3'}
                    ```
                    ![image](https://user-images.githubusercontent.com/56806733/104659184-0c295900-5679-11eb-9f3c-2cd154c0500c.png)

            === "Specifying a Parent Tag"
                Tags can be nested one level. To create a tag that is nested, include the label of the parent tag.
                The parent tag should already exist.

                ```python
                tag = client.tag.create('Fun', parent='Hobbies')
                ```

                ??? success "Result"
                    The tag object dictionary is returned and our tag is created nested under the parent tag.

                    ```python
                    {'name': 'fun', 'label': 'Fun', 'sortOrder': 0, 'sortType': 'project', 'color': '#d2a6e4', 'etag': 'nauticx1', 'parent': 'hobbies'}
                    ```

                    **Before**

                    ![image](https://user-images.githubusercontent.com/56806733/104659785-24e63e80-567a-11eb-9a62-01ebca55e649.png)

                    **After**

                    ![image](https://user-images.githubusercontent.com/56806733/104659814-33ccf100-567a-11eb-8dca-c91aea68b4c7.png)

            === "Sort Type"
                You can specify the sort type of the created tag using integer values from the [sort dictionary](#sort-dictionary).

                ```python
                tag = client.tag.create('Fun', sort=2)  # Sort by `title`
                ```

                ??? success "Result"
                    The tag object dictionary is returned and our tag has the specified sort type.

                    ```python
                    {'name': 'fun', 'label': 'Fun', 'sortOrder': 0, 'sortType': 'title', 'color': '#e7e7ba', 'etag': 'n4k3pezc'}
                    ```

                    ![image](https://user-images.githubusercontent.com/56806733/104660156-e4d38b80-567a-11eb-8c61-8fb874a515a2.png)

        !!! example "Multiple Tag Creation (batch)"
            To create multiple tags, build the tag objects first using the [builder][managers.projects.ProjectManager.builder] method. Pass
            in a list of the project objects to create them remotely.

            ```python
            parent_tag = client.tag.create('Hobbies')  # Create a parent tag.
            # We will create tag objects using builder that will be nested under the parent tag
            fun_tag = client.tag.builder('Fun', sort=2, parent='Hobbies')
            read_tag = client.tag.builder('Read', color='#d2a6e4', parent='Hobbies')
            movie_tag = client.tag.builder('Movies', parent='Hobbies')
            # Create the tags
            tag_list = [fun_tag, read_tag, movie_tag]
            created_tags = client.tag.create(tag_list)
            ```

            ??? success "Result"
                The tag object dictionaries are returned in a list.

                ```python
                [{'name': 'fun', 'label': 'Fun', 'sortOrder': 0, 'sortType': 'title', 'color': '#172d1c', 'etag': '1tceclp4', 'parent': 'hobbies'},

                {'name': 'read', 'label': 'Read', 'sortOrder': 0, 'sortType': 'project', 'color': '#d2a6e4', 'etag': 'ykdem8dg', 'parent': 'hobbies'},

                {'name': 'movies', 'label': 'Movies', 'sortOrder': 0, 'sortType': 'project', 'color': '#94a5f8', 'etag': 'o0nifkbv', 'parent': 'hobbies'}]
                ```

                ![image](https://user-images.githubusercontent.com/56806733/104660625-cb7f0f00-567b-11eb-8649-68646870ccfa.png)

        """
        batch = False  # Bool signifying batch create or not
        if isinstance(label, list):
            obj = label  # Assuming all correct objects
            batch = True
        else:
            if not isinstance(label, str):
                raise TypeError(
                    "Required Positional Argument Must Be A String or List of Tag Objects"
                )
            obj = self.builder(label=label, color=color, parent=parent, sort=sort)
        if not batch:
            obj = [obj]
        url = self._client.BASE_URL + "batch/tag"
        payload = {"add": obj}
        response = self._client.http_post(
            url, json=payload, cookies=self._client.cookies, headers=self.headers
        )
        self._client.sync()
        if not batch:
            return self._client.get_by_etag(
                self._client.parse_etag(response), search="tags"
            )
        etag = response["id2etag"]
        etag2 = list(etag.keys())  # Tag names are out of order
        labels = [x["name"] for x in obj]  # Tag names are in order
        items = [""] * len(obj)  # Create enough spots for the objects
        for tag in etag2:
            index = labels.index(tag)  # Object of the index is here
            actual_etag = etag[tag]  # Get the actual etag
            found = self._client.get_by_etag(actual_etag, search="tags")
            items[index] = found  # Place at the correct index
        if len(items) == 1:
            return items[0]
        return items

    def rename(self, old: str, new: str) -> dict:
        """Rename a tag.

        Arguments:
            old: Current label of the tag to be changed.
            new: Desired new label of the tag.

        Returns:
            The tag object with the updated label.

        Raises:
            TypeError: If `old` and `new` are not strings.
            ValueError: If the `old` tag label does not exist.
            ValueError: If the `new` tag label already exists.
            RuntimeError: If the renaming was unsuccessful.

        !!! example "Changing a Tag's Label"

            Pass in the current label of the tag, and the desired new label of the tag.

            ```python
            # Lets assume that we have a tag that already exists named "Movie"
            old_label = "Movie"
            new_label = "Movies"
            updated_tag = client.tag.rename(old_label, new_label)
            ```

            ??? success "Result"
                The updated tag object dictionary is returned.

                ```python
                {'name': 'movies', 'label': 'Movies', 'sortOrder': 0, 'sortType': 'project', 'color': '#134397', 'etag': 'qer1jygy'}
                ```

                **Before**

                ![image](https://user-images.githubusercontent.com/56806733/104661255-fcac0f00-567c-11eb-9f10-69af8b50e0b4.png)

                **After**

                ![image](https://user-images.githubusercontent.com/56806733/104661299-19e0dd80-567d-11eb-825f-758d83178295.png)

        """
        if not isinstance(old, str) or not isinstance(new, str):
            raise TypeError("Old and New Must Be Strings")
        old = old.lower()
        obj = self._client.get_by_fields(name=old, search="tags")
        if not obj:
            raise ValueError(f"Tag '{old}' Does Not Exist To Rename")
        temp_new = new.lower()
        found = self._client.get_by_fields(name=temp_new, search="tags")
        if found:
            raise ValueError(f"Name '{new}' Already Exists -> Cannot Duplicate Name")
        url = self._client.BASE_URL + "tag/rename"
        payload = {"name": obj["name"], "newName": new}
        self._client.http_put(
            url, json=payload, cookies=self._client.cookies, headers=self.headers
        )
        self._client.sync()
        new_obj = self._client.get_by_fields(name=temp_new, search="tags")
        return self._client.get_by_etag(new_obj["etag"], search="tags")

    def color(self, label: str, color: str) -> dict:
        """Change the color of a tag. For batch changing colors, see [update][managers.tags.TagsManager.update].

        Arguments:
            label: The label of the tag to be changed.
            color: The new desired hex color string.

        Returns:
            The updated tag dictionary object.

        Raises:
            TypeError: If `label` or `color` are not strings.
            ValueError: If the tag `label` does not exist.
            ValueError: If `color` is not a valid hex color string.
            RuntimeError: If changing the color was not successful.

        !!! example "Changing a Tag's Color"
            ```python
            # Lets assume that we have a tag named "Movies" that we want to change the color for.
            new_color = '#134397'
            movies_updated = client.tag.color('Movies', new_color)
            ```

            ??? success "Result"
                The updated tag dictionary object is returned.

                ```python
                {'name': 'movies', 'label': 'Movies', 'sortOrder': 0, 'sortType': 'project', 'color': '#134397', 'etag': 'wwb49yfr'}
                ```

                **Before**

                ![image](https://user-images.githubusercontent.com/56806733/104661749-0eda7d00-567e-11eb-836f-3a8851bcf9a5.png)

                **After**

                ![image](https://user-images.githubusercontent.com/56806733/104661860-55c87280-567e-11eb-93b5-054fa4f1104a.png)

        """
        if not isinstance(label, str) or not isinstance(color, str):
            raise TypeError("Label and Color Must Be Strings")
        label = label.lower()
        obj = self._client.get_by_fields(name=label, search="tags")
        if not obj:
            raise ValueError(f"Tag '{label}' Does Not Exist To Update")
        if not check_hex_color(color):
            raise ValueError(f"Hex Color String '{color}' Is Not Valid")
        obj["color"] = color  # Set the color
        url = self._client.BASE_URL + "batch/tag"
        payload = {"update": [obj]}
        response = self._client.http_post(
            url, json=payload, cookies=self._client.cookies, headers=self.headers
        )
        self._client.sync()
        return self._client.get_by_etag(response["id2etag"][obj["name"]])

    def sorting(self, label: str, sort: int) -> dict:
        """Change the sort type of a tag. For batch changing sort types, see [update][managers.tags.TagsManager.update].

        Arguments:
            label: The label of the tag to be changed.
            sort: The new sort type specified by an integer 0-3. See [sort dictionary](tags.md#sort-dictionary).

        Returns:
            The updated tag dictionary object.

        Raises:
            TypeError: If `label` is not a string or if `sort` is not an int.
            ValueError: If the tag `label` does not exist.
            RuntimeError: If the updating was unsuccessful.

        !!! example "Changing the Sort Type"

            ```python
            # Lets assume that we have a tag named "Movies" with the sort type "project"
            changed_sort_type = client.tag.sorting("Movies", 1)  # Sort by 'dueDate'
            ```

            ??? success "Result"
                The updated task dictionary object is returned.

                ```python
                {'name': 'movies', 'label': 'Movies', 'sortOrder': 0, 'sortType': 'dueDate', 'color': '#134397', 'etag': 'fflj8iy0'}
                ```

                **Before**

                ![image](https://user-images.githubusercontent.com/56806733/104663625-3f241a80-5682-11eb-93a7-73d280c59b3e.png)

                **After**

                ![image](https://user-images.githubusercontent.com/56806733/104663663-5531db00-5682-11eb-9440-5673a70840b4.png)

        """
        if not isinstance(label, str) or not isinstance(sort, int):
            raise TypeError("Label Must Be A String and Sort Must Be An Int")
        label = label.lower()
        obj = self._client.get_by_fields(name=label, search="tags")
        if not obj:
            raise ValueError(f"Tag '{label}' Does Not Exist To Update")
        sort = self._sort_string_value(sort)  # Get the sort string for the value
        obj["sortType"] = sort  # set the object field
        url = self._client.BASE_URL + "batch/tag"
        payload = {"update": [obj]}
        response = self._client.http_post(
            url, json=payload, cookies=self._client.cookies, headers=self.headers
        )
        self._client.sync()
        return self._client.get_by_etag(response["id2etag"][obj["name"]])

    def nesting(self, child: str, parent: str) -> dict:
        """Update tag nesting.

        Move an already created tag to be nested underneath a parent tag - or ungroup an already
        nested tag.

        !!! warning "Nesting Tags More Than One Level Does Not Work"
            !!! example

                === "Nesting Explanation"
                    ```md
                    Parent Tag -> Level Zero
                        Child Tag 1 -> Level One: This is the most nesting that is allowed by TickTick for tags.
                            Child Tag 2 -> Level Two: Not allowed
                    ```

        Arguments:
            child: Label of the tag to become the child
            parent: Label of the tag that will become the parent.

        Returns:
            The updated tag object dictionary.

        Raises:
            TypeError: If `child` and `parent` are not strings
            ValueError: If `child` does not exist to update.
            ValueError: If `parent` does not exist.
            RuntimeError: If setting the parent was unsuccessful.

        !!! example "Nesting"

            === "Nesting A Tag"
                To nest a tag underneath another tag, pass in the labels of the child and parent.

                ```python
                # Lets assume that we have a tag named "Movies"
                # We have another tag named "Hobbies" that we want to make the parent to "Movies"
                child = "Movies"
                parent = "Hobbies"
                nesting_update = client.tag.nesting(child, parent)
                ```

                ??? success "Result"
                    The updated child tag dictionary object is returned.

                    ```python
                    {'name': 'movies', 'label': 'Movies', 'sortOrder': 0, 'sortType': 'dueDate', 'color': '#134397', 'etag': 'ee34aft9', 'parent': 'hobbies'}
                    ```

                    **Before**

                    ![image](https://user-images.githubusercontent.com/56806733/104665300-da6abf00-5685-11eb-947f-889187cec008.png)

                    **After**

                    ![image](https://user-images.githubusercontent.com/56806733/104665366-f706f700-5685-11eb-93eb-9316befec5fc.png)

            === "Changing The Parent Of An Already Nested Tag"
                If the tag is already nested, changing the parent is still no different.

                ```python
                # We have a tag named "Movies" that is already nested underneath "Hobbies"
                # We want to nest "Movies" underneath the tag "Fun" instead.
                child = "Movies"
                parent = "Fun"
                nesting_update = client.tag.nesting(child, parent)
                ```

                ??? success "Result"
                    The updated child tag dictionary object is returned.

                    ```python
                    {'name': 'movies', 'label': 'Movies', 'sortOrder': 0, 'sortType': 'dueDate', 'color': '#134397', 'etag': '91qpuq71', 'parent': 'fun'}
                    ```

                    **Before**

                    ![image](https://user-images.githubusercontent.com/56806733/104665599-ab088200-5686-11eb-8b36-5ee873289db7.png)

                    **After**

                    ![image](https://user-images.githubusercontent.com/56806733/104665821-35e97c80-5687-11eb-8098-426816970f3e.png)

            === "Un-grouping A Child Tag"
                If the tag is nested and you want to ungroup it, pass in `None` for `parent`.

                ```python
                # We have a tag named "Movies" that is nested underneath "Fun"
                # We don't want to have "Movies" nested anymore.
                child = "Movies"
                parent = None
                nesting_update = client.tag.nesting(child, parent)
                ```

                ??? success "Result"
                    The updated child tag dictionary object is returned.

                    ```python
                    {'name': 'movies', 'label': 'Movies', 'sortOrder': 0, 'sortType': 'dueDate', 'color': '#134397', 'etag': 'jcoc94p6'}
                    ```

                    **Before**

                    ![image](https://user-images.githubusercontent.com/56806733/104666038-be681d00-5687-11eb-8490-83c370977267.png)

                    **After**

                    ![image](https://user-images.githubusercontent.com/56806733/104666080-dcce1880-5687-11eb-9ca8-5abcdb4109ba.png)

        """
        if not isinstance(child, str):
            raise TypeError("Inputs Must Be Strings")
        if parent is not None:
            if not isinstance(parent, str):
                raise TypeError("Inputs Must Be Strings")
        child = child.lower()
        obj = self._client.get_by_fields(name=child, search="tags")
        if not obj:
            raise ValueError(f"Tag '{child}' Does Not Exist To Update")
        try:
            if obj["parent"]:
                if parent is not None:  # Case 3
                    if obj["parent"] == parent.lower():
                        return obj
                    new_p = parent.lower()
                    obj["parent"] = new_p
                else:
                    new_p = obj["parent"]  # Case 4
                    obj["parent"] = ""
            elif obj["parent"] is None:
                raise ValueError("Parent Does Not Exist")
        except KeyError:
            if parent is not None:  # Wants a different parent
                new_p = parent.lower()  # -> Case 1
                obj["parent"] = new_p
            else:  # Doesn't want a parent -> Case 2
                return obj  # We don't have to do anything if no parent and doesn't want a parent
        pobj = self._client.get_by_fields(name=new_p, search="tags")
        if not pobj:
            raise ValueError(f"Tag '{parent}' Does Not Exist To Set As Parent")
        url = self._client.BASE_URL + "batch/tag"
        payload = {"update": [pobj, obj]}
        response = self._client.http_post(
            url, json=payload, cookies=self._client.cookies, headers=self.headers
        )
        self._client.sync()
        return self._client.get_by_etag(response["id2etag"][obj["name"]], search="tags")

    def update(self, obj):
        """Update one or multiple tag objects.

        Supports single and batch tag update.

        !!! important
            Updating tag properties like `parent` and renaming tags must be completed through
            their respective class methods to work: [nesting][managers.tags.TagsManager.nesting]
            and [renaming][managers.tags.TagsManager.rename]. These updates use different
            endpoints to the traditional updating.

        !!! important
            You are able to batch update sorting and color of tag objects through this method. If you only
            need to update single tags, it is recommended you use the class methods: [sorting][managers.tags.TagsManager.sorting]
            and [color][managers.tags.TagsManager.color]

        !!! info
            More information on Tag Object properties [here](tags.md#example-ticktick-tag-dictionary)

        Arguments:
            obj (dict or list):
                **Single Tag (dict)**: The tag dictionary object to update.

                **Multiple Tags (list)**: The tag dictionaries to update in a list.

        Returns:
            dict or list:
            **Single Tag (dict)**: The updated tag dictionary object.

            **Multiple Tags (list)**: The updated tag dictionaries in a list.

        Raises:
            TypeError: If `obj` is not a dict or list.
            RuntimeError: If the updating was unsuccessful.

        !!! example "Updating Tags"
            === "Single Tag Update"
                Change a field directly in the task object then pass it to the method. See above
                for more information about what can actually be successfully changed through this method.

                ```python
                # Lets say we have a tag named "Fun" that we want to change the color of.
                # We can change the color by updating the field directly.
                fun_tag = client.get_by_fields(label='Fun', search='tags')  # Get the tag object
                new_color = '#d00000'
                fun_tag['color'] = new_color  # Change the color
                updated_fun_tag = client.tag.update(fun_tag)  # Pass the object to update.
                ```

                ??? success "Result"
                    The updated tag dictionary object is returned.

                    ```python
                    {'name': 'fun', 'label': 'Fun', 'sortOrder': 2199023255552, 'sortType': 'project', 'color': '#d00000', 'etag': 'i85c8ijo'}
                    ```

                    **Before**

                    ![image](https://user-images.githubusercontent.com/56806733/104669635-4aca0e00-568f-11eb-8bc6-9572a432b623.png)

                    **After**

                    ![image](https://user-images.githubusercontent.com/56806733/104669824-ac8a7800-568f-11eb-93d6-ac40235bcd3f.png)

            === "Multiple Tag Update"
                Changing the fields is the same as with updating a single tag, except you will need
                to pass the objects in a list to the method.

                ```python
                # Lets update the colors for three tags: "Fun", "Hobbies", and "Productivity"
                fun_tag = client.get_by_fields(label="Fun", search='tags')
                hobbies_tag = client.get_by_fields(label="Hobbies", search='tags')
                productivity_tag = client.get_by_fields(label="Productivity", search='tags')
                fun_color_new = "#951a63"
                hobbies_color_new = "#0f8a1f"
                productivity_color_new = "#493293"
                # Change the fields directly
                fun_tag['color'] = fun_color_new
                hobbies_tag['color'] = hobbies_color_new
                productivity_tag['color'] = productivity_color_new
                # The objects must be passed in a list
                update_tag_list = [fun_tag, hobbies_tag, productivity_tag]
                updated_tags = client.tag.update(update_tag_list)
                ```

                ??? success "Result"
                    The updated task dictionary objects are returned in a list.

                    ```python
                    [{'name': 'fun', 'label': 'Fun', 'sortOrder': -1099511627776, 'sortType': 'project', 'color': '#951a63', 'etag': 'n543ajq2'},

                    {'name': 'hobbies', 'label': 'Hobbies', 'sortOrder': -549755813888, 'sortType': 'project', 'color': '#0f8a1f', 'etag': 'j4nspkg4'},

                    {'name': 'productivity', 'label': 'Productivity', 'sortOrder': 0, 'sortType': 'project', 'color': '#493293', 'etag': '34qz9bzq'}]
                    ```

                    **Before**

                    ![image](https://user-images.githubusercontent.com/56806733/104670498-cd070200-5690-11eb-9fdd-0287fa6c7e7b.png)

                    **After**

                    ![image](https://user-images.githubusercontent.com/56806733/104670531-dc864b00-5690-11eb-844a-899031335922.png)

        """
        batch = False  # Bool signifying batch create or not
        if isinstance(obj, list):
            # Batch tag creation triggered
            obj_list = obj  # Assuming all correct objects
            batch = True
        elif not isinstance(obj, dict):
            raise TypeError(
                "Required Positional Argument Must Be A Dict or List of Tag Objects"
            )
        if not batch:
            obj_list = [obj]
        url = self._client.BASE_URL + "batch/tag"
        payload = {"update": obj_list}
        response = self._client.http_post(
            url, json=payload, cookies=self._client.cookies, headers=self.headers
        )
        self._client.sync()
        if not batch:
            return self._client.get_by_etag(
                self._client.parse_etag(response), search="tags"
            )
        etag = response["id2etag"]
        etag2 = list(etag.keys())  # Tag names are out of order
        labels = [x["name"] for x in obj_list]  # Tag names are in order
        items = [""] * len(obj_list)  # Create enough spots for the objects
        for tag in etag2:
            index = labels.index(tag)  # Object of the index is here
            actual_etag = etag[tag]  # Get the actual etag
            found = self._client.get_by_etag(actual_etag, search="tags")
            items[index] = found  # Place at the correct index
        return items

    def merge(self, label, merged: str):
        """Merge the tasks of the passed tags into the argument `merged` and deletes all the tags except `merged`.

        Args can be individual label strings, or a list of strings

        Arguments:
            label (str or list):
                **Single Tag (str)**: The label string of the tag to merge.

                **Multiple Tags (list)**: The label strings of the tags to merge in a list.
            merged: The label of the tag that will remain after the merge.

        Returns:
            dict: The tag dictionary object that remains after the merge.

        Raises:
            TypeError: If `merged` is not a str or if `label` is not a str or list.
            ValueError: If any of the labels do not exist.
            RuntimeError: If the merge could not be successfully completed.

        !!! example "Merging Tags"
            === "Merging Two Tags"
                Merging two tags requires the label of the tag that you want kept after the merge, and the
                label of the tag that will be merged.

                Lets assume that we have two tags: "Work" and "School". I want to merge the tag "School"
                into "Work". What should happen is that any tasks that are tagged "School", will be updated
                to have the tag "Work", and the "School" tag will be deleted.

                ```python
                merged_tags = client.tag.merge("School", "Work")
                ```

                ??? success "Result"
                    The tag that remains after the merge is returned.

                    ```python
                    {'name': 'work', 'label': 'Work', 'sortOrder': 2199023255552, 'sortType': 'project', 'color': '#3876E4', 'etag': 'eeh8zrup'}
                    ```

                    **Before**

                    "School" has two tasks that have it's tag.

                    ![image](https://user-images.githubusercontent.com/56806733/104680244-45c38980-56a4-11eb-968d-884160c77247.png)

                    "Work" has no tasks.

                    ![image](https://user-images.githubusercontent.com/56806733/104680366-90dd9c80-56a4-11eb-975f-5e769e9ea491.png)

                    **After**

                    "School" has been deleted. The tasks that used to be tagged with "School" are now
                    tagged with "Work".

                    ![image](https://user-images.githubusercontent.com/56806733/104680576-0c3f4e00-56a5-11eb-9536-ef3a7fcf20ec.png)

            === "Merging Three Or More Tags"
                Merging multiple tags into a single tag requires passing the labels of the tags to merge in a list.

                Lets assume that we have three tags: "Work", "School", and "Hobbies" . I want to merge the tag "School"
                and the tag "Hobbies" into "Work". What should happen is that any tasks that are tagged with "School" or "Hobbies", will be updated
                to have the tag "Work", and the "School" and "Hobbies" tags will be deleted.

                ```python
                merge_tags = ["School", "Hobbies"]
                result = client.tag.merge(merge_tags, "Work")
                ```

                ??? success "Result"
                    The tag that remains after the merge is returned.

                    ```python
                    {'name': 'work', 'label': 'Work', 'sortOrder': 2199023255552, 'sortType': 'project', 'color': '#3876E4', 'etag': 'ke23lp06'}
                    ```

                    **Before**

                    "School" has two tasks.

                    ![image](https://user-images.githubusercontent.com/56806733/104681135-7ad0db80-56a6-11eb-81dd-03e4a151cfd9.png)

                    "Hobbies" has two tasks.

                    ![image](https://user-images.githubusercontent.com/56806733/104681104-67257500-56a6-11eb-99b0-57bbb876a59e.png)

                    "Work" has one task.

                    ![image](https://user-images.githubusercontent.com/56806733/104681164-89b78e00-56a6-11eb-99a8-c85ef418d2a0.png)

                    **After**

                    "Work" has five tasks now, and the tags "School" and "Hobbies" have been deleted.

                    ![image](https://user-images.githubusercontent.com/56806733/104681239-b7043c00-56a6-11eb-9b45-5522b9c69cb0.png)

        """
        if not isinstance(merged, str):
            raise TypeError("Merged Must Be A String")
        if not isinstance(label, str) and not isinstance(label, list):
            raise TypeError("Label must be a string or a list.")
        merged = merged.lower()
        kept_obj = self._client.get_by_fields(name=merged, search="tags")
        if not kept_obj:
            raise ValueError(f"Kept Tag '{merged}' Does Not Exist To Merge")
        merge_queue = []
        if isinstance(label, str):
            string = label.lower()
            retrieved = self._client.get_by_fields(name=string, search="tags")
            if not retrieved:
                raise ValueError(f"Tag '{label}' Does Not Exist To Merge")
            merge_queue.append(retrieved)
        else:
            for item in label:  # Loop through the items in the list and check items are a string and exist
                if not isinstance(item, str):
                    raise TypeError(f"Item '{item}' Must Be A String")
                string = item.lower()
                found = self._client.get_by_fields(name=string, search="tags")
                if not found:
                    raise ValueError(f"Tag '{item}' Does Not Exist To Merge")
                merge_queue.append(found)
        for labels in merge_queue:
            url = self._client.BASE_URL + "tag/merge"
            payload = {"name": labels["name"], "newName": kept_obj["name"]}
            self._client.http_put(
                url, json=payload, cookies=self._client.cookies, headers=self.headers
            )
        self._client.sync()
        return kept_obj

    def delete(self, label):
        """Delete tag(s). Supports single tag deletion and "mock" batch tag deletion.

        !!! info
            Batch deleting for tags is not supported by TickTick. However, passing in
            a list of labels to delete will "mock" batch deleting - but individual requests
            will have to be made for each deletion.

        Arguments:
            label (str or list):
                **Single Tag (str)**: The label of the tag.

                **Multiple Tags (list)**: A list of tag label strings.

        Returns:
            dict or list:
            **Single Tag (dict)**: The dictionary object of the deleted tag.

            **Multiple Tags (list)**: The dictionary objects of the deleted tags in a list.

        Raises:
            TypeError: If `label` is not a string or list.
            ValueError: If a label does not exist.
            RuntimeError: If the tag could not be deleted successfully.

        !!! example "Tag Deletion"
            === "Single Tag Deletion"
                Deleting a single tag requires passing in the label string of the tag.

                ```python
                # Lets delete a tag named "Fun"
                delete_tag = client.tag.delete("Fun")
                ```

                ??? success "Result"
                    The dictionary object of the deleted tag returned.

                    ```python
                    {'name': 'fun', 'label': 'Fun', 'sortOrder': -3298534883328, 'sortType': 'project', 'color': '#A9949E', 'etag': '32balm5l'}
                    ```

                    **Before**

                    "Fun" Tag Exists

                    ![image](https://user-images.githubusercontent.com/56806733/104668024-2c164800-568c-11eb-853e-5b7eba1f4528.png)

                    **After**

                    "Fun" Tag Does Not Exist

                    ![image](https://user-images.githubusercontent.com/56806733/104667768-ac887900-568b-11eb-9bfb-597c752e4c3b.png)

            === "Multiple Tag Deletion"
                Deleting multiple tags requires passing the label strings of the tags in a list.

                ```python
                # Lets delete tags named "Fun", "Movies", and "Hobbies"
                delete_labels = ["Fun", "Movies", "Hobbies"]
                deleted_tags = client.tag.delete(delete_labels)
                ```

                ??? success "Result"

                    The dictionary object of the deleted tags returned in a list.

                    ```python
                    [{'name': 'fun', 'label': 'Fun', 'sortOrder': -3848290697216, 'sortType': 'project', 'color': '#FFD966', 'etag': '56aa6dva'},

                    {'name': 'movies', 'label': 'Movies', 'sortOrder': -2748779069440, 'sortType': 'dueDate', 'color': '#134397', 'etag': 's0czro3e'},

                    {'name': 'hobbies', 'label': 'Hobbies', 'sortOrder': -2199023255552, 'sortType': 'project', 'color': '#ABA6B5', 'etag': 'shu2xbvq'}]
                    ```

                    **Before**

                    All three tags exist.

                    ![image](https://user-images.githubusercontent.com/56806733/104668135-61bb3100-568c-11eb-8707-314deb42cd1d.png)

                    **After**

                    All three tags don't exist.

                    ![image](https://user-images.githubusercontent.com/56806733/104668185-7b5c7880-568c-11eb-8da0-aaee68d53500.png)

        """
        if not isinstance(label, str) and not isinstance(label, list):
            raise TypeError("Label Must Be A String or List Of Strings")
        url = self._client.BASE_URL + "tag"
        if isinstance(label, str):
            label = [label]  # If a singular string we are going to add it to a list
        objects = []
        for lbl in label:
            if not isinstance(lbl, str):
                raise TypeError(f"'{lbl}' Must Be A String")
            lbl = lbl.lower()
            tag_obj = self._client.get_by_fields(
                name=lbl, search="tags"
            )  # Get the tag object
            if not tag_obj:
                raise ValueError(f"Tag '{lbl}' Does Not Exist To Delete")
            params = {"name": tag_obj["name"]}
            self._client.http_delete(
                url, params=params, cookies=self._client.cookies, headers=self.headers
            )
            objects.append(
                self._client.delete_from_local_state(
                    search="tags", etag=tag_obj["etag"]
                )
            )
        self._client.sync()
        if len(objects) == 1:
            return objects[0]
        return objects


class SettingsManager:
    """Class for managing user settings."""

    def __init__(self, client_class) -> None:
        """Initialize the SettingsManager class."""
        self._client = client_class
        self.access_token = ""

    def get_templates(self):
        """Get the available templates for the user."""
        # https://api.ticktick.com/api/v2/templates

    def get_user_settings(self):
        """Get the user settings."""
        # https://api.ticktick.com/api/v2/user/preferences/settings?includeWeb=true


def logged_in(func):
    """Ensure the instance is still logged in before a function call."""

    @wraps(func)
    def call(self, *args, **kwargs):
        if not self.oauth_access_token:
            raise RuntimeError("ERROR -> Not Logged In")
        return func(self, *args, **kwargs)

    return call


def generate_hex_color() -> str:
    """Generate a random hexadecimal color string to be used for rgb color schemes.

    Returns:
        '#' followed by 6 hexadecimal digits.

    ??? info "Import Help"
        ```python
        from ticktick.helpers.hex_color import generate_hex_color
        ```

    """
    num = random.randint(1118481, 16777215)
    hex_num = format(num, "x")
    return "#" + hex_num


def check_hex_color(color: str) -> bool:
    """Verify if the passed in color string is a valid hexadecimal color string.

    Arguments:
        color: String to check.

    Returns:
        True if the string is a valid hex code, else False.

    ??? info "Import Help"
        ```python
        from ticktick.helpers.hex_color import check_hex_color
        ```

    """
    check_color = re.search(VALID_HEX_VALUES, color)
    if not check_color:
        return False
    return True


class ProjectManager:
    """Handle all interactions for projects."""

    def __init__(self, client_class) -> None:
        """Initialize the ProjectManager class."""
        self._client = client_class
        self.access_token = self._client.access_token
        self.headers = self._client.HEADERS

    def builder(
        self,
        name: str,
        color: str = "random",
        project_type: str = "TASK",
        folder_id: str | None = None,
    ) -> dict:
        """Create and returns a local project object.

        Helper method for [create][managers.projects.ProjectManager.create]
        to make batch creating projects easier.

        !!! note
            The project [folder][managers.projects.ProjectManager.create_folder] must already exist prior to calling this method.

        Arguments:
            name: Desired name of the project - project names cannot be repeated
            color: Hex color string. A random color will be generated if no color is specified.
            project_type: 'TASK' or 'NOTE'
            folder_id: The project folder id that the project should be placed under (if desired)

        Returns:
            A dictionary containing all the fields necessary to create a remote project.

        Raises:
            TypeError: If any of the types of the arguments are wrong.
            ValueError: Project name already exists
            ValueError: Project Folder corresponding to the ID does not exist.
            ValueError: The hex string color inputted is invalid.

        Argument rules are shared with [create][managers.projects.ProjectManager.create], so for more examples on how
        to use the arguments see that method.

        !!! example
            ```python
            project_name = 'Work'  # The name of our project

            # Lets assume that we have a project group folder that already exists named 'Productivity'
            productivity_folder = client.get_by_fields(name='Productivity', search='project_folders')
            productivity_id = productivity_folder['id']

            # Build the object
            project_object = client.project.builder(project_name, folder_id=productivity_id)
            ```

            ??? success "Result"
                ```python
                # The fields needed for a successful project creation are set.
                {'name': 'Work', 'color': '#665122', 'kind': 'TASK', 'groupId': '5ffe11b7b04b356ce74d49da'}
                ```

        """
        if not isinstance(name, str):
            raise TypeError("Name must be a string")
        if not isinstance(color, str) and color is not None:
            raise TypeError("Color must be a string")
        if not isinstance(project_type, str):
            raise TypeError("Project type must be a string")
        if not isinstance(folder_id, str) and folder_id is not None:
            raise TypeError("Folder id must be a string")
        id_list = self._client.get_by_fields(search="projects", name=name)
        if id_list:
            raise ValueError(f"Invalid Project Name '{name}' -> It Already Exists")
        if folder_id is not None:
            parent = self._client.get_by_id(folder_id, search="project_folders")
            if not parent:
                raise ValueError(f"Parent Id {folder_id} Does Not Exist")
        if project_type not in ("TASK", "NOTE"):
            raise ValueError(
                f"Invalid Project Type '{project_type}' -> Should be 'TASK' or 'NOTE'"
            )
        if color == "random":
            color = generate_hex_color()  # Random color will be generated
        elif color is not None:
            if not check_hex_color(color):
                raise ValueError("Invalid Hex Color String")
        return {
            "name": name,
            "color": color,
            "kind": project_type,
            "groupId": folder_id,
        }

    def create(
        self,
        name,
        color: str = "random",
        project_type: str = "TASK",
        folder_id: str | None = None,
    ):
        """Create a project remotely.

        Supports single project creation or batch project creation.

        Arguments:
            name (str or list):
                **Single Project** (str) : The desired name of the project. Project names cannot be repeated.

                **Multiple Projects** (list) : A list of project objects created using the [builder][managers.projects.ProjectManager.builder] method.
            color: Hex color string. A random color will be generated if no color is specified.
            project_type: 'TASK' or 'NOTE'
            folder_id: The project folder id that the project should be placed under (if desired)

        Returns:
            dict or list: **Single Project**: Return the dictionary of the object.

            **Multiple Projects**: Return a list of dictionaries containing all the created objects in the same order as created.

        Raises:
            TypeError: If any of the types of the arguments are wrong.
            ValueError: Project name already exists
            ValueError: Project Folder corresponding to the ID does not exist.
            ValueError: The hex string color inputted is invalid.
            RuntimeError: The project(s) could not be created.

        !!! example "Single Project"

            === "Just A Name"
                ```python
                project = client.project.create('School')
                ```

                ??? success "Result"
                    ```python
                    # The dictionary object of the created project is returned.
                    {'id': '5ffe1673e4b062d60dd29dc0', 'name': 'School', 'isOwner': True, 'color': '#51b9e3', 'inAll': True,
                    'sortOrder': 0, 'sortType': None, 'userCount': 1, 'etag': 'uerkdkcd',
                    'modifiedTime': '2021-01-12T21:36:51.890+0000', 'closed': None, 'muted': False,
                    'transferred': None, 'groupId': None, 'viewMode': None, 'notificationOptions': None,
                    'teamId': None, 'permission': None, 'kind': 'TASK'}
                    ```
                    Our project is created.

                    [![project-create.png](https://i.postimg.cc/d1NNqN7F/project-create.png)](https://postimg.cc/PpZQy4zV)

            === "Specify a Color"
                A random color can be generated using [generate_hex_color][helpers.hex_color.generate_hex_color].
                However, just not specifying a color will automatically generate a random color (as seen in the previous tab).
                You can always specify the color that you want.

                ```python
                project = client.project.create('Work', color='#86bb6d')
                ```

                ??? success "Result"
                    Our project is created with the color specified.

                    [![project-color.png](https://i.postimg.cc/K8ppnvrb/project-color.png)](https://postimg.cc/5XvmJJRK)

            === "Changing the Project Type"
                The default project type is for Tasks. To change the type to handle Notes, pass in the string 'NOTE'

                ```python
                project = client.project.create('Hobbies', project_type='NOTE')
                ```

                ??? success "Result"
                    The project type is now for notes.

                    [![project-note.png](https://i.postimg.cc/fy0Mhrzt/project-note.png)](https://postimg.cc/rRcB1gtM)

            === "Creating Inside of A Folder"
                !!! warning "Note For `folder_id`"
                    The project [folder][managers.projects.ProjectManager.create_folder] must already exist prior to calling this method.

                ```python
                project_name = 'Day Job'  # The name of our project

                # Lets assume that we have a project group folder that already exists named 'Productivity'
                productivity_folder = client.get_by_fields(name='Productivity', search='project_folders')
                productivity_id = productivity_folder['id']

                # Create the object
                project_object = client.project.create(project_name, folder_id=productivity_id)
                ```

                ??? success "Result"
                    The project was created in the group folder.

                    [![project-create-with-folder.png](https://i.postimg.cc/mr53rmfN/project-create-with-folder.png)](https://postimg.cc/rd5RnCpK)

        !!! example "Multiple Projects (batch)"
            To create multiple projects, you will need to build the projects locally prior to calling the `create` method. This
            can be accomplished using the [builder][managers.projects.ProjectManager.builder] method. Pass in a list of the locally created
            project objects to create them remotely.

            !!! warning "(Again About Folders)"
                The project folders should already be created prior to calling the create method.

            ```python
            # Lets assume that we have a project group folder that already exists named 'Productivity'
            productivity_folder = client.get_by_fields(name='Productivity', search='project_folders')
            productivity_id = productivity_folder['id']
            # Names of our projects
            name_1 = 'Reading'
            name_2 = 'Writing'
            # Build the local projects
            project1 = client.project.builder(name_1, folder_id=productivity_id)
            project2 = client.project.builder(name_2, folder_id=productivity_id)
            project_list = [project1, project2]
            # Create the projects
            project_object = client.project.create(project_list)
            ```

            ??? success "Result"
                When multiple projects are created, the dictionaries will be returned in a list in the same order as
                the input.

                ```python
                [{'id': '5ffe24a18f081003f3294c44', 'name': 'Reading', 'isOwner': True, 'color': '#6fcbdf',
                'inAll': True, 'sortOrder': 0, 'sortType': None, 'userCount': 1, 'etag': 'qbj4z0gl',
                'modifiedTime': '2021-01-12T22:37:21.823+0000', 'closed': None, 'muted': False, 'transferred': None,
                'groupId': '5ffe11b7b04b356ce74d49da', 'viewMode': None, 'notificationOptions': None, 'teamId': None,
                'permission': None, 'kind': 'TASK'},

                {'id': '5ffe24a18f081003f3294c46', 'name': 'Writing', 'isOwner': True,
                'color': '#9730ce', 'inAll': True, 'sortOrder': 0, 'sortType': None, 'userCount': 1, 'etag': 'u0loxz2v',
                'modifiedTime': '2021-01-12T22:37:21.827+0000', 'closed': None, 'muted': False, 'transferred': None,
                'groupId': '5ffe11b7b04b356ce74d49da', 'viewMode': None, 'notificationOptions': None, 'teamId': None,
                'permission': None, 'kind': 'TASK'}]
                ```
                [![project-batch-create.png](https://i.postimg.cc/8CHH8xSZ/project-batch-create.png)](https://postimg.cc/d7hdrHDC)

        """
        if isinstance(name, list):
            obj = name
            # batch = True
        elif isinstance(name, str):
            # batch = False
            obj = self.builder(
                name=name, color=color, project_type=project_type, folder_id=folder_id
            )
            obj = [obj]
        else:
            raise TypeError(
                "Required Positional Argument Must Be A String or List of Project Objects"
            )
        url = self._client.BASE_URL + "batch/project"
        payload = {"add": obj}
        response = self._client.http_post(
            url, json=payload, cookies=self._client.cookies, headers=self.headers
        )
        self._client.sync()
        if len(obj) == 1:
            return self._client.get_by_id(
                self._client.parse_id(response), search="projects"
            )
        etag = response["id2etag"]
        etag2 = list(etag.keys())  # Get the ids
        items = [""] * len(obj)  # Create enough spots for the objects
        for proj_id in etag2:
            found = self._client.get_by_id(proj_id, search="projects")
            for original in obj:
                if found["name"] == original["name"]:
                    # Get the index of original
                    index = obj.index(original)
                    # Place found at the index in return list
                    items[index] = found
        return items

    def update(self, obj):
        """Update the passed project(s).

        Supports single project update and multiple project update (batch)

        Make local changes to the project objects that you want to change first, then pass the actual objects to the method.

        !!! info
            Every potential update to a project's attributes have not been tested. See [Example `TickTick` Project Dictionary](projects.md#example-ticktick-project-dictionary) for
            a listing of the fields present in a project.

        Arguments:
            obj (dict or list):
                **Single Project (dict)**: The project dictionary.

                **Multiple Projects (list)**: A list of project dictionaries.

        Returns:
            dict or list:
            **Single Project (dict)**: The updated project dictionary

            **Multiple Projects (list)**: A list containing the updated project dictionaries.

        Raises:
            TypeError: If the input is not a dict or a list.
            RuntimeError: If the projects could not be updated successfully.

        Updates are done by changing the fields in the objects locally first.

        !!! example "Single Project Update"

            === "Changing The Name"
                ```python
                # Lets assume that we have a project named "Reading" that we want to change to "Summer Reading"
                project = client.get_by_fields(name='Reading', search='projects')  # Get the project
                # Now lets change the name
                project['name'] = 'Summer Reading'
                # Updating a single project requires just passing in the entire dictionary.
                updated = client.project.update(project)
                ```

                ??? success "Result"
                    The dictionary is returned and the name changed remotely.
                    ```python
                    {'id': '5ffe24a18f081003f3294c44', 'name': 'Summer Reading', 'isOwner': True,
                    'color': '#6fcbdf', 'inAll': True, 'sortOrder': -6236426731520,
                    'sortType': 'sortOrder', 'userCount': 1, 'etag': '0vbsvn8e', 'modifiedTime': '2021-01-12T23:38:16.456+0000',
                    'closed': None, 'muted': False, 'transferred': None, 'groupId': '5ffe2d37b04b35082bbcdf74',
                    'viewMode': 'list', 'notificationOptions': None, 'teamId': None,
                    'permission': None, 'kind': 'TASK'}
                    ```
                    **Before**

                    [![project-update-before.png](https://i.postimg.cc/K8hcpzvP/project-update-before.png)](https://postimg.cc/crTNrd3C)

                    **After**

                    [![project-update-after.png](https://i.postimg.cc/DwcWqsdJ/project-update-after.png)](https://postimg.cc/FY7svY6N)

        !!! example "Multiple Project Update"

            === "Changing Multiple Names"

                ```python
                # Lets assume that we have a project named "Writing" that we want to change to "Summer Reading"
                project = client.get_by_fields(name='Writing', search='projects')  # Get the project
                project['name'] = 'Summer Writing'
                # Lets assume that we have a project named "Movies" that we want to change to "Summer Movies"
                movie_project = client.get_by_fields(name='Movies', search='projects')
                movie_project['name'] = 'Summer Movies'
                # Updating multiple projects requires passing the projects in a list.
                update_list = [project, movie_project]
                # Lets update remotely now
                updated_projects = client.project.update(update_list)
                ```

            ??? success "Result"
                A list containing the updated projects is returned.

                ```python
                [{'id': '5ffe24a18f081003f3294c46', 'name': 'Summer Reading',
                'isOwner': True, 'color': '#9730ce', 'inAll': True, 'sortOrder': 0,
                'sortType': None, 'userCount': 1, 'etag': 'bgl0pkm8',
                'modifiedTime': '2021-01-13T00:13:29.796+0000', 'closed': None,
                'muted': False, 'transferred': None, 'groupId': '5ffe11b7b04b356ce74d49da',
                'viewMode': None, 'notificationOptions': None, 'teamId': None, 'permission': None,
                'kind': 'TASK'},

                {'id': '5ffe399c8f08237f3d144ece', 'name': 'Summer Movies', 'isOwner': True,
                'color': '#F18181', 'inAll': True, 'sortOrder': -2843335458816, 'sortType': 'sortOrder',
                'userCount': 1, 'etag': 'jmjy1xtc', 'modifiedTime': '2021-01-13T00:13:29.800+0000',
                'closed': None, 'muted': False, 'transferred': None, 'groupId': '5ffe11b7b04b356ce74d49da',
                'viewMode': None, 'notificationOptions': None, 'teamId': None, 'permission': None, 'kind': 'TASK'}]
                ```

                **Before**

                [![project-update-multiople.png](https://i.postimg.cc/9QbcJH81/project-update-multiople.png)](https://postimg.cc/zyLmG61R)

                **After**

                [![project-update-multiple-after.png](https://i.postimg.cc/3RVGNv2y/project-update-multiple-after.png)](https://postimg.cc/0MGjHrWx)

        """
        if not isinstance(obj, dict) and not isinstance(obj, list):
            raise TypeError("Project objects must be a dict or list of dicts.")
        if isinstance(obj, dict):
            tasks = [obj]
        else:
            tasks = obj
        url = self._client.BASE_URL + "batch/project"
        payload = {"update": tasks}
        response = self._client.http_post(
            url, json=payload, cookies=self._client.cookies, headers=self.headers
        )
        self._client.sync()
        if len(tasks) == 1:
            return self._client.get_by_id(
                self._client.parse_id(response), search="projects"
            )
        etag = response["id2etag"]
        etag2 = list(etag.keys())  # Get the ids
        items = [""] * len(obj)  # Create enough spots for the objects
        for proj_id in etag2:
            found = self._client.get_by_id(proj_id, search="projects")
            for original in obj:
                if found["name"] == original["name"]:
                    index = obj.index(original)
                    items[index] = found
        return items

    def delete(self, ids):
        """Delete the project(s) with the passed ID string.

        !!! warning
            [Tasks](tasks.md) will be deleted from the project. If you want to preserve the
            tasks before deletion, use [move_all][managers.tasks.TaskManager.move_all]

        Arguments:
            ids (str or list):
                **Single Deletion (str)**: ID string of the project

                **Multiple Deletions (list)**: List of ID strings of projects to be deleted.

        Returns:
            dict or list:
            **Single Deletion (dict)**: Dictionary of the deleted project.

            **Multiple Deletions (list)**: A list of dictionaries of the deleted projects.

        Raises:
            TypeError: If `ids` is not a string or list of strings
            ValueError: If `ids` does not exist.
            RuntimeError: If the deletion was not successful.

        !!! example

            === "Single Project Deletion"

                ```python
                # Lets assume that we have a project that exists named 'School'
                school = client.get_by_fields(name='School', search='projects')  # Get the project object
                project_id = school['id']  # Get the project id
                delete = client.project.delete(project_id)
                ```

                A dictionary of the deleted project object will be returned.

            === "Multiple Project Deletion"
                ```python
                # Lets assume that we have two projects that we want to delete: 'School' and 'Work'
                school = client.get_by_fields(name='School', search='projects')  # Get the project object
                work = client.get_by_fields(name='Work', search='projects')
                delete_ids = [school['id'], work['id']]  # A list of the ID strings of the projects to be deleted
                delete = client.project.delete(delete_ids)
                ```

                A list of the deleted dictionary objects will be returned.

        """
        if not isinstance(ids, str) and not isinstance(ids, list):
            raise TypeError("Ids Must Be A String or List Of Strings")
        if isinstance(ids, str):
            proj = self._client.get_by_fields(id=ids, search="projects")
            if not proj:
                raise ValueError(f"Project '{ids}' Does Not Exist To Delete")
            ids = [ids]
        else:
            for i in ids:
                proj = self._client.get_by_fields(id=i, search="projects")
                if not proj:
                    raise ValueError(f"Project '{i}' Does Not Exist To Delete")
        url = self._client.BASE_URL + "batch/project"
        payload = {"delete": ids}
        self._client.http_post(
            url, json=payload, cookies=self._client.cookies, headers=self.headers
        )
        deleted_list = []
        for current_id in ids:
            tasks = self._client.task.get_from_project(current_id)
            for task in tasks:
                self._client.delete_from_local_state(id=task["id"], search="tasks")
            deleted_list.append(
                self._client.delete_from_local_state(id=current_id, search="projects")
            )
        if len(deleted_list) == 1:
            return deleted_list[0]
        return deleted_list

    def archive(self, ids):
        """Move the project(s) to a project folder created by `TickTick` called "Archived Lists.

        To unarchive a project, change its `'closed'` field to `True`, then [update][managers.projects.ProjectManager.update]

        Arguments:
            ids (str or list):
                **Single Project (str)**: ID string of the project to archive.

                **Multiple Projects (list)**: List of ID strings of the projects to archive.

        Returns:
            dict or list:

            **Single Project (dict)**: Dictionary of the archived object.

            **Multiple Projects (list)**: List of dictionaries of the archived objects.

        Raises:
            TypeError: If `ids` is not a string or list.
            ValueError: If the project(s) don't already exist
            RuntimeError: If the project(s) could not be successfully archived.

        !!! example
            === "Single Project Archive"
                ```python
                # Lets assume there is a project that exists named "Reading"
                reading_project = client.get_by_fields(name="Reading", search="projects")
                reading_project_id = reading_project['id']
                archived = client.project.archive(reading_project_id)
                ```

                ??? success "Result"
                    A single dictionary is returned.
                    ```python
                    {'id': '5ffe1673e4b062d60dd29dc0', 'name': 'Reading', 'isOwner': True, 'color': '#51b9e3', 'inAll': True,
                    'sortOrder': 0, 'sortType': 'sortOrder', 'userCount': 1, 'etag': 'c9tgze9b',
                    'modifiedTime': '2021-01-13T00:34:50.449+0000', 'closed': True, 'muted': False,
                    'transferred': None, 'groupId': None, 'viewMode': None, 'notificationOptions': None,
                    'teamId': None, 'permission': None, 'kind': 'TASK'}
                    ```

                    **Before**

                    [![archive-before.png](https://i.postimg.cc/R0jfVt7W/archive-before.png)](https://postimg.cc/B8BtmXw3)

                    **After**

                    [![archived-after.png](https://i.postimg.cc/xjPkBh4J/archived-after.png)](https://postimg.cc/K4RvMqFx)

            === "Multiple Project Archive"
                ```python
                # Lets assume there is a project that exists named "Reading"
                reading_project = client.get_by_fields(name="Reading", search="projects")
                reading_project_id = reading_project['id']
                # Lets assume another project exists named "Writing"
                writing_project = client.get_by_fields(name='Writing', search='projects')
                writing_project_id = writing_project['id']
                # Archiving multiple requires putting the ID's in a list.
                archive_list = [reading_project_id, writing_project_id]
                archived = client.project.archive(archive_list)
                ```

                ??? success "Result"
                    A list of dictionary objects is returned.
                    ```python
                    [{'id': '5ffe1673e4b062d60dd29dc0', 'name': 'Reading', 'isOwner': True,
                    'color': '#51b9e3', 'inAll': True, 'sortOrder': -7335938359296,
                    'sortType': 'sortOrder', 'userCount': 1, 'etag': 'qrga45as',
                    'modifiedTime': '2021-01-13T00:40:49.839+0000', 'closed': True,
                    'muted': False, 'transferred': None, 'groupId': None, 'viewMode': None,
                    'notificationOptions': None, 'teamId': None, 'permission': None, 'kind': 'TASK'},

                    {'id': '5ffe41328f08237f3d147e33', 'name': 'Writing', 'isOwner': True,
                    'color': '#F2B04B', 'inAll': True, 'sortOrder': -7885694173184, 'sortType': 'sortOrder',
                    'userCount': 1, 'etag': 'aenkajam', 'modifiedTime': '2021-01-13T00:40:49.843+0000',
                    'closed': True, 'muted': False, 'transferred': None, 'groupId': None, 'viewMode': None,
                    'notificationOptions': None, 'teamId': None, 'permission': None, 'kind': 'TASK'}]
                    ```

                    **Before**

                    [![archive-multiple-before.png](https://i.postimg.cc/sgHHmnrb/archive-multiple-before.png)](https://postimg.cc/qNnGMxgG)

                    **After**

                    [![archived-multiple-after.png](https://i.postimg.cc/tg1SMhRJ/archived-multiple-after.png)](https://postimg.cc/rdkNdRr2)

        """
        if not isinstance(ids, str) and not isinstance(ids, list):
            raise TypeError("Ids Must Be A String or List Of Strings")
        objs = []
        if isinstance(ids, str):
            proj = self._client.get_by_fields(id=ids, search="projects")
            if not proj:
                raise ValueError(f"Project '{ids}' Does Not Exist To Archive")
            proj["closed"] = True
            objs = [proj]
        else:
            for i in ids:
                proj = self._client.get_by_fields(id=i, search="projects")
                if not proj:
                    raise ValueError(f"Project '{i}' Does Not Exist To Archive")
                proj["closed"] = True
                objs.append(proj)
        return self.update(objs)

    def create_folder(self, name):
        """Create a project folder to allow for project grouping.

        Project folder names can be repeated.

        Arguments:
            name (str or list):
                **Single Folder (str)**: A string for the name of the folder

                **Multiple Folders (list)**: A list of strings for names of the folders.

        Returns:
            dict or list:
            **Single Folder (dict)**: A dictionary for the created folder.

            **Multiple Folders (list)**: A list of dictionaries for the created folders.

        Raises:
            TypeError: If `name` is not a string or list
            RuntimeError: If the folder(s) could not be created.

        !!! example

            === "Creating a Single Folder"
                A single string for the name is the only parameter needed.

                ```python
                project_folder = client.project.create_folder('Productivity')
                ```

                ??? success "Result"
                    A single dictionary is returned.

                    ```python
                    {'id': '5ffe44528f089fb5795c45bf', 'etag': '9eun9kyc', 'name': 'Productivity', 'showAll': True,
                    'sortOrder': 0, 'deleted': 0, 'userId': 115781412, 'sortType': 'project', 'teamId': None}
                    ```

                    [![folder.png](https://i.postimg.cc/HWRTjtRW/folder.png)](https://postimg.cc/c6RpbfdP)



            === "Creating Multiple Folders"
                The desired names of the folders are passed to create as a list.

                ```python
                names = ['Productivity', 'School', 'Hobbies']
                project_folder = client.project.create_folder(names)
                ```


                ??? success "Result"
                    A list of dictionaries containing the foler objects is returned.

                    ```python
                    [{'id': '5ffe45d6e4b062d60dd3ce15', 'etag': '4nvnuiw1', 'name': 'Productivity',
                    'showAll': True, 'sortOrder': 0, 'deleted': 0, 'userId': 447666584, 'sortType': 'project',
                    'teamId': None},

                    {'id': '5ffe45d6e4b062d60dd3ce16', 'etag': 's072l3pu', 'name': 'School',
                    'showAll': True, 'sortOrder': 0, 'deleted': 0, 'userId': 447666584, 'sortType': 'project',
                    'teamId': None},

                    {'id': '5ffe45d6e4b062d60dd3ce17', 'etag': '12t1xmt9', 'name': 'Hobbies',
                    'showAll': True, 'sortOrder': 0, 'deleted': 0, 'userId': 447666584, 'sortType': 'project',
                    'teamId': None}]
                    ```

                    [![folders-multiple.png](https://i.postimg.cc/2jwXKjds/folders-multiple.png)](https://postimg.cc/0rzf6sBn)

        """
        if not isinstance(name, str) and not isinstance(name, list):
            raise TypeError("Name Must Be A String or List Of Strings")
        objs = []
        if isinstance(name, str):
            names = {"name": name, "listType": "group"}
            objs = [names]
        else:
            for nm in name:
                objs.append({"name": nm, "listType": "group"})
        url = self._client.BASE_URL + "batch/projectGroup"
        payload = {"add": objs}
        response = self._client.http_post(
            url, json=payload, cookies=self._client.cookies, headers=self.headers
        )
        self._client.sync()
        if len(objs) == 1:
            return self._client.get_by_id(
                self._client.parse_id(response), search="project_folders"
            )
        etag = response["id2etag"]
        etag2 = list(etag.keys())  # Get the ids
        items = [""] * len(objs)  # Create enough spots for the objects
        for proj_id in etag2:
            found = self._client.get_by_id(proj_id, search="project_folders")
            for original in objs:
                if found["name"] == original["name"]:
                    index = objs.index(original)
                    items[index] = found
        return items

    def update_folder(self, obj):
        """Update the project folders(s) remotely based off changes made locally.

        Make the changes you want to the project folder(s) first.

        Arguments:
            obj (dict or list):
                **Single Folder (dict)**: The dictionary object of the folder to update.

                **Multiple Folders (list)**: A list containing dictionary objects of folders to update.

        Returns:
            dict or list:
            **Single Folder (dict)**: The dictionary object of the updated folder.

            **Multiple Folders (list)**: A list of dictionary objects corresponding to the updated folders.

        Raises:
            TypeError: If `obj` is not a dictionary or list
            RuntimeError: If the updating was unsuccessful.

        !!! example "Updating A Project Folder"
            === "Single Folder Update"

                ```python
                # Lets assume that we have a folder called "Productivity"
                productivity_folder = client.get_by_fields(name='Productivity', search='project_folders')
                # Lets change the name to "Hobbies"
                productivity_folder['name'] = "Hobbies"
                # Update
                updated_folder = client.project.update_folder(productivity_folder)
                ```

                ??? success "Result"
                    The dictionary of the updated folder is returned.

                    ```python
                    {'id': '5ffe7dab8f089fb5795d8ef2', 'etag': 'r9xl60e5', 'name': 'Hobbies', 'showAll': True,
                    'sortOrder': 0, 'deleted': 0, 'userId': 447666584, 'sortType': 'project', 'teamId': None}
                    ```

                    **Before**

                    ![image](https://user-images.githubusercontent.com/56806733/104408388-c48bbb80-5518-11eb-80d4-34e82bbaffd7.png)

                    **After**

                    ![image](https://user-images.githubusercontent.com/56806733/104408436-e1c08a00-5518-11eb-953a-4933f407e4f9.png)

            === "Multiple Folder Update"

                ```python
                # Lets assume that we have a folder called "Productivity"
                productivity_folder = client.get_by_fields(name='Productivity', search='project_folders')
                # Lets assume that we have another folder called "Games"
                games_folder = client.get_by_fields(name='Games', search='project_folders')
                # Lets change the "Productivity" folder to "Work"
                productivity_folder['name'] = "Work"
                # Lets change the "Games" folder to "Hobbies"
                games_folder['name'] = "Hobbies"
                update_list = [productivity_folder, games_folder]  # List of objects to update
                # Update
                updated_folder = client.project.update_folder(update_list)
                ```

                ??? success "Result"
                    A list of the updated folder objects is returned.

                    ```python
                    [{'id': '5ffe80ce8f08068e86aab288', 'etag': '0oh0pxel', 'name': 'Work', 'showAll': True,
                    'sortOrder': 0, 'deleted': 0, 'userId': 447666584, 'sortType': 'project', 'teamId': None},

                    {'id': '5ffe80cf8f08068e86aab289', 'etag': 'xwvehtfo', 'name': 'Hobbies', 'showAll': True,
                    'sortOrder': 0, 'deleted': 0, 'userId': 447666584, 'sortType': 'project', 'teamId': None}]
                    ```

                    **Before**

                    ![image](https://user-images.githubusercontent.com/56806733/104409143-75468a80-551a-11eb-96c8-5953c97d6f6a.png)

                    **After**

                    ![image](https://user-images.githubusercontent.com/56806733/104409181-8bece180-551a-11eb-8424-9f147d85eb80.png)

        """
        if not isinstance(obj, dict) and not isinstance(obj, list):
            raise TypeError("Project objects must be a dict or list of dicts.")
        if isinstance(obj, dict):
            tasks = [obj]
        else:
            tasks = obj
        url = self._client.BASE_URL + "batch/projectGroup"
        payload = {"update": tasks}
        response = self._client.http_post(
            url, json=payload, cookies=self._client.cookies, headers=self.headers
        )
        self._client.sync()
        if len(tasks) == 1:
            return self._client.get_by_id(
                self._client.parse_id(response), search="project_folders"
            )
        etag = response["id2etag"]
        etag2 = list(etag.keys())  # Get the ids
        items = [""] * len(tasks)  # Create enough spots for the objects
        for proj_id in etag2:
            found = self._client.get_by_id(proj_id, search="project_folders")
            for original in tasks:
                if found["name"] == original["name"]:
                    index = tasks.index(original)
                    items[index] = found
        return items

    def delete_folder(self, ids):
        """Delete the folder(s).

        !!! tip
            Any projects inside of the folder will be preserved - they will just not be grouped anymore.

        Arguments:
            ids (str or list):
                **Single Folder (str)**: The ID of the folder to be deleted.

                **Multiple Folders (list)**: A list containing the ID strings of the folders to be deleted.

        Returns:
            dict or list:
            **Single Folder (dict)**: The dictionary object for the deleted folder.

            **Multiple Folders (list)**: A list of dictionary objects of the deleted folders.

        Raises:
            TypeError: If `ids` is not a str or list
            ValueError: If `ids` does not match an actual folder object.
            RunTimeError: If the folders could not be successfully deleted.

        !!! example "Folder Deletion"

            === "Single Folder Deletion"
                Pass in the ID of the folder object to delete it remotely.

                ```python
                # Lets assume we have a folder named "Productivity"
                project_folder = client.get_by_fields(name='Productivity', search='project_folders')  # Get the project folder
                deleted_folder = client.project.delete_folder(project_folder['id'])
                ```

                ??? success "Result"
                    The folder is deleted, and a single dictionary of the deleted folder object is returned.

                    ```python
                    {'id': '5ffe75008f089fb5795d544a', 'etag': 'e95rdzi7', 'name': 'Productivity',
                    'showAll': True, 'sortOrder': 0, 'deleted': 0, 'userId': 447666584,
                    'sortType': 'project', 'teamId': None}
                    ```

                    **Before**

                    ![image](https://user-images.githubusercontent.com/56806733/104407093-b5573e80-5515-11eb-99dc-16ca4f33d06a.png)

                    **After**

                    The project inside still exists.

                    ![image](https://user-images.githubusercontent.com/56806733/104407123-c607b480-5515-11eb-92ff-15df1d41b404.png)


            === "Multiple Folder Deletion"

                Pass in the list of ID strings of the folders to be deleted.

                ```python
                # Lets assume that we have two folders that already exist: "Productivity" and "Hobbies"
                productivity_folder = client.get_by_fields(name='Productivity', search='project_folders')
                hobbies_folder = client.get_by_fields(name='Hobbies', search='project_folders')
                ids = [productivity_folder['id'], hobbies_folder['id']]
                deleted_folders = client.project.delete_folder(ids)
                ```

                ??? success "Result"
                    The folders are deleted, and a list of dictionaries for the deleted folder objects are returned.

                    ```python
                    [{'id': '5ffe79d78f08237f3d1636ad', 'etag': '2o2dn2al', 'name': 'Productivity',
                    'showAll': True, 'sortOrder': 0, 'deleted': 0, 'userId': 447666584, 'sortType': 'project',
                    'teamId': None},

                    {'id': '5ffe79d78f08237f3d1636ae', 'etag': 'mah5a78l', 'name': 'Hobbies',
                    'showAll': True, 'sortOrder': 0, 'deleted': 0, 'userId': 447666584, 'sortType': 'project',
                    'teamId': None}]
                    ```

                    **Before**

                    ![image](https://user-images.githubusercontent.com/56806733/104407469-8097b700-5516-11eb-9919-069e5beb3b8a.png)

                    **After**

                    All folders deleted and all projects retained.

                    ![image](https://user-images.githubusercontent.com/56806733/104407546-a8871a80-5516-11eb-815b-4df41e3d797a.png)

        """
        if not isinstance(ids, str) and not isinstance(ids, list):
            raise TypeError("Ids Must Be A String or List Of Strings")
        if isinstance(ids, str):
            proj = self._client.get_by_fields(id=ids, search="project_folders")
            if not proj:
                raise ValueError(f"Project Folder '{ids}' Does Not Exist To Delete")
            ids = [ids]
        else:
            for i in ids:
                proj = self._client.get_by_fields(id=i, search="project_folders")
                if not proj:
                    raise ValueError(f"Project Folder '{i}' Does Not Exist To Delete")
        url = self._client.BASE_URL + "batch/projectGroup"
        payload = {"delete": ids}
        self._client.http_post(
            url, json=payload, cookies=self._client.cookies, headers=self.headers
        )
        deleted_list = [
            self._client.get_by_id(current_id, search="project_folders")
            for current_id in ids
        ]
        self._client.sync()
        if len(deleted_list) == 1:
            return deleted_list[0]
        return deleted_list


class FocusTimeManager:
    """The Focus Time Manager Class."""

    def __init__(self, client_class) -> None:
        """Initialize the Focus Time Manager."""

        self._client = client_class
        self.access_token = ""

    def start(self):
        """Start the focus timer."""


class HabitManager:
    """The Habit Manager Class."""

    def __init__(self, client_class) -> None:
        """Initialize the Habit Manager."""

        self._client = client_class
        self.access_token = ""

    def create(self):
        """Create a new habit."""

    def update(self):
        """Update a habit."""


class PomoManager:
    """The Pomo Manager Class."""

    def __init__(self, client_class) -> None:
        """Initialize the Pomo Manager."""

        self._client = client_class
        self.access_token = ""

    def start(self):
        """Start a Pomo."""

    def statistics(self):
        """Get Pomo statistics."""
        # https://api.ticktick.com/api/v2/statistics/general


class TickTickClient:
    """The Main Client Class for TickTick."""

    BASE_URL = "https://api.ticktick.com/api/v2/"
    OPEN_API_BASE_URL = "https://api.ticktick.com"
    INITIAL_BATCH_URL = BASE_URL + "batch/check/0"
    USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:123.0) Gecko/20100101 Firefox/123.0"
    X_DEVICE_ = (
        '{"platform":"web","os":"OS X","device":"Firefox 123.0","name":"unofficial api!","version":4531,'
        '"id":"6490'
        + secrets.token_hex(10)
        + '","channel":"website","campaign":"","websocket":""}'
    )
    HEADERS = {"User-Agent": USER_AGENT, "x-device": X_DEVICE_}

    def __init__(self, username: str, password: str, oauth: OAuth2) -> None:
        """Initialize a client session.

        In order to interact with the API
        a successful login must occur.

        Arguments:
            username: TickTick Username
            password: TickTick Password
            oauth: OAuth2 manager

        Raises:
            RunTimeError: If the login was not successful.

        """
        self.access_token = None
        self.cookies = {}
        self.time_zone = ""
        self.profile_id = ""
        self.inbox_id = ""
        self.state = {}
        self.reset_local_state()
        self.oauth_manager = oauth
        self._session = self.oauth_manager.session
        self._prepare_session(username, password)
        self.focus = FocusTimeManager(self)
        self.habit = HabitManager(self)
        self.project = ProjectManager(self)
        self.pomo = PomoManager(self)
        self.settings = SettingsManager(self)
        self.tag = TagsManager(self)
        self.task = TaskManager(self)

    def _prepare_session(self, username, password):
        self._login(username, password)
        self._settings()
        self.sync()

    def reset_local_state(self):
        """Reset the contents of the items in the [`state`](api.md#state) dictionary."""
        self.state = {
            "projects": [],
            "project_folders": [],
            "tags": [],
            "tasks": [],
            "user_settings": {},
            "profile": {},
        }

    def _login(self, username: str, password: str) -> None:
        """Log in to TickTick and sets the instance access token.

        Arguments:
            username: TickTick Username
            password: TickTick Password

        """
        url = self.BASE_URL + "user/signon?wc=true&remember=true"
        user_info = {"username": username, "password": password}
        parameters = {"wc": True, "remember": True}
        response = self.http_post(
            url, json=user_info, params=parameters, headers=self.HEADERS
        )
        self.access_token = response["token"]
        self.cookies["t"] = self.access_token

    @staticmethod
    def check_status_code(response, error_message: str) -> None:
        """Verify the http response was status code 200.

        Arguments:
            response (httpx): Httpx response
            error_message: Error message to be included with the exception

        Raises:
            RuntimeError: If the status code of the response was not 200.

        """
        if response.status_code != 200:
            raise RuntimeError(error_message)

    def _settings(self):
        """Set the time_zone and profile_id.

        Returns:
            The httpx response object.
        :return: httpx object containing the response from the get request

        """
        url = self.BASE_URL + "user/preferences/settings"
        parameters = {"includeWeb": True}
        response = self.http_get(
            url, params=parameters, cookies=self.cookies, headers=self.HEADERS
        )
        self.time_zone = response["timeZone"]
        self.profile_id = response["id"]
        return response

    def sync(self):
        """Populate the `TickTickClient` [`state`](api.md#state) dictionary with the contents of your account.

        **This method is called when necessary by other methods and does not need to be explicitly called.**

        Returns:
            httpx: The response from the get request.

        Raises:
            RunTimeError: If the request could not be completed.

        """
        response = self.http_get(
            self.INITIAL_BATCH_URL, cookies=self.cookies, headers=self.HEADERS
        )
        self.inbox_id = response["inboxId"]
        self.state["project_folders"] = response["projectGroups"]
        self.state["projects"] = response["projectProfiles"]
        self.state["tasks"] = response["syncTaskBean"]["update"]
        self.state["tags"] = response["tags"]
        return response

    def http_post(self, url, **kwargs):
        """Send an http post request with the specified url and keyword arguments.

        Arguments:
            url (str): Url to send the request.
            **kwargs: Arguments to send with the request.

        Returns:
            dict: The json parsed response if possible or just a string of the response text if not.

        Raises:
            RunTimeError: If the request could not be completed.

        """
        response = self._session.post(url, **kwargs)
        self.check_status_code(response, "Could Not Complete Request")
        try:
            return response.json()
        except ValueError:
            return response.text

    def http_get(self, url, **kwargs):
        """Send an http get request with the specified url and keyword arguments.

        Arguments:
            url (str): Url to send the request.
            **kwargs: Arguments to send with the request.

        Returns:
            dict: The json parsed response if possible or just a string of the response text if not.

        Raises:
            RunTimeError: If the request could not be completed.

        """
        response = self._session.get(url, **kwargs)
        self.check_status_code(response, "Could Not Complete Request")
        try:
            return response.json()
        except ValueError:
            return response.text

    def http_delete(self, url, **kwargs):
        """Send an http delete request with the specified url and keyword arguments.

        Arguments:
            url (str): Url to send the request.
            **kwargs: Arguments to send with the request.

        Returns:
            dict: The json parsed response if possible or just a string of the response text if not.

        Raises:
            RunTimeError: If the request could not be completed.

        """
        response = self._session.delete(url, **kwargs)
        self.check_status_code(response, "Could Not Complete Request")
        try:
            return response.json()
        except ValueError:
            return response.text

    def http_put(self, url, **kwargs):
        """Send an http put request with the specified url and keyword arguments.

        Arguments:
            url (str): Url to send the request.
            **kwargs: Arguments to send with the request.

        Returns:
            dict: The json parsed response if possible or just a string of the response text if not.

        Raises:
            RunTimeError: If the request could not be completed.

        """
        response = self._session.put(url, **kwargs)
        self.check_status_code(response, "Could Not Complete Request")
        try:
            return response.json()
        except ValueError:
            return response.text

    @staticmethod
    def parse_id(response: dict) -> str:
        """Parse the Id of a successful creation of a TickTick object.

        !!! info
            The response from the TickTick servers is in this form:

            ```md
            {'id2etag': {'5ff2bcf68f08093e5b745a30': '3okkc2xm'}, 'id2error': {}}
            ```
            We want to obtain '5ff2bcf68f08093e5b745a30' in this example - the id of the object.

        Arguments:
            response: Dictionary containing the Dd from the TickTick servers.

        Returns:
            Id string of the object.

        """
        id_tag = response["id2etag"]
        id_tag = list(id_tag.keys())
        return id_tag[0]

    @staticmethod
    def parse_etag(response: dict, multiple: bool = False) -> str:
        """Parse the etag of a successful creation of a tag object.

        !!! info
            The response from TickTick upon a successful tag creation is in this form:

            ```md
            {"id2etag":{"MyTag":"vxzpwo38"},"id2error":{}}
            ```
            We want to obtain "vxzpwo38" in this example - the etag of the object.

        Arguments:
            response: Dictionary from the successful creation of a tag object
            multiple: Specifies whether there are multiple etags to return.

        Return:
            A single etag string if not multiple, or a list of etag strings if multiple.

        """
        etag = response["id2etag"]
        etag2 = list(etag.keys())
        if not multiple:
            return etag[etag2[0]]
        return [etag[etag2[key]] for key in range(len(etag2))]

    def get_by_fields(self, search: str | None = None, **kwargs):
        """Find and return the objects in `state` that match the inputted fields.

        If search is specified, it will only search the specific [`state`](api.md#state) list,
        else the entire [`state`](api.md#state) dictionary will be searched.

        !!! example
            Since each TickTick object like tasks, projects, and tags are just dictionaries of fields,
            we can find an object by
            comparing any fields contained in those objects.

            For example: Lets say we have 3 task objects that are titled 'Hello', and we want to obtain all of them.

            The call to the function would look like this:

            ```python
            # Assumes that `client` is the name referencing the TickTickClient instance.

            found_objs = client.get_by_fields(title='Hello')
            ```
            `found_objs` would now reference a list containing the 3 objects with titles 'Hello'.

            Furthermore if we know the type of object we are looking for, we can make the search more efficient by
            specifying the key its located under in the [`state`](#state) dictionary.

            ```python
            # Assumes that `client` is the name referencing the TickTickClient instance.

            found_obj = client.get_by_fields(title='Hello', search='tasks')
            ```

            The search will now only look through `tasks` in [`state`](api.md#state).


        Arguments:
            search: Key in [`state`](api.md#state) that the search should take place in. If empty the
            entire [`state`](api.md#state) dictionary will be searched.
            **kwargs: Matching fields in the object to look for.

        Returns:
            dict or list:
            **Single Object (dict)**: The dictionary of the object.

            **Multiple Objects (list)**: A list of dictionary objects.

            **Nothing Found (list)**: Empty List

        Raises:
            ValueError: If no key word arguments are provided.
            KeyError: If the search key provided is not a key in `state`.

        """
        if not kwargs:
            raise ValueError("Must Include Field(s) To Be Searched For")
        if search is not None and search not in self.state:
            raise KeyError(f"'{search}' Is Not Present In self.state Dictionary")
        objects = []
        if search is not None:
            for index in self.state[search]:
                all_match = True
                for field in kwargs:
                    if kwargs[field] != index[field]:
                        all_match = False
                        break
                if all_match:
                    objects.append(index)
        else:
            for primarykey in self.state:
                skip_primary_key = False
                all_match = True
                middle_key = 0
                for middle_key in range(len(self.state[primarykey])):
                    if skip_primary_key:
                        break
                    for fields in kwargs:
                        if fields not in self.state[primarykey][middle_key]:
                            all_match = False
                            skip_primary_key = True
                            break
                        if kwargs[fields] == self.state[primarykey][middle_key][fields]:
                            all_match = True
                        else:
                            all_match = False
                    if all_match:
                        objects.append(self.state[primarykey][middle_key])
        if len(objects) == 1:
            return objects[0]
        return objects

    def get_by_id(self, obj_id: str, search: str | None = None) -> dict:
        """Return the dictionary of the object corresponding to the passed id.

        If search is specified, it will only search the specific [`state`](api.md#state) list, else the
        entire [`state`](api.md#state) dictionary will be searched.


        !!! example
            Since each TickTick object like tasks, projects, and tags are just dictionaries of fields,
            we can find an object by
            comparing the id fields.

            For example: Lets get the object that corresponds to an id referenced by `my_id`.

            The call to the function would look like this:

            ```python
            # Assumes that `client` is the name referencing the TickTickClient instance.

            found_obj = client.get_by_id(my_id)
            ```
            `found_obj` would now reference the object if it was found, else it would reference an empty dictionary.

            Furthermore if we know the type of object we are looking for, we can make the search more efficient by
            specifying the key its located under in the [`state`](api.md#state) dictionary.

            ```python
            # Assumes that `client` is the name referencing the TickTickClient instance.

            found_obj = client.get_by_id(my_id, search='projects')
            ```

            The search will now only look through `projects` in [`state`](api.md#state).

        Arguments:
            obj_id: Id of the item.
            search: Key in [`state`](api.md#state) that the search should take place in. If empty the
            entire [`state`](api.md#state) dictionary will be searched.

        Returns:
            The dictionary object of the item if found, or an empty dictionary if not found.

        Raises:
            KeyError: If the search key provided is not a key in [`state`](api.md#state).

        """
        if search is not None and search not in self.state:
            raise KeyError(f"'{search}' Is Not Present In self.state Dictionary")
        if search is not None:
            for index in self.state[search]:
                if index["id"] == obj_id:
                    return index
        else:
            for prim_key in self.state:
                for our_object in self.state[prim_key]:
                    if "id" not in our_object:
                        break
                    if our_object["id"] == obj_id:
                        return our_object
        return {}

    def get_by_etag(self, etag: str, search: str | None = None) -> dict:
        """Return the dictionary object of the item with the matching etag.

        If search is specified, it will only search the specific [`state`](api.md#state) list, else the
        entire [`state`](api.md#state) dictionary will be searched.

        !!! example
            Since each TickTick object like tasks, projects, and tags are just dictionaries of fields,
            we can find an object by
            comparing the etag fields.

            For example: Lets get the object that corresponds to an etag referenced by `my_etag`.

            The call to the function would look like this:

            ```python
            # Assumes that `client` is the name referencing the TickTickClient instance.

            found_obj = client.get_by_etag(my_etag)
            ```
            `found_obj` would now reference the object if it was found, else it would reference an empty dictionary.

            Furthermore if we know the type of object we are looking for, we can make the search more efficient by
            specifying the key its located under in the [`state`](api.md#state) dictionary.

            ```python
            # Assumes that `client` is the name referencing the TickTickClient instance.

            found_obj = client.get_by_etag(my_etag, search='projects')
            ```

            The search will now only look through `projects` in [`state`](api.md#state).

        Arguments:
            etag: The etag of the object that you are looking for.
            search: Key in [`state`](#state) that the search should take place in. If empty the
            entire [`state`](api.md#state) dictionary will be searched.

        Returns:
            The dictionary object of the item if found, or an empty dictionary if not found.

        Raises:
            KeyError: If the search key provided is not a key in [`state`](api.md#state).

        """
        if search is not None and search not in self.state:
            raise KeyError(f"'{search}' Is Not Present In self.state Dictionary")
        if search is not None:
            for index in self.state[search]:
                if index["etag"] == etag:
                    return index
        else:
            for prim_key in self.state:
                for our_object in self.state[prim_key]:
                    if "etag" not in our_object:
                        break
                    if our_object["etag"] == etag:
                        return our_object
        return {}

    def delete_from_local_state(self, search: str | None = None, **kwargs) -> dict:
        """Delete a single object from the local `state` dictionary.

        **Does not delete any items remotely.**

        If search is specified, it will only search the specific [`state`](api.md#state) list,
        else the entire [`state`](api.md#state) dictionary will be searched.

        !!! example
            Since each TickTick object like tasks, lists, and tags are just dictionaries of fields,
            we can find an object by
            comparing the fields.

            For example: Lets say that we wanted to find and delete an existing task object from our local state
            with the name 'Get Groceries'. To do this, we can specify the field(s) that we want to compare for in
            the task objects -> in this case the `title` 'Get Groceries'.

            The call to the function would look like this:

            ```python
            # Assumes that `client` is the name referencing the TickTickClient instance.

            deleted_task = client.delete_from_local_state(title='Get Groceries')
            ```
            `deleted_task` would now hold the object that was deleted from the [`state`](api.md#state)
            dictionary if it was found.

            Furthermore if we know the type of object we are looking for, we can make the search more efficient by
            specifying the key its located under in the [`state`](api.md#state) dictionary.

            ```python
            # Assumes that `client` is the name referencing the TickTickClient instance.

            deleted_task = client.delete_from_local_state(title='Get Groceries', search='tasks')
            ```

            The search will now only look through `tasks` in `state`.


        Arguments:
            search: A specific item to look through in the [`state`](api.md#state) dictionary. When not specified the
            entire [`state`](api.md#state) dictionary will be searched.
            **kwargs: Matching fields in the object to look for.

        Returns:
            The dictionary of the object that was deleted.

        Raises:
            ValueError: If no key word arguments are provided.
            KeyError: If the search key provided is not a key in [`state`](api.md#state).

        """
        if not kwargs:
            raise ValueError("Must Include Field(s) To Be Searched For")
        if search is not None and search not in self.state:
            raise KeyError(f"'{search}' Is Not Present In self.state Dictionary")
        if search is not None:
            for item in range(len(self.state[search])):
                all_match = True
                for field in kwargs:
                    if kwargs[field] != self.state[search][item][field]:
                        all_match = False
                        break
                if all_match:
                    deleted = self.state[search][item]
                    del self.state[search][item]
                    return deleted
        else:
            for primary_key in self.state:
                skip_primary_key = False
                all_match = True
                middle_key = 0
                for middle_key in range(len(self.state[primary_key])):
                    if skip_primary_key:
                        break
                    for fields in kwargs:
                        if fields not in self.state[primary_key][middle_key]:
                            all_match = False
                            skip_primary_key = True
                            break
                        if (
                            kwargs[fields]
                            == self.state[primary_key][middle_key][fields]
                        ):
                            all_match = True
                        else:
                            all_match = False
                    if all_match:
                        deleted = self.state[primary_key][middle_key]
                        del self.state[primary_key][middle_key]
                        return deleted


def _create_ticktick_client(email, password, client_id, client_secret, access_token):
    auth_client = OAuth2(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri="http://127.0.0.1:8080",
        access_token=access_token,
    )
    return TickTickClient(email, password, auth_client)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up TickTickMod from a config entry."""

    client_id = entry.data[CONF_CLIENT_ID]
    client_secret = entry.data[CONF_CLIENT_SECRET]
    email = entry.data[CONF_EMAIL]
    password = entry.data[CONF_PASSWORD]
    access_token = entry.data.get(CONF_ACCESS_TOKEN)

    # Initialize your TickTick client
    try:
        ticktick_client = await hass.async_add_executor_job(
            _create_ticktick_client,
            email,
            password,
            client_id,
            client_secret,
            access_token,
        )

        _LOGGER.debug("Authentication successful")
        _LOGGER.debug(client_id)
        # _LOGGER.debug(client_secret)
        _LOGGER.debug(email)
        # _LOGGER.debug(password)
        # _LOGGER.debug(access_token)

        # Log the projects
        # projects = ticktick_client.state["projects"]
        tasks = ticktick_client.task.get_from_project("5dad62dff0fe1fc4fbea252b")
        _LOGGER.debug("TickTick Tasks: %s", tasks)
        hass.data.setdefault(DOMAIN, {})[entry.entry_id] = ticktick_client
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    except Exception as e:
        _LOGGER.exception("Error setting up TickTickMod: %s", e)
        return False
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    hass.data[DOMAIN].pop(entry.entry_id)
    return True
