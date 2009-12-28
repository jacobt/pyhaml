import sys
from functools import *
from .lexer import tokens

doctypes = {
	'xhtml': {
		'strict':
			'<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN" '
			'"http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">',
		'transitional':
			'<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" '
			'"http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">',
		'basic':
			'<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML Basic 1.1//EN" '
			'"http://www.w3.org/TR/xhtml-basic/xhtml-basic11.dtd">',
		'mobile':
			'<!DOCTYPE html PUBLIC "-//WAPFORUM//DTD XHTML Mobile 1.2//EN" '
			'"http://www.openmobilealliance.org/tech/DTD/xhtml-mobile12.dtd">',
		'frameset':
			'<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Frameset//EN" '
			'"http://www.w3.org/TR/xhtml1/DTD/xhtml1-frameset.dtd">'
	},
	'html4': {
		'strict':
			'<!DOCTYPE html PUBLIC "-//W3C//DTD HTML 4.01//EN" '
			'"http://www.w3.org/TR/html4/strict.dtd">',
		'frameset':
			'<!DOCTYPE html PUBLIC "-//W3C//DTD HTML 4.01 Frameset//EN" '
			'"http://www.w3.org/TR/html4/frameset.dtd">',
		'transitional':
			'<!DOCTYPE html PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN" '
			'"http://www.w3.org/TR/html4/loose.dtd">'
	},
	'html5': { '': '<!doctype html>' }
}

doctypes['xhtml'][''] = doctypes['xhtml']['transitional']
doctypes['html4'][''] = doctypes['html4']['transitional']

class haml_obj(object):
	
	def __init__(self, parser):
		self.parser = parser
		self.__dict__.update({
			'push': partial(push, parser),
			'write': partial(write, parser),
			'script': partial(script, parser),
			'enblock': partial(enblock, parser),
			'deblock': partial(deblock, parser),
		})
	
	def entab(self):
		script(self.parser, '_haml.entab()')
	
	def detab(self):
		script(self.parser, '_haml.detab()')
	
	def open(self):
		pass
	
	def close(self):
		pass
	
	def no_nesting(self):
		if not self.parser.last_obj is self:
			self.error('illegal nesting')
	
	def error(self, msg):
		raise Exception(msg)

class Filter(haml_obj):
	
	def __init__(self, parser):
		haml_obj.__init__(self, parser)
		self.lines = []
	
	def addline(self, l):
		self.lines.append(l)
	
	def open(self):
		for l in self.lines:
			self.push(l, literal=True)

class JavascriptFilter(Filter):
	
	def open(self):
		self.push('<script type="text/javascript">', literal=True)
		self.entab()
		if self.parser.op.format == 'xhtml':
			self.push('//<![CDATA[', literal=True)
			self.entab()
		for l in self.lines:
			self.push(l, literal=True)
		self.detab()
		if self.parser.op.format == 'xhtml':
			self.push('//]]>', literal=True)
			self.detab()
		self.push('</script>', literal=True)

class Content(haml_obj):
	
	def __init__(self, parser, value):
		haml_obj.__init__(self, parser)
		self.value = value
	
	def open(self):
		self.push(self.value, literal=True)
	
	def close(self):
		self.no_nesting()

class Script(haml_obj):
	
	def __init__(self, parser, type='=', value=''):
		haml_obj.__init__(self, parser)
		self.type = type
		self.value = value
		self.escape = False
		if self.type == '&=':
			self.escape = True
		elif self.type == '=' and parser.op.escape_html:
			self.escape = True
	
	def open(self):
		self.push(self.value, escape=self.escape)
	
	def close(self):
		pass

class SilentScript(haml_obj):
	
	def __init__(self, parser, value=''):
		haml_obj.__init__(self, parser)
		self.value = value
	
	def entab(self):
		pass
	
	def detab(self):
		pass
	
	def open(self):
		self.script(self.value)
		self.enblock()
	
	def close(self):
		self.deblock()

