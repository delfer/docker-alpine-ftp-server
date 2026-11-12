# Repository contribution rules

These rules apply to all work in this repository, including changes made by
coding agents.

## Branches and pull requests

- Make every change on a dedicated task branch based on the current default
  branch (`master`). Never commit or push directly to the default branch.
- Keep unrelated tasks on separate branches and in separate pull requests.
- Submit every completed change through a pull request to the default branch.
  Describe the problem, the resulting behavior, validation performed, and any
  known failures or limitations.
- The maintainer reviews, validates, and merges pull requests. Do not merge a
  pull request or enable automatic merging on the maintainer's behalf.
- Do not bypass checks or hide failing tests to make a pull request appear green.
  Report existing application defects explicitly; respect the task's scope.

## Commits

- Commit frequently as meaningful milestones are completed. Do not wait until
  the end of a task to create one large commit containing unrelated work.
- Keep commits small, granular, complete, and independently meaningful. Each
  commit should have one purpose and leave its changes internally consistent.
  Do not split work into incomplete fragments merely to increase commit count.
- Use Conventional Commits: `<type>(<optional scope>): <description>`.
  Examples: `docs(agents): define contribution workflow`,
  `test(ftp): cover active and passive transfers`, and
  `ci(tests): run FTP integration checks`.
- Use a concise description of the actual change. Add a commit body when the
  rationale, validation, or known failures need explanation.
- Validate each completed milestone with the checks appropriate to its scope.
  Known application failures must remain visible and be documented accurately.
