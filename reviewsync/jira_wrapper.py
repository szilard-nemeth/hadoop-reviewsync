from jira import JIRA
import re
import os
import logging
from jira_patch import JiraPatch, PatchOwner

LOG = logging.getLogger(__name__)

DEFAULT_PATCH_EXTENSION = "patch"

class JiraWrapper:
  def __init__(self, jira_url, patches_root):
    options = { 'server': jira_url}
    self.jira = JIRA(options)
    self.patches_root = patches_root
    
  def download_attachment(self, patch):
    issue = self.jira.issue(patch.issue_id)

    found = False
    for attachment in issue.fields.attachment:
      if patch.filename == attachment.filename:
        patch_file_path = os.path.join(self.patches_root, patch.issue_id, patch.filename)

        issue_dir = os.path.dirname(patch_file_path)
        if not os.path.exists(issue_dir):
          os.makedirs(issue_dir)
          
        print "Downloading attachment from issue %s to file %s" % (patch.issue_id, patch_file_path)
        
        #TODO let JiraPatch object create the path
        patch.set_patch_file_path(patch_file_path)
        with open(patch_file_path, "w") as file:
          file.write(attachment.get())
        found = True
        break
    
    if not found:
      raise ValueError("Cannot find attachment with name '{name}' for issue {issue}"
                       .format(name=patch.filename, issue=patch.issue_id))
    
      
  def list_attachments(self, issue_id):
    issue = self.jira.issue(issue_id)

    for attachment in issue.fields.attachment:
      print("Name: '{filename}', size: {size}".format(
        filename=attachment.filename, size=attachment.size))
      # to read content use `get` method:
      # print("Content: '{}'".format(attachment.get()))
      
  def get_status(self, issue_id):
    issue = self.jira.issue(issue_id)
    status = issue.fields.status
    print "Status of %s: %s" % (issue_id, status)
    return status.name

  def get_attachments_per_branch(self, issue_id):
    issue = self.jira.issue(issue_id)
    # print "Issue obj: %s" % issue.fields.assignee
    # for property, value in vars(issue.fields.assignee).iteritems():
    #   print property, ": ", value
    # displayName : Szilard Nemeth
    # name :  snemeth
    
    owner_name = issue.fields.assignee.name
    owner_display_name = issue.fields.assignee.displayName
    owner = PatchOwner(owner_name, owner_display_name)
    jira_patches = map(lambda a: self.create_jira_patch_obj(a.filename, owner), issue.fields.attachment)
    
    # key: branch name, value: list of JiraPatch objects
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
      
      
  def create_jira_patch_obj(self, filename, owner):
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
        return JiraPatch(issue_id, owner, version, "trunk", filename)
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
        return JiraPatch(issue_id, owner, version, branch, filename)
      else:
        raise ValueError("Filename {} does not match for any pattern!".format(filename))

  def _get_separator_char(self, filename):
    search_obj = re.search(r'\w+-\d+(.)', filename)
    if not search_obj or len(search_obj.groups()) != 1:
      raise ValueError("Filename %s seem to does not have separator char after issue ID!".format(filename))
    return search_obj.group(1)
