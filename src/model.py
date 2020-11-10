#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# IMPORTS #############################################################################################################


from __future__ import annotations

from collections.abc import Iterator, Reversible, Set
from dataclasses import dataclass, field
from functools import total_ordering
from math import fsum
from pathlib import Path
from typing import NamedTuple, TypeVar

from graph_model import Graph, Job

from sortedcontainers import SortedSet  # type: ignore


# CLASSES AND TYPE ALIASES ############################################################################################


@dataclass
@total_ordering
class Core:
	"""Represents a core.

	Attributes
	----------
	id : int
		The core id within a `Processor`.
	processor : Processor
		The processor this core belongs to.
	workload : float
		Workload carried by the tasks scheduled on this core.
	"""

	id: int
	processor: Processor
	workload: float = field(default=0.0)

	def __hash__(self: Core) -> int:
		return hash(str(self.id) + str(self.processor) + str(self.workload))

	def __lt__(self: Core, other: Core) -> bool:
		return self.workload < other.workload

	def __eq__(self: Core, other: object) -> bool:
		if isinstance(other, Core):
			return self.id == other.id and self.processor == other.processor
		else:
			return NotImplemented

	def short(self: Core) -> str:
		return f"{self.processor.id} / {self.id}"

	def pformat(self: Core, level: int = 0) -> str:
		return ("\n" + ("\t" * level)
			+ f"core {{ id : {self.id}; processor : {self.processor.id}; workload: {self.workload}; }}")


@dataclass(eq=True)
@total_ordering
class Processor(Set, Reversible):
	"""Represents a processor.

	Attributes
	----------
	id : int
		The processor within an `Architecture`.
	cores : SortedSet[Core]
		The set containing the `Core` objects within the Processor.
	"""

	id: int
	cores: SortedSet[Core] = field(compare=False)

	def workload(self: Processor) -> float:
		""" The workload of the processor.

		Parameters
		----------
		self : Processor
			The instance of `Processor`.

		Returns
		-------
		float
			The sum of workload of all cores on this processor.
		"""

		return fsum(core.workload for core in self.cores) if len(self.cores) != 0 else 0.0

	def get_min_core(self: Processor) -> Core:
		""" The core on the processor with the lowest workload.

		Parameters
		----------
		self : Processor
			The instance of `Processor`.

		Returns
		-------
		core
			A core.
		"""

		return min(self.cores)

	def __lt__(self: Processor, other: object) -> bool:
		if isinstance(other, Processor):
			return self.workload() < other.workload()
		else:
			return NotImplemented

	def __contains__(self: Processor, item: object) -> bool:
		if isinstance(item, Core):
			return item.processor is self and item in self.cores
		else:
			return NotImplemented

	def __iter__(self: Processor) -> Iterator[Core]:
		return iter(self.cores)

	def __reversed__(self: Processor) -> Iterator[Core]:
		return reversed(self.cores)

	def __len__(self: Processor) -> int:
		return len(self.cores)

	def __hash__(self: Processor) -> int:
		return hash(str(self.id))

	def pformat(self: Processor, level: int = 0) -> str:
		i = "\n" + ("\t" * level)

		return f"{i}cpu {{{i}\tid : {self.id};" + "".join(core.pformat(level + 1) for core in self) + i + "}"


"""An set of `Processor` representing an `Architecture`."""
Architecture = set[Processor]


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
		i = "\n" + ("\t" * level)

		return (f"{i}params {{{i}"
			f"\talgorithm : {self.algorithm}{i}"
			f"\tobjective : {self.objective}{i}"
			f"\tswitch_time : {self.switch_time}{i}"
			f"\tinitial_step : {self.initial_step}{i}"
			f"\ttrial_limit : {self.trial_limit};{i}}}")


CONFIG_JSON = TypeVar('CONFIG_JSON', dict[str, str], int, str)


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

	def json(self: Configuration) -> dict[str, CONFIG_JSON]:
		return {
			"case": {
				"tsk": str(self.filepaths.tsk),
				"cfg": str(self.filepaths.cfg),
			},
			"params": str(self.params),
		}

	def pformat(self: Configuration, level: int = 0) -> str:
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
		i = "\n" + ("\t" * level)

		return (i + "\nproblem {" + self.config.pformat(level + 1)
			+ i + "\tarchitecture {" + "".join(cpu.pformat(level + 2) for cpu in self.arch) + i + "\t}"
			+ self.graph.pformat(level + 1) + i + "}\n")


"""A mapping of cores to slices, representing the inital mapping."""
Mapping = dict[Core, list[Job]]


@dataclass
class Solution:
	"""A solution from a final schedule.

	Attributes
	----------
	config: Configuration
		A configuration for a scheduling problem.
	hyperperiod : int
		The hyperperiod length for this `Solution`.
	score : int
		The score of a Solution regarding an objective function.
	mapping : Mapping
		A mapping between cores and tasks.
	"""

	config: Configuration
	hyperperiod: int
	score: int
	mapping: Mapping

	def pformat(self: Solution, level: int = 0) -> str:
		i = "\n" + ("\t" * level)

		return (i + "solution {"
			+ self.config.pformat(level + 1) + i
			+ f"\thyperperiod : {self.hyperperiod};" + i
			+ f"\tscore : {self.score};" + i
			+ "\tmapping {" + "".join(
				core.pformat(level + 2) + " : {"
					+ "".join(_slice.pformat(level + 3) for _slice in slices)
				+ i + "\t\t}" for core, slices in self.mapping.items()
			) + i + "\t}" + i
			+ "}")
