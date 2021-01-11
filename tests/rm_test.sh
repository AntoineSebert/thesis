#!/bin/bash

printf "Testing standard cases with svg...\n\n"

printf "data/0 :\n"
python src/main.py -a rm -f svg -o cumulated_free -s 10 --case data/0 > tests/rm_test0.svg

printf "data/1 :\n"
python src/main.py -a rm -f svg -o cumulated_free -s 10 --case data/1 > tests/rm_test1.svg

printf "data/2 :\n"
python src/main.py -a rm -f svg -o cumulated_free -s 10 --case data/2 > tests/rm_test2.svg

printf "data/3 :\n"
python src/main.py -a rm -f svg -o cumulated_free -s 10 --case data/3 > tests/rm_test3.svg

printf "data/4 :\n"
#python src/main.py -a rm -f svg -o cumulated_free -s 10 --case data/4 > tests/rm_test4.svg & # too long ?

printf "data/5 :\n"
python src/main.py -a rm -f svg -o cumulated_free -s 10 --case data/5 > tests/rm_test5.svg

printf "data/6 :\n"
python src/main.py -a rm -f svg -o cumulated_free -s 10 --case data/6 > tests/rm_test6.svg

printf "done."
