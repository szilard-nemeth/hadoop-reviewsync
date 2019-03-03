from jira import JIRA
import re
import os
import logging
from jira_patch import JiraPatch, PatchOwner
from attachment_utils import AttachmentUtils

LOG = logging.getLogger(__name__)

DEFAULT_PATCH_EXTENSION = "patch"

class JiraWrapper:
  def __init__(self, jira_url, default_branch, patches_root):
    options = { 'server': jira_url}
    self.jira = JIRA(options)
    self.default_branch = default_branch
    self.patches_root = patches_root
    
  def download_patch_file(self, patch):
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
  
  def is_status_resolved(self, issue_id):
    status = self.get_status(issue_id)
    if status == "Resolved":
      print "Status of jira is 'Resolved': %s" % issue_id
      return True
    return False

  def get_patches_per_branch(self, issue_id, additional_branches):
    issue = self.jira.issue(issue_id)
    # print "Issue obj: %s" % issue.fields.assignee
    # for property, value in vars(issue.fields.assignee).iteritems():
    #   print property, ": ", value
    # displayName : Szilard Nemeth
    # name :  snemeth
    
    owner_name = issue.fields.assignee.name
    owner_display_name = issue.fields.assignee.displayName
    owner = PatchOwner(owner_name, owner_display_name)

    applicable = False if self.is_status_resolved(issue_id) else True
    patches = map(lambda a: self.create_jira_patch_obj(a.filename, owner, applicable), issue.fields.attachment)

    # key: branch name, value: list of JiraPatch objects
    branches_to_patches = {}
    for patch in patches:
      # Sanity check
      if not len(patch.target_branches) == 1:
        raise ValueError("Patch should be targeted to "
                         "only one branch at this point. Patch: {}, Branches: {}"
                         .format(patch.filename, patch.target_branches))
      branch = patch.target_branches[0]
      if branch not in branches_to_patches:
        branches_to_patches[branch] = []
      branches_to_patches[branch].append(patch)

    print "BRANCHES TO PATCHES before: " + str(branches_to_patches)
    # After this call, we have on 1-1 mappings between patch and branch
    branches_to_patches = AttachmentUtils.get_latest_patches_per_branch(branches_to_patches)
    print "BRANCHES TO PATCHES after: " + str(branches_to_patches)
    
    for branch in additional_branches:
      # If we don't have patch for this branch, use the same patch targeted to the default branch.
      # Otherwise, keeping the one that explicitly targets the branch is a must!
      # In other words: We should make an override: patches explicitly targeted to 
      # another branches should have precedence over trunk targeted to specified branches.
      # Example: 
      # Branch: branch-3.2
      # Trunk patch: 002.patch
      # Result: branches_to_patches = { 'trunk': '002.patch', 'branch-3.2': '002.patch' }

      # Example2:
      # Patches: 002.patch, branch-3.2.001.patch
      # Branches: trunk, branch-3.2
      # Result: 002.patch --> trunk, branch-3.2.001.patch --> branch-3.2 [[002.patch does not target branch-3.2]]
      if branch not in branches_to_patches:
        patch = branches_to_patches[self.default_branch]
        patch.add_additional_branch(branch)
        branches_to_patches[branch] = patch
        
    print "BRANCHES TO PATCHES 2: " + str(branches_to_patches)
          
    #Sanity check: trunk patch is present for all patch objects
    if self.default_branch not in branches_to_patches:
      raise ValueError("Patch targeted to branch '%s' should be present "
                       "for each patch, however trunk patch is not present for issue %s!", self.default_branch, issue_id)
    
    # As a last step, we can convert the dict to list as all patch object hold the reference to target branches
    # We can also have duplicates here
    result = set()
    for branch, patch in branches_to_patches.iteritems():
      result.add(patch)
    
    return list(result)
      
      
  def create_jira_patch_obj(self, filename, owner, applicable):
    # YARN-9213.branch3.2.001.patch
    # YARN-9139.branch-3.1.001.patch
    # YARN-9213.003.patch
    sep_char = self._get_separator_char(filename)
    
    trunk_search_obj = re.search(r'(\w+-\d+)' + re.escape(sep_char) + '(\d+)\.'
                                 + DEFAULT_PATCH_EXTENSION + '$', filename)
    
    # First, let's suppose that we have a patch file targeted to trunk
    if trunk_search_obj:
      if len(trunk_search_obj.groups()) == 2:
        issue_id = trunk_search_obj.group(1)
        version = trunk_search_obj.group(2)
        return JiraPatch(issue_id, owner, version, [self.default_branch], filename, applicable)
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
        return JiraPatch(issue_id, owner, version, [branch], filename, applicable)
      else:
        raise ValueError("Filename {} does not match for any pattern!".format(filename))

  def _get_separator_char(self, filename):
    search_obj = re.search(r'\w+-\d+(.)', filename)
    if not search_obj or len(search_obj.groups()) != 1:
      raise ValueError("Filename %s seem to does not have separator char after issue ID!".format(filename))
    return search_obj.group(1)