class Doctype(haml_obj):
	
	def __init__(self, parser):
		haml_obj.__init__(self, parser)
		self.xml = False
		self.type = ''
	
	def open(self):
		if self.xml:
			s = '<?xml version="1.0" encoding="%s"?>'
			self.push(s % self.type, literal=True)
		else:
			s = doctypes[self.parser.op.format][self.type]
			self.push(s, literal=True)
	
	def close(self):
		self.no_nesting()

class Comment(haml_obj):
	
	def __init__(self, parser, value='', condition=''):
		haml_obj.__init__(self, parser)
		self.value = value.strip()
		self.condition = condition.strip()
	
	def open(self):
		if self.condition:
			s = '<!--[%s]>' % self.condition
		else:
			s = '<!--'
		if self.value:
			s += ' ' + self.value
		self.push(s, literal=True)
	
	def close(self):
		if self.condition:
			s = '<![endif]-->'
		else:
			s = '-->'
		if self.value:
			self.write(' ' + s, literal=True)
		else:
			self.push(s, literal=True)

class Tag(haml_obj):
	
	preserve = (
		'textarea',
		'pre',
	)
	
	autoclose = (
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
	)
	
	def __init__(self, parser):
		haml_obj.__init__(self, parser)
		self.dict = ''
		self.attrs = {}
		self.tagname = 'div'
		self.inner = False
		self.outer = False
		self.selfclose = False
	
	def addclass(self, s):
		if not 'class' in self.attrs:
			self.attrs['class'] = s
		else:
			self.attrs['class'] += ' ' + s
	
	def auto(self):
		return (not self.value and
			(self.selfclose or self.tagname in Tag.autoclose))
	
	def open(self):
		if self.selfclose and self.value:
			self.error('self-closing tags cannot have content')
		
		self.push('<' + self.tagname, inner=self.inner, outer=self.outer, literal=True)
		self.script('_haml.attrs(%s, %s)' % (self.dict, repr(self.attrs)))
		
		if self.auto():
			self.no_nesting()
			self.write('/', literal=True)
		
		self.write('>', literal=True)
		
		if self.value:
			if isinstance(self.value, Script):
				script = self.value
				self.write(script.value, escape=script.escape)
			else:
				self.write(self.value, literal=True)
	
	def close(self):
		if self.value or self.selfclose:
			self.no_nesting()
		
		if self.value or self is self.parser.last_obj and not self.auto():
			self.write('</' + self.tagname + '>', literal=True)
		
		if self.auto() or self.value or self is self.parser.last_obj:
			self.parser.trim_next = self.outer
		else:
			self.push('</' + self.tagname + '>', inner=self.outer, outer=self.inner, literal=True)

def enblock(parser):
	parser.depth += 1

def deblock(parser):
	parser.depth -= 1

def push(parser, s, inner=False, outer=False, **kwargs):
	if outer or parser.trim_next:
		write(parser, s, **kwargs)
	else:
		script(parser, '_haml.indent()')
		write(parser, s, **kwargs)
	parser.trim_next = inner

def write(parser, s, literal=False, escape=False):
	s = repr(s) if literal else 'str(%s)' % s
	f = '_haml.escape' if escape else '_haml.write'
	script(parser, '%s(%s)' % (f, s))

def script(parser, s):
	pre = '\t' * parser.depth
	parser.src += [pre + s]

def close(obj):
	obj.detab()
	obj.close()

def open(p, obj):
	while len(p.parser.to_close) > p.lexer.depth:
		close(p.parser.to_close.pop())
	p.parser.last_obj = obj
	obj.open()
	obj.entab()
	p.parser.to_close.append(obj)

def p_haml_doc(p):
	'''haml :
			| doc
			| doc LF'''
	while len(p.parser.to_close) > 0:
		close(p.parser.to_close.pop())

def p_doc(p):
	'doc : obj'
	open(p, p[1])

def p_doc_obj(p):
	'doc : doc obj'
	open(p, p[2])

def p_doc_indent_obj(p):
	'doc : doc LF obj'
	open(p, p[3])

