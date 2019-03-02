class AttachmentUtils:
  
  @staticmethod
  def get_latest_patches_per_branch(patches):
    result = {}
    
    for branch, patches in patches.iteritems():
      # We know that this is ordered by patch version, DESC
      result[branch] = patches[0]

    return result