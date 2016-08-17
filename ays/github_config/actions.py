from JumpScale import j



class Actions(ActionsBaseMgmt):

    
    def init(self,service):

        config="""
        github.label.priority.critical: ['*']
        github.label.priority.minor: ['*']
        github.label.priority.normal: ['*']
        github.label.priority.urgent: ['*']
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
        github.label.type.assistance_request: [proj]
        github.label.type.question: [home, code, proj, ays, doc, cockpit, www,milestone,org]
        github.label.type.story: [home, proj, milestone,org]
        github.label.type.task: [home,milestone,proj,org]
        github.label.task.no_estimation: [home,milestone,proj,org]
        github.label.type.ticket: [proj,org]
        github.label.type.lead: [proj,org]
        github.project.types: [home, proj, cockpit, doc, ays, code, www, milestone,org]
        """


        j.data.text.strip(config)

        labels=j.data.serializer.yaml.loads(config)

        service.hrdCreate()
        service.hrd.setArgs(labels)

    def install(self,service):
        return True