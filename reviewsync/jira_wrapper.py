import requests
from jira import JIRA
import re
import os
import logging
from jira_patch import JiraPatch, PatchOwner
from attachment_utils import AttachmentUtils
from patch_apply import PatchApplicability
import time

LOG = logging.getLogger(__name__)

DEFAULT_PATCH_EXTENSION = "patch"


class JiraWrapper:
  def __init__(self, jira_url, default_branch, patches_root):
    options = { 'server': jira_url}
    self.jira = JIRA(options, timeout=20, max_retries=10)
    self.jira_url = jira_url
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
          
        LOG.debug("Downloading patch from issue %s to file %s", patch.issue_id, patch_file_path)
        attachment_data = self._download_attachment_with_retries(attachment)

        #TODO let JiraPatch object create the path
        patch.set_patch_file_path(patch_file_path)
        with open(patch_file_path, "w") as file:
          file.write(attachment_data)
        found = True
        break
    
    if not found:
      raise ValueError("Cannot find attachment with name '{name}' for issue {issue}"
                       .format(name=patch.filename, issue=patch.issue_id))

  def _download_attachment_with_retries(self, attachment):
    tried = 0
    max_retries = 5
    while max_retries != tried:
      try:
        tried += 1
        return attachment.get()
      except requests.exceptions.Timeout:
        LOG.error("Read timed out while communicating with %s, sleeping for 5 seconds...", self.jira_url)
        time.sleep(5)

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
    LOG.debug("Status of issue %s: %s", issue_id, status)
    return status.name
  
  def is_status_resolved(self, issue_id):
    status = self.get_status(issue_id)
    if status == "Resolved":
      LOG.debug("Status of jira is 'Resolved': %s", issue_id)
      return True
    return False

  def get_patches_per_branch(self, issue_id, additional_branches, committed_on_branches):
    issue = self.jira.issue(issue_id)
    
    if issue.fields.assignee:
      owner_name = issue.fields.assignee.name
      owner_display_name = issue.fields.assignee.displayName
    else:
      owner_name = "unassigned"
      owner_display_name = "unassigned"
    owner = PatchOwner(owner_name, owner_display_name)

    # applicable = False if self.is_status_resolved(issue_id) else True
    patches = map(lambda a: self.create_jira_patch_obj(issue_id, a.filename, owner, committed_on_branches), issue.fields.attachment)
    patches = [p for p in patches if p is not None]
    LOG.debug("[%s] Found patches (all): %s", issue_id, patches)

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

    LOG.debug("[%s] Found patches (grouped by branch): %s", issue_id, branches_to_patches)

    # After this call, we have on 1-1 mappings between patch and branch
    branch_to_patch_dict = AttachmentUtils.get_latest_patches_per_branch(branches_to_patches)
    LOG.info("[%s] Found patches (only latest by filename): %s", issue_id, branches_to_patches)

    # Sanity check: self.default_branch patch is present for the Jira issue
    if self.default_branch not in branch_to_patch_dict:
      LOG.error("[%s] Patch targeted to default branch (name: '%s') should be present for each issue, "
                "however trunk patch is not present for this issue!",
                issue_id, self.default_branch)
      return []
    
    for branch in additional_branches:
      # If we don't have patch for this branch, use the same patch targeted to the default branch.
      # Otherwise, keeping the one that explicitly targets the branch is in precedence.
      # In other words, we should make an override: A Patch explicitly targeted to
      # a branch should have precedence over a patch originally targeted to the default branch.
      # Example:
      # Branch: branch-3.2
      # Trunk patch: 002.patch
      # Result: branches_to_patches = { 'trunk': '002.patch', 'branch-3.2': '002.patch' }

      # Example2:
      # Patches: 002.patch, branch-3.2.001.patch
      # Branches: trunk, branch-3.2
      # Result: 002.patch --> trunk, branch-3.2.001.patch --> branch-3.2 [[002.patch does not target branch-3.2]]
      branch_required = branch not in committed_on_branches
      
      if not branch_required:
        LOG.info("[%s] Patch should be targeted to additional branch %s, but it is already committed on that branch!", issue_id, branch)
      if branch not in branch_to_patch_dict and branch_required:
        patch = branch_to_patch_dict[self.default_branch]
        patch.add_additional_branch(branch, PatchApplicability(True, explicit=False))
        branch_to_patch_dict[branch] = patch

    LOG.debug("Found patches from all issues, only latest and after overrides applied: %s", branches_to_patches)
          
    # We could also have duplicates at this point, 
    # the combination of sets and __eq__ method of JiraPatch will sort out duplicates
    result = set()
    for branch, patch in branch_to_patch_dict.iteritems():
      result.add(patch)
    
    result = list(result)
    LOG.info("Found patches from all issues, after all filters applied: %s", result)
    return result
      
  def create_jira_patch_obj(self, issue_id, filename, owner, committed_on_branches):
    # YARN-9213.branch3.2.001.patch
    # YARN-9139.branch-3.1.001.patch
    # YARN-9213.003.patch
    sep_char = self._get_separator_char(filename)
    if not sep_char:
      LOG.error("[%s] Filename %s does not seem to have separator character after jira issue ID!", issue_id, filename)
      return None
    
    trunk_search_obj = re.search(r'(\w+-\d+)' + re.escape(sep_char) + '(\d+)\.'
                                 + DEFAULT_PATCH_EXTENSION + '$', filename)
    
    #TODO sanity check issue_id and parsed_issue_id is the same!
    
    # First, let's suppose that we have a patch file targeted to trunk
    if trunk_search_obj:
      if len(trunk_search_obj.groups()) == 2:
        parsed_issue_id = trunk_search_obj.group(1)
        parsed_version = trunk_search_obj.group(2)

        if self.default_branch not in committed_on_branches:
          applicability = PatchApplicability(True)
        else:
          applicability = PatchApplicability(False, "Patch already committed on {}".format(self.default_branch))
        return JiraPatch(parsed_issue_id, owner, parsed_version, self.default_branch, filename, applicability)
      else:
        raise ValueError("Filename %s matched for trunk branch pattern, "
                         "but does not have issue ID and version in expected position!".format(filename))
    else:
      # Trunk filename pattern did not match.
      # Try to match against pattern that has other branch than trunk.
      # Example: YARN-9213.branch-3.2.004.patch
      search_obj = re.search(r'(\w+-\d+)' + re.escape(sep_char) +
                             '([a-zA-Z\-0-9.]+)' + re.escape(sep_char) +
                             '(\d+)\.' + DEFAULT_PATCH_EXTENSION + '$', filename)
      if search_obj and len(search_obj.groups()) == 3:
        parsed_issue_id = search_obj.group(1)
        parsed_branch = search_obj.group(2)
        parsed_version = search_obj.group(3)

        if parsed_branch not in committed_on_branches:
          applicability = PatchApplicability(True)
        else:
          applicability = PatchApplicability(False, "Patch already committed on {}".format(parsed_branch))
        return JiraPatch(parsed_issue_id, owner, parsed_version, parsed_branch, filename, applicability)
      else:
        LOG.error("[%s] Filename %s does not match for any patch file name regex pattern!", issue_id, filename)
        return None

  def _get_separator_char(self, filename):
    search_obj = re.search(r'\w+-\d+(.)', filename)
    if search_obj and len(search_obj.groups()) == 1:
      return search_obj.group(1)
    return None
    

class JiraFetchMode:
  GSHEET = "GSHEET"
  ISSUES_CMDLINE = "ISSUES_CMDLINE"
