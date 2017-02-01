from JumpScale import j

import re
import collections
#from github.GithubObject import NotSet
import threading



def input(job):
    args = job.model.args
    service = job.service

    if "repo.name" not in args or args["repo.name"].strip() == "":
        args["repo.name"] = service.name

def init(job):
    service = job.service
    url = service.parent.model.data.githubUrl.rstrip("/")
    url += "/%s"%service.model.data.repoName

    service.model.data.repoUrl = url
    service.saveAll()

    client = service.producers["github_client"][0]
    client.model.data.codePath = j.dirs.replaceTxtDirVars(client.model.data.codePath)

    client.saveAll()

    path = j.sal.fs.joinPaths(client.model.data.codePath, client.model.data.repoAccount)
    service.model.data.codePath = path
    service.saveAll()


class Actions(ActionsBaseMgmt):
    def __init__(self, *args, **kwargs):
        self.logger = j.logger.get("github.repo")
        self.lock = threading.RLock()

    def install(self, service):
        self.process_issues(service=service, refresh=True)



    def _process_stories(self, service, issues):
        #make sure all stories are auto labeled correctly
        stories = dict()

        for issue in issues:
            if issue.repo.type not in ['home', 'proj', 'milestone', 'org']:
                continue

            story_name = self._story_name(issue.title)
            if story_name is not None:
                if not issue.assignee:
                    self._notify(service, "Story %s has no owner" % self._issue_url(issue))
                stories[story_name] = issue
                if issue.type != 'story':
                    issue.type = 'story'

        return stories



    def _process_todos(self, repo, issues):
        priorities_map = {
            'crit': 'critical',
            'mino': 'minor',
            'norm': 'normal',
            'urge': 'urgent',
        }

        client = repo.client

        for issue in issues:
            #only process open issues.
            if not issue.isOpen:
                continue

            for todo in issue.todo:
                cmd, _, args = todo.partition(' ')

                if not args:
                    # it seems all commands requires arguments
                    self.logger.warning("cannot process todo for %s" % (todo,))
                    continue

                if cmd == 'move':
                    destination_repo = client.getRepo(args)
                    self._move_to_repo(issue, destination_repo)
                    story_name = self._story_name(issue.title)
                    if story_name is not None:
                        for task in self._story_tasks(story_name, issues):
                            self._move_to_repo(task, destination_repo)

                elif cmd == 'p' or cmd == 'prio':
                    if len(args) == 4:
                        prio = priorities_map[args]
                    else:
                        prio = args

                    if prio not in priorities_map.values():
                        # Try to set
                        self.logger.warning(
                            'Try to set an non supported priority : %s' % prio)
                        continue

                    prio = "priority_%s" % prio
                    if prio not in issue.labels:
                        labels = issue.labels
                        labels.append(prio)
                        issue.labels = labels
                else:
                    self.logger.warning("command %s not supported" % cmd)





    def _notify(self, service, message):
        handle = service.parent.hrd.getStr('telegram.handle', '')
        if not handle:
            return

        self.ask_telegram(handle, message, expect_response=False)

    def _check_deadline(self, service, milestones, report):
        for milestone_key, stories in report.items():
            if milestone_key == NOMILESTONE:
                continue
            milestone = None
            deadline = None

            for story in stories:
                if milestone is None:
                    #note that milestones keys are in 'number:title' so we can only retrieve it via the issue reference.
                    milestone = milestones[story.milestone]
                    deadline = j.data.time.any2epoch(milestone.deadline)

                dl, _ = self._story_deadline(story)
                if dl > deadline:
                    self._notify(service, "Story %s ETA is behind milestone deadline" % self._issue_url(story))

    def _process_issues(self, service, repo, issues=None):
        """
        Process issues will find all the issues in the repo and label them accordin to the
        detected type (story, or task) add the proper linking of tasks to their parent stories, and
        adds a nice table in the story to list all story tasks.

        The tool, will also generate and commit some reports (in markdown syntax) with milestones, open stories
        assignees and estimates.

        It will also process the todo's comments

        !! prio $prio  ($prio is checked on first 4 letters, e.g. critical, or crit matches same)
        !! p $prio (alias above)

        !! move gig-projects/home (move issue to this project, try to keep milestones, labels, ...)
        """
        if issues is None:
            issues = repo.issues
        stories = self._process_stories(service, issues)

        issues = sorted(issues, key=lambda i: i.number)

        org_repo = self._is_org_repo(repo.name)

        _ms = [('{m.number}:{m.title}'.format(m=m), m) for m in repo.milestones]
        milestones = collections.OrderedDict(sorted(_ms, key=lambda i: i[1].title))
        report = dict()
        self._process_todos(repo, issues)

        # Do not complete if repo is not supported
        if not org_repo:
            return

        stories_tasks = dict()
        for issue in issues:
            if self._is_story(issue) and issue.isOpen:
                key = NOMILESTONE
                if issue.milestone:
                    ms = milestones.get(issue.milestone, None)
                    if ms is not None:
                        key = ms.title

                report.setdefault(key, [])
                report[key].append(issue)

            start = issue.title.partition(":")[0].strip()
            if start not in stories:
                # task that doesn't belong to any story. We skip for now
                # but i believe a different logic should be implemented
                continue

            story = stories[start]
            labels = issue.labels
            labels_dirty = False

            if "type_task" not in labels:
                labels.append("type_task")
                labels_dirty = True

            if self._task_estimate(issue.title) is None:
                self._notify(service, "Issue: %s has no estimates" % self._issue_url(issue))
                if "task_no_estimation" not in labels:
                    labels.append("task_no_estimation")
                    labels_dirty = True
            else:
                # pop label out
                if "task_no_estimation" in labels:
                    labels.remove("task_no_estimation")
                    labels_dirty = True

            if labels_dirty:
                # Only update labels if it was changed.
                self.logger.debug('setting issue label')
                issue.labels = labels

            # create link between story and tasks
            # linking logic
            self._task_link_to_story(story, issue)
            tasks = stories_tasks.setdefault(story, [])
            tasks.append(issue)

        # update story links
        for story, tasks in stories_tasks.items():
            self._story_add_tasks(story, tasks)

        self._check_deadline(service, milestones, report)
        self._generate_views(repo, milestones, issues, report)




    @action()
    def sync_milestones(self, service):
        repo = self.get_github_repo(service=service)

        for milestone in repo.milestones:
            args = {
                'github.repo': service.instance,
                'milestone.title': milestone.title,
                'milestone.description': milestone.description,
                'milestone.deadline': milestone.deadline
            }
            service.aysrepo.new(name='github_milestone', instance=str(milestone.title), args=args, model=milestone.ddict)



    @action()
    def set_labels(self, service):
        config = service.getProducers('github_config')[0]

        projtype = service.hrd.get("repo.type")
        labels = []

        for key, value in config.hrd.getDictFromPrefix("github.label").items():
            # label=key.split(".")[-1]
            label = key.replace(".", "_")
            if projtype in value or "*" in value:
                labels.append(label)

        r = self.get_github_repo(service)
        # first make sure issues get right labels
        r.labelsSet(labels, ignoreDelete=["p_"])

    @action()
    def process_issues(self, service, refresh=False):
        """
        refresh: bool, force loading of issue from github
        """
        self.lock.acquire()
        try:
            self.sync_milestones(service=service)
            self.set_labels(service=service)

            if service.state.get('process_issues', die=False) == 'RUNNING':
                # don't processIssue twice at the same time.
                j.logger.log('process_issues already running')
                return

            service.state.set('process_issues', 'RUNNING')
            service.state.save()

            repo = self.get_github_repo(service=service)
            if refresh:
                # force reload of services from github.
                repo._issues = None
            else:
                # load issues from ays.
                repo._issues = self.get_issues_from_ays(service=service)

            self._process_issues(service, repo)

            for issue in repo.issues:
                args = {'github.repo': service.instance}
                service.aysrepo.new(name='github_issue', instance=str(issue.id), args=args, model=issue.ddict)
        finally:
            self.lock.release()



    @action()
    def recurring_process_issues_from_model(self, service):
        self.process_issues(service=service, refresh=False)

    @action()
    def recurring_process_issues_from_github(self, service):
        self.process_issues(service=service, refresh=True)

    def event_new_issue(self, service, event):
        event = j.data.models.cockpit_event.Generic.from_json(event)

        if event.args.get('source', None) != 'github' or \
                'key' not in event.args or \
                event.args.get('event', None) != 'issues':
            return

        data = j.core.db.hget('webhooks', event.args['key'])
        if data is None:
            return
        github_payload = j.data.serializer.json.loads(data.decode())
        action = github_payload.get('action', None)
        if action != 'opened':
            return

        # at this point we know we are interested in the event.
        repo = self.get_github_repo(service)
        # create issue object
        issue = repo.getIssue(github_payload['issue']['number'])
        # create service gitub_issue
        args = {'github.repo': service.instance}
        service.aysrepo.new(name='github_issue', instance=str(issue.id), args=args, model=issue.ddict)
        pattern = '(?P<story_card>\w+)(:)'
        import re
        match = re.search(pattern, issue.title)
        if match:
            if ("type_bug" in issue.labels or "type_feature" in issue.labels) and repo.type == 'code':
                repo_name = service.hrd.get("repo.account") + "/" + service.hrd.get("org.repo")
                org_repo = self.get_github_repo(service, repo_name)
                org_issue = org_repo.api.create_issue(issue.title. issue.body)
                if 'type_bug' in issue.labels:
                    org_issue.add_to_labels("type_bug")
                else:
                    org_issue.add_to_labels("type_feature")
                for comment in issue.comments:
                    org_issue.create_comment(comment.body)
