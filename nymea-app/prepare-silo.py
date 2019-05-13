#!/usr/bin/python3

import os
import sys
import simplejson
from urllib.request import urlopen
import subprocess

def call(*args, env=os.environ):
    return subprocess.check_call(list(args), env=env)

args = sys.argv
if len(args) < 2:
  print("usage: %s tag" % args[0])
  exit(1)

silo_name = "%s-silo" %args[1]
tag_name = args[1]

print("I: Preparing silo \"%s\" using tag \"%s\"" % (silo_name, tag_name))

changelog = open("changelog.txt", "a")
changelog.truncate(0)

repository = "git@github.com:guh/nymea-app.git"
repo_user = repository.split(':')[1].split('.')[0].split('/')[0]
repo_name = repository.split(':')[1].split('.')[0].split('/')[1]
print("I: Preparing silo for repository: %s (%s/%s)" % (repository, repo_user, repo_name))

pull_requests_data = simplejson.load(urlopen("http://api.github.com/repos/%s/%s/pulls" % (repo_user, repo_name)))
pull_requests = []
for pull_request_data in pull_requests_data:
  if len(pull_request_data["labels"]) > 0 and pull_request_data["labels"][0]["name"] == tag_name:
    pull_requests.append(pull_request_data)

if len(pull_requests) == 0:
  print("W: No pull requests with tag \"%s\" found for %s. Rebuilding master." % (tag_name, repository))

call("git", "clone", repository, repo_name)
os.chdir(repo_name)
call("git", "checkout", "-b", silo_name)

users_names = {}
users_commits = {}

for pull_request in pull_requests:
  branch_name = pull_request["head"]["ref"]
  pr_title = pull_request["title"]
  pr_number = pull_request["number"]
  user_id = pull_request["user"]["login"]
  # Fetch user name if we don't have it yet
  if user_id not in users_names:
    user_data = simplejson.load(urlopen(pull_request["user"]["url"]))
    user_name = user_data["name"]
    users_names[user_id] = user_name
    users_commits[user_id] = []

  commit_msg = "Merge PR #%i: %s" % (pr_number, pr_title)
  print("I: %s" % (commit_msg))
  call("git", "merge", "--no-ff", ("origin/%s" % branch_name), "-m", commit_msg)
  users_commits[user_id].append(pr_title)

for user_id in users_names:
#  changelog.write("%s:\n" % users_names[user_id])
  for commit in users_commits[user_id]:
    changelog.write("* %s\n" % commit)

changelog.close()

# Disabled because lupdate on xenial can't parse qtquick.controls2 yet
#call("lupdate", "nymea-app.pro")
#call("git", "commit", "-am", "Jenkins translations update")

versionfile = open("version.txt", "r")
oldversion = versionfile.readlines()
versionfile.close()
major_version = int(oldversion[0].split(".")[0])
minor_version = int(oldversion[0].split(".")[1])
patch_version = int(oldversion[0].split(".")[2].rstrip("\n"))
revision = int(oldversion[1].rstrip("\n"))
print("Old version: %s.%s.%s (%s)" % (major_version, minor_version, patch_version, revision))
patch_version += 1
revision += 1
print("New version: %s.%s.%s (%s)" % (major_version, minor_version, patch_version, revision))
versionfile = open("version.txt", "w")
versionfile.truncate(0)
versionfile.write("%s.%s.%s\n" % (major_version, minor_version, patch_version))
versionfile.write("%s\n" % revision)
versionfile.close()


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
#   call("dch", "-a", pr_title, env=env_override)
  call("dch", "-v", ("%s.%s.%s" % (major_version, minor_version, patch_version)), "-U", pr_title, env=env_override)

call("dch", "--distribution", "bionic", "-r", "")

call("git", "commit", "-am", "Jenkins automated build %s.%s.%s (%s)" % (major_version, minor_version, patch_version, revision))
call("git", "push", "origin", silo_name, "-f")
os.chdir("..")

