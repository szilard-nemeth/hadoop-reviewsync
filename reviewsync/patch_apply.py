from git_utils import GitUtils


class PatchApply:
  def __init__(self, patch, branch, result, conflicts=0, conflict_details=None):
    self.patch = patch
    self.branch = branch
    local_branch = GitUtils.convert_remote_branch_name_to_local(branch)
    self.explicit = patch.get_applicability(local_branch).explicit

    if result not in PatchStatus.ALLOWED_VALUES:
      raise ValueError('result must be a value found in PatchStatus!')
    
    if result != PatchStatus.CONFLICT and conflicts > 0:
      raise ValueError("Number of conflicts should be specified only if value of result is 'PatchStatus.CONFLICT'!")
    if result != PatchStatus.CONFLICT and conflict_details and len(conflict_details) > 0:
      raise ValueError("Conflict details should be specified only if value of result is 'PatchStatus.CONFLICT'!")
    
    self.result = result
    self.conflicts = conflicts
    self.conflict_details = conflict_details

  # TODO fix repr / str
  def __repr__(self):
    return repr((self.patch, self.branch, self.result))

  def __str__(self):
    return self.__class__.__name__ + \
           " { patch: " + self.patch + \
           ", branch: " + str(self.branch) + \
           ", result: " + str(self.result) + " }"


class PatchStatus:
  APPLIES_CLEANLY = "APPLIES CLEANLY"
  CONFLICT = "CONFLICT"
  PATCH_ALREADY_COMMITTED = "PATCH_ALREADY_COMMITTED"

  ALLOWED_VALUES = {APPLIES_CLEANLY, CONFLICT, PATCH_ALREADY_COMMITTED}


class PatchApplicability:
  def __init__(self, applicable, reason=None, explicit=True):
    self.applicable = applicable
    self.explicit = explicit
    self.reason = reason
    if not applicable and not reason:
      raise ValueError("Reason should be specified is Patch is not applicable!")

  def __repr__(self):
    return repr((self.applicable, self.reason))

  def __str__(self):
    return self.__class__.__name__ + \
           " { applicable: " + str(self.applicable) + \
           ", reason: " + self.reason + " }"
