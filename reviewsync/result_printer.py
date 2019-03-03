from tabulate import tabulate


class ResultPrinter:
  def __init__(self, data, headers):
    self.data = data
    self.headers = headers
    
  def print_table(self):
    print(tabulate(self.data, self.headers, tablefmt="fancy_grid"))

  def print_table_html(self):
    print(tabulate(self.data, self.headers, tablefmt="html"))

  # def print_examples(self):
  #   format_list = ['plain', 'simple', 'grid', 'fancy_grid', 'pipe', 'orgtbl', 'jira', 'presto', 'psql', 'rst', 'mediawiki', 'moinmoin', 'youtrack', 'html', 'latex', 'latex_raw', 'latex_booktabs']
  # 
  #   # Each element in the table list is a row in the generated table
  #   table = [["spam",42],["eggs",451],["bacon",0]]
  #   headers = ["item", "qty"]
  #   
  #   for f in format_list:
  #     print("\nformat: {}\n".format(f))
  #     print(tabulate(table, headers, tablefmt=f))