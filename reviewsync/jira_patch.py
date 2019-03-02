class JiraPatch:
  def __init__(self, issue_id, owner, version, target_branch, patch_file):
    self.issue_id = issue_id
    self.owner = owner
    self.version = version
    self.patch_file = patch_file
    self.target_branch = target_branch

  def __repr__(self):
    return repr((self.issue_id, self.owner, self.version, self.target_branch, self.patch_file))

  def __str__(self):
    return self.__class__.__name__ + \
           " { issue_id: " + self.issue_id + \
           ", owner: " + self.owner + \
           ", version: " + str(self.version) + \
           ", patch_file: " + str(self.patch_file) + \
           ", target_branch: " + str(self.target_branch) + " }"
    