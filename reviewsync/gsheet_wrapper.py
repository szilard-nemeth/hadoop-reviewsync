import gspread
import logging

from gspread import SpreadsheetNotFound, WorksheetNotFound
from gspread.utils import rowcol_to_a1
from oauth2client.service_account import ServiceAccountCredentials
from pprint import pformat

SCOPE = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
LOG = logging.getLogger(__name__)


class GSheetOptions:
  def __init__(self, client_secret, spreadsheet, worksheet, jira_column, update_date_column=None, status_column=None):
    self.client_secret = client_secret
    self.spreadsheet = spreadsheet
    self.worksheet = worksheet
    self.jira_column = jira_column
    self.update_date_column = update_date_column
    self.status_column = status_column

    if self.update_date_column:
      self.do_update_date = True
    if self.status_column:
      self.do_update_status = True

  def __repr__(self):
    return repr((self.client_secret, self.spreadsheet, self.worksheet, self.jira_column, self.update_date_column, self.status_column))

  def __str__(self):
    return self.__class__.__name__ + \
           " { spreadsheet: " + self.spreadsheet + \
           ", worksheet: " + str(self.worksheet) + \
           ", jira_column: " + self.jira_column + \
           ", update_date_column: " + self.update_date_column + \
           ", status_column: " + str(self.status_column) + " }"


class CellUpdateForIssue:
  def __init__(self, issue, update_date_cell, status_cell):
    self.issue = issue
    self.update_date_cell = update_date_cell
    self.status_cell = status_cell

  def __repr__(self):
    return repr((self.issue, self.update_date_cell, self.status_cell))

  def __str__(self):
    return self.__class__.__name__ + \
           " { issue: " + self.issue + \
           ", update_date_cell: " + str(self.update_date_cell) + \
           ", status_cell: " + str(self.status_cell) + " }"


class GSheetWrapper:
  def __init__(self, options):
    if not isinstance(options, GSheetOptions):
      raise ValueError('options must be an instance of GSheetOptions!')

    LOG.debug("GSheetWrapper options: %s", str(options))
    self.options = options

    if not options.client_secret:
      raise ValueError("Client secret should be specified!")

    self.creds = ServiceAccountCredentials.from_json_keyfile_name(options.client_secret, SCOPE)
    self.client = gspread.authorize(self.creds)
    self.issue_to_cellupdate = {}

  def fetch(self):
    try:
      sheet = self.client.open(self.options.spreadsheet).worksheet(self.options.worksheet)
    except SpreadsheetNotFound:
      raise ValueError("Spreadsheet was not found with name '{}'".format(self.options.spreadsheet))
    except WorksheetNotFound:
      raise ValueError("Worksheet was not found with name '{}'".format(self.options.worksheet))

    header = sheet.row_values(1)
    LOG.debug("Fetched spreadsheet header: %s", header)

    update_date_col_idx = self.find_column_idx_in_header(header, self.options.update_date_column, "update date")
    if update_date_col_idx < 0:
      self.options.do_update_date = False

    status_col_idx = self.find_column_idx_in_header(header, self.options.status_column, "status")
    if status_col_idx < 0:
      self.options.do_update_status = False

    rows = sheet.get_all_records()
    LOG.debug("Received data from sheet %s: %s", self.options.worksheet, pformat(rows))

    # Check column is found
    jira_col = self.options.jira_column
    if rows and len(rows) > 0:
      if not jira_col in rows[0]:
        row0 = rows[0]
        raise ValueError("Jira column with name '{}' was not found in "
                         "received data! First row of data: {}".format(jira_col, row0))

    issues = []

    # 1 because of 0-based indexing (rows are 1-based)
    # 2 because of header row is the 1st row
    idx_correction_row = 2

    # 1 because of 0-based col indexing from header
    idx_correction_col = 1
    for idx, row in enumerate(rows):
      issue = row[jira_col]
      issues.append(issue)

      update_date_cell_id, status_cell_id = None, None
      if self.options.do_update_date:
        update_date_cell_id = rowcol_to_a1(idx + idx_correction_row, update_date_col_idx + idx_correction_col)
      if self.options.do_update_status:
        status_cell_id = rowcol_to_a1(idx + idx_correction_row, status_col_idx + idx_correction_col)

      # If update is required for any cell, we need to store a CellUpdateForIssue object, otherwise don't store it
      if update_date_cell_id or status_cell_id:
        self.issue_to_cellupdate[issue] = CellUpdateForIssue(issue, update_date_cell_id, status_cell_id)

    LOG.debug("Issue to CellUpdate mappings: %s", self.issue_to_cellupdate)
    LOG.debug("Found Jira issue from GSheet: %s", issues)
    
    self.sheet = sheet
    return issues

  def find_column_idx_in_header(self, header, column, type_of_column):
    column_idx = -1
    try:
      LOG.debug("Using %s column with name '%s'", type_of_column,
                self.options.update_date_column)
      column_idx = header.index(column)
    except ValueError:
      LOG.error("Omitting future updates of %s column as "
                "it was not found in header %s with name '%s'"
                .format(type_of_column, header, column))
    if column_idx > -1:
      LOG.debug("%s column was found with index: %d", type_of_column, column_idx)
    return column_idx

  def update_issue_with_results(self, issue, date_str, status):
    if not self.sheet:
      raise ValueError("Sheet data is not yet fetched! Please invoke 'fetch' method first!")
    
    if issue not in self.issue_to_cellupdate:
      LOG.info("No cell update will be performed for issue %s", issue)
      return

    cu = self.issue_to_cellupdate[issue]
    if self.options.do_update_date:
      LOG.info("[%s] Updating GSheet cell '%s' with value: '%s' (update date)", issue, cu.update_date_cell, date_str)
      self.sheet.update_acell(cu.update_date_cell, date_str)
    
    if self.options.do_update_status:
      LOG.info("[%s] Updating GSheet cell '%s' with value: '%s' (overall status)", issue, cu.status_cell, status)
      self.sheet.update_acell(cu.status_cell, status.status)
    