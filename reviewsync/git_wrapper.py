import logging
from git import Repo, RemoteProgress, GitCommandError
import os

from patch_apply import PatchApply, PatchStatus
from jira_patch import JiraPatch

HADOOP_UPSTREAM_REPO_URL = "https://github.com/apache/hadoop.git"
BRANCH_PREFIX = "reviewsync"
LOG = logging.getLogger(__name__)


class GitWrapper:
  def __init__(self, base_path):
    self.base_path = base_path
    self.hadoop_repo_path = os.path.join(self.base_path, 'hadoop')
    self._ensure_base_path_exists()

  def _ensure_base_path_exists(self):
    if not os.path.exists(self.base_path):
      os.mkdir(self.base_path)
      
  def sync_hadoop(self, fetch=True):
    if not os.path.exists(self.hadoop_repo_path):
      # Do initial clone
      LOG.info("Cloning Hadoop for the first time, into directory: %s", self.hadoop_repo_path)
      self.repo = Repo.clone_from(HADOOP_UPSTREAM_REPO_URL, self.hadoop_repo_path, progress=ProgressPrinter("clone"))
    else:
      self.repo = Repo(self.hadoop_repo_path)
      origin = self.repo.remote("origin")
      assert origin
      
      if fetch:
        LOG.info("Fetching changes from Hadoop repository (%s) into directory %s", 
                 HADOOP_UPSTREAM_REPO_URL, self.hadoop_repo_path)
        for fetch_info in origin.fetch(progress=ProgressPrinter("fetch")):
          LOG.debug("Updated %s to %s", fetch_info.ref, fetch_info.commit)
          
  def validate_branches(self, branches):
    if not self.repo:
      raise ValueError("Repository is not yet synced! Please invoke sync_hadoop method before this method!")
    for branch in branches:
      Repo.rev_parse(self.repo, "origin/" + branch)
        
  def apply_patch(self, patch):
    if not isinstance(patch, JiraPatch):
      raise ValueError('patch must be an instance of JiraPatch!')
    if not self.repo:
      raise ValueError("Repository is not yet synced! Please invoke sync_hadoop method before this method!")
    
    LOG.info("Applying patch %s on branches: %s", patch.filename, patch.target_branches)
    LOG.debug("Applying patch %s", patch)
    
    results = []
    for branch in patch.target_branches:
      patch_branch_name = "{prefix}-{branch}-{filename}"\
        .format(prefix=BRANCH_PREFIX, branch=branch, filename=patch.filename)
      target_branch = "origin/" + branch

      if not patch.applicable:
        #TODO store reasons of non-applicability to patchapply object!
        LOG.warn("Patch %s is not applicable! Either due to jira is Resolved or for some other reason!", patch)
        results.append(PatchApply(patch, target_branch, PatchStatus.JIRA_ISSUE_RESOLVED))
        continue
      
      # If branch already exists, move it to target_branch
      if patch_branch_name in self.repo.heads:
        LOG.info("Patch branch already exists with name %s, moving branch pointer to %s", patch_branch_name, target_branch)
        patch_branch = self.repo.heads[patch_branch_name]
        patch_branch.set_commit(target_branch)
      else:
        patch_branch = self.repo.create_head(patch_branch_name, target_branch)
  
      self.repo.head.reference = patch_branch
      self.repo.head.reset(index=True, working_tree=True)
      try:
        LOG.debug("[%s] Applying patch %s to branch: %s...", patch.issue_id, patch.filename, target_branch)
        status, stdout, stderr = self.repo.git.execute(['git', 'apply', patch.file_path], with_extended_output=True)
        if status == 0:
          LOG.info("[%s] Successfully applied patch %s to branch: %s.", patch.issue_id, patch.filename, target_branch)
          self.log_git_exec(status, stderr, stdout)
          results.append(PatchApply(patch, target_branch, PatchStatus.APPLIES_CLEANLY))
      except GitCommandError as gce:
        # TODO Collect number of file conflicts to PatchApply object and log it to the final table
        if "patch does not apply" in gce.stderr:
          LOG.info("[%s] Patch %s does not apply to %s!" % (patch.issue_id, patch.filename, target_branch))
          self.log_git_exec(gce.status, gce.stderr, gce.stdout)
          results.append(PatchApply(patch, target_branch, PatchStatus.CONFLICT))
    
    return results

  def log_git_exec(self, status, stderr, stdout):
    LOG.debug("Status of git command: %s", status)
    LOG.debug("stdout of git command: %s", stdout)
    LOG.debug("stderr of git command: %s", stderr)


class ProgressPrinter(RemoteProgress):
  def __init__(self, operation):
    super(ProgressPrinter, self).__init__()
    self.operation = operation

  def update(self, op_code, cur_count, max_count=None, message=''):
    percentage = cur_count / (max_count or 100.0) * 100
    LOG.debug("Progress of git %s: %s%% (speed: %s)", self.operation, percentage, message or "-")