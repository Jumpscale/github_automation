def init(job):
    service = job.service
    # github_product__p1:
    #   repos:
    #     - orgrepo
    #     - coderepo
    #   milestones:
    #     - 810
    #     - 820
    #

    # BATCH CONSUME MILESTONES.
    githubmilestone_actor = service.aysrepo.actorGet('github_milestone')
    for repo in service.model.data.repos:
        reposv = service.aysrepo.serviceGet("github_repo", repo)
        for m in service.model.data.milestones:
            msv = service.aysrepo.serviceGet("github_milestone", m)
            reposv.consume(msv)
        reposv.saveAll()
