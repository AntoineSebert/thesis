#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# IMPORTS #############################################################################################################


from __future__ import annotations

from collections.abc import Iterator, Reversible, Set
from dataclasses import dataclass, field
from functools import cached_property, total_ordering
from math import fsum
from pathlib import Path
from typing import NamedTuple, TypeVar


from graph_model import Graph, Task


# CLASSES AND TYPE ALIASES ############################################################################################


@dataclass(eq=True)
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
	workload: float = field(compare=False, default=0.0)

	def __init__(self: Core, id: int, processor: Processor) -> None:
		self.id = id
		self.processor = processor

	def __hash__(self: Core) -> int:
		return hash(str(self.id) + str(self.processor))

	def __lt__(self: Core, other: Core) -> bool:
		return self.workload < other.workload

	def pformat(self: Core, level: int = 0) -> str:
		return "\n" + ("\t" * level) + f"core {{ id : {self.id}; processor : {self.processor.id}; workload: {self.workload} }}"


@dataclass(eq=True)
@total_ordering
class Processor(Set, Reversible):
	"""Represents a processor.

	Attributes
	----------
	id : int
		The processor within an `Architecture`.
	cores : set[Core]
		The set containing the `Core` objects within the Processor.
	"""

	id: int
	cores: set[Core] = field(compare=False)

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
		return self.workload() < other.workload()

	def __contains__(self: Processor, item: object) -> bool:
		if item.processor is self:
			for core in self.cores:
				if item.id == core.id:
					return True
		return False

	def __iter__(self: Processor) -> Iterator[Processor]:
		return iter(self.cores)

	def __reversed__(self: Processor) -> Iterator[Processor]:
		for core in self.cores[::-1]:
			yield core

	def __len__(self: Processor) -> int:
		return len(self.cores)

	def __hash__(self: Processor) -> int:
		return hash(str(self.id))

	def pformat(self: Processor, level: int = 0) -> str:
		i = "\n" + ("\t" * level)

		return f"{i}cpu {{{i}\tid : {self.id};" + "".join(core.pformat(level + 1) for core in self) + i + "}"


"""An set of `Processor` representing an `Architecture`."""
Architecture = set[Processor]


exec_window = slice


class ExecSlice(NamedTuple):
	"""Represents an execution slice of a task.

	Attributes
	----------
	task : Task
		The task the slice belongs to.
	core : Core
		The core the slice is scheduled on.
	et : exec_window
		The window execution time.
	"""

	task: Task
	core: Core
	et: exec_window

	@cached_property
	def duration(self: ExecSlice) -> int:
		"""Computes and caches the duration of the slice.

		Parameters
		----------
		self : ExecSlice
			The instance of `ExecSlice`.

		Returns
		-------
		int
			The duration of the slice.
		"""

		return self.et.stop - self.et.start

	def __hash__(self: Processor) -> int:
		return hash(str(hash(self.task)) + str(hash(self.core)) + str(self.et.start) + str(self.et.stop))

	def pformat(self: ExecSlice, level: int = 0) -> str:
		i = "\n" + ("\t" * level)
		ii = i + "\t"

		return (f"{i}slice {{{ii}"
			f"task : {self.task.app().name} / {self.task.id};{ii}"
			f"core : {self.core.processor.id} / {self.core.id};{ii}"
			f"slice : {self.et} / {self.duration};{i}}}")


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


CONFIG_JSON = TypeVar('CONFIG_JSON', FilepathPair, int, str)


class Configuration(NamedTuple):
	"""Binds a `FilepathPair` to a constraint level and a scheduling policy.

	Attributes
	----------
	filepaths : FilepathPair
		A `FilepathPair` from which a `Problem` will be generated.
	policy : str
		A scheduling policy.
	switch_time : int
		A partition switch time.
	objective : str
		An objective function for the optimization step.
	"""

	filepaths: FilepathPair
	policy: str
	switch_time: int
	objective: str

	def json(self: Configuration) -> dict[str, CONFIG_JSON]:
		return {
			"case": {
				"tsk": str(self.filepaths.tsk),
				"cfg": str(self.filepaths.cfg),
			},
			"policy": self.policy,
			"switch time": self.switch_time,
		}

	def pformat(self: Configuration, level: int = 0) -> str:
		i = "\n" + ("\t" * level)

		return (i + "configuration {"
			+ self.filepaths.pformat(level + 1)
			+ f"{i}\tpolicy : {self.policy};"
			+ f"{i}\tswitch_time : {self.switch_time};{i}}}")


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
Mapping = dict[Core, list[ExecSlice]]


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
				core().pformat(level + 2) + " : {"
					+ "".join(_slice().pformat(level + 3) for _slice in slices)
				+ i + "\t\t}" for core, slices in self.mapping.items()
			) + i + "\t}" + i
			+ "}")
