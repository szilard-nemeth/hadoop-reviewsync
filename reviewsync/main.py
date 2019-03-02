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


def download_latest_patches():
  all_patches = jira_wrapper.get_attachments_per_branch(i)
  patches = AttachmentUtils.get_latest_patches_per_branch(all_patches)
  
  for branch, patch in patches.iteritems():
    jira_wrapper.download_attachment(patch)


if __name__ == '__main__':
  # print "sys.path is:"
  # print '\n'.join(sys.path)

  home = expanduser("~")
  reviewsync_root = os.path.join(home, "reviewsync")

  git_root = os.path.join(reviewsync_root, "repos")
  git_wrapper = GitWrapper(git_root)
  git_wrapper.sync_hadoop()


  jira_url, issues = get_args()
  print "Jira URL: %s" % jira_url
  print "Issues: %s" % issues
  patches_root = os.path.join(reviewsync_root, "patches")
  jira_wrapper = JiraWrapper(jira_url, patches_root)
  
  for i in issues:
    download_latest_patches()
