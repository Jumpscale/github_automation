from JumpScale import j

import re
import collections
from jinja2 import Template
from github.GithubObject import NotSet
import threading

NOMILESTONE = '__no_milestone__'

MILESTONE_REPORT_FILE = 'milestone-report.md'
ASSIGNEE_REPORT_FILE = 'assignee-report.md'

MILESTONE_REPORT_TMP = Template('''\
> This file is auto generated by `ays` services. Please don't modify manually.

# Summary
|Milestone|ETA|
|---------|---|
{% for milestone in milestones.values() -%}
|[{{ milestone.title }}](#milestone-{{ milestone.title | replace(' ', '-')| replace('.', '')| lower }})|{{ summary(milestone.title) }}|
{% endfor -%}
|[No milestone](#no-milestone)|{{ summary('__no_milestone__') }}|

{% for key, milestone in milestones.items() -%}
## [Milestone {{ milestone.title }}](milestones/{{ key }}.md)

{% set issues = report.get(milestone.title, []) %}
|Issue|Title|State|Owner|ETA|
|-----|-----|-----|-----|---|
{% for issue in issues -%}
|[#{{ issue.number }}](https://github.com/{{ repo.fullname }}/issues/{{ issue.number }})|\
{{ issue.title }}|\
{{ state(issue.state) }}|\
{% if issue.assignee %}[{{ issue.assignee }}](https://github.com/{{ issue.assignee }}){% endif %}|\
{% set eta, id = estimate(issue) %}{% if eta %}[{{ eta|trim }}]({{ issue.url }}#issuecomment-{{ id }}){% else %}N/A{% endif %}|
{% endfor %}
{% endfor %}


## No milestone
|Issue|Title|State|Owner|ETA|
|-----|-----|-----|-----|---|
{% for issue in report.get('__no_milestone__', []) -%}
|[#{{ issue.number }}](https://github.com/{{ repo.fullname }}/issues/{{ issue.number }})|\
{{ issue.title }}|\
{{ state(issue.state) }}|\
{% if issue.assignee %}[{{ issue.assignee }}](https://github.com/{{ issue.assignee }}){% endif %}|\
{% set eta, id = estimate(issue) %}{% if eta %}[{{ eta|trim }}]({{ issue.url }}#issuecomment-{{ id }}){% else %}N/A{% endif %}|
{% endfor %}
''')

MILESTONE_DETAILS_TEMP = Template('''\
> This file is auto generated by `ays` services. Please don't modify manually.

# Milestone {{milestone.title}}

## List of all unassigned issues in this milestone

|Issue|Title|State|Type|
|-----|-----|-----|---|
{% for issue in issues -%}
{% if issue.milestone == key and not issue.assignee and issue.isOpen -%}
|[#{{ issue.number }}](https://github.com/{{ repo.fullname }}/issues/{{ issue.number }})|\
{{ issue.title }}|\
{{ state(issue.state) }}|\
{{ issue.type }}|
{% endif -%}
{% endfor %}

## Issues per assignee
{% for user, issues in assignees.items() -%}
- [{{ user }}](#{{ user|replace(' ', '-')|replace('.', '')|lower }})
{% endfor %}

{% for user, issues in assignees.items() %}
### [{{ user }}](https://github.com/{{user}})

|Issue|Title|State|Type|
|-----|-----|-----|----|
{% for issue in issues -%}
{% if issue.milestone == key -%}
|[#{{ issue.number }}](https://github.com/{{ repo.fullname }}/issues/{{ issue.number }})|\
{{ issue.title }}|\
{{ state(issue.state) }}|\
{{ issue.type }}|
{% endif -%}
{% endfor %}
{% endfor %}
''')

ASSIGNEE_REPORT_TMP = Template('''\
> This file is auto generated by `ays` services. Please don't modify manually.

# Issues per assignee
{% for user, issues in assignees.items() -%}
- [{{ user }}](#{{ user|replace(' ', '-')|replace('.', '')|lower }}) has {{ issues|count }} assigned
{% endfor %}

{% for user, issues in assignees.items() %}
## [{{ user }}](https://github.com/{{user}})

|Issue|Title|State|Type|
|-----|-----|-----|----|
{% for issue in issues -%}
|[#{{ issue.number }}](https://github.com/{{ repo.fullname }}/issues/{{ issue.number }})|\
{{ issue.title }}|\
{{ state(issue.state) }}|\
{{ issue.type }}|
{% endfor %}
{% endfor %}
''')

re_story_name = re.compile('.+\((.+)\)\s*$')
re_task_estimate = re.compile('.+\[([^\]]+)\]\s*$')
re_story_estimate = re.compile('^ETA:\s*(.+)\s*$', re.MULTILINE)


