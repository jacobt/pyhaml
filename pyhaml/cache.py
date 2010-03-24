import os

class Cache(object):
	
	def __init__(self):
		self.cache = {}
	
	def __contains__(self, key):
		if not os.path.isfile(key) or not key in self.cache:
			return False
		
		(k,_) = self.cache[key]
		if k < os.path.getmtime(key):
			del self.cache[key]
			return False
		
		return True
	
	def __getitem__(self, key):
		if not key in self:
			raise KeyError(key)
		
		(k,v) = self.cache[key]
		return v
	
	def __setitem__(self, key, val):
		if not os.path.isfile(key):
			raise IOError('invalid file path: ' + key)
		
		self.cache[key] = (os.path.getmtime(key), val)
