from JumpScale import j



class Actions(ActionsBaseMgmt):


    def init(self,service):

        config="""
        github.label.priority.critical: ['*']
        github.label.priority.minor: ['*']
        github.label.priority.major: ['*']
        github.label.process.duplicate: ['*']
        github.label.process.wontfix: ['*']
        github.label.state.inprogress: ['*']
        github.label.state.planned: ['*']
        github.label.state.question: ['*']
        github.label.state.verification: ['*']
        github.label.state.ready: ['org']
        github.label.type.bug: [code, ays, cockpit, doc, www]
        github.label.type.feature: [code, ays, cockpit, doc, www]
        github.label.type.monitor: [proj, www, cockpit]
        github.label.type.assistance_request: [proj, env]
        github.label.type.question: [home, code, proj, ays, doc, cockpit, www,milestone,org, env]
        github.label.type.story: [home, proj, milestone,org, env]
        github.label.type.task: [home,milestone,proj,org]
        github.label.task.no_estimation: [home,milestone,proj,org, env]
        github.label.type.ticket: [proj,org, code, env]
        github.label.type.lead: [proj,org, env]
        github.label.customer.centrilogic: ['*']
        github.label.customer.LCI.Mauritius: ['*']
        github.project.types: [home, proj, cockpit, doc, ays, code, www, milestone,org, env]
        """


        j.data.text.strip(config)

        labels=j.data.serializer.yaml.loads(config)

        service.hrdCreate()
        service.hrd.setArgs(labels)

    def install(self,service):
        return True
