"""Print links to relevant docs."""
from .model import Info


def print_relevant_docs(template: str, info: Info) -> None:
    """Print relevant docs."""
    if template == "integration":
        print(
            f"""
Your integration has been created at {info.integration_dir} . Next step is to fill in the blanks for the code marked with TODO.

For a breakdown of each file, check the developer documentation at:
https://developers.home-assistant.io/docs/en/creating_integration_file_structure.html
"""
        )

    elif template == "config_flow":
        print(
            f"""
The config flow has been added to the {info.domain} integration. Next step is to fill in the blanks for the code marked with TODO.
"""
        )

    elif template == "reproduce_state":
        print(
            f"""
Reproduce state code has been added to the {info.domain} integration:
 - {info.integration_dir / "reproduce_state.py"}
 - {info.tests_dir / "test_reproduce_state.py"}

Please update the relevant items marked as TODO before submitting a pull request.
"""
        )
