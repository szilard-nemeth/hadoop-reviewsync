from jira import JIRA
import re
import logging
from jira_patch import JiraPatch
LOG = logging.getLogger(__name__)

DEFAULT_PATCH_EXTENSION = "patch"

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

  def get_latest_attachments_per_branch(self, issue_id):
    issue = self.jira.issue(issue_id)
    jira_patches = map(lambda a: self.create_jira_patch_obj(a.filename), issue.fields.attachment)
    
    # key: branch name, value: JiraPath object
    patches = {}
    for patch in jira_patches:
      branch = patch.target_branch
      if branch not in patches:
        patches[branch] = []
      patches[branch].append(patch)
      
    # Sort patches in descending order, i.e. [004, 003, 002, 001]
    for branch_name in patches:
      patches[branch_name].sort(key=lambda patch: patch.version, reverse=True)
      
    print "Found patches: " + str(patches)
    LOG.info("Found patches: %s", patches)

    #Sanity check: trunk patch is present for all patch objects
    if "trunk" not in patches:
      raise ValueError("Patch targeted to branch 'trunk' should be present "
                       "for each patch, however trunk patch is not present for issue %s!", issue_id)
      
    
    return patches
      
      
  def create_jira_patch_obj(self, filename):
    # YARN-9213.branch3.2.001.patch
    # YARN-9139.branch-3.1.001.patch
    # YARN-9213.003.patch
    sep_char = self._get_separator_char(filename)
    
    trunk_search_obj = re.search(r'(\w+-\d+)' + re.escape(sep_char) + '(\d+)\.'
                                 + DEFAULT_PATCH_EXTENSION + '$', filename)
    
    # First, let's suppose that we have a patch file targetet to trunk
    if trunk_search_obj:
      if len(trunk_search_obj.groups()) == 2:
        issue_id = trunk_search_obj.group(1)
        version = trunk_search_obj.group(2)
        #TODO owner is hardcoded
        return JiraPatch(issue_id, "owner", version, "trunk", filename)
      else:
        raise ValueError("Filename %s matched for trunk branch pattern, "
                         "but does not have issue ID and version in expected places!".format(filename))
    else:
      # Trunk filename pattern did not match.
      # Try to match against pattern that has other branch than trunk.
      # Example: YARN-9213.branch-3.2.004.patch
      search_obj = re.search(r'(\w+-\d+)' + re.escape(sep_char) + 
                             '([a-zA-Z\-0-9.]+)' + re.escape(sep_char) + 
                             '(\d+)\.' + DEFAULT_PATCH_EXTENSION + '$', filename)
      if search_obj and len(search_obj.groups()) == 3:
        issue_id = search_obj.group(1)
        branch = search_obj.group(2)
        version = search_obj.group(3)
        #TODO owner is hardcoded
        return JiraPatch(issue_id, "owner", version, branch, filename)
      else:
        raise ValueError("Filename {} does not match for any pattern!".format(filename))

  def _get_separator_char(self, filename):
    search_obj = re.search(r'\w+-\d+(.)', filename)
    if not search_obj or len(search_obj.groups()) != 1:
      raise ValueError("Filename %s seem to does not have separator char after issue ID!".format(filename))
    return search_obj.group(1)
    