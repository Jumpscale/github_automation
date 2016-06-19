from JumpScale import j


class Actions(ActionsBaseMgmt):

    def init(self,service):
        return True

    def install(self,service):
        self.monitor()

    def monitor(self,service):
        g=self.getGithubClient(service=service)
        #@todo implement test

    def getGithubClient(self, service):
        g=j.clients.github.getClient(service.hrd.get("github.secret"))
        return g
