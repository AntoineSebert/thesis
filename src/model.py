#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# IMPORTS #############################################################################################################


from __future__ import annotations

from collections.abc import AsyncIterable, Set, Reversible
from dataclasses import dataclass, field
from enum import IntEnum, unique
from functools import cached_property, total_ordering
from math import fsum
from pathlib import Path
from typing import Callable, NamedTuple, Optional, TypeVar, Union, Iterator
from weakref import ReferenceType, ref

from defusedxml import ElementTree  # type: ignore


@unique
class Criticality(IntEnum):
	"""Task criticality level

	dyn_0: null
	sta_1: minimal E2E delay
	sta_2: bounded jitter
	sta_3: 0 jitter
	sta_4: 0 jitter and minimal completion time
	"""

	dyn_0 = 0
	sta_1 = 1
	sta_2 = 2
	sta_3 = 3
	sta_4 = 4


"""Scheduling policies."""
Policy = Callable[[Optional[int]], float]


"""Main policy for scheduling, either rate monotonic or earliest deadline first."""
policies: dict[str, Policy] = {
	"edf": lambda _: 1,
	"rm": lambda count: count * (2**(1 / count) - 1),
}


"""Objective functions that assign a score to a feasible solution."""
ObjectiveFunction = Callable[['Solution'], Union[int, float]]


"""Objectives and descriptions.
min end-to-end app delay :	- cumulative
							- normal distribution
free space :	- cumulative
				- normal distribution
"""
objectives = {
	"min_e2e": (
		"minimal end-to-end application delay",
		{
			"cmltd": (
				"cumulated; lower is better",
				lambda s: s,
			),
			"nrml": (
				"normal distribution; lower is better",
				lambda s: s,
			)
		}
	),
	"max_empty": (
		"maximal empty space",
		{
			"cmltd": (
				"cumulated; lower is better",
				lambda s: s,
			),
			"nrml": (
				"normal distribution; lower is better",
				lambda s: s,
			)
		}
	),
}


@total_ordering
@dataclass
class Core:
	"""Represents a core. Mutable to support `weakref`, not modified in practice.

	Attributes
	----------
	id : int
		The core id within a `Processor`.
	processor : ReferenceType[Processor]
		The processor this core belongs to.
	"""

	id: int
	processor: ReferenceType[Processor]

	def __hash__(self: Core) -> int:
		return hash(str(self.id) + str(self.processor))

	def __eq__(self: Core, other: object) -> bool:
		if not isinstance(other, Core):
			return NotImplemented
		return self.id == other.id and self.processor == other.processor

	def __lt__(self: Core, other: Core) -> bool:
		return self.processor().id < other.processor().id and self.id < other.id

	def pformat(self: Core, level: int = 0) -> str:
		return "\n" + ("\t" * level) + f"core {{ id : {self.id}; processor : {self.processor().id} }}"


@dataclass
class Processor(AsyncIterable, Set, Reversible):
	"""Represents a processor. Mutable.

	Attributes
	----------
	id : int
		The processor within an `Architecture`.
	cores : set[Core]
		The set containing the `Core` objects within the Processor.
	"""

	id: int
	cores: set[Core]

	def __aiter__(self: Processor):
		return self

	def __contains__(self: Processor, item: Core) -> bool:
		if item.processor is self:
			for core in self:
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


class Slice(NamedTuple):
	"""Named tuple representing an execution slice of a task. Immutable.

	Attributes
	----------
	task : int
		The reference to the task the slice belongs to.
	core : ReferenceType[Core]
		The reference to the core the slice is scheduled on.
	start : int
		The start time of the slice.
	stop : int
		The stop time of the slice.
	"""

	task: ReferenceType[Task]
	core: ReferenceType[Core]
	start: int
	stop: int

	@cached_property
	def duration(self: Slice) -> int:
		"""Computes and caches the duration of the slice.

		Parameters
		----------
		self : Slice
			The instance of `Slice`.

		Returns
		-------
		int
			The duration of the slice.
		"""

		return self.stop - self.start

	def pformat(self: Slice, level: int = 0) -> str:
		i = "\n" + ("\t" * level)
		ii = i + "\t"

		return (i + "slice {" + ii
			+ f"task : {self.task().app().name}/{self.task().id};{ii}"
			f"core : {self.core().processor().id}/{self.core().id};{ii}"
			f"start : {self.start};{ii}stop : {self.stop};{ii}duration : {self.stop - self.start};{i}"
		+ "}")


