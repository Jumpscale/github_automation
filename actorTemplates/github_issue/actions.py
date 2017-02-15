from JumpScale import j
# class Actions(ActionsBaseMgmt):
#
#     @action()
#     def process(self, service):
#         Issue = j.clients.github.getIssueClass()
#         repo = service.parent.actions.get_github_repo(service=service.parent)
#
#         raise NotImplementedError()
#
#         # only process this specific issue.
#         for issue in repo.issues:
#             if issue.id == service.model['id']:
#                 repo.process_issues([issue])
#                 break

def init(job):
    service = job.service
    # SET UP EVENT HANDLERS.
    handlers_map = [('webhooks.issue', 'update_from_github')]

    for (event, callback) in handlers_map:
        service.model.eventFilterSet(command=event, action=callback)
    service.saveAll()

def update_from_github(job):
    import datetime
    from pickle import dumps, loads
    service = job.service
    args = job.model.args
    src = args.get('source', None)  # should be github
    sender_service_name = args.get('sender_service_name', None)
    event_type = args.get('issues', None)
    key = args.get('key', None)


    if not any([src, event_type, sender_service_name]):
        return

    # data = j.core.db.hget('webhooks', key)
    data = j.data.serializer.json.loads(args['hookdata'])
    if data is None:
        return

    github_payload = data

    action = github_payload.get('action', None)
    if action is None:
        return

    if github_payload['issue']['id'] != service.model.data.id:
        # event not for this issue
        return

    model = service.model.data.pickledmodel
    loaded_model = loads(model)
    data = loaded_model['data']
    if event_type == 'issue_comment':
        if action == 'created':
            dt = datetime.datetime.strptime(github_payload['comment']['updated_at'], "%Y-%m-%dT%H:%M:%SZ")
            comment = {
                'body': github_payload['comment']['body'],
                'id': github_payload['comment']['id'],
                'time': j.data.time.any2HRDateTime(dt),
                'url': github_payload['comment']['url'],
                'user': github_payload['comment']['user']['login']
            }

            data['comments'].append(comment)
        elif action == 'edited':
            # find comment in model
            comment = None
            for i, comment in enumerate(model.data.comments):
                if comment['id'] == github_payload['comment']['id']:
                    break

            # update comment
            if comment is not None:
                dt = datetime.datetime.strptime(github_payload['comment']['updated_at'], "%Y-%m-%dT%H:%M:%SZ")
                new_comment = {
                    'body': github_payload['comment']['body'],
                    'id': github_payload['comment']['id'],
                    'time': j.data.time.any2HRDateTime(dt),
                    'url': github_payload['comment']['url'],
                    'user': github_payload['comment']['user']['login']
                }
                # save new comment
                data['comments'][i] = new_comment

            # find comment in model
            comment = None
            for i, comment in enumerate(model.comments):
                if comment['id'] == github_payload['comment']['id']:
                    data['comments'].remove(comment)
            j.logger.log('not supported action: %s' % action)
            return
    elif event_type == 'issues':
        if github_payload['issue']['id'] != service.model.data.id:
            return

        if action == 'closed':
            pattern = r"#(\d+)"
            import re
            data['open'] = False
            data['state'] = 'closed'
            repo = j.tools.devprocess.get_github_repo(service=service.parent)
            if repo.type != "org":
                return
            client_ays = service.parent.producers['github_client'][0]
            client = j.tools.devprocess.getGithubClient(client_ays)

            story = repo.getIssue(service.model.data.number)
            if "type_story" not in story.labels:
                return
            issues_nums = re.findall(pattern, story.body)
            j.logger.log("Story Card closed will closes these related issue with nums %s" % issues_nums)
            for issue_num in issues_nums:
                issue = repo.getIssue(int(issue_num))
                issue.api.edit(state="closed")

        elif action == 'reopened':
            data['open'] = True
            data['state'] = 'reopened'
            loaded_model['data'] = data
        elif action in ['assigned', 'unassigned']:
            assignee = github_payload['issue']['assignee']
            if assignee is None:
                data['assignee'] = ''
            else:
                if j.data.types.list.check(assignee):
                    data['assignee'] = [a['login'] for a in assignee]
                elif j.data.types.dict.check(assignee):
                    data['assignee'] = assignee['login']
        elif action in ['labeled', 'unlabeled']:
            data['labels'] = [i['name'] for i in github_payload['issue']['labels']]
        elif action == 'edited':
            data['body'] = github_payload['issue']['body']
            data['title'] = github_payload['issue']['title']
            data['milestone'] = github_payload['issue']['milestone'] or ''
        else:
            j.logger.log('not supported action: %s' % action)
            return
        loaded_model['data'] = data
        service.model.pickledmodel = dumps(loaded_model)
        service.model.saveAll()
