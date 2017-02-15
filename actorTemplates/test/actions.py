def init_actions_(service, args):
    return {
        'test_devprocess': ['install']
    }

def test_devprocess(job):
    from github import Github
    service = job.service

    ## SETUP
    # CREATE org/code repo (PASS ALREADY SET IN THE BLUEPRINT)

    # CHECK LABELS SET (depending on the type of the repo)

    client = service.aysrepo.servicesFind(actor='github_client')[0]
    g = Github(client.model.data.githubSecret)
    githubclient = j.tools.devprocess.getGithubClient(service=client)

    ## get org repo

    orgrepo = None
    coderepo = None
    repos = service.aysrepo.servicesFind(actor="github_repo")

    orgreposv = service.aysrepo.serviceGet('github_repo', service.model.data.orgrepo)
    codereposv = service.aysrepo.serviceGet('github_repo', service.model.data.coderepo)

    # orgrepo_api = j.tools.devprocess.get_github_repo(orgrepo)
    # coderepo_api = j.tools.devprocess.get_github_repo(coderepo)

    orgrepo = g.get_repo(orgreposv.model.data.repoAccount+"/"+orgreposv.model.data.repoName)
    i0 = orgrepo.create_issue("my story (storykey)")
    i1 = orgrepo.create_issue("storykey: first issue [1h]")
    i2 = orgrepo.create_issue("storykey: second issue [2h]")
    i3 = orgrepo.create_issue("leaf issue")

    paginated_list = orgrepo.get_labels()
    first_page = paginated_list.get_page(0)

    lblfound = False
    for lbl in first_page:
        if lbl.name.split("_")[0] in ["customer", "type", "state"]:
            lblfound = True
            break #we got the label covered.

    errs = []
    try:
        assert lblfound == True
        print("Labels are set correctly.")
    except:
        errs.append("couldn't set labels.")
    j.tools.devprocess.process_issues(orgreposv, refresh=True)
    j.tools.devprocess.process_issues(codereposv, refresh=True)

    # get i0
    i0 = orgrepo.get_issue(i0.number)
    story_body = i0.body
    try:
        assert 'first issue' in story_body
    except:
        errs.append("first issue not in the story_body")
    try:
        assert 'second issue' in story_body
    except:
        errs.append("second issue not in the story_body")
    try:
        assert 'leaf issue' not in story_body
    except:
        errs.append("left issue in the story_body")
    try:
        assert "Remaining" in story_body
    except:
        errs.append("No remaining time in story body")
    try:
        assert "Progress" in story_body
    except:
        errs.append("not progress in the story_body")
    try:
        assert "Tasks" in story_body
    except:
        errs.append("No tasks the story_body")

    errstring = "Errors\n".join(errs)
    print(errstring)
    # make sure to check the labels



    # CREATE story > fix all bugs (fixbugs)     ### STORY TITLE (storykey)
    # create 3 issues in org repo (2 belongs to a story)  storykey: issue title, another regular one
    # CHECK IF 2 issues are linked in the story
    # CHECK URLS
    # CHECK IF 1 issue not linked in the story


    # CREATE story > fix all bugs (fixbugs)   ### STORY TITLE (storykey)
    # create 3 issues in org repo (2 belongs to a story with 1, 2 hours estimation)  storykey: issue title, another regular one
    # CHECK IF 2 issues are linked in the story
    # CHECK IF 1 issue not linked in the story
    # CHECK IF REMAINING TIME adds up to 3 hours


    # CHECK
