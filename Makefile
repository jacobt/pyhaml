
script = test/test.py
versions = 2.5 2.6 3.1

.PHONY: test $(versions) clean

test: $(versions)
	@$(MAKE) -s clean

$(versions):
	@$(MAKE) -s clean
	@python$@ $(script)

clean:
	@find . -name *.pyc | xargs rm -f
	@rm -f parser.out
	@rm -f test/haml/*.py
