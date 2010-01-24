from __future__ import division
from __future__ import with_statement

import os
import imp
import cgi
import sys
from optparse import OptionParser

import lexer
import parser
from ply import lex, yacc
from patch import ex

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
	
	optparser.add_option('-i', '--filename',
		help='file to render',
		dest='filename')
	
	optparser.add_option('-d', '--debug',
		help='display debugging information',
		action='store_true',
		dest='debug',
		default=False)
	
	optparser.add_option('-w', '--attr_wrapper',
		help='attribute wrapper character',
		type='choice',
		choices=['"',"'"],
		dest='attr_wrapper',
		default="'")

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
	
	optparser.add_option('-s', '--suppress_eval',
		help='suppress script evaluation',
		action='store_true',
		dest='suppress_eval',
		default=False)
	
	optparser.add_option('-p', '--preserve',
		help='preserve whitespace tags',
		action='append',
		type='str',
		dest='preserve',
		default=['pre', 'textarea'])
	
	optparser.add_option('-a', '--autoclose',
		help='autoclose tags',
		action='append',
		type='str',
		dest='autoclose',
		default=[
			'meta',
			'img',
			'input',
			'link',
			'br',
			'hr',
			'area',
			'param',
			'col',
			'base',
		])
	
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
		(self.op, _) = engine.optparser.parse_args([])
		for (k,v) in kwargs.items():
			opt = engine.optparser.get_option('--' + k)
			if opt:
				self.op.__dict__[k] = opt.check_value(k,v)
	
	def find_module(self, fullname):
		dir = os.path.dirname(self.op.filename)
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
		self.write('  ' * self.depth)
	
	def write(self, s):
		self.html.append(s)
	
	def escape(self, s):
		self.write(cgi.escape(s, True))
	
	def attrs(self, id, klass, a):
		a = dict((k,v) for k,v in a.items() if v != None)
		if id:
			a['id'] = id + '_' + a.get('id','') if 'id' in a else id
		if klass:
			a['class'] = (klass + ' ' + a.get('class','')).strip()
		w = self.op.attr_wrapper
		for k,v in a.items():
			v = str(v).replace(w, {'"':'&quot;', "'":'&#39;'}[w])
			self.write(' %s=%s%s%s' % (k,w,v,w))
	
	def compile(self, s):
		self.parser.__dict__.update({
			'depth': 0,
			'src': [],
			'trim_next': False,
			'last_obj': None,
			'debug': self.op.debug,
			'op': self.op,
			'to_close': [],
			'preserve': 0,
		})
		
		self.lexer.begin('INITIAL')
		self.lexer.__dict__.update({
			'depth': 0,
			'type': None,
			'length': None,
			'block': None,
		})
		
		self.parser.parse(s, lexer=self.lexer, debug=self.op.debug)
		return '\n'.join(map(str, self.parser.src)) + '\n'
	
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
	
	def cache(self, filename):
		if not os.path.isfile(filename):
			raise Exception('file not found "%s"' % filename)
		if os.path.exists(filename + '.py'):
			if os.path.getmtime(filename) <= os.path.getmtime(filename + '.py'):
				return
		with open(filename + '.py', 'w') as py:
			with open(filename) as haml:
				py.write(self.compile(haml.read()))
	
	def to_html(self, s, *args, **kwargs):
		s = s.strip()
		if s == '':
			return ''
		self.setops(*args, **kwargs)
		return self.execute(self.compile(s), *args)
	
	def render(self, filename, *args, **kwargs):
		self.setops(filename=filename, *args, **kwargs)
		self.cache(filename)
		with open(filename + '.py') as f:
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
