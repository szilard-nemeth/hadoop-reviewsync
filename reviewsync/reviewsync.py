#!/usr/bin/python

import argparse
import sys
import datetime
import logging
import os
from jira_wrapper import JiraWrapper
from git_wrapper import GitWrapper
from os.path import expanduser

from attachment_utils import AttachmentUtils
from result_printer import ResultPrinter
from obj_utils import ObjUtils
from logging.handlers import TimedRotatingFileHandler

from file_utils import FileUtils

DEFAULT_BRANCH = "trunk"
JIRA_URL = "https://issues.apache.org/jira"
LOG = logging.getLogger(__name__)

__author__ = 'Szilard Nemeth'


class ReviewSync:
  def __init__(self, args):
    self.setup_dirs()
    self.issues = self.get_issues(args)
    self.branches = self.get_branches(args)
    self.git_wrapper = GitWrapper(self.git_root)
    self.jira_wrapper = JiraWrapper(JIRA_URL, DEFAULT_BRANCH, self.patches_root)

  @staticmethod
  def get_issues(args):
    issues = args.issues
    if not issues or len(issues) == 0:
      raise ValueError("Jira issues should be specified!")
    return issues

  @staticmethod
  def get_branches(args):
    branches = [DEFAULT_BRANCH]
    if args.branches and len(args.branches) > 0:
      if DEFAULT_BRANCH in args.branches:
        args.branches.remove(DEFAULT_BRANCH)
      branches = branches + args.branches
    return branches

  def setup_dirs(self):
    home = expanduser("~")
    self.reviewsync_root = os.path.join(home, "reviewsync")
    self.git_root = os.path.join(self.reviewsync_root, "repos")
    self.patches_root = os.path.join(self.reviewsync_root, "patches")
    self.log_dir = os.path.join(self.reviewsync_root, 'logs')
    
    FileUtils.ensure_dir_created(self.reviewsync_root)
    FileUtils.ensure_dir_created(self.git_root)
    FileUtils.ensure_dir_created(self.patches_root)
    FileUtils.ensure_dir_created(self.log_dir)

  def sync(self):
    LOG.info("Jira issues will be synced: %s", self.issues)
    LOG.info("Branches specified: %s", self.branches)
    
    self.git_wrapper.sync_hadoop(fetch=True)
    self.git_wrapper.validate_branches(self.branches)

    # key: jira issue ID
    # value: list of PatchApply objects
    # For non-appliable patches (e.g. jira is already Resolved, patch object is None)
    results = {}
    for issue_id in self.issues:
      patches = self.download_latest_patches(issue_id)
      if len(patches) == 0:
        LOG.warn("No patch found for jira issue %s!", issue_id)
        continue

      for patch in patches:
        patch_applies = self.git_wrapper.apply_patch(patch)
        if patch.issue_id not in results:
          results[patch.issue_id] = []
        results[patch.issue_id] += patch_applies
    LOG.info("List of Patch applies: %s", results)
    return results

  @staticmethod
  def init_logger(log_dir, console_debug=False):
    # get root logger
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)

    # create file handler which logs even debug messages
    logfilename = datetime.datetime.now().strftime(
      'reviewsync-%Y_%m_%d_%H_%M_%S.log')

    fh = TimedRotatingFileHandler(os.path.join(log_dir, logfilename), when='midnight')
    fh.suffix = '%Y_%m_%d.log'
    fh.setLevel(logging.DEBUG)

    # create console handler with a higher log level
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    if console_debug:
      ch.setLevel(logging.DEBUG)

    formatter = logging.Formatter(
      '%(asctime)s - %(levelname)s - %(name)s - %(message)s')
    fh.setFormatter(formatter)
    ch.setFormatter(formatter)
    # add the handlers to the logger
    logger.addHandler(fh)
    logger.addHandler(ch)

  @staticmethod
  def parse_args():
    """This function parses and return arguments passed in"""

    parser = argparse.ArgumentParser(
      description='Script retrieves patches for specified jiras and generates input file for conflict checker script')

    parser.add_argument(
      '-i', '--issues', nargs='+', type=str,
      help='List of jira issues to check', required=True)
    parser.add_argument(
      '-b', '--branches', nargs='+', type=str,
      help='List of branches to apply patches that are targeted to trunk (default is trunk only)',
      required=False)
    parser.add_argument('-v', '--verbose', action='store_true',
                        dest='verbose', default=None, required=False,
                        help='More verbose log')
    # parser.add_argument(
    #   '-j', '--jira-url', type=str, help='URL of jira to check', required=True)
    args = parser.parse_args()
    return args

  def download_latest_patches(self, issue_id):
    patches = self.jira_wrapper.get_patches_per_branch(issue_id, self.branches)
    for patch in patches:
      if patch.applicable:
        self.jira_wrapper.download_patch_file(patch)
      else:
        LOG.info("Skipping download of non-applicable patch: %s", patch)

    return patches

  def print_results_table(self, results):
    data, headers = self.convert_data_to_result_printer(results)
    result_printer = ResultPrinter(data, headers)
    result_printer.print_table()

  @staticmethod
  def convert_data_to_result_printer(results):
    data = []
    headers = ["Issue", "Owner", "Patch file", "Branch", "Result"]
    for issue_id, patch_applies in results.iteritems():
      for patch_apply in patch_applies:
        patch = patch_apply.patch
        data.append([issue_id, patch.owner_display_name, patch.filename,
                     patch_apply.branch, patch_apply.result])

    return data, headers


if __name__ == '__main__':
  # Parse args
  args = ReviewSync.parse_args()
  reviewsync = ReviewSync(args)
  
  # Initialize logging
  verbose = True if args.verbose else False
  ReviewSync.init_logger(reviewsync.log_dir, console_debug=verbose)

  results = reviewsync.sync()
  reviewsync.print_results_table(results)
