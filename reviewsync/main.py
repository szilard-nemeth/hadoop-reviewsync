#!/usr/bin/python

import argparse
import sys
import os
from jira_wrapper import JiraWrapper
from git_wrapper import GitWrapper
from os.path import expanduser

from attachment_utils import AttachmentUtils

__author__ = 'Jason Vasquez Orona'


def get_args():
  """This function parses and return arguments passed in"""
  
  parser = argparse.ArgumentParser(
    description='Script retrieves patches for specified jiras and generates input file for conflict checker script')
  
  parser.add_argument(
    '-i', '--issues', nargs='+', type=str, help='List of jira issues to check', required=True)
  # parser.add_argument(
  #   '-j', '--jira-url', type=str, help='URL of jira to check', required=True)
  args = parser.parse_args()
  
  issues = args.issues
  
  #hardcode the jira URL for now
  jira_url = "https://issues.apache.org/jira"
  # jira_url = args.jira_url
  return jira_url, issues


def download_latest_patches(issue_id):
  status = jira_wrapper.get_status(issue_id)
  if status == "Resolved":
    print "Status of jira should not be resolved: %s" % issue_id
    return []
  
  all_patches = jira_wrapper.get_attachments_per_branch(issue_id)
  patches = AttachmentUtils.get_latest_patches_per_branch(all_patches)
  
  for branch, patch in patches.iteritems():
    jira_wrapper.download_attachment(patch)

  return [patch for patch in patches.values()]


if __name__ == '__main__':
  # print "sys.path is:"
  # print '\n'.join(sys.path)

  home = expanduser("~")
  reviewsync_root = os.path.join(home, "reviewsync")

  git_root = os.path.join(reviewsync_root, "repos")
  git_wrapper = GitWrapper(git_root)
  git_wrapper.sync_hadoop()


  jira_url, issues = get_args()
  print "Jira isssues will be checked: %s" % issues
  patches_root = os.path.join(reviewsync_root, "patches")
  jira_wrapper = JiraWrapper(jira_url, patches_root)
  
  # key: issue ID
  # value: list of tuples of (patch object, result as bool)
  results = {}
  for issue_id in issues:
    patches = download_latest_patches(issue_id)
    if len(patches) == 0:
      print "Patches found for jira issue %s was 0!" % issue_id
      continue
    
    print "Patches: %s" % patches

    results[issue_id] = []
    for patch in patches:
      success = git_wrapper.apply_patch(patch)
      results[patch.issue_id].append((patch, success))
  
  print "Overall results: " + str(results)
