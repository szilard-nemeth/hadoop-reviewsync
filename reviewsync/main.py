#!/usr/bin/python

import argparse
import sys
import os
from jira_wrapper import JiraWrapper
from git_wrapper import GitWrapper
from os.path import expanduser

from attachment_utils import AttachmentUtils
from result_printer import ResultPrinter
from obj_utils import ObjUtils

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
  patches = jira_wrapper.get_patches_per_branch(issue_id, branches)
  print "ALL PATCHES: " + str(patches)
  
  for patch in patches:
    if patch.applicable:
      jira_wrapper.download_patch_file(patch)
    else:
      print "Skipping download of non-applicable patch: %s" % patch
  
  return patches

def _convert_data_to_result_printer(results):
  data = []
  headers = ["Issue", "Owner", "Patch file", "Branch", "Result"]
  for issue_id, patch_applies in results.iteritems():
    print "PATCH APPLIES: " + str(patch_applies)
    for patch_apply in patch_applies:
      data.append([issue_id, patch.owner_display_name, patch.filename, patch_apply.branch, patch_apply.result])
      
  return data, headers

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
  
  print "Jira issues will be checked: %s" % issues
  print "Branches: %s" % branches

  git_wrapper = GitWrapper(git_root)
  #TODO
  git_wrapper.sync_hadoop(fetch=False)
  git_wrapper.validate_branches(branches)
  
  patches_root = os.path.join(reviewsync_root, "patches")
  jira_wrapper = JiraWrapper(JIRA_URL, DEFAULT_BRANCH, patches_root)
  
  # key: jira issue ID
  # value: list of PatchApply objects
  # For non-appliable patches (e.g. jira is already Resolved, patch object is None)
  results = {}
  for issue_id in issues:
    patches = download_latest_patches(issue_id, jira_wrapper, branches)
    if len(patches) == 0:
      print "Patches found for jira issue %s was 0!" % issue_id
      continue
    
    print "Patches: %s" % patches

    for patch in patches:
      patch_applies = git_wrapper.apply_patch(patch)
      if patch.issue_id not in results:
        results[patch.issue_id] = []
      results[patch.issue_id] += patch_applies
  print "Overall results: " + str(results)

  data, headers = _convert_data_to_result_printer(results)
  result_printer = ResultPrinter(data, headers)
  result_printer.print_table()
