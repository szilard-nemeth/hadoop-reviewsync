class PatchApply:
  def __init__(self, patch, branch, result):
    self.patch = patch
    self.branch = branch
    #TODO typecheck PatchStatus
    self.result = result

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
  JIRA_ISSUE_RESOLVED = "JIRA_ISSUE_RESOLVED"
