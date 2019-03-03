class JiraPatch:
  def __init__(self, issue_id, owner, version, target_branches, patch_file):
    self.issue_id = issue_id
    self.owner = owner
    self.version = version
    self.filename = patch_file
    self.target_branches = target_branches
    
  def set_patch_file_path(self, file_path):
    self.file_path = file_path
    
  def add_additional_branch(self, branch):
    self.target_branches.append(branch)

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
    return self.__class__.__name__ + \
           " { name: " + self.name + \
           ", display_name: " + str(self.display_name) + " }"