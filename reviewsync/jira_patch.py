from patch_apply import PatchStatus
from string_utils import StringUtils
import logging

LOG = logging.getLogger(__name__)


class JiraPatch:
  def __init__(self, issue_id, owner, version, target_branch, patch_file, applicability):
    self.issue_id = issue_id
    self.owner = owner
    self.owner_short = owner.name
    self.owner_display_name = owner.display_name
    self.version = version
    self.filename = patch_file
    self.target_branches = [target_branch]
    self.applicability = {target_branch: applicability}
    self.overall_status = PatchOverallStatus("N/A")

  def get_applicability(self, branch):
    return self.applicability[branch]

  def set_patch_file_path(self, file_path):
    self.file_path = file_path
    
  def set_overall_status(self, overall_status):
    self.overall_status = overall_status

  def add_additional_branch(self, branch, applicability):
    self.target_branches.append(branch)
    self.applicability[branch] = applicability

  def is_applicable_for_branch(self, branch):
    if branch in self.applicability:
      return self.applicability[branch].applicable
    return False

  def get_reason_for_non_applicability(self, branch):
    if branch in self.applicability:
      return self.applicability[branch].reason
    return "Unknown"

  def is_applicable(self):
    applicabilities = set([True if a.applicable else False for a in self.applicability.values()])
    LOG.debug("Patch applicabilities: %s for patch %s", applicabilities, self)
    return True in applicabilities

  def __repr__(self):
    return repr((self.issue_id, self.owner, self.version, self.target_branches, self.filename))

  def __str__(self):
    return self.__class__.__name__ + \
           " { issue_id: " + self.issue_id + \
           ", owner: " + str(self.owner) + \
           ", version: " + str(self.version) + \
           ", filename: " + str(self.filename) + \
           ", target_branch: " + str(self.target_branches) + " }"

  def __hash__(self):
    return hash((self.issue_id, self.owner, self.filename, tuple(self.target_branches)))

  def __eq__(self, other):
    if isinstance(other, JiraPatch):
      return self.issue_id == other.issue_id and \
             self.owner == other.owner and \
             self.filename == other.filename and \
             self.target_branches == other.target_branches
    return False


class PatchOwner:
  def __init__(self, name, display_name):
    self.name = name
    self.display_name = display_name

  def __repr__(self):
    return repr((self.name, self.display_name))

  def __str__(self):
    # TODO understand unicode conversion issue in more details
    # return self.__class__.__name__ + \
    #        " { name: " + self.name + \
    #        ", display_name: " + str(self.display_name) + " }"
    # UnicodeEncodeError: 'ascii' codec can't encode character u'\xe1' in position 7: ordinal not in range(128)
    return self.__class__.__name__ + \
           " { name: " + self.name + \
           ", display_name: " + StringUtils.replace_special_chars(self.display_name) + " }"


class PatchOverallStatus:
  def __init__(self, status):
    self.status = status
    
  def __repr__(self):
    return repr(self.status)
  
  def __str__(self):
    return self.__class__.__name__ + \
           " { status: " + self.status + "}"