for v in "2.5" "2.6" "3.1"
do
	make clean
	python$v $(dirname $0)/test.py
done
make clean
