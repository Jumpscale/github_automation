# Operation
The automation tool lives inside an ays cockpit. Once installed from a blue print it creates service instances of all repository issues. While setting up the issues it processes them as follows:

- issues that has a title in `Some title (story-name)` is considered a story with story name `story-name`
- issues that has a title in `story-name: task title` is considered a task in the user story `story-name`
- A story task should have an estimation in the title as in the format `[nU]` where n is a number an U is one of (m, h, d) for (minute, hour and day) respectively. So a typical task title should be in the format `story-name: task title [nU]`
  - A story with no estimates will be automatically labeled with `task_no_estimate` label and a notification will be sent to the account telegram handle.
- The github tools will automatically label stories and tasks correctly with `type_story` and `type_task`.
- A link will be added to all tasks of the story that links back the parent story
- A list of links will be added to the story that links forward to all child tasks. The links will have a check mark that notates the state of the task (open, or closed).
- While processing all the repo issues, if a story card found with no owner (no assigne) a notification will be sent to the account telegram handle.
- If the story belongs to a milestone, the ETA for the issue will be checked against the milestone deadline. A notification will be sent if the ETA exceeds the milestone deadline.
- If the repo is an `org` repo (name start with *org_* or *proj_* reports will get generated and commited to the repo. The reports has the following information:
  - `milestones report` shows all milestones with there corresponding stories.
  - `milestone details report` per milestone shows list of unassigned issues in that milestone and all the milestones issues grouped by contributors.
  - `assignee report` shows all issues grouped by contributors.

## Keep ays in sync
To keep ays model in sync with github we apply the followin 2 processes

### Handle github webhooks
On receiving a webhook event from github, we update the ays model of the local issue. The webhook doesn't trigger processing of issues or regenerating the report.

### 15 minute schedule
Once every 15 minute, the cockpit starts issues processing but based on the local ays model we have. So all changes received by the webhooks now will take effect and reflect in the generated reports.

### 24 hour schedule
Once every 24 hour, the system force syncronizing everything back from github to make sure the always is 100% in sync with github even if we missed any of the webhook events.

