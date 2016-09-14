## First
- [ ] I have read and understand the [Contributing](https://github.com/home-assistant/home-assistant/CONTRIBUTING.md) documentation.

## Description
<!--- Describe your changes. -->

## Types of Changes
<!--- What types of changes does your code introduce? Put an `x` in all the boxes that apply. -->
- [ ] Bug fix (non-breaking change which fixes an issue)
- [ ] New feature (non-breaking change which adds functionality)
- [ ] Breaking change (fix or feature that would cause existing functionality to change)

## Issues
<!-- List all issues that your change addresses ex( - home-assistant/home-assistant/issues/3745 ) -->

## Pull Requests
<!-- List your related pull requests here. Put an 'x' in all the boxes that apply. -->
- [ ] Frontend in [home-assistant-polymer](https://github.com/home-assistant/home-assistant-polymer):
- [ ] Documentation in [home-assistant.io](https://github.com/home-assistant/home-assistant.io):
- [ ] Javascript in [home-assistant-js](https://github.com/home-assistant/home-assistant-js):

## Configuration.yaml Example
```yaml
[your-code]
```

## Screenshots (if applicable)
<!-- Paste your screenshots here -->

## Checklist
- [ ] Local tests with `tox` run successfully. **Your PR cannot be merged unless tests pass**
- [ ] Tests have been added to verify that the new code works.
- [ ] Changes add/change user functionality or configuration variables. (requires items below)
  - [ ] Documentation has been updated and pull request has been submitted.
  - [ ] Pull request link is listed in Pull Requests section above.
- [ ] New code communicates with devices or webservices. (requires items below)
  - [ ] New dependencies have been added to the `REQUIREMENTS` variable ([example][ex-requir]).
  - [ ] New dependencies are only imported inside functions that use them ([example][ex-import]).
  - [ ] New dependencies have been added to `requirements_all.txt` by running `script/gen_requirements_all.py`.
  - [ ] New files were added to `.coveragerc`.


[ex-requir]: https://github.com/home-assistant/home-assistant/blob/dev/homeassistant/components/keyboard.py#L16
[ex-import]: https://github.com/home-assistant/home-assistant/blob/dev/homeassistant/components/keyboard.py#L51
