#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Resources
	https://numpydoc.readthedocs.io/en/latest/format.html

Static analysis
	tests :			https://github.com/pytest-dev/pytest
	type checking :	https://github.com/python/mypy

Sample
	python src/main.py -a edf -f svg -o max_empty-cmltd -s 10 --case data/1
"""

# IMPORTS #############################################################################################################


import logging
from argparse import ArgumentParser, Namespace
from concurrent.futures import ThreadPoolExecutor, as_completed
from json import load
from pathlib import Path
from time import process_time
from typing import Callable, TypeVar

from builder import build

from format import OutputFormat

from log import ColoredHandler

from model import Configuration, FilepathPair, Parameters, Problem, Solution, objectives

from solver import algorithms, solve

from tqdm import tqdm  # type: ignore


# FUNCTIONS ###########################################################################################################


def _add_dataset_arggroup(parser: ArgumentParser) -> ArgumentParser:
	"""Adds a mutual exclusive group of arguments to the parser to handle dataset batch or single mode, then returns it.

	Parameters
	----------
	parser : ArgumentParser
		An `ArgumentParser`, to which will be added an argument group.

	Returns
	-------
	parser : ArgumentParser
		An `ArgumentParser` holding the program's CLI.
	"""

	group = parser.add_mutually_exclusive_group(required=True)
	group.add_argument(
		"--case",
		type=Path,
		help="Import problem description from FOLDER\
		(only the first *.tsk and *.cfg files found are taken, all potential others are ignored).",
		metavar='FOLDER',
	)
	group.add_argument(
		"--collection",
		type=Path,
		help="Recursively import problem descriptions from FOLDER and/or subfolders\
		(only the first *.tsk and *.cfg files found of each folder are taken, all potential others are ignored).",
		metavar='FOLDER',
	)

	return parser


def _create_cli_parser() -> ArgumentParser:
	"""Creates a CLI argument parser and returns it.

	Returns
	-------
	parser : ArgumentParser
		An `ArgumentParser` holding part of the program's CLI.
	"""

	parser = ArgumentParser(
		prog="Extensibility Static Scheduler",
		description="Static scheduler maximizing the amount of time that can be dynamically allocated for sporadic tasks",
		allow_abbrev=True,
	)

	parser.add_argument(
		'-a', '--algorithm',
		nargs='?',
		type=str,
		choices=algorithms.keys(),
		help="Scheduling algorithm, either one of: " + ', '.join(algorithms.keys()),
		metavar="POLICY",
		dest="algorithm",
	)
	parser.add_argument(
		'-f', '--format',
		nargs='?',
		default=next(iter(OutputFormat)).name,
		type=str,
		choices=[member.name for member in OutputFormat],
		help="Output format, either one of: " + ', '.join(member.name for member in OutputFormat),
		metavar="FORMAT",
		dest="format",
	)
	parser.add_argument(
		'-i', '--initial-step',
		nargs='?',
		type=int,
		help="Initial step of the backtracking process.",
		metavar="INITIAL_STEP",
		dest="initial_step",
	)
	parser.add_argument(
		'-o', '--objective',
		nargs='?',
		type=str,
		choices=[f"{abbr}-{abbr2}" for abbr, val in objectives.items() for abbr2 in val[1].keys()],
		help="Objective function to evaluate solutions, either one of: "
		+ ', '.join(f"{abbr}-{abbr2} ({val[0]}, {val2[0]})"
			for abbr, val in objectives.items() for abbr2, val2 in val[1].items()),
		metavar="OBJECTIVE",
		dest="objective",
	)
	parser.add_argument(
		'-s', '--switch-time',
		nargs='?',
		type=int,
		help="Partition switch time.",
		metavar="SWITCH_TIME",
		dest="switch_time",
	)
	parser.add_argument(
		'-t', '--trial-limit',
		nargs='?',
		type=int,
		help="Backtracking trial limit.",
		metavar="TRIAL_LIMIT",
		dest="trial_limit",
	)
	parser.add_argument(
		"--verbose",
		action="store_true",
		help="Toggle program verbosity.",
		default=False,
	)
	parser.add_argument("--version", action="version", version="%(prog)s 0.1.0")

	return _add_dataset_arggroup(parser)


def _import_files_from_folder(folder_path: Path) -> FilepathPair:
	"""Creates a filepath pair from a given folder.

	Parameters
	----------
	folder_path : Path
		A `Path` from which build the filepath pair of `*.tsk` and `*.cfg` files.
		Only the first encountered file of each type is taken, all the others are ignored.

	Returns
	-------
	FilepathPair
		A `FilepathPair` pointing to the `*.tsk` and `*.cfg` files.
	"""

	tsk = next(filter(Path.is_file, folder_path.glob('*.tsk')))
	cfg = next(filter(Path.is_file, folder_path.glob('*.cfg')))

	if tsk.stem != cfg.stem:
		logging.warning("The names of the files mismatch: '" + tsk.stem + "' and '" + cfg.stem + "'")

	return FilepathPair(tsk, cfg)


def _get_filepath_pairs(folder_path: Path, recursive: bool = False) -> set[FilepathPair]:
	"""Gathers the filepath pairs from a given folder.

	Parameters
	----------
	folder_path : Path
		A `Path` from which build the filepath pairs of`*.tsk` and `*.cfg` files.
	recursive : bool, optional
		Toggles the recursive search for cases (default: False).
		All the folders and subfolders containing at least one `*.tsk` and `*.cfg` file will be taken.

	Returns
	-------
	filepath_pairs : set[FilepathPair]
		A set of populated `FilepathPair`.
	"""

	filepath_pairs: set[FilepathPair] = set()

	try:
		filepath_pairs.add(_import_files_from_folder(folder_path))
	except StopIteration:
		pass

	if recursive:
		for subfolder in filter(lambda e: e.is_dir(), folder_path.iterdir()):
			try:
				filepath_pairs |= {filepath for filepath in _get_filepath_pairs(subfolder, True) if filepath}
			except StopIteration:
				pass

	return filepath_pairs


def _create_parameters(args: Namespace) -> Parameters:
	"""Create the scheduling parameters from the CLI and the configuration file.
	The CLI arguments have priority over the configuration file.

	Parameters
	----------
	args : Namespace
		The CLI arguments.

	Returns
	-------
	params : Parameters
		The scheduling parameters
	"""

	with open("config.json") as config_file:
		config = load(config_file)

	_or = lambda base, backup: base if base is not None else backup
	or_in = lambda d, k, backup: d[k] if k in d else backup

	params = Parameters(
		_or(args.algorithm, or_in(config, "algorithm", next(iter(algorithms.keys())))),
		_or(
			args.objective,
			or_in(
				config,
				"objective",
				f"{next(iter(objectives.keys()))}-{next(iter(next(iter(objectives.values()))[1].keys()))}",
			),
		),
		_or(args.switch_time, or_in(config, "switch_time", 10)),
		_or(args.initial_step, or_in(config, "initial_step", 10)),
		_or(args.trial_limit, or_in(config, "trial_limit", 10)),
	)

	return params


INPUT = TypeVar('INPUT', Configuration, Problem, Solution)
OUTPUT = TypeVar('OUTPUT', Problem, Solution, str)


def _wrapper(config: Configuration, pbar: tqdm, operations: list[Callable[[INPUT], OUTPUT]]) -> str:
	"""Handles a test case from building to solving and formatting.

	Parameters
	----------
	config : Configuration
		A configuration for the scheduling problem.
	pbar : tqdm
		A progress bar to update each time an action of the test case in completed.
	operations : list[Callable[[INPUT], OUTPUT]]
		A list of chained operations to perform from a filepath pair.

	Returns
	-------
	output : str
		A `Solution` formatted as a `str` in the given format.
	"""

	output = config

	for function in operations:
		output = function(output)
		pbar.update()

	return output


# ENTRY POINT #########################################################################################################


def main() -> int:
	"""Program entry point.

	Returns
	-------
	int
		Returns `-1` if errors have been encountered, and 0 otherwise.

	Raises
	------
	FileNotFoundError
		If the list of file path pairs is empty.
	"""

	args = _create_cli_parser().parse_args()
	logging.getLogger().addHandler(ColoredHandler(verbose=args.verbose))
	filepath_pairs = _get_filepath_pairs(args.case) if args.case else _get_filepath_pairs(args.collection, True)
	params = _create_parameters(args)

	if not filepath_pairs:
		raise FileNotFoundError("No matching files found. At least one *.tsk file and one *.cfg file are necessary.")

	logging.info("Files found:\n\t" + "\n\t".join(
		filepath_pair.tsk.name + "\t" + filepath_pair.cfg.name for filepath_pair in filepath_pairs
	))

	operations = [build, solve, OutputFormat[args.format]]

	with ThreadPoolExecutor(max_workers=len(filepath_pairs)) as executor,\
		tqdm(total=len(filepath_pairs) * len(operations)) as pbar:

		futures = [
			executor.submit(_wrapper, Configuration(filepath_pair, params), pbar, operations)
			for filepath_pair in filepath_pairs
		]

		for future in as_completed(futures):
			future.result()

		logging.info(f"Total ellasped time: {process_time()}s.")

		return 0

	return -1


if __name__ == "__main__":
	main()