def p_obj(p):
	'''obj : element
		| filter
		| content
		| comment
		| condcomment
		| doctype
		| script
		| silentscript'''
	p[0] = p[1]

def p_filter(p):
	'''filter : filter FILTER
				| FILTER'''
	if len(p) == 2:
		types = {
			'plain': Filter,
			'javascript': JavascriptFilter,
		}
		if not p[1] in types:
			raise Exception('Invalid filter: %s' % type)
		p[0] = types[p[1]](p.parser)
	elif len(p) == 3:
		p[0] = p[1]
		p[0].addline(p[2])

def p_silentscript(p):
	'''silentscript : SILENTSCRIPT'''
	if p.parser.op.suppress_eval:
		raise Exception('python evaluation is not allowed')
	p[0] = SilentScript(p.parser, value=p[1])

def p_script(p):
	'''script : TYPE SCRIPT'''
	if p.parser.op.suppress_eval:
		p[2] = '""'
	p[0] = Script(p.parser, type=p[1], value=p[2])

def p_content(p):
	'''content : value'''
	p[0] = Content(p.parser, p[1])

def p_doctype(p):
	'''doctype : DOCTYPE'''
	p[0] = Doctype(p.parser)

def p_htmltype(p):
	'''doctype : DOCTYPE HTMLTYPE'''
	p[0] = Doctype(p.parser)
	p[0].type = p[2]

def p_xmltype(p):
	'''doctype : DOCTYPE XMLTYPE'''
	p[0] = Doctype(p.parser)
	if p[2] == '':
		p[2] = 'utf-8'
	p[0].type = p[2]
	p[0].xml = True

def p_condcomment(p):
	'''condcomment : CONDCOMMENT
				| CONDCOMMENT VALUE'''
	p[0] = Comment(p.parser, condition=p[1])
	if len(p) == 3:
		p[0].value = p[2]

def p_comment(p):
	'''comment : COMMENT
			| COMMENT VALUE'''
	p[0] = Comment(p.parser)
	if len(p) == 3:
		p[0].value = p[2]

def p_element_tag_trim_dict_value(p):
	'''element : tag trim dict selfclose text'''
	p[0] = p[1]
	p[0].inner = '<' in p[2]
	p[0].outer = '>' in p[2]
	p[0].dict = p[3]
	p[0].selfclose = p[4]
	p[0].value = p[5]

def p_selfclose(p):
	'''selfclose :
				| '/' '''
	p[0] = len(p) == 2

def p_trim(p):
	'''trim :
		| TRIM'''
	if len(p) == 1:
		p[0] = ''
	else:
		p[0] = p[1]

def p_text(p):
	'''text :
			| value
			| script'''
	if len(p) == 1:
		p[0] = None
	elif len(p) == 2:
		p[0] = p[1]

def p_value(p):
	'''value : value VALUE
			| VALUE'''
	if len(p) == 2:
		p[0] = p[1]
	elif len(p) == 3:
		p[0] = '%s %s' % (p[1], p[2])

def p_dict(p):
	'''dict : 
			| DICT '''
	if len(p) == 1 or p.parser.op.suppress_eval:
		p[0] = '{}' 
	else:
		p[0] = p[1]

def p_tag_tagname(p):
	'tag : TAGNAME'
	p[0] = Tag(p.parser)
	p[0].tagname = p[1]

def p_tag_id(p):
	'tag : ID'
	p[0] = Tag(p.parser)
	p[0].attrs['id'] = p[1]

def p_tag_class(p):
	'tag : CLASSNAME'
	p[0] = Tag(p.parser)
	p[0].addclass(p[1])

def p_tag_tagname_id(p):
	'tag : TAGNAME ID'
	p[0] = Tag(p.parser)
	p[0].tagname = p[1]
	p[0].attrs['id'] = p[2]

def p_tag_tag_class(p):
	'tag : tag CLASSNAME'
	p[0] = p[1]
	p[0].addclass(p[2])

def p_error(p):
	sys.stderr.write('syntax error[%s]\n' % (p,))
