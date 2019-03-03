class AttachmentUtils:
  
  @staticmethod
  def get_latest_patches_per_branch(patches_dict):
    # Sort patches in descending order, i.e. [004, 003, 002, 001]
    for branch_name in patches_dict:
      patches_dict[branch_name].sort(key=lambda patch: patch.version, reverse=True)
      
    result = {}
    for branch, patches in patches_dict.iteritems():
      # We know that this is ordered by patch version, DESC
      if len(patches) == 0:
        raise ValueError("Expected at least one target branch for patch: " + str(patches))
      result[branch] = patches[0]

    return result