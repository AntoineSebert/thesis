#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# IMPORTS #############################################################################################################


from __future__ import annotations
from enum import IntEnum, unique
from dataclasses import dataclass, field
from fractions import Fraction
from json import JSONEncoder
from pathlib import Path
from queue import PriorityQueue
from typing import Any, Iterable, NamedTuple, Optional, Dict
from weakref import ReferenceType


@unique
class Criticality(IntEnum):
	"""Task criticality level

	sta_1: null
	sta_2: bounded jitter
	sta_3: 0 jitter
	sta_4: 0 jitter and minimal completion time
	"""

	sta_1 = 1
	sta_2 = 2
	sta_3 = 3
	sta_4 = 4


@dataclass
class Core:
	"""Represents a core.

	Attributes
	----------
	id : int
		The core id within a `Processor`.
	processor : ReferenceType[Processor]
		The processor this core belongs to.
	macrotick : Optional[int]
		The macrotick of the core.
	slices : Iterable[ReferenceType[Slice]] (can be empty)
		The execution slices scheduled on this core.
	"""

	id: int
	processor: ReferenceType[Processor]
	macrotick: Optional[int]
	slices: Iterable[ReferenceType[Slice]]

	def __eq__(self, other) -> bool:
		return self.processor is other.processor and self.id == other.id


class Processor(NamedTuple):
	"""Represents a processor.

	Attributes
	----------
	id : int
		The processor within an `Architecture`.
	cores : Iterable[Core]
		The iterable containing the `Core` objects within the Processor.
	"""

	id: int
	cores: Iterable[Core]


"""An iterable of `Processor` representing an `Architecture`."""
Architecture = Iterable[Processor]


@dataclass
class Slice:
	"""Named tuple representing an execution slice of a task.

	Attributes
	----------
	task : int
		The reference to the task the slice belongs to.
	core : ReferenceType[Core]
		The reference to the core the slice is scheduled on.
	start : int
		The start time of the slice.
	end : int
		The end time of the slice.
	"""

	task: ReferenceType[Task]
	core: ReferenceType[Core]
	start: int
	end: int


@dataclass
class Task():
	"""Represents a task.

	Attributes
	----------
	id : int
		The node id within a `Chain`.
	wcet : int
		The WCET of the node. Cannot be `0.0`.
	period : int
		The period of the node. Cannot be `0.0`.
	deadline : int
		The deadline of the node.
	max_jitter : Optional[int]
		The eventual jitter of the node.
	offset : int
		The start offset of the node.
	cpu : ReferenceType[Processor]
		A `Processor` the node is scheduled on. Cannot be None.
	criticality : Criticality
		The criticality level. [2; 6] for static stask, [0; 1] for dynamic tasks.
	child : Iterable[ReferenceType[Task]]
		A list of tasks to be completed before starting.
	"""

	id: int
	wcet: int
	period: int
	deadline: int
	max_jitter: Optional[int]
	offset: int
	cpu: ReferenceType[Processor]
	criticality: Criticality
	child: Optional[ReferenceType[Task]]


class App(NamedTuple):
	"""An application.

	Attributes
	----------
	name : str
		The name of the Application.
	tasks : Iterable[Task]
		The list of tasks within the Application.
	"""

	name: str
	tasks: Iterable[Task]


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


class Configuration(NamedTuple):
	"""Binds a `FilepathPair` to a constraint level and a scheduling policy.

	Attributes
	----------
	filepaths : FilepathPair
		A `FilepathPair` from which a `Problem` will be generated.
	constraint_level : int
		A constraint level that adjust which constraints will be met.
	policy : str
		A scheduling policy.
	"""

	filepaths: FilepathPair
	constraint_level: int
	policy: str


class Problem(NamedTuple):
	"""A problem holding a `FilepathPair`, a `Graph`, an architecture.

	Attributes
	----------
	config : Configuration
		A configuration for a scheduling problem.
	graph : Graph
		A `Graph` containing task sequences.
	arch : Architecture
		An `Architecture` containing a sequence of `Processor`.
	"""

	config: Configuration
	apps: Iterable[App]
	arch: Architecture


@dataclass
class Solution:
	"""A solution holding an hyperperiod as `int`, and an architecture as Architecture (should be: `ref(Architecture)`).

	Attributes
	----------
	filepaths : FilepathPair
		The `FilepathPair` from which a `Solution` has been generated.
	hyperperiod : int
		The hyperperiod length for this `Solution`.
	score : int
		The score of a Solution regarding an objective function.
	arch : Architecture
		An `Architecture` containing a sequence of `Processor`.
	tasks : Dict[Task, Core]
		A mapping between tasks and cores.
	"""

	filepaths: FilepathPair
	hyperperiod: int
	score: int
	arch: Architecture
	tasks: Dict[Task, Core]


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


@dataclass(order=True)
class PrioritizedItem:
	"""An encoder dedicated to parse `PriorityQueue` objects into JSON.

	Attributes
	----------
	priority : Fraction
		The prioroty of the element as a `Fraction`.
	item : Any
		The data carried by the element. This field is not taken into account for the prioritization.
		(default: `field(compare=False)`)
	"""

	priority: Fraction
	item: Any = field(compare=False)
