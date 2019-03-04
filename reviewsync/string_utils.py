import unicodedata
import string


class StringUtils:

  @staticmethod
  def replace_special_chars(str):
    normalized_title = unicodedata.normalize('NFD', str).encode('ascii', 'ignore')
    normalized_title = normalized_title.decode('utf-8')
    valid_chars = "-_.()%s%s" % (string.ascii_letters, string.digits)
    valid_title = ''.join(c for c in normalized_title if c in valid_chars)
    return valid_title