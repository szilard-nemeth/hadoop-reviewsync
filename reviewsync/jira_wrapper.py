from jira import JIRA
import re
import logging

LOG = logging.getLogger(__name__)


class JiraWrapper:
  def __init__(self, jira_url):
    options = { 'server': jira_url}
    self.jira = JIRA(options)
    
  def list_attachments(self, issue_id):
    issue = self.jira.issue(issue_id)

    for attachment in issue.fields.attachment:
      print("Name: '{filename}', size: {size}".format(
        filename=attachment.filename, size=attachment.size))
      # to read content use `get` method:
      # print("Content: '{}'".format(attachment.get()))