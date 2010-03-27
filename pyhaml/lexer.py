import re
import os
import sys
import token

from patch import toks, untokenize

tokens = (
    'LF',
    'DOCTYPE',
    'HTMLTYPE',
    'XMLTYPE',
    'TAGNAME',
    'ID',
    'CLASSNAME',
    'VALUE',
    'TRIM',
    'DICT',
    'SCRIPT',
    'SILENTSCRIPT',
    'COMMENT',
    'CONDCOMMENT',
    'TYPE',
    'FILTER',
)

states = (
    ('tag', 'exclusive'),
    ('silent', 'exclusive'),
    ('doctype', 'exclusive'),
    ('comment', 'exclusive'),
    ('tabs', 'exclusive'),
    ('multi', 'exclusive'),
    ('script', 'exclusive'),
    ('filter', 'exclusive'),
)

literals = '":,{}<>/'
t_ANY_ignore = '\r'

def build(self, **kwargs):
    self.lexer.depth = 0
    self.lexer.type = None
    self.lexer.length = None
    self.lexer.block = None
    return self

def pytokens(t):
    for tok in toks(t.lexer.lexdata[t.lexer.lexpos:]):
        _, s, _, (_, ecol), _ = tok
        yield tok
        for _ in range(s.count('\n')):
            t.lexer.lineno += 1
            t.lexer.lexpos = t.lexer.lexdata.find('\n', t.lexer.lexpos+1) + 1

def read_dict(t):
    t.value = []
    lvl = 0
    for tok in pytokens(t):
        _, s, _, (_, ecol), _ = tok
        t.value += [tok]
        if s == '{':
            lvl += 1
        elif s == '}':
            lvl -= 1
            if lvl == 0:
                t.lexer.lexpos += ecol
                t.value = untokenize(t.value)
                return t

def read_script(t):
    src = []
    for tok in pytokens(t):
        type, s, _, (_, ecol), _ = tok
        if s == '':
            t.lexer.lexpos = len(t.lexer.lexdata)
            src = untokenize(src).strip()
            return src
        src += [tok]
        if type == token.NEWLINE:
            t.lexer.lexpos += ecol - 1
            src = untokenize(src).strip()
            return src

def t_tag_doctype_comment_INITIAL_LF(t):
    r'\n([\s]*\n)?'
    t.lexer.lineno += t.value.count('\n')
    t.lexer.begin('INITIAL')
    t.lexer.push_state('tabs')
    return t

def t_silent_filter_LF(t):
    r'\n([\s]*\n)?'
    t.lexer.lineno += t.value.count('\n')
    t.lexer.push_state('tabs')

def t_tabs_other(t):
    r'[^ \t]'
    t.lexer.pop_state()
    if not t.lexer.block is None:
        t.lexer.block = None
        t.lexer.begin('INITIAL')
    t.lexer.lexpos -= len(t.value)
    t.lexer.depth = 0

def t_tabs_indent(t):
    r'[ \t]+'
    t.lexer.pop_state()
    if t.lexer.type == None:
        t.lexer.type = t.value[0]
        t.lexer.length = len(t.value)
    
    if not t.lexer.block is None:
        if len(t.value) / t.lexer.length < t.lexer.block:
            t.lexer.block = None
            t.lexer.begin('INITIAL')
        else:
            tablen = t.lexer.length * t.lexer.block
            if tablen < len(t.value):
                t.lexer.lexpos -= (len(t.value) - tablen)
                t.value = t.value[:tablen]
    
    if any(c != t.lexer.type for c in t.value):
        raise Exception('mixed indentation')
    
    (d,r) = divmod(len(t.value), t.lexer.length)
    if r > 0 or d - t.lexer.depth > 1:
        raise Exception('invalid indentation')
    
    t.lexer.depth = d

def t_silentcomment(t):
    r'-\#[^\n]*'
    t.lexer.block = t.lexer.depth + 1
    t.lexer.push_state('silent')

def t_silent_other(t):
    r'[^\n]+'
    pass

def t_DOCTYPE(t):
    r'!!!'
    t.lexer.begin('doctype')
    return t

def t_doctype_XMLTYPE(t):
    r'[ ]+XML([ ]+[^\n]+)?'
    t.value = t.value.replace('XML', '', 1).strip()
    return t

def t_doctype_HTMLTYPE(t):
    r'[ ]+(strict|frameset|mobile|basic|transitional)'
    t.value = t.value.strip()
    return t

def t_VALUE(t):
    r'[^:=&/#!.%\n\t -][^\n]*'
    t.value = t.value.strip()
    if t.value[0] == '\\':
        t.value = t.value[1:]
    if t.value[-2:] in ('\t|',' |'):
        t.lexer.begin('multi')
        t.value = t.value[:-1].strip()
    return t

def t_CONDCOMMENT(t):
    r'/\[[^\]]+\]'
    t.lexer.begin('comment')
    t.value = t.value[2:-1]
    return t

def t_COMMENT(t):
    r'/'
    t.lexer.begin('comment')
    return t

def t_comment_VALUE(t):
    r'[^\n]+'
    t.value = t.value.strip()
    return t

def t_TAGNAME(t):
    r'%[a-zA-Z][a-zA-Z0-9]*'
    t.lexer.begin('tag')
    t.value = t.value[1:]
    return t

def t_tag_INITIAL_ID(t):
    r'\#[a-zA-Z][a-zA-Z0-9]*'
    t.value = t.value[1:]
    t.lexer.begin('tag')
    return t

def t_tag_INITIAL_CLASSNAME(t):
    r'\.[a-zA-Z-][a-zA-Z0-9-]*'
    t.value = t.value[1:]
    t.lexer.begin('tag')
    return t

def t_tag_DICT(t):
    r'[ ]*{'
    t.lexer.lexpos -= 1
    return read_dict(t)

def t_SILENTSCRIPT(t):
    r'-'
    t.value = read_script(t)
    return t

def t_tag_INITIAL_TYPE(t):
    r'[ ]*(&|!)?='
    t.lexer.lexpos -= 1
    t.value = t.value.strip()
    t.lexer.push_state('script')
    return t

def t_script_SCRIPT(t):
    r'='
    t.value = read_script(t)
    t.lexer.pop_state()
    return t

def t_tag_TRIM(t):
    r'<>|><|<|>'
    return t

def t_tag_VALUE(t):
    r'[ \t]*[^{}<>=&/#!.%\n\t -][^\n]*'
    t.value = t.value.strip()
    if t.value[0] == '\\':
        t.value = t.value[1:]
    if t.value[-2:] in ('\t|',' |'):
        t.value = t.value[:-1].strip()
        t.lexer.begin('multi')
    return t

def t_multi_newline(t):
    r'\n([\s]*\n)?'
    t.lexer.lineno += t.value.count('\n')

def t_multi_VALUE(t):
    r'[^\n]+'
    if t.value.strip()[-2:] in ('\t|',' |'):
        t.value = t.value.strip()[:-1].strip()
        return t
    t.lexer.lexpos -= len(t.value)
    t.lexer.begin('INITIAL')
    t.lexer.push_state('tabs')
    t.type = 'LF'
    t.value = '\n'
    return t

def t_FILTER(t):
    r':[^\n]+'
    t.lexer.block = t.lexer.depth + 1
    t.value = t.value[1:]
    t.lexer.push_state('filter')
    return t

def t_filter_FILTER(t):
    r'[^\n]+'
    return t

def t_ANY_error(t):
    sys.stderr.write('Illegal character(s) [%s]\n' % t.value)
    t.lexer.skip(1)
