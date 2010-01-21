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
	
	def push(self, s, **kwargs):
		self.indent()
		self.write(s, **kwargs)
		self.parser.trim_next = False
	
	def write(self, s, literal=False, escape=False):
		s = repr(s) if literal else 'str(%s)' % s
		f = 'escape' if escape else 'write'
		self.script('_haml.%s(%s)' % (f, s))
	
	def script(self, s):
		pre = '\t' * self.parser.depth
		self.parser.src += [pre + s]
	
	def attrs(self, id, klass, attrs):
		if attrs != '{}' or klass or id:
			s = '_haml.attrs(%s,%s,%s)'
			self.script(s % (repr(id), repr(klass), attrs,))
	
	def enblock(self):
		self.parser.depth += 1
	
	def deblock(self):
		self.parser.depth -= 1
	
	def indent(self):
		if not self.parser.trim_next:
			self.write('\n', literal=True)
			if not self.parser.preserve:
				self.script('_haml.indent()')
	
	def entab(self):
		self.script('_haml.entab()')
	
	def detab(self):
		self.script('_haml.detab()')
	
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
	
	def open(self):
		for l in self.lines:
			self.push(l, literal=True)

class JavascriptFilter(Filter):
	
	def open(self):
		w = self.parser.op.attr_wrapper
		self.push('<script type=%stext/javascript%s>' % (w,w), literal=True)
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
	
	def __init__(self, parser):
		haml_obj.__init__(self, parser)
		self.hash = ''
		self.id = ''
		self.klass = ''
		self.tagname = 'div'
		self.inner = False
		self.outer = False
		self.selfclose = False
	
	def addclass(self, s):
		self.klass = (self.klass + ' ' + s).strip()
	
	def auto(self):
		return (not self.value and
			(self.selfclose or self.tagname in self.parser.op.autoclose))
	
	def preserve(self):
		return self.tagname in self.parser.op.preserve
	
	def push(self, s, closing=False, **kwargs):
		(inner, outer) = (self.inner or self.preserve(), self.outer)
		if closing:
			(inner, outer) = (outer, inner)
		if not outer:
			self.indent()
		self.write(s, **kwargs)
		self.parser.trim_next = inner or self.preserve()
	
	def open(self):
		if self.selfclose and self.value:
			self.error('self-closing tags cannot have content')
		
		self.push('<' + self.tagname, literal=True)
		self.attrs(self.id, self.klass, self.hash)
		
		s = '>'
		if self.auto() and self.parser.op.format == 'xhtml':
			s = '/>'
		self.write(s, literal=True)
		
		if self.value:
			if isinstance(self.value, Script):
				self.write(self.value.value, escape=self.value.escape)
			else:
				self.write(self.value, literal=True)
		
		if self.preserve():
			self.parser.preserve += 1
	
	def close(self):
		if self.value or self.selfclose:
			self.no_nesting()
		
		if self.value or self is self.parser.last_obj and not self.auto():
			self.write('</' + self.tagname + '>', literal=True)
		
		if self.auto() or self.value or self is self.parser.last_obj:
			self.parser.trim_next = self.outer
		else:
			self.push('</' + self.tagname + '>', closing=True, literal=True)
		
		if self.preserve():
			self.parser.preserve -= 1

def close(obj):
	obj.detab()
	obj.close()

def p_haml_doc(p):
	'''haml :
			| doc
			| doc LF'''
	while len(p.parser.to_close) > 0:
		close(p.parser.to_close.pop())

def p_doc(p):
	'''doc : obj
			| doc obj
			| doc LF obj'''
	pass

def p_obj(p):
	'''obj : element
		| filter
		| content
		| comment
		| condcomment
		| doctype
		| script
		| silentscript'''
	while len(p.parser.to_close) > p.lexer.depth:
		close(p.parser.to_close.pop())
	p.parser.last_obj = p[1]
	p[1].open()
	p[1].entab()
	p.parser.to_close.append(p[1])

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
		p[0].lines.append(p[2])

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

def p_element(p):
	'''element : tag dict trim selfclose text'''
	p[0] = p[1]
	p[0].hash = p[2]
	p[0].inner = '<' in p[3]
	p[0].outer = '>' in p[3]
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
	if len(p) == 2:
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
	p[0].id = p[1]

def p_tag_class(p):
	'tag : CLASSNAME'
	p[0] = Tag(p.parser)
	p[0].addclass(p[1])

def p_tag_tagname_id(p):
	'tag : TAGNAME ID'
	p[0] = Tag(p.parser)
	p[0].tagname = p[1]
	p[0].id = p[2]

def p_tag_tag_class(p):
	'tag : tag CLASSNAME'
	p[0] = p[1]
	p[0].addclass(p[2])

def p_error(p):
	sys.stderr.write('syntax error[%s]\n' % (p,))
