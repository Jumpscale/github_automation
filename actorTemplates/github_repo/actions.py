from JumpScale import j
import re
import collections
from github.GithubObject import NotSet

def input(job):
    args = job.model.args
    service = job.service

    if "repo.name" not in args or args["repo.name"].strip() == "":
        args["repo.name"] = service.name


def init(job):

    service = job.service
    # SET UP EVENT HANDLERS.
    handlers_map = [
                    #('webhooks.repo', 'process_issues_from_github'),
                    ('webhooks.repo', 'on_new_issue_event'),
    ]

    for (event, callback) in handlers_map:
        service.model.eventFilterSet(command=event, action=callback)
    service.saveAll()
    url = service.parent.model.data.githubUrl.rstrip("/")
    url += "/%s" % service.model.data.repoName

    service.model.data.repoUrl = url

    client = service.producers["github_client"][0]
    client.model.data.codePath = j.dirs.replaceTxtDirVars(client.model.data.codePath)

    client.saveAll()

    path = j.sal.fs.joinPaths(client.model.data.codePath, service.model.data.repoAccount)
    service.model.data.codePath = path
    service.saveAll()

#
# def install(job):
#     service = job.service
#     j.tools.devprocess.process_issues(service=service, refresh=True)

# def process_issues_from_model(job):
#     service = job.service
#     j.tools.devprocess.process_issues(service=service, refresh=False)

def process_issues_from_github(job):
    service = job.service
    j.tools.devprocess.process_issues(service=service, refresh=True)

def on_new_issue_event(job):
    service = job.service
    args = job.model.args
    src = args.get('source', None)  # should be github
    sender_service_name = args.get('sender_service_name', None)
    event_type = args.get('issues', None)
    key = args.get('key', None)
    data = j.data.serializer.json.loads(args['hookdata'])

    if not any([src, event_type, sender_service_name]):
        return

    # data = j.core.db.hget('webhooks', key)
    # if data is None:
    #     return
    github_payload = data
    action = github_payload.get('action', None)
    if action != 'opened':
        return

    sender_service = service.aysrepo.serviceGet(role="github_repo", instance=sender_service_name)
    # at this point we know we are interested in the event.
    repo = j.tools.devprocess.get_github_repo(sender_service)
    # create issue object
    issue = repo.getIssue(github_payload['issue']['number'])
    # create sender_service gitub_issue
    args = {'github.repo': sender_service.name}
    issue_actor = service.aysrepo.actorGet('github_issue')
    sv = issue_actor.serviceCreate(instance=str(issue.id), args=args)

    #FIXME: set model
    pattern = '(?P<story_card>\w+)(:)'
    match = re.search(pattern, issue.title)
    if match:
        if ("type_bug" in issue.labels or "type_feature" in issue.labels) and repo.type == 'code':
            repo_name = sender_service.model.data.repoAccount + "/" + sender_service.model.data.orgRepo
            org_repo = j.tools.devprocess.get_github_repo(sender_service, repo_name)
            org_issue = org_repo.api.create_issue(issue.title. issue.body)
            if 'type_bug' in issue.labels:
                org_issue.add_to_labels("type_bug")
            else:
                org_issue.add_to_labels("type_feature")
            for comment in issue.comments:
                org_issue.create_comment(comment.body)
