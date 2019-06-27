#!/usr/bin/python3

import os
import sys
import simplejson
from urllib.request import urlopen
import subprocess
from time import gmtime, strftime

def call(*args, env=os.environ):
    return subprocess.check_call(list(args), env=env)

def call_output(*args, env=os.environ):
    return subprocess.check_output(list(args), env=env)

def dbg(*args, **kwargs):
    print(*args, **kwargs)
    sys.stdout.flush()

args = sys.argv
if len(args) < 3:
  dbg("usage: %s <tag> <repo1> ..." % args[0])
  exit(1)

silo_name = "%s-silo" % args[1]
tag_name = args[1]
repository = args[2]

dbg("I: Preparing silo \"%s\" using tag \"%s\"" % (silo_name, tag_name))

dbg("I: Working on repository: %s" % repository)
repo_user = repository.split(':')[1].split('.')[0].split('/')[0]
repo_name = repository.split(':')[1].split('.')[0].split('/')[1]
dbg("I: Preparing silo for repository: %s (%s/%s)" % (repository, repo_user, repo_name))
pull_requests_data = simplejson.load(urlopen("http://api.github.com/repos/%s/%s/pulls" % (repo_user, repo_name)))
pull_requests = []
for pull_request_data in pull_requests_data:
  for label in pull_request_data["labels"]:
    if label["name"] == tag_name:
      pull_requests.insert(0, pull_request_data)
      break

if len(pull_requests) == 0:
  dbg("W: No pull requests with tag \"%s\" found for %s." % (tag_name, repository))
  exit(2)

call("git", "clone", repository, repo_name)
os.chdir(repo_name)
call("git", "checkout", "-b", silo_name)

for pull_request in pull_requests:
  branch_name = pull_request["head"]["ref"]
  pr_title = pull_request["title"]
  pr_number = pull_request["number"]
  commit_msg = "Merge PR #%i: %s" % (pr_number, pr_title)
  dbg("I: %s (branch: %s)" % (commit_msg, branch_name))
  call("git", "merge", "--no-ff", ("origin/%s" % branch_name), "-m", commit_msg)

#  call("dch", "-i", "-U", "Prepare for release")

users_cache = {}
for pull_request in pull_requests:
  comitter_user = pull_request["user"]["login"]
  if comitter_user not in users_cache:
    user_data = simplejson.load(urlopen(pull_request["user"]["url"]))
    comitter_name = user_data["name"]
    users_cache[comitter_user] = comitter_name

  pr_title = pull_request["title"]
  env_override = os.environ.copy()
  env_override["DEBFULLNAME"] = users_cache[comitter_user]
  call("dch", "-U", pr_title, env=env_override)

# Finalize release
call("dch", "-r", "")
call("git", "commit", "-am", "Jenkins release build")
call("git", "push", "origin", silo_name, "-f")
os.chdir("..")

