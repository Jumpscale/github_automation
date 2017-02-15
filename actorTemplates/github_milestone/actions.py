from JumpScale import j


def input(job):
    args = job.model.args
    service = job.service

    if 'milestone.title' not in args:
        args['milestrone.title'] = service.name
