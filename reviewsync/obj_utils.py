class ObjUtils:
  @staticmethod
  def print_properties(obj):
    print "Printing properties of obj: %s" % obj
    for property, value in vars(obj).iteritems():
      print property, ": ", value