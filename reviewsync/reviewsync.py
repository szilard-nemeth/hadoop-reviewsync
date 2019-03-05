#!/usr/bin/python

import argparse
import sys
import datetime
import logging
import os
from collections import OrderedDict
from jira_wrapper import JiraWrapper, JiraFetchMode
from git_wrapper import GitWrapper
from gsheet_wrapper import GSheetWrapper, GSheetOptions
from os.path import expanduser
import datetime

from attachment_utils import AttachmentUtils
from result_printer import ResultPrinter
from obj_utils import ObjUtils
from logging.handlers import TimedRotatingFileHandler

from file_utils import FileUtils
from patch_apply import PatchStatus

DEFAULT_BRANCH = "trunk"
JIRA_URL = "https://issues.apache.org/jira"
LOG = logging.getLogger(__name__)

__author__ = 'Szilard Nemeth'

class ReviewSync:
  def __init__(self, args):
    self.setup_dirs()
    self.branches = self.get_branches(args)
    self.git_wrapper = GitWrapper(self.git_root)
    self.jira_wrapper = JiraWrapper(JIRA_URL, DEFAULT_BRANCH, self.patches_root)
    self.issue_fetch_mode = args.fetch_mode
    if self.issue_fetch_mode == JiraFetchMode.GSHEET:
      self.gsheet_wrapper = GSheetWrapper(args.gsheet_options)
    
  def get_or_fetch_issues(self):
    if self.issue_fetch_mode == JiraFetchMode.ISSUES_CMDLINE:
      LOG.info("Using Jira fetch mode from issues specified from command line.")
      issues = args.issues
      if not issues or len(issues) == 0:
        raise ValueError("Jira issues should be specified!")
      return issues
    elif self.issue_fetch_mode == JiraFetchMode.GSHEET:
      LOG.info("Using Jira fetch mode from GSheet.")
      return self.gsheet_wrapper.fetch()
    else:
      raise ValueError("Unknown state! Jira fetch mode should be either "
                       "{} or {} but it is {}"
                       .format(JiraFetchMode.ISSUES_CMDLINE,
                               JiraFetchMode.GSHEET,
                               self.issue_fetch_mode))

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
    issues = self.get_or_fetch_issues()
    if not issues or len(issues) == 0:
      LOG.info("No Jira issues found using fetch mode: %s", self.issue_fetch_mode)
      return
    
    LOG.info("Jira issues will be review-synced: %s", issues)
    LOG.info("Branches specified: %s", self.branches)
    
    self.git_wrapper.sync_hadoop(fetch=True)
    self.git_wrapper.validate_branches(self.branches)

    # key: jira issue ID
    # value: list of PatchApply objects
    # For non-applicable patches (e.g. jira is already Resolved, patch object is None)
    
    results = OrderedDict()
    for issue_id in issues:
      committed_on_branches = self.git_wrapper.get_remote_branches_committed_for_issue(issue_id)
      LOG.info("Issue %s is committed on branches: %s", issue_id, committed_on_branches)
      patches = self.download_latest_patches(issue_id, committed_on_branches)
      if len(patches) == 0:
        LOG.warn("No patch found for Jira issue %s!", issue_id)
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
      '-b', '--branches', nargs='+', type=str,
      help='List of branches to apply patches that are targeted to trunk (default is trunk only)',
      required=False)
    parser.add_argument('-v', '--verbose', action='store_true',
                        dest='verbose', default=None, required=False,
                        help='More verbose log')

    exclusive_group = parser.add_mutually_exclusive_group()
    exclusive_group.add_argument('-i', '--issues', nargs='+', type=str,
                                 help='List of Jira issues to check',
                                 required=False)
    exclusive_group.add_argument('-g', '--gsheet', action='store_true',
                                 dest='gsheet_enable', default=False,
                                 required=False,
                                 help='Enable reading values from Google Sheet API. '
                                      'Additional gsheet arguments need to be specified!')
    
    # Arguments for Google sheet integration
    gsheet_group = parser.add_argument_group('google-sheet', "Arguments for Google sheet integration")

    gsheet_group.add_argument('--gsheet-client-secret',
                              dest='gsheet_client_secret', required=False,
                              help='Client credentials for accessing Google Sheet API')

    gsheet_group.add_argument('--gsheet-spreadsheet',
                              dest='gsheet_spreadsheet', required=False,
                              help='Name of the GSheet spreadsheet')
    
    gsheet_group.add_argument('--gsheet-worksheet',
                              dest='gsheet_worksheet', required=False,
                              help='Name of the worksheet in the GSheet spreadsheet')
    
    gsheet_group.add_argument('--gsheet-jira-column',
                              dest='gsheet_jira_column', required=False,
                              help='Name of the column that contains jira issue IDs in the GSheet spreadsheet')
    
    gsheet_group.add_argument('--gsheet-update-date-column',
                              dest='gsheet_update_date_column', required=False,
                              help='Name of the column where this script will store last updated date in the GSheet spreadsheet')
    
    gsheet_group.add_argument('--gsheet-status-info-column',
                              dest='gsheet_status_info_column', required=False,
                              help='Name of the column where this script will store patch status info in the GSheet spreadsheet')

    # parser.add_argument(
    #   '-j', '--jira-url', type=str, help='URL of jira to check', required=True)
    args = parser.parse_args()
    
    if not args.issues and not args.gsheet_enable:
      parser.error("Either list of jira issues (--issues) or Google Sheet integration (--gsheet) need to be provided!")
    
    #TODO check existence + readability on secret file!!
    if args.gsheet_enable and (args.gsheet_client_secret is None or
                               args.gsheet_spreadsheet is None or 
                               args.gsheet_worksheet is None or
                               args.gsheet_jira_column is None):
      parser.error("--gsheet requires --gsheet-client-secret, --gsheet-spreadsheet, --gsheet-worksheet and --gsheet-jira-column.")
    
    if args.issues and len(args.issues) > 1:
      args.fetch_mode = JiraFetchMode.ISSUES_CMDLINE
    elif args.gsheet_enable:
      args.fetch_mode = JiraFetchMode.GSHEET
      args.gsheet_options = GSheetOptions(args.gsheet_client_secret,
                                          args.gsheet_spreadsheet,
                                          args.gsheet_worksheet,
                                          args.gsheet_jira_column,
                                          update_date_column=args.gsheet_update_date_column,
                                          status_column=args.gsheet_status_info_column)
    
    return args

  def download_latest_patches(self, issue_id, committed_on_branches):
    patches = self.jira_wrapper.get_patches_per_branch(issue_id, self.branches, committed_on_branches)
    for patch in patches:
      if patch.is_applicable():
        #TODO possible optimization: Just download required files based on branch applicability
        self.jira_wrapper.download_patch_file(patch)
      else:
        LOG.info("Skipping download of non-applicable patch: %s", patch)

    return patches

  def print_results_table(self, results):
    data, headers = self.convert_data_for_result_printer(results)
    result_printer = ResultPrinter(data, headers)
    result_printer.print_table()

  def update_gsheet(self, results):
    update_date_str = datetime.datetime.now().strftime('%d/%m/%Y %H:%M:%S')
    
    for issue_id, patch_applies in results.iteritems():
      overall_status = PatchStatus.APPLIES_CLEANLY
      for patch_apply in patch_applies:
        if patch_apply.result != PatchStatus.APPLIES_CLEANLY:
          overall_status = patch_apply.result
          break
        
      self.gsheet_wrapper.update_issue_with_results(issue_id, update_date_str, overall_status)

  @staticmethod
  def convert_data_for_result_printer(results):
    data = []
    headers = ["Row", "Issue", "Patch apply", "Owner", "Patch file", "Branch", "Explicit", "Result"]
    row = 0
    for issue_id, patch_applies in results.iteritems():
      for idx, patch_apply in enumerate(patch_applies):
        row += 1
        patch = patch_apply.patch
        explicit = "Yes" if patch_apply.explicit else "No"
        data.append([row, issue_id, idx + 1, patch.owner_display_name, patch.filename,
                     patch_apply.branch, explicit, patch_apply.result])

    return data, headers


if __name__ == '__main__':
  # Parse args
  args = ReviewSync.parse_args()
  reviewsync = ReviewSync(args)
  
  # Initialize logging
  verbose = True if args.verbose else False
  ReviewSync.init_logger(reviewsync.log_dir, console_debug=verbose)

  results = reviewsync.sync()
  
  if results:
    reviewsync.print_results_table(results)
    if reviewsync.issue_fetch_mode == JiraFetchMode.GSHEET:
      reviewsync.update_gsheet(results)
