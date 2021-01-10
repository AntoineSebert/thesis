#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# IMPORTS #############################################################################################################

from __future__ import annotations

from collections.abc import Iterator, Reversible, Set
from dataclasses import dataclass, field
from functools import cached_property, total_ordering
from math import fsum
from operator import gt, lt
from pathlib import Path
from typing import Callable, Collection, Iterable, NamedTuple, Union

from arch_model import Architecture, CoreJobMap

from graph_model import Graph


# CLASSES AND TYPE ALIASES ############################################################################################


class FilepathPair(NamedTuple):
	"""Holds a `FilepathPair` to a `*.tsk` and a `*.cfg` file, representing a test case.

	Attributes
	----------
	tsk : Path
		A `Path` to a `*.tsk` file.
	cfg : Path
		A `Path` to a `*.cfg` file.
	"""

	tsk: Path
	cfg: Path

	def pformat(self: FilepathPair, level: int = 0) -> str:
		"""A complete description of a pair of file paths.

		Parameters
		----------
		self : FilepathPair
			The instance of `FilepathPair`.
		level, optional : int
			The indentation level (default: 0).

		Returns
		-------
		str
			The complete description.
		"""

		i = "\n" + ("\t" * level)

		return f"{i}case {{{i}\ttsk: {str(self.tsk)};{i}\tcfg: {str(self.cfg)};{i}}}"


class Parameters(NamedTuple):
	"""Holds the parameters of the scheduler.

	Attributes
	----------
	algorithm : str
		A scheduling algorithm.
	objective : str
		An objective.
	switch_time : int
		An partition switch time.
	initial_step : int
		An initial backtracking step.
	trial_limit : int
		A backtracking trial limit.
	"""

	algorithm: str
	objective: str
	switch_time: int
	initial_step: int
	trial_limit: int

	def pformat(self: Parameters, level: int = 0) -> str:
		"""A complete description of the parameters of a problem.

		Parameters
		----------
		self : Parameters
			The instance of `Parameters`.
		level, optional : int
			The indentation level (default: 0).

		Returns
		-------
		str
			The complete description.
		"""

		i = "\n" + ("\t" * level)

		return (f"{i}params {{{i}"
			f"\talgorithm : {self.algorithm}{i}"
			f"\tobjective : {self.objective}{i}"
			f"\tswitch_time : {self.switch_time}{i}"
			f"\tinitial_step : {self.initial_step}{i}"
			f"\ttrial_limit : {self.trial_limit};{i}}}")


class Configuration(NamedTuple):
	"""Binds a `FilepathPair` to the scheduler parameters.

	Attributes
	----------
	filepaths : FilepathPair
		A `FilepathPair` from which a `Problem` will be generated.
	params: Parameters
		A set of scheduling parameters.
	"""

	filepaths: FilepathPair
	params: Parameters

	def json(self: Configuration) -> dict[str, Union[dict[str, str], str]]:
		return {
			"case": {
				"tsk": str(self.filepaths.tsk),
				"cfg": str(self.filepaths.cfg),
			},
			"params": str(self.params),
		}

	def pformat(self: Configuration, level: int = 0) -> str:
		"""A complete description of the configuration of a problem.

		Parameters
		----------
		self : Configuration
			The instance of `Configuration`.
		level, optional : int
			The indentation level (default: 0).

		Returns
		-------
		str
			The complete description.
		"""

		i = "\n" + ("\t" * level)

		return (f"{i}configuration {{"
			f"{self.filepaths.pformat(level + 1)}{i}"
			f"\targuments : {self.params.pformat(level + 1)};{i}}}")


class Problem(NamedTuple):
	"""A problem holding a `FilepathPair`, an architecture and a `Graph`.

	Attributes
	----------
	config : Configuration
		A configuration for a scheduling problem.
	arch : Architecture
		An `Architecture` containing a sequence of `Processor`.
	graph : Graph
		A `Graph` containing task sequences.
	"""

	config: Configuration
	arch: Architecture
	graph: Graph

	def pformat(self: Problem, level: int = 0) -> str:
		"""A complete description of a problem.

		Parameters
		----------
		self : Problem
			The instance of `Problem`.
		level, optional : int
			The indentation level (default: 0).

		Returns
		-------
		str
			The complete description.
		"""

		i = "\n" + ("\t" * level)

		return (i + "\nproblem {" + self.config.pformat(level + 1)
			+ i + "\tarchitecture {" + "".join(cpu.pformat(level + 2) for cpu in self.arch) + i + "\t}"
			+ self.graph.pformat(level + 1) + i + "}\n")


@dataclass
class Solution:
	"""A solution from a final schedule.

	Attributes
	----------
	problem : Problem
		A scheduling problem.
	score : int
		The score of a Solution regarding an objective function.
	core_jobs : CoreJobMap
		A mapping between cores and jobs.
	"""

	problem: Problem
	core_jobs: CoreJobMap
	objective: Objective

	@cached_property
	def score(self: Solution) -> Score:
		"""The score of the solution.

		Parameters
		----------
		self : Solution
			The instance of `Solution`.
		scoring : Scoring
			A scoring algorithm.

		Returns
		-------
		Score
			The score of the solution.
		"""

		return self.objective(self)

	def pformat(self: Solution, level: int = 0) -> str:
		"""A complete description of a solution.

		Parameters
		----------
		self : Solution
			The instance of `Solution`.
		level, optional
			The indentation level (default: 0).

		Returns
		-------
		str
			The complete description.
		"""

		i = "\n" + ("\t" * level)

		return (i + "solution {"
			+ self.problem.config.pformat(level + 1) + i
			+ f"\thyperperiod : {self.problem.graph.hyperperiod};" + i
			+ f"\tscore : {self.score};" + i
			+ "\tcore_job {" + "".join(
				core.pformat(level + 2) + " : {"
					+ "".join(_slice.pformat(level + 3) for _slice in slices)
				+ i + "\t\t}" for core, slices in self.core_jobs.items()
			) + i + "\t}" + i
			+ "}")

	# HASHABLE

	def __hash__(self: Solution) -> int:
		return hash(str(self.core_jobs) + str(self.score) + str(self.offset_sum))

	# TOTAL ORDERING

"""Scheduling check, returns the sufficient condition."""
# Callable[[set[Task]], bool] = lambda tasks: workload(tasks) <= sufficient_condition(len(tasks))
SchedCheck = Callable[[Collection[Task], Collection[Core]], bool]
Ordering = Callable[[Iterable[Job]], Iterable[Job]]
Scoring = Callable[[CoreJobMap], Union[int, float]]

"""
class scheduler/ordinator
	attr
		sec margin
		name
	members
		global sched check
		local sched check
		ordering
"""

"""Algorithms for scheduling, containing the sufficient condition, an ordering function."""
algorithms: dict[str, tuple[SchedCheck, Ordering]] = {
	"edf": (
		lambda tasks, cores: fsum(task.workload for task in tasks) <= len(cores) * 0.9,
		lambda jobs: sorted(jobs, key=lambda job: job.sched_window.stop),
	),
	"rm": (
		lambda tasks, cores: fsum(task.workload for task in tasks) <= len(cores) * 0.9 * (len(tasks) * (2**(1 / len(tasks)) - 1)),
		lambda jobs: sorted(jobs, key=lambda job: job.task.period),
	),
}