@dataclass(order=True)
class Task:
	"""Represents a task.

	Attributes
	----------
	id : int
		The node id within a `Chain`.
	app : ReferenceType[App]
		The App to which the task belongs to.
	wcet : int
		The WCET of the node. Cannot be `0`.
	period : int
		The period of the node. Cannot be `0`.
	deadline : int
		The deadline of the node.
	criticality : Criticality
		The criticality level, [0; 4].
	child : ReferenceType[Task]
		A list of tasks to be completed before starting.
	"""

	id: int = field(compare=False)
	app: ReferenceType[App] = field(compare=False)
	wcet: int = field(compare=False)
	period: int = field(compare=False)
	deadline: int = field(compare=False)
	criticality: Criticality = field(compare=False)
	child: ReferenceType[Task] = field(compare=False)

	def __init__(self: Task, node: ElementTree, app: App, cpu: Processor) -> None:
		self.id = int(node.get("Id"))
		self.app = ref(app)
		self.wcet = int(node.get("WCET"))
		self.period = int(node.find("Period").get("Value"))
		self.deadline = int(node.get("Deadline"))
		self.criticality = Criticality(int(node.get("CIL")))

	def pformat(self: Task, level: int = 0) -> str:
		i = "\n" + ("\t" * level)

		return (i + "task {" + i
			+ f"\tid : {self.id};{i}"
			f"\tapp : {self.app().name};{i}"
			f"\twcet : {self.wcet};{i}"
			f"\tperiod : {self.period};{i}"
			f"\tdeadline : {self.deadline};{i}"
			f"\tcriticality : {int(self.criticality)};{i}"
			+ (f"\tchild : {self.child().id};{i}}}" if self.child is not None else "}"))

	@cached_property
	def workload(self: Task) -> float:
		"""Computes and caches the workload of the instance.

		Parameters
		----------
		self : Task
			The instance of `Task`.

		Returns
		-------
		float
			The workload of the task.
		"""

		return self.wcet / self.period


@dataclass(order=True)
class App(AsyncIterable, Set, Reversible):
	"""An application. Mutable.

	Attributes
	----------
	name : str
		The name of the Application.
	tasks : set[Task]
		The tasks within the Application.
	criticality : Criticality
		The criticality level, [0; 4], from the first task in `tasks`.
	"""

	name: str = field(compare=False)
	tasks: set[Task] = field(compare=False)

	@cached_property
	def criticality(self: App) -> Criticality:
		"""Computes and caches the maximal criticality within the tasks.

		Parameters
		----------
		self
			The instance of `App`.

		Returns
		-------
		Criticality
			The maximal criticality within `self.tasks`, assuming a non-empty list of tasks.
		"""

		return max(self.tasks, key=lambda task: task.criticality).criticality

	def workload(self: App) -> float:
		return fsum(task.workload for task in self.tasks)

	def __aiter__(self: Processor):
		return self

	def __contains__(self: App, item: Task) -> bool:
		if item.app is self:
			for task in self:
				if item.id == task.id:
					return True
		return False

	def __iter__(self: App) -> Iterator[App]:
		return iter(self.tasks)

	def __reversed__(self: App) -> Iterator[App]:
		for task in self.tasks[::-1]:
			yield task

	def __len__(self: App) -> int:
		return len(self.tasks)

	def __hash__(self: App) -> int:
		return hash(self.name)

	def pformat(self: App, level: int = 0) -> str:
		i = "\n" + ("\t" * level)

		return (i + "app {" + i
		+ f"\tname : {self.name};{i}\tcriticality : {self.criticality};{i}\ttasks {{"
			+ "".join(task.pformat(level + 2) for task in self)
		+ i + "\t}" + i + "}")


class Graph(NamedTuple):
	"""A DAG containing apps and an hyperperiod.

	Attributes
	----------
	apps : list[App]
		The applications to schedule.
	hyperperiod : int
		The hyperperiod length for this `Graph`, the least common divisor of the periods of all tasks.
	"""

	apps: list[App]
	hyperperiod: int

	@cached_property
	def max_criticality(self: Graph) -> Criticality:
		"""Computes and caches the maximal criticality within the apps.

		Parameters
		----------
		self
			The instance of `Graph`.

		Returns
		-------
		Criticality
			The maximal criticality within `self.apps`, assuming a non-empty list of applications.
		"""

		return max(self.apps, key=lambda app: app.criticality).criticality

	def pformat(self: Graph, level: int = 0) -> str:
		i = "\n" + ("\t" * level)

		return (f"{i}graph {{{i}\thyperperiod : {self.hyperperiod};"
			+ "".join(app.pformat(level + 1) for app in self.apps) + i + "}")


class FilepathPair(NamedTuple):
	"""Holds a `FilepathPair` to a `*.tsk` and a `*.cfg` file, representing a test case. Immutable.

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
	"""Binds a `FilepathPair` to a constraint level and a scheduling policy. Immutable.

	Attributes
	----------
	filepaths : FilepathPair
		A `FilepathPair` from which a `Problem` will be generated.
	policy : str
		A scheduling policy.
	switch_time : int
		A partition switch time.
	"""

	filepaths: FilepathPair
	policy: str
	switch_time: int
	# objective: str

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
Mapping = dict[ReferenceType[Core], list[ReferenceType[Slice]]]


@dataclass
class Solution:
	"""A solution holding an hyperperiod as `int`, and an architecture as Architecture (should be: `ref(Architecture)`).

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
