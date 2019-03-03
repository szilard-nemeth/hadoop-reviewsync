from git import Repo, RemoteProgress, GitCommandError
import os

from patch_apply import PatchApply

HADOOP_UPSTREAM_REPO_URL = "https://github.com/apache/hadoop.git"
BRANCH_PREFIX = "reviewsync"

class GitWrapper:
  def __init__(self, base_path):
    self.base_path = base_path
    self.hadoop_repo_path = os.path.join(self.base_path, 'hadoop')
    self._ensure_base_path_exists()

  def _ensure_base_path_exists(self):
    if not os.path.exists(self.base_path):
      os.mkdir(self.base_path)
      
  def sync_hadoop(self):
    if not os.path.exists(self.hadoop_repo_path):
      #Do initial clone
      print "Cloning Hadoop for the first time, into directory: %s" % (self.hadoop_repo_path)
      self.repo = Repo.clone_from(HADOOP_UPSTREAM_REPO_URL, self.hadoop_repo_path, progress=ProgressPrinter())
    else:
      self.repo = Repo(self.hadoop_repo_path)
      origin = self.repo.remote("origin")
      assert origin
      
      print "Fetcing changes from Hadoop repository (%s) in repo %s" % (HADOOP_UPSTREAM_REPO_URL, self.hadoop_repo_path)
      for fetch_info in origin.fetch(progress=ProgressPrinter()):
        print("Updated %s to %s" % (fetch_info.ref, fetch_info.commit))
        
  def validate_branches(self, branches):
    if not self.repo:
      raise ValueError("Repository is not yet synced! Please invoke sync_hadoop method before this method!")
    for branch in branches:
      Repo.rev_parse(self.repo, "origin/" + branch)
        
  def apply_patch(self, patch):
    #TODO typecheck JiraPatch
    if not self.repo:
      raise ValueError("Repository is not yet synced! Please invoke sync_hadoop method before this method!")

    print "Applying patch %s on branches: %s" % (patch.filename, patch.target_branches)
    
    results = []
    for branch in patch.target_branches:
      patch_branch_name = "{prefix}-{branch}-{filename}"\
        .format(prefix=BRANCH_PREFIX, branch=branch, filename=patch.filename)
      target_branch = "origin/" + branch
      patch_branch = self.repo.create_head(patch_branch_name, target_branch)
  
      self.repo.head.reference = patch_branch
      self.repo.head.reset(index=True, working_tree=True)
      try:
        print "Applying patch %s on branch: %s" % (patch.filename, target_branch)
        status, stdout, stderr = self.repo.git.execute(['git', 'apply', patch.file_path], with_extended_output=True)
        if status == 0:
          print "Successfully applied patch %s on branch: %s" % (patch.filename, target_branch)
          results.append(PatchApply(patch, target_branch, True))
          
        #TODO debug log
        print "status: " + str(status)
        print "stdout: " + stdout
        print "stderr: " + stderr
      except GitCommandError as gce:
        # print "Exception: " + str(gce)
        if "patch does not apply" in gce.stderr:
          #TODO debug log gce.stdout, gce.stderr, gce.cmd, gce.cmdline, gce object
          print "%s: %s PATCH DOES NOT APPLY to %s" % (patch.issue_id, patch.filename, target_branch)
          results.append(PatchApply(patch, target_branch, False))
    
    return results

class ProgressPrinter(RemoteProgress):
  def update(self, op_code, cur_count, max_count=None, message=''):
    # print(op_code, cur_count, max_count, cur_count / (max_count or 100.0), message or "NO MESSAGE")
    print "Progress: %s%% (speed: %s)" % (cur_count / (max_count or 100.0) * 100, message or "NO MESSAGE")

# class Progress(git.remote.RemoteProgress):
#   def update(self, op_code, cur_count, max_count=None, message=''):
#     print 'update(%s, %s, %s, %s)'%(op_code, cur_count, max_count, message)