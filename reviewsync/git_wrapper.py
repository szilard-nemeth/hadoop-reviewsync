from git import Repo, RemoteProgress
import os

HADOOP_UPSTREAM_REPO_URL = "https://github.com/apache/hadoop.git"

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
      repo = Repo.clone_from(HADOOP_UPSTREAM_REPO_URL, self.hadoop_repo_path, progress=ProgressPrinter())
    else:
      repo = Repo(self.hadoop_repo_path)
      origin = repo.remote("origin")
      assert origin
      
      print "Fetcing changes from Hadoop repository (%s) in repo %s" % (HADOOP_UPSTREAM_REPO_URL, self.hadoop_repo_path)
      for fetch_info in origin.fetch(progress=ProgressPrinter()):
        print("Updated %s to %s" % (fetch_info.ref, fetch_info.commit))


class ProgressPrinter(RemoteProgress):
  def update(self, op_code, cur_count, max_count=None, message=''):
    # print(op_code, cur_count, max_count, cur_count / (max_count or 100.0), message or "NO MESSAGE")
    print "Progress: %s%% (speed: %s)" % (cur_count / (max_count or 100.0) * 100, message or "NO MESSAGE")

# class Progress(git.remote.RemoteProgress):
#   def update(self, op_code, cur_count, max_count=None, message=''):
#     print 'update(%s, %s, %s, %s)'%(op_code, cur_count, max_count, message)