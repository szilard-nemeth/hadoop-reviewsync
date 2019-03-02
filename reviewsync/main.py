#!/usr/bin/python

import argparse
import sys
from jira_wrapper import JiraWrapper

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


if __name__ == '__main__':
  # print "sys.path is:"
  # print '\n'.join(sys.path)

  jira_url, issues = get_args()
  print "Jira URL: %s" % jira_url
  print "Issues: %s" % issues
  jira_wrapper = JiraWrapper(jira_url)
  
  for i in issues:
    jira_wrapper.list_attachments(i)
    jira_wrapper.get_latest_attachments_per_branch(i)