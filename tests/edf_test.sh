#!/bin/bash

printf "Testing standard cases with svg...\n\n"

printf "data/0 :\n"
python src/main.py -a edf -f svg -o cumulated_free -s 10 --case data/0 > tests/edf_test0.svg

printf "data/1 :\n"
python src/main.py -a edf -f svg -o cumulated_free -s 10 --case data/1 > tests/edf_test1.svg

printf "data/2 :\n"
python src/main.py -a edf -f svg -o cumulated_free -s 10 --case data/2 > tests/edf_test2.svg

printf "data/3 :\n"
python src/main.py -a edf -f svg -o cumulated_free -s 10 --case data/3 > tests/edf_test3.svg

#printf "data/4 :\n"
#python src/main.py -a edf -f svg -o cumulated_free -s 10 --case data/4 > tests/edf_test4.svg & # too long ?

printf "data/5 :\n"
python src/main.py -a edf -f svg -o cumulated_free -s 10 --case data/5 > tests/edf_test5.svg

printf "data/6 :\n"
python src/main.py -a edf -f svg -o cumulated_free -s 10 --case data/6 > tests/edf_test6.svg

printf "done."

: '
printf "Testing output formats..."

printf "Testing raw output format..."

python src/main.py -a edf -f raw -o cumulated_free -s 10 --case data/0 > tests/test0.txt

python src/main.py -a edf -f raw -o cumulated_free -s 10 --case data/1 > tests/test1.txt

python src/main.py -a edf -f raw -o cumulated_free -s 10 --case data/2 > tests/test2.txt

python src/main.py -a edf -f raw -o cumulated_free -s 10 --case data/3 > tests/test3.txt

printf "done."

printf "Testing xml output format...\n"

python src/main.py -a edf -f xml -o cumulated_free -s 10 --case data/0 > tests/test0.xml

python src/main.py -a edf -f xml -o cumulated_free -s 10 --case data/1 > tests/test1.xml

python src/main.py -a edf -f xml -o cumulated_free -s 10 --case data/2 > tests/test2.xml

python src/main.py -a edf -f xml -o cumulated_free -s 10 --case data/3 > tests/test3.xml

printf "done."

printf "Testing json output format...\n"

python src/main.py -a edf -f json -o cumulated_free -s 10 --case data/0 > tests/test0.json

python src/main.py -a edf -f json -o cumulated_free -s 10 --case data/1 > tests/test1.json

python src/main.py -a edf -f json -o cumulated_free -s 10 --case data/2 > tests/test2.json

python src/main.py -a edf -f json -o cumulated_free -s 10 --case data/3 > tests/test3.json

printf "done."

printf "All tests done."
'