class Actions(ActionsBaseMgmt):
    def __init__(self, *args, **kwargs):
        self.logger = j.logger.get("github.repo")
        self.lock = threading.RLock()
    def input(self, service, name, role, instance, args={}):

        # if repo.name not filled in then same as instance
        if "repo.name" not in args or args["repo.name"].strip() == "":
            args["repo.name"] = instance

        return args

    @action()
    def init(self, service):

        # set url based on properties of parent
        url = service.parent.hrd.get("github.url").rstrip("/")
        url += "/%s" % service.hrd.get("repo.name")
        service.hrd.set("repo.url", url)

        # set path based on properties from above

        clienthrd = service.producers["github_client"][0].hrd

        clienthrd.set("code.path", j.dirs.replaceTxtDirVars(clienthrd.get("code.path")))

        path = j.sal.fs.joinPaths(clienthrd.get("code.path"), service.hrd.get("repo.account"), service.hrd.get("repo.name"))
        service.hrd.set("code.path", path)
        return True

    def install(self, service):
        self.process_issues(service=service, refresh=True)


    def _story_name(self, title):
        m = re_story_name.match(title.strip())
        if m is None:
            return None

        return m.group(1)

    def _story_tasks(self, name, issues):
        tasks = []
        for issue in issues:
            story = issue.title.partition(':')[0].strip()
            if story == name:
                tasks.append(issue)
        return tasks

    def _task_estimate(self, title):
        m = re_task_estimate.match(title)
        if m is not None:
            return m.group(1).strip()
        return None

    def _story_estimate(self, issue):
        comments = issue.comments
        if not len(comments):
            return None, None
        # find last comment with ETA
        for last in reversed(comments):
            m = re_story_estimate.search(last['body'])
            if m is not None:
                return m.group(1), last['id']
        return None, None

    def _issue_url(self, issue):
        return 'https://github.com/%s/issues/%s' % (issue.repo.fullname, issue.number)

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

    def _move_to_repo(self, issue, dest):
        self.logger.info("%s: move to repo:%s" % (issue, dest))
        ref = self._issue_url(issue)
        body = "Issue moved from %s\n\n" % ref

        for line in issue.api.body.splitlines():
            if line.startswith("!!") or line.startswith(
                    '### Tasks:') or line.startswith('### Part of Story'):
                continue
            body += "%s\n" % line

        assignee = issue.api.assignee if issue.api.assignee else NotSet
        labels = issue.api.labels if issue.api.labels else NotSet
        moved_issue = dest.api.create_issue(title=issue.title, body=body,
                                            assignee=assignee, labels=labels)
        moved_issue.create_comment(self._create_comments_backlog(issue))
        moved_ref = 'https://github.com/%s/issues/%s' % (dest.fullname, moved_issue.number)
        issue.api.create_comment("Moved to %s" % moved_ref)
        issue.api.edit(state='close')  # we shouldn't process todos from closed issues.

    def _create_comments_backlog(self, issue):
        out = "### backlog comments of '%s' (%s)\n\n" % (issue.title, issue.url)

        for comment in issue.api.get_comments():
            if comment.body.find("!! move") != -1:
                continue
            date = j.data.time.any2HRDateTime(
                [comment.last_modified, comment.created_at])
            out += "from @%s at %s\n" % (comment.user.login, date)
            out += comment.body + "\n\n"
            out += "---\n\n"
        return out

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

    def _is_story(self, issue):
        return issue.type == 'story' or self._story_name(issue.title) is not None


    def _story_add_tasks(self, story, tasks):
        """
        If this issue is a story, add a link to a subtasks
        """

        if not self._is_story(story):
            j.exceptions.Input("This issue is not a story")
            return

        def state(s):
            s = s.lower()
            if s == 'closed':
                return 'x'
            else:
                return ' '

        doc = j.data.markdown.getDocument(story.body)
        # remove all list items that start with
        # also remove the progress bar
        for item in reversed(doc.items):
            if item.type == "block":
                if item.text.startswith("![Progress]"):
                    doc.items.pop()

            elif item.type == 'header':
                if item.title.startswith("Remaining Time:"):
                    doc.items.pop()
                # if item.type != 'list':
                #     break
            elif item.type == "list":
                if item.text.startswith('- ['):
                    doc.items.pop()



        for task in tasks:
            line = '- [%s] %s #%s' % (state(task.api.state), task.title, task.number)
            doc.addMDListItem(0, line)

        # drop the table for backward compatibility
        for item in doc.items:
            if item.type == 'table':
                break

                doc.items.remove(item)
        progress, remaining_time = self.calculate_story_progress(story, tasks)
        doc.addMDBlock("# Remaining Time: %sh" % remaining_time)
        doc.addMDBlock("![Progress](http://progressed.io/bar/%s)" % progress)
        body = str(doc)

        if body != story.body:
            story.api.edit(body=body)



    def calculate_story_progress(self, story, tasks):
        total_estimation = 0
        remaining_time = 0
        progress = 0
        done = 0

        for task in tasks:
            estimation = self._task_estimate(task.title)
            if estimation:
                m = re.match(r'(\d+)(\w)',estimation)
                if not m:
                    continue
                estimation_time = m.group(1)
                estimation_unit = m.group(2)
                if estimation_unit == 'd':
                    estimation_time = float(estimation_time) * 8
                total_estimation += int(estimation_time)
                if task.api.state == 'closed':
                    done += int(estimation_time)

                else:
                    remaining_time += int(estimation_time)
        if total_estimation:
            progress = (done*100) / total_estimation
        return (int(progress), remaining_time)

    def _task_link_to_story(self, story, task):
        """
        If this issue is a task from a story, add link in to the story in the description
        """

        body = task.body
        if body is None:
            body = ''

        doc = j.data.markdown.getDocument(body)

        change = False
        header = None
        for item in doc.items:
            if item.type == 'header' and item.level == 3 and item.title.find("Part of Story") != -1:
                header = item
                break

        if header is not None:
            title = 'Part of Story: #%s' % story.number
            if title != header.title:
                header.title = title
                change = True
        else:
            change = True
            doc.addMDHeader(3, 'Part of Story: #%s' % story.number)
            # make sure it's on the first line of the comment
            title = doc.items.pop(-1)
            doc.items.insert(0, title)

        if change:
            self.logger.info("%s: link to story:%s" % (task, story))
            task.body = str(doc)

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

    def _is_org_repo(self, name):
        """ Check if repo name starts with our supported initials """
        SUPPORTED_REPOS = ('org_', 'proj_')
        for typ in SUPPORTED_REPOS:
            if name.lower().startswith(typ):
                return True
        return False

    def _story_deadline(self, issue):
        eta, id = self._story_estimate(issue)
        try:
            return j.data.time.getEpochFuture(eta), id
        except:
            pass
        try:
            return j.data.time.any2epoch(eta), id
        except:
            pass

        return 0, id

    def _generate_views(self, repo, milestones, issues, report):
        # end for
        # process milestones

        def summary(ms):
            issues = report.get(ms, [])
            ts = 0
            for issue in issues:
                eta_stamp, _ = self._story_deadline(issue)
                if eta_stamp > ts:
                    ts = eta_stamp

            if ts:
                return j.data.time.epoch2HRDate(ts)
            else:
                return 'N/A'

        def state(s):
            if s == 'verification':
                return ':white_circle: Verification'
            elif s == 'inprogress':
                return ':large_blue_circle: In Progress'
            else:
                return ':red_circle: Open'

        def estimate(issue):
            eta, id = self._story_deadline(issue)
            if eta:
                return j.data.time.epoch2HRDate(eta), id
            return None, None

        view = MILESTONE_REPORT_TMP.render(repo=repo, report=report, milestones=milestones,
                                           summary=summary, state=state, estimate=estimate)

        repo.set_file(MILESTONE_REPORT_FILE, view)

        # group per user
        assignees = dict()
        for issue in issues:
            if not issue.assignee or not issue.isOpen:
                continue

            assignees.setdefault(issue.assignee, [])
            assignees[issue.assignee].append(issue)

        # sort the assignees dict.
        assignees = collections.OrderedDict(sorted([(k, v) for k, v in assignees.items()], key=lambda i: i[0]))

        # generate milestone details page
        for key, milestone in milestones.items():
            view = MILESTONE_DETAILS_TEMP.render(repo=repo, key=key, milestone=milestone,
                                                 issues=issues, assignees=assignees, state=state)
            repo.set_file("milestones/%s.md" % key, view)

        # assignee details page
        view = ASSIGNEE_REPORT_TMP.render(repo=repo, assignees=assignees, state=state)
        repo.set_file(ASSIGNEE_REPORT_FILE, view)

    @action()
    def pull(self, service):
        j.do.pullGitRepo(url=service.hrd.get("repo.url"), dest=service.hrd.get("code.path"), login=None, passwd=None, depth=1,
                         ignorelocalchanges=False, reset=False, branch=None, revision=None, ssh=True, executor=None, codeDir=None)

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

    def get_issues_from_ays(self, service):
        repo = self.get_github_repo(service)
        issues = []
        Issue = j.clients.github.getIssueClass()
        for child in service.children:
            if child.role != 'github_issue':
                continue
            issue = Issue(repo=repo, ddict=child.model)
            issues.append(issue)

        return issues

    def get_github_repo(self,service, repokey=None):
        githubclientays=service.getProducers('github_client')[0]
        client = githubclientays.actions.getGithubClient(service=githubclientays)
        if not repokey:
            repokey = service.hrd.get("repo.account") + "/" + service.hrd.get("repo.name")
        return client.getRepo(repokey)

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

    def stories2pdf(self, service):
        repo = self.get_github_repo(service)
        raise NotImplementedError()

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
