## Breaking Change:

<!-- What is breaking and why we have to break it. Remove this section only if it was NOT a breaking change. -->

## Description:


**Related issue (if applicable):** fixes #<home-assistant issue number goes here>

**Pull request with documentation for [home-assistant.io](https://github.com/home-assistant/home-assistant.io) (if applicable):** home-assistant/home-assistant.io#<home-assistant.io PR number goes here>

## Example entry for `configuration.yaml` (if applicable):
```yaml

```

## Checklist:
  - [ ] The code change is tested and works locally.
  - [ ] Local tests pass with `tox`. **Your PR cannot be merged unless tests pass**
  - [ ] There is no commented out code in this PR.
  - [ ] I have followed the [development checklist][dev-checklist]

If user exposed functionality or configuration variables are added/changed:
  - [ ] Documentation added/updated in [home-assistant.io](https://github.com/home-assistant/home-assistant.io)

If the code communicates with devices, web services, or third-party tools:
  - [ ] [_The manifest file_][manifest-docs] has all fields filled out correctly. Update and include derived files by running `python3 -m script.hassfest`.
  - [ ] New or updated dependencies have been added to `requirements_all.txt` by running `python3 -m script.gen_requirements_all`.
  - [ ] Untested files have been added to `.coveragerc`.

If the code does not interact with devices:
  - [ ] Tests have been added to verify that the new code works.

[dev-checklist]: https://developers.home-assistant.io/docs/en/development_checklist.html
[manifest-docs]: https://developers.home-assistant.io/docs/en/creating_integration_manifest.html
