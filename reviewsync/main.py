#!/usr/bin/python

import argparse
import sys
import os
from jira_wrapper import JiraWrapper
from git_wrapper import GitWrapper
from os.path import expanduser

from attachment_utils import AttachmentUtils

DEFAULT_BRANCH = "trunk"
JIRA_URL = "https://issues.apache.org/jira"

__author__ = 'Jason Vasquez Orona'


def get_args():
  """This function parses and return arguments passed in"""
  
  parser = argparse.ArgumentParser(
    description='Script retrieves patches for specified jiras and generates input file for conflict checker script')
  
  parser.add_argument(
    '-i', '--issues', nargs='+', type=str, help='List of jira issues to check', required=True)
  parser.add_argument(
    '-b', '--branches', nargs='+', type=str, 
    help='List of branches to apply patches that are targeted to trunk (default is trunk only)', required=False)
  # parser.add_argument(
  #   '-j', '--jira-url', type=str, help='URL of jira to check', required=True)
  args = parser.parse_args()
  return args

def download_latest_patches(issue_id, jira_wrapper, branches):
  status = jira_wrapper.get_status(issue_id)
  if status == "Resolved":
    print "Status of jira should not be resolved: %s" % issue_id
    return []
  
  patches = jira_wrapper.get_patches_per_branch(issue_id, branches)
  print "ALL PATCHES: " + str(patches)
  
  downloaded = set()
  for patch in patches:
    if patch.filename not in downloaded:
      jira_wrapper.download_patch_file(patch)
    downloaded.add(patch.filename)
  
  return patches

if __name__ == '__main__':
  # print "sys.path is:"
  # print '\n'.join(sys.path)

  home = expanduser("~")
  reviewsync_root = os.path.join(home, "reviewsync")
  git_root = os.path.join(reviewsync_root, "repos")

  # Parse args
  args = get_args()
  issues = args.issues
  branches = [DEFAULT_BRANCH]
  if args.branches and len(args.branches) > 0:
    if DEFAULT_BRANCH in args.branches:
      args.branches.remove(DEFAULT_BRANCH)
    branches = branches + args.branches
  
  print "Jira isssues will be checked: %s" % issues
  print "Branches: %s" % branches

  git_wrapper = GitWrapper(git_root)
  git_wrapper.sync_hadoop()
  git_wrapper.validate_branches(branches)
  
  patches_root = os.path.join(reviewsync_root, "patches")
  jira_wrapper = JiraWrapper(JIRA_URL, DEFAULT_BRANCH, patches_root)
  
  # key: issue ID
  # value: list of tuples of (patch object, result as bool)
  results = {}
  for issue_id in issues:
    patches = download_latest_patches(issue_id, jira_wrapper, branches)
    if len(patches) == 0:
      print "Patches found for jira issue %s was 0!" % issue_id
      continue
    
    print "Patches: %s" % patches

    results[issue_id] = {}
    for patch in patches:
      patch_apply = git_wrapper.apply_patch(patch)
      if not results[patch.issue_id]:
        results[patch.issue_id] = []
      results[patch.issue_id].append((patch_apply))
  
  print "Overall results: " + str(results)
