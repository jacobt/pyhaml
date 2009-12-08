#pyHaml

pyHaml is a python port of [Haml](http://haml.hamptoncatlin.com), an HTML templating engine used primarily with Ruby on Rails.  Ruby Haml will be referred to as rHaml for the purposes of this document.

In order to make pyHaml a bit more pythonic, most of the syntax evaluated as Ruby in rHaml is evaluated as python.  For example, the following rHaml code snippet:

    %tagname{:attr1 => 'value1', :attr2 => 'value2'} Contents

is written in pyhaml, using python `dict`, as:

    %tagname{'attr1': 'value1', 'attr2': 'value2'} Contents

pyHaml aims to be flexible and intuitive, allowing python to be evaluated inline as would be expected.

    - def foo(i):
      %p = i ** 2
    - for i in range(4):
      - foo(i)

yields

    <p>0</p>
    <p>1</p>
    <p>4</p>
    <p>9</p>

By allowing haml inside of python code blocks, some handy functionality can be produced through function composition.  For instance, to wrap the output of a function in some predefined html one could use the following construct:

    -def wrap(f):
      .wrapper
        %p
          -f()
    
    -def foo():
      foo
    
    -wrap(foo)

which produces the following html:

    <div class="wrapper">
      <p>
        foo
      </p>
    </div>

#imports

Markup should be reused just like code (since it is code).  In this vein there should be some way to use one haml document from within another.  In the spirit of python, pyHaml does this using the import statement.  For instance, assuming the following two documents:

    -# foo.haml
    - def foo():
      %p foo

    -# bar.haml
    - import foo
    - foo.foo()

rendering `bar.haml` produces `<p>foo</p>`.  Some versions of python, particularly the one used in google appengine, cache imports.  This makes it impossible to use import for this purpose.  For this reason, the `__imp__` method is provided instead.  In the previous example the line `- import foo` would be written as `-foo = _haml.imp('foo')`.

#command line

pyhaml uses relative imports within the package.  For command line use, the guidlines in [PEP 366](http://www.python.org/dev/peps/pep-0366/) are followed.  Therefore, when running pyhaml from the command line, one must use python's -m switch in order to run pyhaml.  For instance, one could use `python -m pyhaml.haml <args...>` at the command line.

#portability

pyHaml runs on python 2.5, 2.6 and the latest version of python 3.
