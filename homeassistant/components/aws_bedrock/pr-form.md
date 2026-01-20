<!--
  You are amazing! Thanks for contributing to our project!
  Please, DO NOT DELETE ANY TEXT from this template! (unless instructed).
-->

## Proposed change
<!--
  Describe the big picture of your changes here to communicate to the
  maintainers why we should accept this pull request. If it fixes a bug
  or resolves a feature request, be sure to link to that issue in the
  additional information section.
-->

Add a new integration for **AWS Bedrock**, Amazon's fully managed service that provides access to foundation models from leading AI providers through a single API.

This integration enables Home Assistant users to:
- Use AWS Bedrock foundation models (Anthropic Claude, Amazon Nova, Meta Llama, Mistral, and others) as **conversation agents**
- Leverage Bedrock models for **AI task processing** (structured data generation)
- Optionally enable **web search capabilities** via Google Custom Search API for real-time information retrieval
- Configure multiple conversation agents and AI tasks through subentries

### Key Features
- **Config flow** with AWS credential validation and region selection
- **Subentry-based configuration** for conversation agents and AI tasks
- **Tool use support** with proper handling for Nova and Claude models
- **Web search integration** (optional) for accessing current information
- **File attachments** support for images and PDFs
- **99% test coverage** across all modules

### Technical Implementation
- Uses `boto3` SDK with `async_add_executor_job` for non-blocking calls
- Implements `conversation.ConversationEntity` and `ai_task.AITaskEntity` platforms
- Creates devices per subentry with proper DeviceInfo
- Follows Home Assistant quality scale Bronze requirements

## Type of change
<!--
  What type of change does your PR introduce to Home Assistant?
  NOTE: Please, check only 1! box!
  If your PR requires multiple boxes to be checked, you'll most likely need to
  split it into multiple PRs. This makes things easier and faster to code review.
-->

- [ ] Dependency upgrade
- [ ] Bugfix (non-breaking change which fixes an issue)
- [x] New integration (thank you!)
- [ ] New feature (which adds functionality to an existing integration)
- [ ] Deprecation (breaking change to happen in the future)
- [ ] Breaking change (fix/feature causing existing functionality to break)
- [ ] Code quality improvements to existing code or addition of tests

## Additional information
<!--
  Details are important, and help maintainers processing your PR.
  Please be sure to fill out additional details, if applicable.
-->

- This PR fixes or closes issue: fixes #
- This PR is related to issue:
- Link to documentation pull request: https://github.com/home-assistant/home-assistant.io/pull/XXXX
- Link to developer documentation pull request:
- Link to frontend pull request:

### Dependencies
- `boto3==1.37.1` - AWS SDK for Python ([changelog](https://github.com/boto/boto3/blob/develop/CHANGELOG.rst))
- `trafilatura==2.0.0` - Web content extraction library ([changelog](https://github.com/adbar/trafilatura/blob/master/HISTORY.md))

## Checklist
<!--
  Put an `x` in the boxes that apply. You can also fill these out after
  creating the PR. If you're unsure about any of them, don't hesitate to ask.
  We're here to help! This is simply a reminder of what we are going to look
  for before merging your code.

  AI tools are welcome, but contributors are responsible for *fully*
  understanding the code before submitting a PR.
-->

- [x] I understand the code I am submitting and can explain how it works.
- [x] The code change is tested and works locally.
- [x] Local tests pass. **Your PR cannot be merged unless tests pass**
- [x] There is no commented out code in this PR.
- [x] I have followed the [development checklist][dev-checklist]
- [x] I have followed the [perfect PR recommendations][perfect-pr]
- [x] The code has been formatted using Ruff (`ruff format homeassistant tests`)
- [x] Tests have been added to verify that the new code works.
- [x] Any generated code has been carefully reviewed for correctness and compliance with project standards.

If user exposed functionality or configuration variables are added/changed:

- [x] Documentation added/updated for [www.home-assistant.io][docs-repository]

If the code communicates with devices, web services, or third-party tools:

- [x] The [manifest file][manifest-docs] has all fields filled out correctly.
      Updated and included derived files by running: `python3 -m script.hassfest`.
- [x] New or updated dependencies have been added to `requirements_all.txt`.
      Updated by running `python3 -m script.gen_requirements_all`.
- [x] For the updated dependencies - a link to the changelog, or at minimum a diff between library versions is added to the PR description.

<!--
  This project is very active and we have a high turnover of pull requests.

  Unfortunately, the number of incoming pull requests is higher than what our
  reviewers can review and merge so there is a long backlog of pull requests
  waiting for review. You can help here!

  By reviewing another pull request, you will help raise the code quality of
  that pull request and the final review will be faster. This way the general
  pace of pull request reviews will go up and your wait time will go down.

  When picking a pull request to review, try to choose one that hasn't yet
  been reviewed.

  Thanks for helping out!
-->

To help with the load of incoming pull requests:

- [ ] I have reviewed two other [open pull requests][prs] in this repository.

[prs]: https://github.com/home-assistant/core/pulls?q=is%3Aopen+is%3Apr+-author%3A%40me+-draft%3Atrue+-label%3Awaiting-for-upstream+sort%3Acreated-desc+review%3Anone+-status%3Afailure

<!--
  Thank you for contributing <3

  Below, some useful links you could explore:
-->
[dev-checklist]: https://developers.home-assistant.io/docs/development_checklist/
[manifest-docs]: https://developers.home-assistant.io/docs/creating_integration_manifest/
[quality-scale]: https://developers.home-assistant.io/docs/integration_quality_scale_index/
[docs-repository]: https://github.com/home-assistant/home-assistant.io
[perfect-pr]: https://developers.home-assistant.io/docs/review-process/#creating-the-perfect-pr
