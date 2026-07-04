"""Tests for the Azure DevOps integration."""

from datetime import datetime
from typing import Final

from aioazuredevops.models.build import Build, BuildDefinition
from aioazuredevops.models.core import Project
from aioazuredevops.models.work_item import WorkItem, WorkItemFields
from aioazuredevops.models.work_item_type import Category, Icon, State, WorkItemType

from homeassistant.components.azure_devops.const import CONF_ORG, CONF_PAT, CONF_PROJECT
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

ORGANIZATION: Final[str] = "testorg"
PROJECT: Final[str] = "testproject"
PAT: Final[str] = "abc123"

UNIQUE_ID = f"{ORGANIZATION}_{PROJECT}"


FIXTURE_USER_INPUT = {
    CONF_ORG: ORGANIZATION,
    CONF_PROJECT: PROJECT,
    CONF_PAT: PAT,
}

FIXTURE_REAUTH_INPUT = {
    CONF_PAT: PAT,
}


DEVOPS_PROJECT = Project(
    id="1234",
    name=PROJECT,
    description="Test Description",
    url=f"https://dev.azure.com/{ORGANIZATION}/{PROJECT}",
    state="wellFormed",
    revision=1,
    visibility="private",
    default_team=None,
    links=None,
)

DEVOPS_BUILD_DEFINITION = BuildDefinition(
    build_id=9876,
    name="CI",
    url=f"https://dev.azure.com/{ORGANIZATION}/{PROJECT}/_apis/build/definitions/1",
    path="",
    build_type="build",
    queue_status="enabled",
    revision=1,
)

DEVOPS_BUILD = Build(
    build_id=5678,
    build_number="1",
    status="completed",
    result="succeeded",
    source_branch="main",
    source_version="123",
    priority="normal",
    reason="manual",
    queue_time="2021-01-01T00:00:00Z",
    start_time="2021-01-01T00:00:00Z",
    finish_time="2021-01-01T00:00:00Z",
    definition=DEVOPS_BUILD_DEFINITION,
    project=DEVOPS_PROJECT,
    links=None,
)

DEVOPS_BUILD_MISSING_DATA = Build(
    build_id=6789,
    definition=DEVOPS_BUILD_DEFINITION,
    project=DEVOPS_PROJECT,
)

DEVOPS_BUILD_MISSING_PROJECT_DEFINITION = Build(
    build_id=9876,
)

DEVOPS_WORK_ITEM_TYPES = [
    WorkItemType(
        name="Bug",
        reference_name="System.Bug",
        description="Bug",
        color="ff0000",
        icon=Icon(id="1234", url="https://example.com/icon.png"),
        is_disabled=False,
        xml_form="",
        fields=[],
        field_instances=[],
        transitions={},
        states=[
            State(name="New", color="ff0000", category=Category.PROPOSED),
            State(name="Active", color="ff0000", category=Category.IN_PROGRESS),
            State(name="Resolved", color="ff0000", category=Category.RESOLVED),
            State(name="Closed", color="ff0000", category=Category.COMPLETED),
        ],
        url="",
    )
]

DEVOPS_WORK_ITEM_IDS = [1]

DEVOPS_WORK_ITEMS = [
    WorkItem(
        id=1,
        rev=1,
        fields=WorkItemFields(
            area_path="",
            team_project="",
            iteration_path="",
            work_item_type="Bug",
            state="New",
            reason="New",
            assigned_to=None,
            created_date=datetime(2021, 1, 1),
            created_by=None,
            changed_date=datetime(2021, 1, 1),
            changed_by=None,
            comment_count=0,
            title="Test",
            microsoft_vsts_common_state_change_date=datetime(2021, 1, 1),
            microsoft_vsts_common_priority=1,
        ),
        url="https://example.com",
    )
]


async def setup_integration(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> bool:
    """Fixture for setting up the component."""
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    return result
