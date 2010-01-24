from __future__ import with_statement
import os
import sys
import difflib
import unittest
from functools import partial
from optparse import OptionValueError

dir = os.path.dirname(__file__)
parent = os.path.dirname(dir)
sys.path.insert(0, parent)
sys.path.insert(0, os.path.join(parent, 'pyhaml'))

from pyhaml.patch import StringIO
from pyhaml.parser import doctypes
from pyhaml.haml import to_html, render, engine

class TestHaml(unittest.TestCase):
	
	def diff(self, s, *args):
		p = os.path.join(dir, 'haml/%s.haml' % s)
		s1 = StringIO(render(p, *args)).readlines()
		
		p = os.path.join(dir, 'html/%s.html' % s)
		with open(p) as f:
			s2 = f.readlines()
		g = difflib.context_diff(s1, s2,
			fromfile='%s.haml' % s,
			tofile='%s.html' % s)
		
		fail = False
		for line in g:
			if not fail:
				sys.stdout.write('\n')
			fail = True
			sys.stdout.write(line)
		if fail:
			self.fail()
	
	def testempty(self):
		self.assertEqual('', to_html(''))
	
	def testtag(self):
		self.assertEqual('<div></div>\n', to_html("%div"))
		self.assertEqual("<div id='id'></div>\n", to_html("#id"))
		self.assertEqual("<div class='class'></div>\n", to_html(".class"))
		self.assertEqual("<div class='foo bar'></div>\n", to_html(".foo.bar"))
		self.assertEqual("<div id='foo' class='bar'></div>\n", to_html("#foo.bar"))
		self.assertEqual("<img id='foo' class='bar baz'>\n", to_html("%img#foo.bar.baz"))
		self.assertEqual("<p id='foo_bar'></p>\n", to_html("%p#foo{'id':'bar'}"))
		self.assertEqual("<p id='foo'></p>\n", to_html("%p#foo{'id':None}"))
		self.assertEqual("<p class='foo bar'></p>\n", to_html("%p.foo{'class':'bar'}"))
	
	def testattrs(self):
		self.assertEqual("<p a='b'></p>\n", to_html("%p{ 'a':'b', 'c':None }"))
		self.assertEqual("<div style='ugly' class='atlantis'></div>\n", to_html(".atlantis{'style' : 'ugly'}"))
		self.assertEqual("<img alt=''>\n", to_html("%img{'alt':''}"))
		self.assertEqual("<p foo='bar}'></p>\n", to_html("%p{'foo':'bar}'}"))
		self.assertEqual("<p foo='{bar'></p>\n", to_html("%p{'foo':'{bar'}"))
		self.assertEqual("<p foo='bar'></p>\n", to_html("%p{'foo':'''bar'''}"))
	
	def testoneline(self):
		self.assertEqual('<p>foo</p>\n', to_html('%p foo'))
	
	def teststripvalue(self):
		self.assertEqual('<p>strip</p>\n', to_html('%p       strip     '))
	
	def testemptytags(self):
		self.assertEqual('<p></p>\n<p></p>\n', to_html('%p\n%p'))
	
	def testmulti(self):
		self.assertEqual('<strong>foo</strong>\n', to_html('%strong foo'))
		self.assertEqual('<strong>foo</strong>\n', to_html('%strong foo'))
		self.assertEqual('<strong>foo</strong>\n', to_html('%strong foo'))
	
	def testhashwithnewline(self):
		self.assertEqual("<p a='b' c='d'>foo</p>\n", to_html("%p{'a' : 'b',\n   'c':'d'} foo"))
		self.assertEqual("<p a='b' c='d'>\n", to_html("%p{'a' : 'b',\n    'c' : 'd'}/"))
	
	def testtrim(self):
		self.assertEqual('<img><img><img>\n', to_html('%img\n%img>\n%img'))
		self.assertEqual('<p><b>foo</b></p>\n', to_html('%p\n %b<>\n  foo'))
		self.assertEqual("<p><b a='b'>foo</b></p>\n", to_html("%p\n %b{'a':'b'}<>\n  foo"))
		self.assertEqual("<p><b></b></p>\n", to_html('-def f():\n %b>\n%p\n -f()'))
		self.assertEqual("<p><b></b></p>\n", to_html('-def f():\n %b\n%p<\n -f()'))
	
	def testflextabs(self):
		html = '<p>\n  foo\n</p>\n<q>\n  bar\n  <a>\n    baz\n  </a>\n</q>\n'
		self.assertEqual(html, to_html('%p\n  foo\n%q\n  bar\n  %a\n    baz'))
		self.assertEqual(html, to_html('%p\n foo\n%q\n bar\n %a\n  baz'))
		self.assertEqual(html, to_html('%p\n\tfoo\n%q\n\tbar\n\t%a\n\t\tbaz'))
	
	def testmultilineattrs(self):
		self.assertEqual("<p foo='bar'>val</p>\n", to_html("%p{  \n   'foo'  :  \n  'bar'  \n } val"))
	
	def testcodeinattrs(self):
		self.assertEqual("<p foo='3'></p>\n", to_html("%p{ 'foo': 1+2 }"))
	
	def testnestedattrs(self):
		self.assertEqual(
			'''<p foo="{'foo': 'bar'}">val</p>\n''',
			to_html("%p{'foo':{'foo':'bar'}} val", attr_wrapper='"'))
	
	def testcrlf(self):
		self.assertEqual('<p>foo</p>\n<p>bar</p>\n<p>baz</p>\n<p>boom</p>\n',
			to_html('%p foo\r\n%p bar\r\n%p baz\n\r%p boom'))
	
	def testscript(self):
		self.assertEqual('<p>foo</p>\n', to_html("%p= 'foo'"))
		self.assertEqual('<p>foo</p>\n<p></p>\n', to_html("%p= 'foo'\n%p"))
		self.assertEqual('5\n', to_html("-foo=5\n&=foo"))
	
	def testmultilinescript(self):
		self.assertEqual('<p>foo\nbar</p>\n', to_html("%p='''foo\nbar'''"))
		self.assertEqual('<p>multiline</p>\n', to_html("%p=('multi'\n'line')"))
	
	def testescapeattrs(self):
		self.assertEqual("<img title='foo&#39;s'>\n", to_html("%img{'title':'foo\\'s'}"))
		self.assertEqual("<img foo='bar&baz'>\n", to_html("%img{'foo':'bar&baz'}"))
		self.assertEqual("<p foo='&#39;'></p>\n", to_html("%p{'foo':'\\''}"))
	
	def testsilent(self):
		self.assertEqual('\n', to_html('-#'))
		self.assertEqual('<p></p>\n<p></p>\n', to_html("%p\n-# foo\n%p"))
		self.assertEqual('<p></p>\n<p></p>\n', to_html("%p\n-# foo\n  bar\n    baz\n%p"))
		self.assertEqual('<div>\n  <span>foo</span>\n</div>\n', to_html("%div\n  %span foo\n  -# foo\n    bar\n      baz"))
		self.assertEqual('<div>\n  <p>\n    <b></b>\n  </p>\n</div>\n', to_html('%div\n %p\n  -#foo\n  %b'))
		self.assertEqual('<p></p>\n', to_html('%p\n -#\n \n  %b'))
	
	def testcomment(self):
		self.assertEqual('<!-- foo -->\n', to_html("/foo"))
		self.assertEqual('<!-- strip -->\n', to_html("/      strip     "))
		self.assertEqual('<!--\n  foo\n  bar\n-->\n', to_html("/\n foo\n bar"))
		self.assertEqual('<!--[if IE]> foo <![endif]-->\n', to_html('/[if IE] foo'))
		self.assertEqual('<!--[if IE]>\n  foo\n<![endif]-->\n', to_html('/[if IE]\n foo'))
	
	def testdoctype(self):
		self.assertEqual(doctypes['xhtml'][''], to_html('!!!', format='xhtml').strip())
		self.assertEqual(doctypes['xhtml']['strict'], to_html('!!! strict', format='xhtml').strip())
		self.assertEqual(doctypes['xhtml']['transitional'], to_html('!!! transitional', format='xhtml').strip())
		self.assertEqual(doctypes['xhtml']['basic'], to_html('!!! basic', format='xhtml').strip())
		self.assertEqual(doctypes['xhtml']['mobile'], to_html('!!! mobile', format='xhtml').strip())
		self.assertEqual(doctypes['xhtml']['frameset'], to_html('!!! frameset', format='xhtml').strip())
		self.assertEqual(doctypes['html4'][''], to_html('!!!', format='html4').strip())
		self.assertEqual(doctypes['html4']['strict'], to_html('!!! strict', format='html4').strip())
		self.assertEqual(doctypes['html4']['frameset'], to_html('!!! frameset', format='html4').strip())
		self.assertEqual(doctypes['html4']['transitional'], to_html('!!! transitional', format='html4').strip())
		self.assertEqual(doctypes['html5'][''], to_html('!!!', format='html5').strip())
	
	def testxmldoctype(self):
		self.assertEqual('<?xml version="1.0" encoding="utf-8"?>\n', to_html('!!! XML'))
		self.assertEqual('<?xml version="1.0" encoding="utf-16"?>\n', to_html('!!! XML utf-16'))
		self.assertEqual('<?xml version="1.0" encoding="utf-8"?>\n<!doctype html>\n', to_html('!!! XML\n!!!'))
	
	def testsanitize(self):
		self.assertEqual('cheese &amp; crackers\n', to_html("&= 'cheese & crackers'"))
		self.assertEqual('foo &lt; bar\n', to_html("&= 'foo < bar'"))
		self.assertEqual('foo &gt; bar\n', to_html("&='foo > bar'"))
	
	def testescapeopt(self):
		self.assertEqual('cheese & crackers\n', to_html("='cheese & crackers'", escape_html=False))
		self.assertEqual('cheese &amp; crackers\n', to_html("='cheese & crackers'", escape_html=True))
		self.assertEqual('foo &gt; bar\n', to_html("= 'foo > bar'", escape_html=True))
		self.assertEqual('foo < bar\n', to_html("= 'foo < bar'", escape_html=False))
	
	def testnosanitize(self):
		self.assertEqual('<&>\n', to_html("!='<&>'", escape_html=True))
		self.assertEqual('<&>\n', to_html("!='<&>'", escape_html=False))
	
	def testbackslashstart(self):
		self.assertEqual('#\n', to_html('\\#'))
		self.assertEqual('.foo\n%bar\n', to_html('\\.foo\n\\%bar'))
		self.assertEqual('<div>foo</div>\n', to_html('%div \\foo'))
		self.assertEqual('<p>.foo</p>\n<p>%bar</p>\n', to_html('%p\\.foo\n%p\\%bar'))
	
	def testdictlocals(self):
		def foo():
			return 'bar'
		self.assertEqual("<p foo='bar'></p>\n", to_html("%p{'foo':foo}", {'foo':'bar'}))
		self.assertEqual("<p foo='bar'></p>\n", to_html("%p{'foo':foo()}", {'foo':foo}))
	
	def testscriptlocals(self):
		def foo():
			return 'bar'
		self.assertEqual('<p>bar</p>\n', to_html("%p=foo", {'foo':'bar'}))
		self.assertEqual('<p>bar</p>\n', to_html("%p=foo()", {'foo':foo}))
	
	def testsilentscript(self):
		self.assertEqual('<p>bar</p>\n', to_html("-foo='bar'\n%p=foo"))
		self.assertEqual('<p>barboom</p>\n', to_html("-foo='bar'\n-foo+='boom'\n%p=foo"))
		self.assertEqual('<p>multiline</p>\n', to_html("-foo=('multi'\n'line')\n%p=foo"))
		self.assertEqual('ab\n', to_html("-a='a'\n\n-b='b'\n=a+b"))
	
	def testattrwithscript(self):
		self.assertEqual("<p foo='bar'></p>\n", to_html("-foo='bar'\n%p{'foo':foo}"))
	
	def testfor(self):
		self.assertEqual('<p>0</p>\n<p>1</p>\n', to_html("-for i in range(2):\n %p=i"))
	
	def testfunc(self):
		self.assertEqual('<p>0</p>\n<p>1</p>\n', to_html('-def foo(n):\n %p=n\n-for i in range(2):\n -foo(i)'))
		self.assertEqual('<p>\n  <a></a>\n</p>\n', to_html('-def foo():\n %a\n%p\n - foo()'))
		self.assertEqual('foo\n', to_html('-foo="foo"\n-def bar():\n =foo\n-bar()'))
	
	def testautoclose(self):
		self.assertEqual('<sandwich/>\n', to_html('%sandwich/', format='xhtml'))
		self.assertEqual("<script src='foo'></script>\n", to_html("%script{'src':'foo'}"))
		self.assertEqual("<script src='foo'>fallback</script>\n", to_html("%script{'src':'foo'} fallback"))
		self.assertEqual("<script src='foo'>\n  bar\n</script>\n", to_html("%script{'src':'foo'}\n bar"))
		self.assertEqual("<link rel='stylesheet'>\n", to_html("%link{'rel':'stylesheet'}"))
		self.assertEqual("<link rel='stylesheet'>foo</link>\n", to_html("%link{'rel':'stylesheet'} foo"))
		self.assertEqual("<meta content='text/html'>\n", to_html("%meta{'content':'text/html'}"))
		self.assertEqual("<input type='text'/>\n", to_html("%input{ 'type':'text' }", format='xhtml'))
		self.assertEqual("<foo>\n<bar>\n", to_html("%foo\n%bar", autoclose=['foo','bar']))
	
	def testillegalnesting(self):
		self.assertRaises(Exception, partial(to_html, '!!!\n %p'))
		self.assertRaises(Exception, partial(to_html, 'foo\n bar'))
		self.assertRaises(Exception, partial(to_html, '%p foo\n bar'))
		self.assertRaises(Exception, partial(to_html, '%p/\n foo'))
	
	def testillegalvalue(self):
		self.assertRaises(Exception, partial(to_html, '%p/ foo'))
	
	def testraise(self):
		self.assertRaises(Exception, partial(to_html, '-raise Exception("")'))
	
	def testindentation(self):
		self.assertRaises(Exception, partial(to_html, '%p\n\t %p'))
		self.assertRaises(Exception, partial(to_html, '%p\n %p\n    %p'))
		self.assertRaises(Exception, partial(to_html, '%p\n  %p\n   %p'))
		self.assertRaises(Exception, partial(to_html, '%p\n  %p\n\t\t%p'))
		self.assertRaises(Exception, partial(to_html, '%p\n\t%p\n  %p'))
	
	def testspace(self):
		self.assertEqual('<p>3</p>\n', to_html("%p   =   3"))
		self.assertEqual("<p foo='bar'></p>\n", to_html("%p  { 'foo':'bar' }"))
		self.assertEqual('<p>foo</p>\n', to_html("%p   !=   'foo'"))
		self.assertEqual('<p>bar</p>\n', to_html("%p   &=   'bar'"))
	
	def testmultiline(self):
		self.assertEqual('<p>multi line string</p>\n', to_html('%p multi |\n  line |\n  string |'))
		self.assertEqual('<p>multi %line .string</p>\n<p></p>\n', to_html('%p multi |\n  %line |\n  .string |\n%p'))
		self.assertEqual('<p>\n  multi %line .string\n</p>\n', to_html('%p\n multi |\n %line |\n .string |'))
		self.assertEqual('multi %line .string\n', to_html('multi |\n%line |\n.string |'))
		self.assertEqual('<p>multi line</p>\n', to_html('%p multi |\n  \n line |\n'))
		self.assertEqual('<p>\n  multi line\n</p>\n<p></p>\n', to_html('%p\n multi |\n line |\n%p'))
	
	def testfilters(self):
		self.assertEqual('\n', to_html(':plain'))
		self.assertEqual('foo\n  bar\nbaz\n', to_html(':plain\n  foo\n    bar\n  baz'))
		self.assertEqual('<div></div>\n', to_html(':plain\n%div'))
		self.assertRaises(Exception, partial(to_html, ':foo\n foo'))
		self.assertEqual(
			"<script type='text/javascript'>\n  //<![CDATA[\n    var foo;\n  //]]>\n</script>\n",
			to_html(':javascript\n\tvar foo;', format='xhtml'))
		self.assertEqual(
			"<script type='text/javascript'>\n  var foo;\n</script>\n",
			to_html(':javascript\n\tvar foo;'))
	
	def testsuppress(self):
		self.assertEqual('<p></p>\n', to_html('%p = "foo"', suppress_eval=True))
		self.assertEqual('<p></p>\n', to_html("%p{'foo':'bar'}", suppress_eval=True))
		self.assertEqual('\n', to_html("= 'foo'", suppress_eval=True))
		self.assertRaises(Exception, partial(to_html, '-foo="foo"', suppress_eval=True))
	
	def testpreserve(self):
		self.assertEqual('<pre><code></code></pre>\n', to_html('%pre\n %code'))
		self.assertEqual('<div>\n  <pre></pre>\n</div>\n', to_html('%div\n %pre'))
		self.assertEqual('<pre>a\nb\nc</pre>\n', to_html('%pre\n  a\n  b\n  c'))
		self.assertEqual('<pre>a\nb\nc</pre>\n', to_html("%pre = 'a\\nb\\nc'"))
	
	def testwrapper(self):
		self.assertEqual("<div class='foo'></div>\n", to_html('.foo', attr_wrapper="'"))
		self.assertEqual('<div class="foo"></div>\n', to_html('.foo', attr_wrapper='"'))
		self.assertRaises(OptionValueError, partial(to_html, '.foo', attr_wrapper=''))
	
	def testbasicdiff(self):
		self.diff('basic')
	
	def testfuncdiff(self):
		self.diff('func')
	
	def testimportdiff(self):
		self.diff('ext', { 'bar': 'foo'})
	
	def testimpdiff(self):
		self.diff('imp', { 'bar': 'foo'})
	
if __name__ == '__main__':
	unittest.main()
