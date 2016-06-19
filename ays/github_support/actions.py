from JumpScale import j


class Actions(ActionsBaseMgmt):

#     def notify_telegram(self, ticket_url):
#         evt = j.data.models.cockpit_event.Telegram()
#         evt.io = 'output'
#         evt.args['chat_id'] =
#         msg = """*New support ticket received*
# Link to ticket: {url}
#         """.format(url=ticket_url)
#         evt.args['msg'] = msg
#         self.bot.sendMessage(chat_id=chat_id, text=msg, parse_mode=telegram.ParseMode.MARKDOWN)

    @action()
    def from_github_ticket(self, service, event):
        event = j.data.models.cockpit_event.Generic.from_json(event)

        if 'source' not in event.args or event.args['source'] != 'github':
            return

        if 'key' not in event.args:
            print("bad format of event")
            return
        key = event.args['key']
        data = j.core.db.hget('webhooks', event.args['key'])
        event_type = event.args['event']
        github_payload = j.data.serializer.json.loads(data)
        if event_type != 'issues':
            return
        action = github_payload['action']

        if action == 'opened':

            account = github_payload['repository']['owner']['login']
            name = github_payload['repository']['name']

            repo_service = None
            for s in service.producers['github_repo']:
                if name == s.hrd.getStr('repo.name') and account == s.hrd.getStr('repo.account'):
                    repo_service = s
                    break

            if repo_service is None:
                print("targeted repo is not monitored by this service.")
                # TODO, send email back to client to tell him
                return

            repo = repo_service.actions.get_github_repo(repo_service)
            issue = repo.getIssue(github_payload['issue']['number'])
            if issue.body.startswith('Ticket_'):
                # already processed
                # delete issue from redis
                j.core.db.hdel('webhooks', key)
                return

            # allocation of a unique ID to the Ticket
            guid = j.data.idgenerator.generateGUID()
            # Add ticket id in issue description
            issue.body = "Ticket_%s\n\n%s" % (guid, issue.body)
            # add labels to issue
            labels = issue.labels.copy()
            if 'type_assistance_request' not in labels:
                labels.append('type_assistance_request')
                issue.labels = labels
            # creation of the issue in the github repo
            repo.issues.append(issue)
            # Create issue service instance of the newly created github issue
            args = {'github.repo': repo_service.instance}
            issue_service = service.aysrepo.new(name='github_issue', instance=str(issue.id), args=args, model=issue.ddict)

            # delete issue from redis when processed
            j.core.db.hdel('webhooks', key)
            self.escalate_issue(service, issue)

    @action()
    def from_email_ticket(self,service, event):
        email = j.data.models.cockpit_event.Email.from_json(event)
        repos_ays = service.producers['github_repo']
        mail_service = service.getProducers('mailclient')[0]
        email_sender = mail_service.actions.getSender(mail_service)
        for repo in repos_ays:
            if email.sender in repo.hrd.getList("repo.emails", []):
                repo_service = repo
                service.logger.info('email from known emails')
                break
        else:
            service.logger.info('can not identify email')
            email_sender.send(email.sender,
                              mail_service.hrd.getStr("smtp.sender"),
                              "Your email is not linked",
                              "Hi, We received your email (%s) but this email is not linked to any repo" % email.subject)
            return
        if not email.subject.startswith('(Ticket)'):
            # this mail doesn't concerne us
            return
        Issue = j.clients.github.getIssueClass()
        repo = repo_service.actions.get_github_repo(repo_service)
        # allocation of a unique ID to the Ticket
        guid = j.data.idgenerator.generateGUID()
        # Add ticket id in issue description
        body = "Ticket_%s\n\n" % guid
        body += email.body
        # creation of the issue in the github repo
        issue_obj = repo.api.create_issue(email.subject, body=body, labels=['type_assistance_request'])
        issue = Issue(repo=repo, githubObj=issue_obj)
        repo.issues.append(issue)
        # Create issue service instance of the newly created github issue
        args = {'github.repo': repo_service.instance}
        github_issue_service = service.aysrepo.new(name='github_issue', instance=str(issue.id), args=args, model=issue.ddict)

        self.escalate_issue(service, issue, email.sender)


    def get_oncall_username(self, oncall_sheet, name):
        team_sheet = oncall_sheet.worksheet('Team')
        oncall_eng_cell = team_sheet.find(name)
        username = team_sheet.cell(oncall_eng_cell.row, oncall_eng_cell.col+2).value
        return username

    def get_oncall_name(self, oncall_sheet):
        import datetime
        import calendar
        worksheets = oncall_sheet.worksheets()
        now = datetime.datetime.now()
        month_name = calendar.month_name[now.month]
        month = now.month
        hour = now.hour
        day = now.day
        year = now.year
        worksheet = None
        for wsheet in worksheets:
            if wsheet.title.lower() == month_name.lower():
                worksheet = wsheet
                break
        else:
             raise j.exceptions.NotFound("No sheets found for this month")

        day_cell = worksheet.find("%s/%s/%s" % (month, day, year))

        if hour in [i for i in range(0, 8)]:
            col = day_cell.col + 1
        elif hour in [i for i in range(8, 17)]:
            col = day_cell.col + 2
        else:
            col = day_cell.col + 3
        oncall_name = worksheet.cell(day_cell.row, col).value
        backup = worksheet.cell(day_cell.row, day_cell.col+4).value
        return oncall_name, backup

    def get_oncall_contact(self, oncall_sheet, username):
        team_sheet = oncall_sheet.worksheet('Team')
        username_cell = team_sheet.find(username)
        email = team_sheet.cell(username_cell.row, username_cell.col+1).value
        phone = team_sheet.cell(username_cell.row, username_cell.col-1).value
        return email, phone

    def get_username_by_role(self, oncall_sheet, role):
        team_sheet = oncall_sheet.worksheet('Team')
        role_cell = team_sheet.find(role)
        username = team_sheet.cell(role_cell.row, role.col-2).value
        return username

    def escalate_issue(self, service, issue, sender_email=None):
        import random
        import gspread
        from oauth2client.service_account import ServiceAccountCredentials
        if sender_email:
            mail_service = service.getProducers('mailclient')[0]
            email_sender = mail_service.actions.getSender(mail_service)
        scope = ['https://spreadsheets.google.com/feeds']
        service_key_path = service.hrd.getStr("service_key_path", None)
        if not service_key_path:
            return
        credentials = ServiceAccountCredentials.from_json_keyfile_name(service_key_path, scope)
        gc = gspread.authorize(credentials)
        oncall_sheet = gc.open("On-Call Sheet")
        try:
            oncall_name, backup = self.get_oncall_name(oncall_sheet)
        except:
            service.logger.error("No sheet found for this month")
            return
        usernames = self.get_oncall_username(oncall_sheet, oncall_name).split(",")
        email_body_template = """

            "Hi,
            We received your email and your issue is created\n
            for any questions you can follow up with our on call engineer \n
            telegram: {telegram_username}\n
            email : {email}\n
            phone: {phone}"
            """
        try:
            username = random.choice(usernames)
            self.ask_telegram(username, "issue created %s" % issue.url, [], True, 900, None)
            service.logger.info("%s got the issue" % username)
            if sender_email:
                email, phone = self.get_oncall_contact(oncall_sheet, username)
                email_sender.send(sender_email,
                                  mail_service.hrd.getStr("smtp.sender"),
                                  "Issue Created",
                                  email_body_template.format(telegram_username=username,
                                                             phone=phone,
                                                             email=email))

        except j.exceptions.Timeout:

            service.logger.info("No one get the issue sending to backup on call engineer")
            # the on call engineer didn't get the issue,send to backup on call
            username = self.get_oncall_username(oncall_sheet, backup)
            email, phone = self.get_oncall_contact(oncall_sheet, username)
            try:
                self.ask_telegram(username, "issue created %s" % issue.url, [], True, 900, None)
                service.logger.info("%s got the issue" % username)
                if sender_email:
                    email_sender.send(sender_email,
                                  mail_service.hrd.getStr("smtp.sender"),
                                  "Issue Created",
                                  email_body_template.format(telegram_username=username,
                                                             phone=phone,
                                                             email=email))
            except j.exceptions.Timeout:
                try:
                    support_manager = self.get_username_by_role(oncall_sheet, "SM")
                    self.ask_telegram(support_manager, "Issue Created %s and no on-call engineer got it" % issue.url, [], True, 900, None)
                    service.logger.info("support manager got the issue")
                    if sender_email:
                        email_sender.send(sender_email,
                                  mail_service.hrd.getStr("smtp.sender"),
                                  "Issue Created",
                                  email_body_template.format(telegram_username=support_manager,
                                                             phone=phone,
                                                             email=email))
                except:
                    coo = self.get_username_by_role(oncall_sheet, "COO")
                    service.logger.info("Issue escalated to the COO")
                    self.ask_telegram(coo, "issue created %s and no on-call engineers" % issue.url, [], True, 900, None)
