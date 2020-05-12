#!/usr/bin/python3

import os
import sys
import simplejson
from urllib.request import urlopen, Request
import subprocess
from time import gmtime, strftime

def call(*args, env=os.environ):
    return subprocess.check_call(list(args), env=env)

def call_output(*args, env=os.environ):
    return subprocess.check_output(list(args), env=env)

def dbg(*args, **kwargs):
    print(*args, **kwargs)
    sys.stdout.flush()

def parse_repo_url(url):
  repo_user = repository.split(':')[1].split('.')[0].split('/')[0]
  repo_name = repository.split(':')[1].split('.')[0].split('/')[1]
  return repo_user, repo_name

def get_pull_requests(repository, tag_name, token):
  repo_user, repo_name = parse_repo_url(repository)
  if "github" in repository:
    return get_pull_requests_github(repo_user, repo_name, tag_name, token)
  elif "gitlab.nymea.io" in repository:
    return get_pull_requests_gitlab(repo_user, repo_name, tag_name, token)

def get_pull_requests_github(repo_user, repo_name, tag_name, token):
  request = Request("http://api.github.com/repos/%s/%s/pulls" % (repo_user, repo_name))
  request.add_header('Authorization', "token %s" % token)
  pull_requests_data = simplejson.load(urlopen(request))
  pull_requests = []
  users_cache = {}
  for pull_request_data in pull_requests_data:
    for label in pull_request_data["labels"]:
      if label["name"] == tag_name:
        pull_request = {}
        pull_request["branch_name"] = pull_request_data["head"]["ref"]
        pull_request["title"] = pull_request_data["title"]
        pull_request["number"] = pull_request_data["number"]
        comitter_user = pull_request_data["user"]["login"]
        if comitter_user not in users_cache:
          user_data = simplejson.load(urlopen(pull_request_data["user"]["url"]))
          comitter_name = user_data["name"]
          users_cache[comitter_user] = comitter_name
        pull_request["author"] = users_cache[comitter_user]
        pull_requests.insert(0, pull_request)
        break
  return pull_requests

def get_pull_requests_gitlab(repo_user, repo_name, tag_name, token):
  projects_data = simplejson.load(urlopen("https://gitlab.nymea.io/api/v4/projects?private_token=%s&simple=true&search=%s" % (token, repo_name)))
  project_id = -1;
  #print("data: %s" % projects_data)
  for project_data in projects_data:
    if project_data["path_with_namespace"] == "%s/%s" % (repo_user, repo_name):
      project_id = project_data["id"]
      break
  if project_id == -1:
    print("E: Could not find repository %s/%s" % (repo_user, repo_name))
    exit(1)

  pull_requests = []
  merges_data = simplejson.load(urlopen("https://gitlab.nymea.io/api/v4/projects/%s/merge_requests?private_token=%s&labels=%s&state=opened" % (project_id, token, tag_name)))
  for merge_data in merges_data:
    pull_request = {}
    pull_request["branch_name"] = merge_data["source_branch"]
    pull_request["title"] = merge_data["title"]
    pull_request["number"] = merge_data["iid"]
    pull_request["author"] = merge_data["author"]["name"]
    pull_requests.insert(0, pull_request)
  return pull_requests

args = sys.argv
if len(args) < 2:
  dbg("usage: %s <repo> <tag> [--rebuild] [token]" % args[0])
  exit(1)

repository = args[1]
silo_name = "%s-silo" % args[2]
tag_name = args[2]
token = ""
force_rebuild = 0
if len(args) > 3:
  if args[3] == "--rebuild":
    force_rebuild = 1
    if len(args) > 4:
      token = args[4]
  else:
    token = args[3]

dbg("I: Preparing silo \"%s\" using tag \"%s\" for repository \"%s\"" % (silo_name, tag_name, repository))
repo_user, repo_name = parse_repo_url(repository)

pull_requests = get_pull_requests(repository, tag_name, token)

if len(pull_requests) == 0 and not force_rebuild:
  dbg("W: No pull requests with tag \"%s\" found for %s." % (tag_name, repository))
  exit(2)

call("rm", "-rf", "%s" % repo_name)
call("git", "clone", repository, repo_name)
os.chdir(repo_name)
call("git", "checkout", "-b", silo_name)

for pull_request in pull_requests:
  pr_number = pull_request["number"]
  pr_title = pull_request["title"]
  branch_name = pull_request["branch_name"]
  commit_msg = "Merge PR #%i: %s" % (pr_number, pr_title)
  dbg("I: %s (branch: %s)" % (commit_msg, branch_name))
  call("git", "merge", "--no-ff", ("origin/%s" % branch_name), "-m", commit_msg)

#  call("dch", "-i", "-U", "Prepare for release")

if os.path.isfile("debian/changelog"):
  for pull_request in pull_requests:
    author = pull_request["author"]
    pr_title = pull_request["title"]
    env_override = os.environ.copy()
    env_override["DEBFULLNAME"] = author
    call("dch", "-U", pr_title, env=env_override)

  # Finalize release
  version = call_output("dpkg-parsechangelog", "--show-field", "version").decode('UTF-8')
  call("dch", "-r", "")
  call("git", "commit", "-am", "Jenkins release build %s" % version)

  merge_result = subprocess.call(["git", "diff", "HEAD^", "origin/%s^" % silo_name, "--exit-code", "--quiet"])
else:
  merge_result = subprocess.call(["git", "diff", "HEAD", "origin/%s" % silo_name, "--exit-code", "--quiet"])

if merge_result == 0:
  print("I: No changes since last build. Nothing to do...")
  os.chdir("..")
  exit(3);
else:
  print("There are changes. Rebuild required")
  call("git", "push", "origin", silo_name, "-f")

os.chdir("..")
exit(0)
