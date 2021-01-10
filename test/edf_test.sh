#!/bin/bash


# test cases

python src/main.py -a edf -f svg -o cumulated_free -s 10 --case data/0

python src/main.py -a edf -f svg -o cumulated_free -s 10 --case data/1

python src/main.py -a edf -f svg -o cumulated_free -s 10 --case data/2

python src/main.py -a edf -f svg -o cumulated_free -s 10 --case data/3

python src/main.py -a edf -f svg -o cumulated_free -s 10 --case data/4

python src/main.py -a edf -f svg -o cumulated_free -s 10 --case data/5

python src/main.py -a edf -f svg -o cumulated_free -s 10 --case data/6

python src/main.py -a edf -f svg -o cumulated_free -s 10 --case data/order


# output

## raw

python src/main.py -a edf -f raw -o cumulated_free -s 10 --case data/0

python src/main.py -a edf -f raw -o cumulated_free -s 10 --case data/1

python src/main.py -a edf -f raw -o cumulated_free -s 10 --case data/order

## xml

python src/main.py -a edf -f xml -o cumulated_free -s 10 --case data/0

python src/main.py -a edf -f xml -o cumulated_free -s 10 --case data/1

python src/main.py -a edf -f xml -o cumulated_free -s 10 --case data/order

## json

python src/main.py -a edf -f json -o cumulated_free -s 10 --case data/0

python src/main.py -a edf -f json -o cumulated_free -s 10 --case data/1

python src/main.py -a edf -f json -o cumulated_free -s 10 --case data/order

