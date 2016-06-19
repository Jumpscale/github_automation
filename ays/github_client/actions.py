
class Actions(ActionsBaseMgmt):

    def install(self,service):
        self.monitor(service=service)

    def monitor(self,service):
        g=self.getGithubClient(service=service)
        #@todo implement test

    def getGithubClient(self,service):
        g=j.clients.github.getClient(service.hrd.get("github.secret"))        
        return g

    @action()
    def test(self,service):
        print ("test")

    @action()
    def test2(self,service):
        print ("test2")        
        print ("$(github.secret)")        

    @action(queue="main")
    def testasync(self,service):
        print ("testasync")        
        print ("$(github.secret)")                