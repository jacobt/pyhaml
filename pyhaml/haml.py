from __future__ import division
from __future__ import with_statement

import re
import os
import imp
import cgi
import sys
from optparse import OptionParser

if __name__ == '__main__' and __package__ == None:
	__package__ = 'pyhaml'

from . import lexer,parser
from .ply import lex, yacc
from .patch import ex

__version__ = '0.1'
	
class haml_loader(object):
	
	def __init__(self, engine, path):
		self.engine = engine
		self.path = path
	
	def load_module(self, fullname):
		return self.engine.load_module(fullname, self.path, self)

class haml_finder(object):
	
	def __init__(self, engine):
		self.engine = engine
	
	def find_module(self, fullname, path=None):
		return self.engine.find_module(fullname)

class engine(object):
	
	optparser = OptionParser(version=__version__)
	
	optparser.add_option('-d', '--debug',
		help='display debugging information',
		action='store_true',
		dest='debug',
		default=False)

	optparser.add_option('-f', '--format',
		help='(html5|html4|xhtml)',
		type='choice',
		choices=['html5', 'html4', 'xhtml'],
		default='html5',
		dest='format')

	optparser.add_option('-e', '--escape_html',
		help='sanitize values by default',
		action='store_true',
		dest='escape_html',
		default=True)
	
	optparser.add_option('-b', '--batch',
		help='batch compile haml files',
		action='store_true',
		dest='batch',
		default=False)
	
	def __init__(self):
		self.parser = yacc.yacc(
			module=parser,
			write_tables=0,
			debug=0)
		self.lexer = lex.lex(module=lexer)
	
	def reset(self):
		self.depth = 0
		self.html = []
		self.globals = { '_haml': self }
	
	def setops(self, *args, **kwargs):
		self.op, _ = engine.optparser.parse_args([])
		self.op.__dict__.update(kwargs)
	
	def find_module(self, fullname):
		dir = os.path.dirname(self.op.path)
		path = os.path.join(dir, '%s.haml' % fullname)
		if os.path.exists(path):
			return haml_loader(self, path)
		return None
	
	def load_module(self, fullname, path, loader):
		self.cache(path)
		with open(path + '.py') as f:
			src = f.read()
		mod = imp.new_module(fullname)
		mod = sys.modules.setdefault(fullname, mod)
		mod.__file__ = path
		mod.__loader__ = loader
		mod.__dict__.update(self.globals)
		ex(src, mod.__dict__)
		return mod
	
	def imp(self, fullname):
		finder = haml_finder(self)
		loader = finder.find_module(fullname)
		if loader:
			return loader.load_module(fullname)
		return None
	
	def entab(self):
		self.depth += 1
	
	def detab(self):
		self.depth -= 1
	
	def indent(self):
		self.write('\n' + '  ' * self.depth)
	
	def write(self, s):
		self.html.append(s)
	
	def escape(self, s):
		self.write(cgi.escape(s, True))
	
	def attrs(self, *args):
		attrs = {}
		for a in args:
			attrs.update(a)
		for k,v in attrs.items():
			self.write(' %s="%s"' % (k, str(v).replace('"', '&quot;')))
	
	def compile(self, s):
		self.parser.__dict__.update({
			'depth': 0,
			'src': [],
			'trim_next': False,
			'last_obj': None,
			'debug': self.op.debug,
			'op': self.op,
			'to_close': [],
		})
		
		self.lexer.begin('INITIAL')
		self.lexer.__dict__.update({
			'depth': 0,
			'type': None,
			'length': None,
			'block': None,
		})
		
		self.parser.parse(s, lexer=self.lexer, debug=self.op.debug)
		return '\n'.join(self.parser.src) + '\n'
	
	def execute(self, src, *args):
		self.reset()
		if len(args) > 0:
			self.globals.update(args[0])
		if self.op.debug:
			sys.stdout.write(src)
		finder = haml_finder(self)
		sys.meta_path.append(finder)
		try:
			ex(src, self.globals)
			return ''.join(self.html).strip() + '\n'
		finally:
			sys.meta_path.remove(finder)
	
	def cache(self, path):
		if not os.path.isfile(path):
			raise Exception('file not found "%s"' % path)
		if os.path.exists(path + '.py'):
			if os.path.getmtime(path) <= os.path.getmtime(path + '.py'):
				return
		with open(path + '.py', 'w') as py:
			with open(path) as haml:
				py.write(self.compile(haml.read()))
	
	def to_html(self, s, *args, **kwargs):
		s = s.strip()
		if s == '':
			return ''
		self.setops(*args, **kwargs)
		return self.execute(self.compile(s), *args)
	
	def render(self, path, *args, **kwargs):
		self.setops(path=path, *args, **kwargs)
		self.cache(path)
		with open(path + '.py') as f:
			return self.execute(f.read(), *args)

eng = engine()
to_html = eng.to_html
render = eng.render

if __name__ == '__main__':
	(op, args) = engine.optparser.parse_args(sys.argv[1:])
	
	if op.batch:
		eng.setops(**op.__dict__)
		for p in (s for s in args if s.endswith('.haml')):
			eng.cache(p)
	else:
		if not len(args):
			s = to_html(sys.stdin.read(), **op.__dict__)
		else:
			s = render(args[0], **op.__dict__)
		
		sys.stdout.write(s)
