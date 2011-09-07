from __future__ import division
from __future__ import with_statement

import os
import imp
import cgi
import sys
import re
import code
from optparse import OptionParser
import logging
import pyhaml.traceback as traceback

import lexer
import parser
from lexer import HamlParserException
from parser import get_lines_in_position_range
from ply import lex, yacc
from patch import ex, StringIO
from cache import Cache

__version__ = '0.1'

class HamlException(Exception):
    """
An exception thrown while parsing or rendering Haml.
    """
    pass

class Loader(object):

    def __init__(self, engine, path):
        self.engine = engine
        self.path = path

    def load_module(self, fullname):
        return self.engine.load_module(fullname, self.path, self)

class Finder(object):

    def __init__(self, engine):
        self.engine = engine

    def find_module(self, fullname, path=None):
        return self.engine.find_module(fullname)

class Engine(object):

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
        default='"')

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
        self._cache = Cache()
        self.haml_line_cache = {}
        self.parser = yacc.yacc(
            module=parser,
            write_tables=0,
            debug=0)
        self.lexer = lex.lex(module=lexer)

    def reset(self):
        self.depth = 0
        self.html = StringIO()
        self.trim_next = False
        self.globals = { '_haml': self }

    def setops(self, *args, **kwargs):
        """
Sets options for the Haml engine.  Options should be given as keyword arguments.
        """
        (self.op, _) = Engine.optparser.parse_args([])
        for (k,v) in kwargs.items():
            opt = Engine.optparser.get_option('--' + k)
            if opt:
                self.op.__dict__[k] = opt.check_value(k,v)

    def find_module(self, fullname):
        dir = os.path.dirname(self.op.filename)
        path = os.path.join(dir, '%s.haml' % fullname)
        if os.path.exists(path):
            return Loader(self, path)
        return None

    def load_module(self, fullname, path, loader):
        code = self.cache(path)
        mod = imp.new_module(fullname)
        mod = sys.modules.setdefault(fullname, mod)
        mod.__file__ = path
        mod.__loader__ = loader
        mod.__dict__.update(self.globals)
        ex(code, mod.__dict__)
        return mod

    def imp(self, fullname):
        finder = Finder(self)
        loader = finder.find_module(fullname)
        if loader:
            return loader.load_module(fullname)
        return None

    def entab(self):
        self.depth += 1

    def detab(self):
        self.depth -= 1

    def trim(self):
        self.trim_next = True

    def indent(self, indent):
        if not self.trim_next:
            self.write('\n')
            if indent:
                self.write('  ' * self.depth)
        self.trim_next = False

    def write(self, *args):
        for arg in args:
            arg = arg.encode("ascii", "xmlcharrefreplace")
            self.html.write(arg)

    def escape(self, string):
        return cgi.escape(string, True)

    def preserve_whitespace(self, string):
        return string.replace('\n', '&#x000A;')

    def attrs(self, id, klass, a):
        a = dict((k,v) for k,v in a.items() if v != None)
        if id:
            a['id'] = id + '_' + a.get('id','') if 'id' in a else id
        if klass:
            a['class'] = (klass + ' ' + a.get('class','')).strip()
        w = self.op.attr_wrapper
        for k,v in a.items():
            if v is None or v is False: continue
            if v is True: v = k # for things like checked=checked
            v = unicode(v).replace(w, {'"':'&quot;', "'":'&#39;'}[w])
            self.write(' %s=%s%s%s' % (k,w,v,w))

    def compile(self, s, filename="<string>"):
        """
Compile a HAML string, returning a Python code object that can be exec'd.
Optional filename parameter specifies the name of the file containing the HAML
code, which helps give better error messages.
        """
        self.parser.__dict__.update({
            'depth': 0,
            'src': [],
            'last_obj': None,
            'debug': self.op.debug,
            'op': self.op,
            'to_close': [],
            'preserve': 0,
            'lineno': 1,
        })

        self.lexer.begin('INITIAL')
        self.lexer.__dict__.update({
            'depth': 0,
            'type': None,
            'length': None,
            'block': None,
            'lineno': 1,
        })

        try:
            self.parser.parse(s, lexer=self.lexer, debug=self.op.debug, tracking=True)
        except HamlParserException, ex:
            lineno, haml_line, msg = ex
            if type(haml_line) == int:
                #interpret haml_line as character position to get the line
                haml_line = get_lines_in_position_range(self.lexer.lexdata,
                    haml_line, haml_line)
            raise HamlException, (-1, "HAML error",
                "Parse error in file %r: %s at line %d:\n%s\n%s" %
(filename, msg, lineno, haml_line, traceback.format_exc(with_vars=True)))
        #add a line too the beginning of the Python source indicating which
        #Haml file this is.  This can be accessed later for getting descriptive
        #error messages.
        lines = ["HAML_file_name = %r" % filename]
        #haml_lines maps Python lines to Haml (line number, code) pairs.
        haml_lines = [(0, "<no line 0>"), (0, "<HAML setup>")]
        for call in self.parser.src:
            line = str(call)
            lines.append(line)
            haml_line = call.haml.posinfo
            #append once for every Python line this Haml call turned into
            for i in range(1 + line.count('\n')):
                haml_lines.append(haml_line)
        self.haml_line_cache[filename] = haml_lines
        src = '\n'.join(lines) + '\n'
        try:
            #important for file to be "<haml>" so execute() can detect Haml
            #code in tracebacks
            return code.compile_command(src, "<haml>", "exec")
        except SyntaxError:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            haml_line_number, haml_line = self.get_haml_line_info(filename,
exc_value.lineno, exc_value.text)
            #change the syntax error message to show the Haml code
            message = traceback.format_exception_only(exc_type, exc_value)
            #message[0] was originally 'File "<pythonfile>", line <pythonline>'
            message[0] = '  File "%s", line %d\n' % (filename, haml_line_number)
            #message[1] was originally the python line with the syntax error
            message[1] = '    %s\n  Python:\n%s' % (haml_line, message[1])
            raise HamlException(-1, "HAML error", ''.join(message))

    def get_haml_line_info(self, haml_file_name, python_line_number,
                           python_text="<unknown Python>"):
        """
Given a Haml file name and Python line number, figure out what Haml code in the
file produced the Python line.  Returns pair (Haml line number, Haml code).
Optional python_text argument specifies the Python code that caused the error,
which is used in case the Haml line can't be found.
        """
        haml_lines = self.haml_line_cache.get(haml_file_name, [])
        if python_line_number < len(haml_lines):
            return haml_lines[python_line_number]
        else:
            return (-1, "-# Python at line %d with unknown HAML: %s" %
                    (python_line_number, python_text))


    def execute(self, src, *args, **kwargs):
        """
Given Python code, execute it and report any Haml errors in a readable
traceback.
        """
        self.reset()
        if len(args) > 0:
            self.globals.update(args[0])
        if self.op.debug:
            sys.stdout.write(src)
        finder = Finder(self)
        sys.meta_path.append(finder)
        try:
            ex(src, self.globals)
            return self.html.getvalue().strip() + '\n'
        except:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            tb = traceback.extract_tb(exc_traceback)
            for i, (python_file_name, python_line_number, function_name, python_text, local) in enumerate(tb):
                if python_file_name == "<haml>":
                    haml_file_name = exc_traceback.tb_frame.f_globals.get(
                        "HAML_file_name", "<string>")
                    haml_line_number, haml_line = self.get_haml_line_info(
                        haml_file_name, python_line_number, python_text)
                    tb[i] = (haml_file_name, haml_line_number, function_name,
                             haml_line, local)
                exc_traceback = exc_traceback.tb_next
            formatted = ["Traceback (most recent call last):\n"]
            formatted += traceback.format_list(tb, with_vars=True)
            formatted += traceback.format_exception_only(exc_type, exc_value)
            raise HamlException, (-1, "HAML error", "".join(formatted))
        # finally:
        #     sys.meta_path.remove(finder)

    def cache(self, filename):
        """
Given a Haml filename, returns a Python code object that generates the HTML for
that Haml file.  This uses a cache so the same file isn't compiled twice.
        """
        if not filename in self._cache:
            with open(filename) as haml:
                self._cache[filename] = self.compile(haml.read(), filename)
        return self._cache[filename]

    def to_html(self, s, *args, **kwargs):
        """
Converts Haml code to its corresponding HTML.
        """
        s = s.strip()
        if s == '':
            return ''
        self.setops(*args, **kwargs)
        return self.execute(self.compile(s), *args)

    def render(self, filename, *args, **kwargs):
        """
Renders HTML from a Haml file.
        """
        self.setops(filename=filename, *args, **kwargs)
        src = self.cache(filename)
        return self.execute(src, filename=filename, *args)

eng = Engine()
setops = eng.setops
to_html = eng.to_html
render = eng.render

if __name__ == '__main__':
    (op, args) = Engine.optparser.parse_args(sys.argv[1:])

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
