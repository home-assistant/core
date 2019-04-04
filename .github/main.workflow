workflow "Mention CODEOWNERS of integrations when integration label is added to an issue" {
  on = "issues"
  resolves = "codeowners-mention"
}

workflow "Mention CODEOWNERS of integrations when integration label is added to an PRs" {
  on = "pull_request"
  resolves = "codeowners-mention"
}

action "codeowners-mention" {
  uses = "home-assistant/codeowners-mention@master"
  secrets = ["GITHUB_TOKEN"]
}
