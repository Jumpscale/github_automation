# Installation
Agile github tools are installed inside your cockpit setup with a blueprint. 

```yaml
# setup github client
github_client__main:
  github.secret : '<github-token>'
  code.path : '$vardir/codetmp/'

# setup github account
github_account__<account-name>:
  github.url: 'https://github.com/<account-name>'
  telegram.handle: '<telegram-handle>'

# add repos that will be managed by the agile tools
github_repo__<repo-name>:
  repo.name : '<repo-name>'
  repo.type : 'org'
  repo.account : '<account-name>'
  milestone.category : '<category>'

#... add more repos.
```

## Blueprint details
How to write a blueprint is outside the scope of this book. But we sill still explain the services templates that are used here.
- github_client
- github_acocunt
- github_milestone
- github_repo

### github_client
Github client template, is needed by the operation of other github service to allow access to the github API. It must be configured with a valid working token that is authorized to work with the repos that are defined later in the blueprint.
```yaml
github_client__main:
  github.secret : '<github-token>'
  code.path : '$vardir/codetmp/'
```
the `github-token` must be a valid token generated on github

### github_account
This represents a user account or an organization. It uses the defined `github_client` to do operations on the repos defined later. Thus the github_client token must have access to this organization repos.
```yaml
github_account__<account-name>:
  github.url: 'https://github.com/<account-name>'
  telegram.handle: '<telegram-handle>'
```
`account-name` is the organizaiton name. 
`telegram-handle` for sending notifications.

### github_repo
Defines a repo that will get managed by the github automation tools. Add as many repos as needed.

## Running the blueprint
You can run the blueprint normally. You also can run it manually using the `ays` command line as

```bash
ays init
ays install
```