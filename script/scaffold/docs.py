"""Print links to relevant docs."""

from .model import Info

DATA = {
    "backup": {
        "title": "Backup",
        "docs": "https://developers.home-assistant.io/docs/core/platform/backup",
    },
    "config_flow": {
        "title": "Config Flow",
        "docs": "https://developers.home-assistant.io/docs/en/config_entries_config_flow_handler.html",
    },
    "config_flow_helper": {
        "title": "Helper Config Flow",
        "docs": "https://developers.home-assistant.io/docs/en/config_entries_config_flow_handler.html#helper",
    },
    "config_flow_discovery": {
        "title": "Discoverable Config Flow",
        "docs": "https://developers.home-assistant.io/docs/en/config_entries_config_flow_handler.html#discoverable-integrations-that-require-no-authentication",
    },
    "config_flow_oauth2": {
        "title": "OAuth2 Config Flow",
        "docs": "https://developers.home-assistant.io/docs/en/next/config_entries_config_flow_handler.html#configuration-via-oauth2",
    },
    "device_action": {
        "title": "Device Action",
        "docs": "https://developers.home-assistant.io/docs/en/device_automation_action.html",
    },
    "device_condition": {
        "title": "Device Condition",
        "docs": "https://developers.home-assistant.io/docs/en/device_automation_condition.html",
    },
    "device_trigger": {
        "title": "Device Trigger",
        "docs": "https://developers.home-assistant.io/docs/en/device_automation_trigger.html",
    },
    "integration": {
        "title": "Integration",
        "docs": "https://developers.home-assistant.io/docs/en/creating_integration_file_structure.html",
    },
    "reproduce_state": {
        "title": "Reproduce State",
        "docs": "https://developers.home-assistant.io/docs/core/platform/reproduce_state",
        "extra": "You will now need to update the code to make sure that every attribute that can occur in the state will cause the right service to be called.",
    },
    "significant_change": {
        "title": "Significant Change",
        "docs": "https://developers.home-assistant.io/docs/core/platform/significant_change",
        "extra": "You will now need to update the code to make sure that entities with different device classes are correctly considered.",
    },
}


def print_relevant_docs(template: str, info: Info) -> None:
    """Print relevant docs."""
    data = DATA[template]

    print()
    print("**************************")
    print()
    print()
    print(f"{data['title']} code has been generated")
    print()
    if info.files_added:
        print("Added the following files:")
        for file in info.files_added:
            print(f"- {file}")
        print()

    if info.tests_added:
        print("Added the following tests:")
        for file in info.tests_added:
            print(f"- {file}")
        print()

    if info.examples_added:
        print(
            "Because some files already existed, we added the following example files. Please copy the relevant code to the existing files."
        )
        for file in info.examples_added:
            print(f"- {file}")
        print()

    print(
        "The next step is to look at the files and deal with all areas marked as TODO."
    )

    if "extra" in data:
        print()
        print(data["extra"])
