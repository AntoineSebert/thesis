#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# IMPORTS #############################################################################################################


from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum, unique
from functools import cached_property, total_ordering
from json import JSONEncoder
from pathlib import Path
from queue import PriorityQueue
from typing import Any, Callable, NamedTuple, Union
from weakref import ReferenceType, ref

from defusedxml import ElementTree


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
Policy = Callable[['Task'], Union[int, float]]  # change to policycheck w/ workload


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
		return hash(str(self.id) + str(self.processor().id))

	def __eq__(self: Core, other: Core) -> bool:
		return self.id == other.id and self.processor == other.processor

	def __lt__(self: Core, other: Core) -> bool:
		return self.processor().id < other.processor().id and self.id < other.id

	def pformat(self: Core, level: int = 0) -> str:
		return "\n" + ("\t" * level) + f"core {{ id : {self.id}; processor : {self.processor().id} }}"


@dataclass
class Processor:
	"""Represents a processor. Mutable.

	Attributes
	----------
	id : int
		The processor within an `Architecture`.
	cores : list[Core]
		The list containing the `Core` objects within the Processor.
	"""

	id: int
	cores: list[Core]

	def pformat(self: Processor, level: int = 0) -> str:
		i = "\n" + ("\t" * level)

		return f"{i}cpu {{{i}\tid : {self.id};" + "".join(core.pformat(level + 1) for core in self.cores) + i + "}"


"""An list of `Processor` representing an `Architecture`."""
Architecture = list[Processor]


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
	child: ReferenceType[Task] = field(compare=False, default=None)

	def __init__(self: Task, node: ElementTree, app: App, cpu: Processor) -> Task:
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
	def priority(self: Task, policy: Policy) -> Union[int, float]:
		"""Computes and caches the priority of the instance depending on the policy.

		Parameters
		----------
		self : Task
			The instance of `Task`.

		Returns
		-------
		int
			The priority of the task.
		"""

		return policy(self)


@dataclass(order=True)
class App:
	"""An application. Mutable.

	Attributes
	----------
	name : str
		The name of the Application.
	tasks : list[Task]
		The list of tasks within the Application.
	criticality : Criticality
		The criticality level, [0; 4], from the first task in `tasks`.
	"""

	name: str = field(compare=False)
	tasks: list[Task] = field(compare=False)
	criticality: Criticality

	def pformat(self: App, level: int = 0) -> str:
		i = "\n" + ("\t" * level)

		return (i + "app {" + i
		+ f"\tname : {self.name};{i}\tcriticality : {self.criticality};{i}\ttasks {{"
			+ "".join(task.pformat(level + 2) for task in self.tasks)
		+ i + "\t}" + i + "}")


class Graph(NamedTuple):
	"""A DAG containing a list of `App` and an hyperperiod.

	Attributes
	----------
	apps : list[App]
		A list of `App`.
	hyperperiod : int
		The hyperperiod length for this `Graph`, the least common divisor of the periods of all tasks.
	"""

	apps: list[App]
	hyperperiod: int

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

		return f"{i}case {{{i}\ttsk: {self.tsk};{i}\tcfg: {self.cfg};{i}}}"


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

	def pformat(self: Configuration, level: int = 0) -> str:
		i = "\n" + ("\t" * level)

		return (i + "configuration {"
			+ self.filepaths.pformat(level + 1)
			+ f"{i}\tpolicy : {self.policy};"
			+ f"{i}\tswitch_time : {self.switch_time};{i}}}")


class Problem(NamedTuple):
	"""A problem holding a `FilepathPair`, a `Graph`, an architecture.

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
	arch : Architecture
		An `Architecture` containing a sequence of `Processor`.
	hyperperiod : int
		The hyperperiod length for this `Solution`.
	score : int
		The score of a Solution regarding an objective function.
	mapping : Mapping
		A mapping between cores and tasks.
	"""

	config: Configuration
	arch: Architecture
	hyperperiod: int
	score: int
	mapping: Mapping


	def pformat(self: Solution, level: int = 0) -> str:
		i = "\n" + ("\t" * level)

		return (i + "solution {"
			+ self.config.pformat(level + 1) + i
			+ "\tarchitecture {" + "".join(cpu.pformat(level + 2) for cpu in self.arch) + i + "\t}" + i
			+ f"\thyperperiod : {self.hyperperiod};" + i
			+ f"\tscore : {self.score};" + i
			+ "\tmapping {" + "".join(
				core.pformat(level + 2) + " : {"
					+ "".join(_slice.pformat(level + 3) for _slice in slices)
				+ i + "\t\t}" for core, slices in self.mapping.items()
			) + i + "\t}" + i
			+ "}")


class PriorityQueueEncoder(JSONEncoder):
	"""An encoder dedicated to parse `PriorityQueue` objects into JSON.

	Methods
	-------
	default(obj)
		Returns a list containing the size of the `PriorityQueue` and a boolean whether it is empty or not.
	"""

	def default(self: JSONEncoder, obj: Any) -> Any:
		if isinstance(obj, PriorityQueue):
			return [obj.qsize(), obj.empty()]
		# Let the base class default method raise the TypeError
		return JSONEncoder.default(self, obj)
