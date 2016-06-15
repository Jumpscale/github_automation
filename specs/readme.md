 tasks

## intro

 - how to schedule recurring tasks
     - as method on ays actions which can be scheduled

## recurring actions

### check_timing

 - run this every morning 8am and lunch 12am
 - go over all stories in the repo (only deal with stories for now!)
 - if story in progress or in validation state or in question state then
     - check there is owner filled in if not on telegram on cockpit warn there is an owner missing
     - check that there is estimate remaining time filled in, if not send email to owner of the story
     - check milestone has been attached and milestone end date < 2 months from now
     - check time between now & milestone date (in working days): if estimate time > 80% of remaining time send warning to owner (email or telegram)
     - check time between now & milestone date (in working days): if estimate time deadline: send warning message to owner (email/telegram) and to cockpit telegram window

### fix issues for tasks

 - once a day walk over all repos/issues
 - fix them : milestones, labels, subtasks of stories, ...
 - report on cockpit telegram

## portal macro's

### overview milestones

 - is wikimacro: milestones()
 - list known milestones in table, sort on deadline
 - only list milestones which have stories underneath
 - per milestone do link to developers_milestone($milestonename)

### overview developers per milestone

 - is wikimacro: developers_milestone($milestonename)
 - developers should be known as aysi in the repo (could be does not exist yet)
     - each developer linked to his itsyou.online account
 - list the developers in table per milestone
     - per developer list
         - nr of stories they own
         - nr of tasks they own
         - remaining time on sum of all tasks
 - this will give overview on how developers/owners are doing in relation to specific milestone
 - per developer link to report_developer($milestone,$loginname)

### report_developer($milestone,$loginname)

 - is wikimacro
 - go over stories & tasks (is in mem because is in gevent)
 - only for stories and tasks of stories which are in progress/validation/question state
     - in other words ignore tasks which belong to story which does not apply to rule above
 - report
     - sorted on prio the stories (put content of story in, & link to story page)
     - per story report the tasks again sorted on prio
 - goal is that people have a nice overview of all work related to them in 1 page

### basic wiki pages

 - to use the macro's and show this info

## remarks

### recurring

 - if recurring e.g. 8am & 12am
     - do recurring action every hour, then check if morning or lunch, otherwise skip

### itsyou.online integration

 - full authentication to cockpit should be from itsyou.online
 - there should be api which can be used by cockpit to get info from users
     - ```cockpit_gig_development``` should be organization in itsyou.online
     - everyone using the cockpit should be in this org (only the mgrs)
     - there should be other org ```org_gig_development``` in which we have all developers
     - the cockpit can access basic info exposed from all users to these orgs through the rest api in the cockpit
     - basic info is email addr, telegram, mobile nr(s)
     - connection to itsyou.online should happen through a jumpscale client which is configured through ays (like we do to e.g. github)
 - users can administer their own info through rogerthat
 - this is required because this will allow cockpit to fetch appropriate info about user to be able to contact user e.g sms, telegram, ...
