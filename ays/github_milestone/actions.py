from JumpScale import j


class Actions(ActionsBaseMgmt):
    def input(self,service,recipe,role,instance,args={}):
        if "milestone.title" not in args:
            args['milestone.title']=instance

        return args