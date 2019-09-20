"""Validate manifests."""
from pathlib import Path
import subprocess
import sys

from . import gather_info, generate, error, model


def main():
    """Scaffold an integration."""
    if not Path("requirements_all.txt").is_file():
        print("Run from project root")
        return 1

    print("Creating a new integration for Home Assistant.")

    if "--develop" in sys.argv:
        print("Running in developer mode. Automatically filling in info.")
        print()

        info = model.Info(
            domain="develop",
            name="Develop Hub",
            codeowner="@developer",
            requirement="aiodevelop==1.2.3",
        )
    else:
        try:
            info = gather_info.gather_info()
        except error.ExitApp as err:
            print()
            print(err.reason)
            return err.exit_code

    generate.generate(info)

    print("Running hassfest to pick up new codeowner and config flow.")
    subprocess.run("python -m script.hassfest", shell=True)
    print()

    print("Running tests")
    print(f"$ pytest tests/components/{info.domain}")
    if (
        subprocess.run(f"pytest tests/components/{info.domain}", shell=True).returncode
        != 0
    ):
        return 1
    print()

    print(f"Successfully created the {info.domain} integration!")

    return 0


if __name__ == "__main__":
    sys.exit(main())
